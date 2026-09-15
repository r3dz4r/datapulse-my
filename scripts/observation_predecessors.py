#!/usr/bin/env python3
"""Predecessor resolution for the historical observation archive.

Each observation in the archive may name the observation it supersedes through
``previous_observation_id`` / ``previous_observation_digest``. That predecessor
link is the spine of change detection, so this module proves a link cannot be
wrong before it is written:

* **same dataset** — a predecessor must belong to the dataset being resolved;
* **strictly earlier** — the predecessor's ``observed_at`` must parse and
  precede the new observation's instant (equal instants have no defined order,
  so they are refused rather than invented);
* **present** — the predecessor's envelope must exist in the store and carry a
  well-formed ``observation_digest``;
* **byte-verified** — when the predecessor kept a ``source_digest``, its blob
  must still exist and re-hash to that value.

``relation_basis`` records what the predecessor retained using the plan's
vocabulary: ``captured`` when its envelope carries a ``source_digest``,
``metadata_only`` when it does not, and ``none`` when the dataset has no prior
observation. The chain head is not a predecessor relation; this module never
reads or writes chain-head state.
"""
from __future__ import annotations

import argparse
import hashlib
import logging
import re
import shutil
import sys
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

try:
    from scripts.observation_store import (
        OBSERVATION_ID_PATTERN,
        DigestFormatError,
        ObjectNotFoundError,
        blob_path,
        list_observations,
        put_blob,
        put_envelope,
        read_blob,
        resolve_root,
        sha256_digest,
        upsert_observation,
    )
except ModuleNotFoundError:  # bare form when scripts/ itself is on sys.path
    from observation_store import (
        OBSERVATION_ID_PATTERN,
        DigestFormatError,
        ObjectNotFoundError,
        blob_path,
        list_observations,
        put_blob,
        put_envelope,
        read_blob,
        resolve_root,
        sha256_digest,
        upsert_observation,
    )

__all__ = [
    "PredecessorError",
    "PredecessorLink",
    "RELATION_BASES",
    "resolve_predecessor",
    "verify_link",
]

logger = logging.getLogger(__name__)

RELATION_BASES: tuple[str, ...] = ("captured", "metadata_only", "none")

# Same pattern as historical-observation.schema.json $defs.observationDigest.
# Repeated verbatim (the store's own convention for its patterns) so the
# resolver cannot drift from the shipped envelope contract.
OBSERVATION_DIGEST_PATTERN: re.Pattern[str] = re.compile(r"^observation:sha256:[0-9a-f]{64}$")


class PredecessorError(Exception):
    """Raised when a predecessor link would violate a resolution constraint.

    ``constraint`` names the broken rule and is exactly one of:
    ``same_dataset``, ``observed_at_parseable``, ``observed_at_earlier``,
    ``observation_digest_present``, ``envelope_present``,
    ``source_digest_bytes``.
    """

    def __init__(self, constraint: str, message: str) -> None:
        super().__init__(message)
        self.constraint = constraint
        self.message = message


@dataclass(frozen=True)
class PredecessorLink:
    """A resolved (or absent) predecessor for one dataset at one instant.

    ``observation_id``/``observed_at`` identify the resolved predecessor
    observation; ``previous_observation_id``/``previous_observation_digest``
    are the values the new envelope records for the link. All four are ``None``
    when ``relation_basis == "none"``. ``relation_basis`` is exactly one of
    :data:`RELATION_BASES` and ``basis_reason`` explains it in prose.
    """

    dataset_id: str
    observation_id: str | None
    observed_at: str | None
    previous_observation_id: str | None
    previous_observation_digest: str | None
    relation_basis: str
    basis_reason: str


def _parse_instant(value: Any, context: str) -> datetime:
    """Parse an offset-carrying ISO-8601 instant, normalised to UTC."""
    if not isinstance(value, str) or not value.strip():
        raise PredecessorError(
            "observed_at_parseable",
            f"{context} observed_at {value!r} must be a non-empty ISO-8601 string",
        )
    text = value.strip()
    if text.endswith(("Z", "z")):
        text = text[:-1] + "+00:00"
    try:
        moment = datetime.fromisoformat(text)
    except ValueError as error:
        raise PredecessorError(
            "observed_at_parseable",
            f"{context} observed_at {value!r} is not a parseable ISO-8601 instant",
        ) from error
    if moment.tzinfo is None:
        raise PredecessorError(
            "observed_at_parseable",
            f"{context} observed_at {value!r} must carry a timezone offset; "
            "a naive local time is ambiguous by design",
        )
    return moment.astimezone(timezone.utc)


def _normalize_instant(moment: datetime) -> str:
    """Canonical UTC Z-form string, matching the index's normalisation."""
    return moment.isoformat().replace("+00:00", "Z")


def _envelope_file(row: Mapping[str, Any], store_root: Path) -> Path:
    """Absolute path of a row's envelope file from its root-relative reference."""
    path = Path(row["envelope_path"])
    return path if path.is_absolute() else store_root / path


def _row_matching(rows: list[dict[str, Any]], observation_id: str) -> dict[str, Any] | None:
    for row in rows:
        if row.get("observation_id") == observation_id:
            return row
    return None


def _verify_source_digest(source_digest: Any, observation_id: str, *, root: Path) -> str:
    """Refuse a predecessor whose retained bytes are missing or do not re-hash."""
    try:
        retained = read_blob(source_digest, root=root)
    except DigestFormatError as error:
        raise PredecessorError(
            "source_digest_bytes",
            f"predecessor {observation_id} carries a malformed source_digest: {error}",
        ) from error
    except ObjectNotFoundError as error:
        raise PredecessorError(
            "source_digest_bytes",
            f"predecessor {observation_id} claims retained bytes under {source_digest} "
            f"but the blob is absent from the store: {error}",
        ) from error
    recomputed = sha256_digest(retained)
    if recomputed != source_digest:
        raise PredecessorError(
            "source_digest_bytes",
            f"predecessor {observation_id} claims source_digest {source_digest} but its "
            f"stored bytes re-hash to {recomputed}; evidence that does not verify cannot "
            "anchor a change claim",
        )
    return source_digest


def _link_from_row(dataset_id: str, row: Mapping[str, Any], store_root: Path) -> PredecessorLink:
    """Build a link from the winning index row, enforcing every store-path rule."""
    observation_id = row.get("observation_id")
    observed_at = row.get("observed_at")
    envelope_file = _envelope_file(row, store_root)
    if not envelope_file.is_file():
        raise PredecessorError(
            "envelope_present",
            f"predecessor {observation_id} of dataset {dataset_id} has no envelope file "
            f"at {envelope_file}; a dangling index row is a broken chain — refused, not "
            "recorded as null",
        )
    observation_digest = row.get("observation_digest")
    if not isinstance(observation_digest, str) or not OBSERVATION_DIGEST_PATTERN.fullmatch(
        observation_digest
    ):
        raise PredecessorError(
            "observation_digest_present",
            f"predecessor {observation_id} of dataset {dataset_id} carries no "
            "well-formed observation_digest (expected "
            "'observation:sha256:' followed by exactly 64 lowercase hex characters)",
        )
    source_digest = row.get("source_digest")
    if source_digest is None:
        return PredecessorLink(
            dataset_id=dataset_id,
            observation_id=observation_id,
            observed_at=observed_at,
            previous_observation_id=observation_id,
            previous_observation_digest=observation_digest,
            relation_basis="metadata_only",
            basis_reason=(
                f"predecessor {observation_id} observed {observed_at} retained no source "
                "bytes (metadata-only capture)"
            ),
        )
    _verify_source_digest(source_digest, observation_id, root=store_root)
    return PredecessorLink(
        dataset_id=dataset_id,
        observation_id=observation_id,
        observed_at=observed_at,
        previous_observation_id=observation_id,
        previous_observation_digest=observation_digest,
        relation_basis="captured",
        basis_reason=(
            f"predecessor {observation_id} observed {observed_at} retained source bytes "
            f"verified to re-hash to {source_digest}"
        ),
    )


def _resolve_explicit(
    dataset_id: str,
    bound: datetime,
    explicit: Any,
    *,
    root: Path | str | None,
    store_root: Path,
) -> PredecessorLink:
    """Resolve a caller-supplied predecessor envelope under every rule."""
    if not isinstance(explicit, Mapping):
        raise PredecessorError(
            "same_dataset",
            f"explicit predecessor must be a JSON object (an envelope), got "
            f"{type(explicit).__name__}; its dataset cannot be confirmed",
        )
    declared_dataset = explicit.get("dataset_id")
    if declared_dataset != dataset_id:
        raise PredecessorError(
            "same_dataset",
            f"explicit predecessor declares dataset_id {declared_dataset!r}; it must "
            f"equal the observed dataset {dataset_id!r}",
        )
    observation_id = explicit.get("observation_id")
    if not isinstance(observation_id, str) or not OBSERVATION_ID_PATTERN.fullmatch(observation_id):
        raise PredecessorError(
            "envelope_present",
            "explicit predecessor must carry a contract-shaped observation_id "
            "(^obs-[a-z0-9][a-z0-9_-]{0,127}$); an unnamed envelope cannot be confirmed "
            "present in the store",
        )
    moment = _parse_instant(explicit.get("observed_at"), f"explicit predecessor {observation_id}")
    if moment >= bound:
        raise PredecessorError(
            "observed_at_earlier",
            f"explicit predecessor {observation_id} was observed at "
            f"{_normalize_instant(moment)}, not strictly earlier than "
            f"{_normalize_instant(bound)}; two observations of one dataset at one "
            "instant have no defined order, so a later or equal instant is refused "
            "rather than linked",
        )
    observation_digest = explicit.get("observation_digest")
    if not isinstance(observation_digest, str) or not OBSERVATION_DIGEST_PATTERN.fullmatch(
        observation_digest
    ):
        raise PredecessorError(
            "observation_digest_present",
            f"explicit predecessor {observation_id} carries no well-formed "
            "observation_digest (expected 'observation:sha256:' followed by exactly "
            "64 lowercase hex characters)",
        )
    row = _row_matching(list_observations(dataset_id, root=root), observation_id)
    if row is None:
        raise PredecessorError(
            "envelope_present",
            f"explicit predecessor {observation_id} has no envelope filed for dataset "
            f"{dataset_id} in the store; an unfiled predecessor is a broken chain",
        )
    envelope_file = _envelope_file(row, store_root)
    if not envelope_file.is_file():
        raise PredecessorError(
            "envelope_present",
            f"explicit predecessor {observation_id}: the named envelope file is absent "
            f"at {envelope_file}",
        )
    observed_at = _normalize_instant(moment)
    source_digest = explicit.get("source_digest")
    if source_digest is None:
        return PredecessorLink(
            dataset_id=dataset_id,
            observation_id=observation_id,
            observed_at=observed_at,
            previous_observation_id=observation_id,
            previous_observation_digest=observation_digest,
            relation_basis="metadata_only",
            basis_reason=(
                f"explicit predecessor {observation_id} observed {observed_at} retained "
                "no source bytes (metadata-only capture)"
            ),
        )
    _verify_source_digest(source_digest, observation_id, root=store_root)
    return PredecessorLink(
        dataset_id=dataset_id,
        observation_id=observation_id,
        observed_at=observed_at,
        previous_observation_id=observation_id,
        previous_observation_digest=observation_digest,
        relation_basis="captured",
        basis_reason=(
            f"explicit predecessor {observation_id} observed {observed_at} retained "
            f"source bytes verified to re-hash to {source_digest}"
        ),
    )


def _no_predecessor(dataset_id: str, bound: datetime) -> PredecessorLink:
    return PredecessorLink(
        dataset_id=dataset_id,
        observation_id=None,
        observed_at=None,
        previous_observation_id=None,
        previous_observation_digest=None,
        relation_basis="none",
        basis_reason=(
            f"no observation of dataset {dataset_id} precedes "
            f"{_normalize_instant(bound)} in the store"
        ),
    )


def resolve_predecessor(
    dataset_id: str,
    observed_at: str,
    *,
    root: Path | str | None = None,
    explicit: Mapping[str, Any] | None = None,
) -> PredecessorLink:
    """Resolve the latest strictly-earlier observation of the same dataset.

    When ``explicit`` is given it is the candidate predecessor envelope (the
    shape ``observation_capture`` passes as ``previous``); otherwise the
    latest prior row of ``list_observations(dataset_id)`` is the candidate,
    and rows at or after ``observed_at`` are never candidates. Raises
    :class:`PredecessorError` naming the broken constraint when the candidate
    belongs to another dataset, is not strictly earlier, has a missing or
    malformed ``observation_digest``, has no envelope in the store, or carries
    a ``source_digest`` whose blob is missing or does not re-hash. With no
    prior observation the link is ``relation_basis="none"``.
    """
    if not isinstance(dataset_id, str) or not dataset_id:
        raise PredecessorError("same_dataset", "dataset_id must be a non-empty string")
    bound = _parse_instant(observed_at, "new observation")
    store_root = resolve_root(root)
    if explicit is not None:
        return _resolve_explicit(dataset_id, bound, explicit, root=root, store_root=store_root)
    for row in list_observations(dataset_id, root=root):
        row_observation_id = row.get("observation_id")
        moment = _parse_instant(
            row.get("observed_at"), f"indexed observation {row_observation_id}"
        )
        if moment >= bound:
            # Later or equal instants are not prior: skipped, never linked,
            # and never reordered — exactly the backdated-capture trap.
            continue
        return _link_from_row(dataset_id, row, store_root)
    return _no_predecessor(dataset_id, bound)


def verify_link(link: PredecessorLink, *, root: Path | str | None = None) -> dict:
    """Re-check an already-written link against the store.

    Returns ``{"errors": [...], "checks": [...]}``. Never raises for a broken
    link; every violated constraint is reported in ``errors`` while ``checks``
    records the checks that were performed and passed. Ordering against the
    new observation's instant is enforced at resolution time (the link does
    not carry it); everything the store can prove is re-proved here.
    """
    errors: list[str] = []
    checks: list[str] = []

    basis = getattr(link, "relation_basis", None)
    if basis not in RELATION_BASES:
        errors.append(
            f"relation_basis: {basis!r} is outside the plan's vocabulary {RELATION_BASES}"
        )
        return {"errors": errors, "checks": checks}

    if basis == "none":
        null_ids = ("observation_id", "observed_at", "previous_observation_id", "previous_observation_digest")
        if all(getattr(link, name) is None for name in null_ids):
            checks.append("null_ids: ok")
        else:
            errors.append(
                "null_ids: link declares no predecessor yet carries non-null ids; "
                "the chain head is not a predecessor relation and must never be "
                "substituted here"
            )
        return {"errors": errors, "checks": checks}

    dataset_id = getattr(link, "dataset_id", None)
    previous_observation_id = getattr(link, "previous_observation_id", None)
    previous_observation_digest = getattr(link, "previous_observation_digest", None)
    link_observed_at = getattr(link, "observed_at", None)
    required = (dataset_id, previous_observation_id, previous_observation_digest, link_observed_at)
    if not all(isinstance(value, str) and value for value in required):
        errors.append(
            f"link_fields: a {basis!r} link must carry dataset_id, observation_id, "
            "observed_at, previous_observation_id and previous_observation_digest "
            "as strings"
        )
        return {"errors": errors, "checks": checks}
    checks.append("link_fields: ok")

    store_root = resolve_root(root)
    rows = list_observations(dataset_id, root=root)
    checks.append(f"same_dataset_scope: ok (index query scoped to dataset {dataset_id})")
    row = _row_matching(rows, previous_observation_id)
    if row is None:
        errors.append(
            f"envelope_indexed: no index row for {previous_observation_id} under "
            f"dataset {dataset_id}"
        )
        return {"errors": errors, "checks": checks}
    checks.append("envelope_indexed: ok")

    envelope_file = _envelope_file(row, store_root)
    if envelope_file.is_file():
        checks.append(f"envelope_file_present: ok ({envelope_file})")
    else:
        errors.append(
            f"envelope_file_present: envelope file for {previous_observation_id} is "
            f"missing at {envelope_file}"
        )

    if row.get("observation_digest") == previous_observation_digest:
        checks.append("digest_recorded: ok")
    else:
        errors.append(
            f"digest_recorded: link records {previous_observation_digest!r} but the "
            f"store row holds {row.get('observation_digest')!r}"
        )

    if row.get("observed_at") == link_observed_at:
        checks.append("observed_at_recorded: ok")
    else:
        errors.append(
            f"observed_at_recorded: link records {link_observed_at!r} but the store "
            f"row holds {row.get('observed_at')!r}"
        )

    row_source_digest = row.get("source_digest")
    if basis == "captured":
        if row_source_digest is None:
            errors.append(
                "relation_basis: link says captured but the store row holds no "
                "source_digest"
            )
        else:
            checks.append("relation_basis: ok")
            try:
                _verify_source_digest(row_source_digest, previous_observation_id, root=store_root)
                checks.append(f"source_digest_bytes: ok ({row_source_digest})")
            except PredecessorError as error:
                errors.append(f"source_digest_bytes: {error.message}")
    elif row_source_digest is None:
        checks.append("relation_basis: ok")
    else:
        errors.append(
            f"relation_basis: link says metadata_only but the store row holds "
            f"source_digest {row_source_digest}"
        )

    return {"errors": errors, "checks": checks}


def _selftest() -> int:
    """Acceptance selftest: every resolution constraint, one verdict per case.

    Builds a scratch store inside the worktree (the production store root is
    never touched) holding two datasets with earlier observations, exercises
    each rule, prints one line per case, and removes the scratch root.
    """
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")
    worktree = Path(__file__).resolve().parents[1]
    scratch = Path(tempfile.mkdtemp(prefix=".observation-predecessors-selftest-", dir=worktree))
    outcomes: list[tuple[str, bool, str]] = []
    try:
        def file_observation(
            dataset_id: str,
            observation_id: str,
            observed_at: str,
            source_bytes: bytes | None,
        ) -> tuple[dict[str, Any], Path]:
            source_digest = (
                put_blob(source_bytes, root=scratch) if source_bytes is not None else None
            )
            observation_digest = (
                "observation:sha256:"
                + hashlib.sha256(f"{dataset_id}\n{observation_id}".encode("utf-8")).hexdigest()
            )
            envelope = {
                "schema": "historical-observation/v2",
                "observation_id": observation_id,
                "dataset_id": dataset_id,
                "observed_at": observed_at,
                "source_digest": source_digest,
                "observation_digest": observation_digest,
            }
            envelope_path = put_envelope(dataset_id, observation_id, envelope, root=scratch)
            upsert_observation(
                dataset_id,
                observation_id,
                observed_at,
                envelope_path,
                source_digest=source_digest,
                observation_digest=observation_digest,
                root=scratch,
            )
            return (envelope, envelope_path)

        fuel_a, _ = file_observation(
            "fuelprice",
            "obs-fuelprice-20260914t020000z-aaa11111",
            "2026-09-14T02:00:00Z",
            b"date,ron95,ron97\n2026-09-14,1.95,2.55\n",
        )
        fuel_b, fuel_b_path = file_observation(
            "fuelprice",
            "obs-fuelprice-20260915t020000z-bbb22222",
            "2026-09-15T02:00:00Z",
            b"date,ron95,ron97\n2026-09-15,1.95,2.55\n",
        )
        cpi_c, _ = file_observation(
            "dosm_consumer_price_index",
            "obs-dosm-cpi-20260915t040000z-ccc33333",
            "2026-09-15T04:00:00Z",
            b"series,value\ncpi,132.4\n",
        )
        met_m, _ = file_observation(
            "met_only",
            "obs-met-only-20260915t060000z-ddd44444",
            "2026-09-15T06:00:00Z",
            None,
        )

        def refused(
            description: str, constraint: str, resolve: Any
        ) -> tuple[bool, str]:
            try:
                resolved = resolve()
            except PredecessorError as error:
                return (
                    error.constraint == constraint,
                    f"PredecessorError({error.constraint}): {error.message}",
                )
            return (
                False,
                f"expected PredecessorError({constraint}) but resolution returned "
                f"{resolved.relation_basis}:{resolved.previous_observation_id}",
            )

        link = resolve_predecessor("fuelprice", "2026-09-16T02:00:00Z", root=scratch)
        link_report = verify_link(link, root=scratch)
        happy_ok = (
            link.relation_basis == "captured"
            and link.observation_id == fuel_b["observation_id"]
            and link.observed_at == "2026-09-15T02:00:00Z"
            and link.previous_observation_id == fuel_b["observation_id"]
            and link.previous_observation_digest == fuel_b["observation_digest"]
            and not link_report["errors"]
        )
        outcomes.append(
            (
                "valid_earlier_same_dataset_predecessor",
                happy_ok,
                f"relation_basis=captured, previous={link.previous_observation_id} "
                f"({link.observed_at}) — the latest strictly-earlier fuelprice row, "
                f"not the later other-dataset observation; verify_link reported "
                f"{len(link_report['errors'])} errors",
            )
        )

        later_ok, later_detail = refused(
            "later",
            "observed_at_earlier",
            lambda: resolve_predecessor(
                "fuelprice", "2026-09-14T00:00:00Z", root=scratch, explicit=fuel_b
            ),
        )
        outcomes.append(("later_timestamp_refused", later_ok, later_detail))

        equal_ok, equal_detail = refused(
            "equal",
            "observed_at_earlier",
            lambda: resolve_predecessor(
                "fuelprice", "2026-09-15T02:00:00Z", root=scratch, explicit=fuel_b
            ),
        )
        outcomes.append(("equal_instant_refused", equal_ok, equal_detail))

        other_ok, other_detail = refused(
            "other dataset",
            "same_dataset",
            lambda: resolve_predecessor(
                "fuelprice", "2026-09-16T02:00:00Z", root=scratch, explicit=cpi_c
            ),
        )
        outcomes.append(("another_dataset_refused", other_ok, other_detail))

        blob_path(fuel_b["source_digest"], root=scratch).write_bytes(b"tampered\n")
        bytes_ok, bytes_detail = refused(
            "bytes",
            "source_digest_bytes",
            lambda: resolve_predecessor(
                "fuelprice", "2026-09-16T02:00:00Z", root=scratch, explicit=fuel_b
            ),
        )
        broken_report = verify_link(link, root=scratch)
        bytes_ok = bytes_ok and bool(broken_report["errors"])
        outcomes.append(
            (
                "digest_not_matching_bytes_refused",
                bytes_ok,
                f"{bytes_detail}; verify_link re-checks the same bytes and now "
                f"reports {len(broken_report['errors'])} error(s)",
            )
        )

        ghost = {
            "schema": "historical-observation/v2",
            "observation_id": "obs-fuelprice-20260913t000000z-ghost999",
            "dataset_id": "fuelprice",
            "observed_at": "2026-09-13T00:00:00Z",
            "source_digest": None,
            "observation_digest": "observation:sha256:" + "0" * 64,
        }
        ghost_ok, ghost_detail = refused(
            "ghost",
            "envelope_present",
            lambda: resolve_predecessor(
                "fuelprice", "2026-09-16T02:00:00Z", root=scratch, explicit=ghost
            ),
        )
        fuel_b_path.unlink()
        dangling_ok, dangling_detail = refused(
            "dangling row",
            "envelope_present",
            lambda: resolve_predecessor("fuelprice", "2026-09-16T02:00:00Z", root=scratch),
        )
        outcomes.append(
            (
                "envelope_missing_from_store_refused",
                ghost_ok and dangling_ok,
                f"explicit ghost: {ghost_detail} | dangling index row: {dangling_detail}",
            )
        )

        met_link = resolve_predecessor("met_only", "2026-09-16T02:00:00Z", root=scratch)
        met_report = verify_link(met_link, root=scratch)
        met_ok = (
            met_link.relation_basis == "metadata_only"
            and met_link.previous_observation_id == met_m["observation_id"]
            and met_link.previous_observation_digest == met_m["observation_digest"]
            and not met_report["errors"]
        )
        outcomes.append(
            (
                "metadata_only_predecessor",
                met_ok,
                f"relation_basis=metadata_only, previous={met_link.previous_observation_id}",
            )
        )

        first_link = resolve_predecessor("kkm_dashboard", "2026-09-16T02:00:00Z", root=scratch)
        first_report = verify_link(first_link, root=scratch)
        first_ok = (
            first_link.relation_basis == "none"
            and first_link.observation_id is None
            and first_link.observed_at is None
            and first_link.previous_observation_id is None
            and first_link.previous_observation_digest is None
            and not first_report["errors"]
        )
        outcomes.append(
            (
                "first_observation_links_to_none",
                first_ok,
                f"relation_basis=none, null ids; basis_reason={first_link.basis_reason!r}",
            )
        )
    except Exception as error:  # noqa: BLE001 — the selftest reports, never traces
        outcomes.append(
            ("selftest_harness", False, f"raised {type(error).__name__}: {error}")
        )
    finally:
        shutil.rmtree(scratch, ignore_errors=True)

    for name, ok, detail in outcomes:
        print(f"{name}: {'PASS' if ok else 'FAIL'} — {detail}")
    failed = [name for name, ok, _ in outcomes if not ok]
    if failed:
        print(f"selftest failed: {', '.join(failed)}", file=sys.stderr)
        return 1
    print("selftest passed: every predecessor constraint behaved as stated")
    return 0


def main(argv: list[str] | None = None) -> int:
    """Entry point; ``--selftest`` exercises every resolution constraint."""
    parser = argparse.ArgumentParser(
        description="Resolve and verify same-dataset predecessor links "
        "for the historical-observation archive."
    )
    parser.add_argument(
        "--selftest",
        action="store_true",
        help="exercise every predecessor constraint against a scratch store "
        "inside the worktree",
    )
    arguments = parser.parse_args(argv)
    if not arguments.selftest:
        parser.print_usage(sys.stderr)
        return 2
    return _selftest()


if __name__ == "__main__":
    raise SystemExit(main())
