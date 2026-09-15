#!/usr/bin/env python3
"""Bounded diff between two historical observations.

Compares the captured representation of a predecessor observation against
its successor along a fixed set of cheap dimensions: source digest,
normalized digest, shape fingerprint, and record counts.  The diff is
bounded by construction — ``DiffResult.evidence`` carries digest
references and counts only, never embedded payloads, row dumps, or
changed lines.

Every dimension is independently unknown-able: a dimension that cannot
be computed is ``None`` AND named in ``unknown_dimensions``.  A zero
always means zero, never "unmeasured".  This module makes no semantic
claim — it reports what changed in the stored representation only and
never consults or emits health status (the status taxonomy is out of
scope).

Digests are resolved through ``observation_store``'s public helpers and
compared as recorded references; content is never re-serialized or
re-hashed to derive a comparison (recomputing a digest over a
re-serialization would let a tooling change masquerade as a source
change).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import re
import shutil
import sys
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Final, Mapping

try:
    # Absolute form when the repo root is on sys.path (pipeline, pytest rootdir).
    from scripts.observation_store import (
        OBSERVATION_ID_PATTERN,
        DigestFormatError,
        blob_path,
        put_blob,
        put_envelope,
        put_normalized,
        resolve_root,
    )
except ModuleNotFoundError:  # bare form when scripts/ itself is on sys.path
    from observation_store import (
        OBSERVATION_ID_PATTERN,
        DigestFormatError,
        blob_path,
        put_blob,
        put_envelope,
        put_normalized,
        resolve_root,
    )

__all__ = ["DiffResult", "diff_observations", "main"]

logger = logging.getLogger(__name__)

#: Canonical print order for ``unknown_dimensions`` (the dataclass field
#: order of the measurable dimensions); ``incomparable`` is never unknown
#: in this part — it is determinately False until part B implements
#: detection.
DIMENSION_ORDER: Final[tuple[str, ...]] = (
    "source_digest_changed",
    "normalized_digest_changed",
    "schema_or_header_changed",
    "record_count",
    "records_added",
    "records_removed",
    "records_modified",
)

#: Record-level counts are part B's deliverable; their names are carried
#: in ``unknown_dimensions`` on every result this module produces.
_PART_B_DIMENSIONS: Final[tuple[str, ...]] = (
    "records_added",
    "records_removed",
    "records_modified",
)

# Capture files the normalized projection's digest reference inside the
# provenance transform string (observation_capture writes e.g.
# "observation_normalize profile fuelprice_csv/v1; projection_digest
# sha256:..."), because the envelope's normalized_projection member is
# closed ({state, format, record_count}) and carries no digest itself.
_PROJECTION_DIGEST_IN_TRANSFORM: Final[re.Pattern[str]] = re.compile(
    r"projection_digest (sha256:[0-9a-f]{64})"
)

_SHAPE_FINGERPRINT_LIMITATION: Final[str] = (
    "Structural fingerprint over keys, types, and headers only; it is not "
    "a digest of the source content."
)


class ObservationDiffError(Exception):
    """Base error for bounded observation diffs."""


class DiffInputError(ObservationDiffError):
    """A side is neither an envelope nor a resolvable id, or carries a
    member this diff cannot interpret (for example a malformed digest)."""


class EnvelopeResolutionError(ObservationDiffError):
    """An observation id could not be resolved to exactly one envelope in
    the store."""


@dataclass(frozen=True)
class DiffResult:
    """Bounded diff between two observations.

    Each dimension is independently unknown-able: ``None`` means the
    dimension could not be measured, and the dimension's name then
    appears in ``unknown_dimensions``.  ``source_unavailable`` is the one
    plain bool — it states whether the blob named by either side's
    ``source_digest`` is absent from the store, and when it is True the
    digest dimensions are forced to ``None`` (a change derived from a
    missing side is never True or False).

    ``record_count`` carries ``{"before", "after", "delta"}``, any of
    which may be ``None``.  ``records_added`` / ``records_removed`` /
    ``records_modified`` are part B's record-level counts and are always
    ``None`` here with their names in ``unknown_dimensions``.
    ``incomparable`` is determinately False until part B implements
    detection.

    ``evidence`` holds digest references and counts only — never embedded
    payloads, row dumps, or changed lines.
    """

    source_digest_changed: bool | None
    normalized_digest_changed: bool | None
    schema_or_header_changed: bool | None
    record_count: dict  # {"before": int | None, "after": int | None, "delta": int | None}
    records_added: int | None
    records_removed: int | None
    records_modified: int | None
    source_unavailable: bool
    incomparable: bool
    incomparable_reason: str | None
    unknown_dimensions: tuple[str, ...]
    evidence: dict

    def to_dict(self) -> dict:
        """Return a JSON-serializable dict view of this result."""
        return asdict(self)


def _resolve_by_id(observation_id: str, *, root: Path | str | None) -> dict[str, Any]:
    """Resolve an observation id to its envelope through the store.

    The envelope tree is the authority (the sqlite index is
    acceleration-only and keyed by dataset, while observation ids are
    globally unique), so an id resolves by locating its single envelope
    file under ``envelopes/``.  Zero or multiple matches are refused —
    an ambiguous or missing side is a broken input, never a silent None.
    """
    if not OBSERVATION_ID_PATTERN.fullmatch(observation_id):
        raise EnvelopeResolutionError(
            f"observation id {observation_id!r} does not match the envelope "
            "contract pattern ^obs-[a-z0-9][a-z0-9_-]{0,127}$"
        )
    envelopes_root = resolve_root(root) / "envelopes"
    if not envelopes_root.is_dir():
        raise EnvelopeResolutionError(
            f"store at {resolve_root(root)} has no envelopes/ tree; observation "
            f"id {observation_id!r} cannot be resolved"
        )
    matches = sorted(path for path in envelopes_root.rglob(f"{observation_id}.json") if path.is_file())
    if not matches:
        raise EnvelopeResolutionError(
            f"no envelope filed for observation id {observation_id!r} under "
            f"{envelopes_root}; an unresolved side is a broken input"
        )
    if len(matches) > 1:
        listed = ", ".join(str(path) for path in matches)
        raise EnvelopeResolutionError(
            f"observation id {observation_id!r} resolves to {len(matches)} envelope "
            f"files ({listed}); ids are unique per contract, so this is a broken store"
        )
    try:
        envelope = json.loads(matches[0].read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise EnvelopeResolutionError(
            f"cannot read envelope {matches[0]} for observation id {observation_id!r}: {error}"
        ) from error
    if not isinstance(envelope, dict):
        raise EnvelopeResolutionError(
            f"envelope {matches[0]} for observation id {observation_id!r} is not a "
            "JSON object"
        )
    declared_id = envelope.get("observation_id")
    if declared_id is not None and declared_id != observation_id:
        raise EnvelopeResolutionError(
            f"envelope {matches[0]} declares observation_id {declared_id!r} but was "
            f"filed under the name {observation_id!r}"
        )
    return envelope


def _resolve_side(
    value: Mapping[str, Any] | str, side: str, *, root: Path | str | None
) -> tuple[dict[str, Any], str | None]:
    """Return ``(envelope, observation_id_or_None)`` for one diff side."""
    if isinstance(value, Mapping):
        return dict(value), value.get("observation_id")
    if isinstance(value, str):
        return _resolve_by_id(value, root=root), value
    raise DiffInputError(
        f"{side} must be an envelope (mapping) or an observation id (str), got "
        f"{type(value).__name__}"
    )


def _source_digest(envelope: Mapping[str, Any], side: str, observation_id: str | None) -> str | None:
    """The side's ``source_digest`` reference, or None when it retained none."""
    digest = envelope.get("source_digest")
    if digest is None:
        return None
    if not isinstance(digest, str):
        raise DiffInputError(
            f"{side} observation {observation_id!r} carries a non-string source_digest "
            f"({type(digest).__name__}); the envelope contract allows only the digest "
            "string form or null"
        )
    return digest


def _blob_present(digest: str, side: str, observation_id: str | None, *, root: Path | str | None) -> bool:
    """Whether the blob named by ``digest`` exists in the store."""
    try:
        return blob_path(digest, root=root).is_file()
    except DigestFormatError as error:
        raise DiffInputError(
            f"{side} observation {observation_id!r} carries a malformed source_digest "
            f"this diff cannot resolve in the store: {error}"
        ) from error


def _normalized_digest_reference(
    envelope: Mapping[str, Any],
) -> str | None:
    """The side's normalized-projection digest reference, or None.

    Looked up on the ``normalized_projection`` member first (should a
    future contract carry the reference there), then in the
    ``field_provenance.normalized_projection.transform`` string capture
    writes today.  Never recomputed from content.
    """
    projection = envelope.get("normalized_projection")
    if isinstance(projection, Mapping):
        for key in ("digest", "projection_digest"):
            reference = projection.get(key)
            if isinstance(reference, str) and reference:
                return reference
    provenance = envelope.get("field_provenance")
    if isinstance(provenance, Mapping):
        entry = provenance.get("normalized_projection")
        if isinstance(entry, Mapping):
            transform = entry.get("transform")
            if isinstance(transform, str):
                match = _PROJECTION_DIGEST_IN_TRANSFORM.search(transform)
                if match is not None:
                    return match.group(1)
    return None


def _shape_fingerprint_value(envelope: Mapping[str, Any]) -> str | None:
    """The side's ``shape_fingerprint.value``, or None when unmeasured."""
    fingerprint = envelope.get("shape_fingerprint")
    if isinstance(fingerprint, Mapping):
        value = fingerprint.get("value")
        if isinstance(value, str) and value:
            return value
    return None


def _record_count(envelope: Mapping[str, Any]) -> int | None:
    """The side's ``normalized_projection.record_count``, or None."""
    projection = envelope.get("normalized_projection")
    if isinstance(projection, Mapping):
        count = projection.get("record_count")
        if isinstance(count, int) and not isinstance(count, bool) and count >= 0:
            return count
    return None


def diff_observations(
    previous: Mapping[str, Any] | str,
    current: Mapping[str, Any] | str,
    *,
    root: Path | str | None = None,
) -> DiffResult:
    """Compute a bounded diff between two observations.

    ``previous`` and ``current`` are envelopes (mappings) or observation
    ids resolvable in the store at ``root``.  Digests are compared as the
    recorded references resolved through the store; content is never
    re-serialized or re-hashed.  Raises :class:`DiffInputError` for an
    unusable side and :class:`EnvelopeResolutionError` for an id the
    store cannot resolve to exactly one envelope.  Deterministic: the
    same inputs produce an equal :class:`DiffResult`.
    """
    previous_envelope, previous_id = _resolve_side(previous, "previous", root=root)
    current_envelope, current_id = _resolve_side(current, "current", root=root)

    unknown: set[str] = set(_PART_B_DIMENSIONS)

    previous_source = _source_digest(previous_envelope, "previous", previous_id)
    current_source = _source_digest(current_envelope, "current", current_id)

    unavailable_sides: list[str] = []
    for side, digest in (("previous", previous_source), ("current", current_source)):
        if digest is not None and not _blob_present(digest, side, previous_id if side == "previous" else current_id, root=root):
            unavailable_sides.append(side)
    source_unavailable = bool(unavailable_sides)

    previous_normalized = _normalized_digest_reference(previous_envelope)
    current_normalized = _normalized_digest_reference(current_envelope)

    if source_unavailable:
        # A change derived from a missing side is never True or False.
        source_digest_changed: bool | None = None
        normalized_digest_changed: bool | None = None
        unknown.update({"source_digest_changed", "normalized_digest_changed"})
    else:
        if previous_source is not None and current_source is not None:
            source_digest_changed = previous_source != current_source
        else:
            source_digest_changed = None
            unknown.add("source_digest_changed")
        if previous_normalized is not None and current_normalized is not None:
            normalized_digest_changed = previous_normalized != current_normalized
        else:
            normalized_digest_changed = None
            unknown.add("normalized_digest_changed")

    previous_fingerprint = _shape_fingerprint_value(previous_envelope)
    current_fingerprint = _shape_fingerprint_value(current_envelope)
    if previous_fingerprint is not None and current_fingerprint is not None:
        schema_or_header_changed: bool | None = previous_fingerprint != current_fingerprint
    else:
        schema_or_header_changed = None
        unknown.add("schema_or_header_changed")

    count_before = _record_count(previous_envelope)
    count_after = _record_count(current_envelope)
    count_delta = (
        count_after - count_before
        if count_before is not None and count_after is not None
        else None
    )
    if count_before is None or count_after is None or count_delta is None:
        unknown.add("record_count")
    record_count = {"before": count_before, "after": count_after, "delta": count_delta}

    evidence: dict[str, Any] = {
        "previous_observation_id": previous_id,
        "current_observation_id": current_id,
        "previous_source_digest": previous_source,
        "current_source_digest": current_source,
        "previous_normalized_digest": previous_normalized,
        "current_normalized_digest": current_normalized,
        "previous_shape_fingerprint": previous_fingerprint,
        "current_shape_fingerprint": current_fingerprint,
        "record_count": dict(record_count),
        "unavailable_sides": list(unavailable_sides),
    }

    result = DiffResult(
        source_digest_changed=source_digest_changed,
        normalized_digest_changed=normalized_digest_changed,
        schema_or_header_changed=schema_or_header_changed,
        record_count=record_count,
        records_added=None,
        records_removed=None,
        records_modified=None,
        source_unavailable=source_unavailable,
        incomparable=False,
        incomparable_reason=None,
        unknown_dimensions=tuple(name for name in DIMENSION_ORDER if name in unknown),
        evidence=evidence,
    )
    logger.debug(
        "diff %s -> %s: source_digest_changed=%s unknown_dimensions=%s",
        previous_id,
        current_id,
        result.source_digest_changed,
        result.unknown_dimensions,
    )
    return result


# ---------------------------------------------------------------------------
# Selftest — one labelled verdict per case, against a scratch store
# ---------------------------------------------------------------------------


def _selftest_envelope(
    *,
    observation_id: str,
    dataset_id: str,
    observed_at: str,
    source_digest: str | None,
    shape_value: str,
    projection_digest: str | None,
    record_count: int | None,
) -> dict[str, Any]:
    """A minimal envelope carrying exactly the members this diff reads."""
    transform = (
        f"observation_normalize profile fuelprice_csv/v1; projection_digest {projection_digest}"
        if projection_digest is not None
        else None
    )
    return {
        "schema": "historical-observation/v2",
        "observation_id": observation_id,
        "dataset_id": dataset_id,
        "observed_at": observed_at,
        "source_digest": source_digest,
        "observation_digest": "observation:sha256:" + hashlib.sha256(observation_id.encode("utf-8")).hexdigest(),
        "shape_fingerprint": {
            "algorithm": "shape-v1",
            "value": shape_value,
            "basis": "csv-headers",
            "limitation": _SHAPE_FINGERPRINT_LIMITATION,
        },
        "normalized_projection": {
            "state": "retained" if projection_digest is not None else "not_retained",
            "format": "csv" if projection_digest is not None else None,
            "record_count": record_count,
        },
        "field_provenance": {
            "normalized_projection": {
                "basis": "platform_computed",
                "derived": True,
                "state": "measured",
                "not_measured_reason": None,
                "transform": transform,
                "counters": {"rows": record_count, "delivered": None, "empty": None, "stringified": None, "truncated": None},
            }
        },
    }


def _file_projection(record_count: int, *, root: Path) -> str:
    """File a small projection through the store and return its digest."""
    return put_normalized(
        {
            "format": "csv",
            "record_count": record_count,
            "columns": ["date", "ron95"],
            "dropped_fields": [],
            "deduped_rows": 0,
            "record_ids": ["sha256:" + hashlib.sha256(f"row-{record_count}".encode("utf-8")).hexdigest()],
        },
        root=root,
    )


def _selftest() -> int:
    """Three cases — unchanged, digest-changed, unavailable — one verdict each.

    Builds a scratch store inside the worktree (the production store root
    is never touched), asserts each case's specific expectations, prints
    the dimension values produced, removes the scratch root, and exits 0
    only if all three held.
    """
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")
    worktree = Path(__file__).resolve().parents[1]
    scratch = Path(tempfile.mkdtemp(prefix=".observation-diff-selftest-", dir=worktree))
    outcomes: list[tuple[str, bool, str]] = []

    def verdict(name: str, ok: bool, result: DiffResult) -> None:
        detail = (
            f"source_digest_changed={result.source_digest_changed} "
            f"normalized_digest_changed={result.normalized_digest_changed} "
            f"schema_or_header_changed={result.schema_or_header_changed} "
            f"record_count={result.record_count} "
            f"source_unavailable={result.source_unavailable} "
            f"unknown_dimensions={result.unknown_dimensions}"
        )
        outcomes.append((name, ok, detail))

    try:
        same_header = b"date,ron95\n2026-09-15,1.95\n"
        # Same header line, different data line: different bytes, same shape.
        changed_body = b"date,ron95\n2026-09-16,1.96\n"
        shape_value = hashlib.sha256(b"date,ron95").hexdigest()

        # -- case 1: unchanged (identical bytes and digests) --------------
        same_digest = put_blob(same_header, root=scratch)
        same_projection = _file_projection(1, root=scratch)
        unchanged_previous = _selftest_envelope(
            observation_id="obs-fuelprice-20260915t020000z-aaa11111",
            dataset_id="fuelprice_unchanged",
            observed_at="2026-09-15T02:00:00Z",
            source_digest=same_digest,
            shape_value=shape_value,
            projection_digest=same_projection,
            record_count=1,
        )
        unchanged_current = _selftest_envelope(
            observation_id="obs-fuelprice-20260916t020000z-bbb22222",
            dataset_id="fuelprice_unchanged",
            observed_at="2026-09-16T02:00:00Z",
            source_digest=same_digest,
            shape_value=shape_value,
            projection_digest=same_projection,
            record_count=1,
        )
        unchanged_result = diff_observations(unchanged_previous, unchanged_current, root=scratch)
        unchanged_ok = (
            unchanged_result.source_digest_changed is False
            and "source_digest_changed" not in unchanged_result.unknown_dimensions
            and unchanged_result.normalized_digest_changed is False
            and "normalized_digest_changed" not in unchanged_result.unknown_dimensions
            and unchanged_result.source_unavailable is False
            and unchanged_result.record_count == {"before": 1, "after": 1, "delta": 0}
            and "record_count" not in unchanged_result.unknown_dimensions
            # Determinism: the same inputs produce an equal DiffResult.
            and unchanged_result == diff_observations(unchanged_previous, unchanged_current, root=scratch)
        )
        verdict("unchanged", unchanged_ok, unchanged_result)

        # -- case 2: digest-changed (same fingerprint, different bytes) ---
        previous_digest = put_blob(same_header, root=scratch)
        current_digest = put_blob(changed_body, root=scratch)
        changed_previous = _selftest_envelope(
            observation_id="obs-fuelprice-20260915t020000z-ccc33333",
            dataset_id="fuelprice_revised",
            observed_at="2026-09-15T02:00:00Z",
            source_digest=previous_digest,
            shape_value=shape_value,
            projection_digest=_file_projection(1, root=scratch),
            record_count=1,
        )
        changed_current = _selftest_envelope(
            observation_id="obs-fuelprice-20260916t020000z-ddd44444",
            dataset_id="fuelprice_revised",
            observed_at="2026-09-16T02:00:00Z",
            source_digest=current_digest,
            shape_value=shape_value,
            projection_digest=_file_projection(2, root=scratch),
            record_count=2,
        )
        put_envelope("fuelprice_revised", changed_previous["observation_id"], changed_previous, root=scratch)
        put_envelope("fuelprice_revised", changed_current["observation_id"], changed_current, root=scratch)
        # Ids, not envelopes: proves resolution through the store's envelope tree.
        changed_result = diff_observations(
            changed_previous["observation_id"], changed_current["observation_id"], root=scratch
        )
        changed_ok = (
            changed_result.source_digest_changed is True
            and changed_result.schema_or_header_changed is False
            and changed_result.source_unavailable is False
        )
        verdict("digest-changed", changed_ok, changed_result)

        # -- case 3: unavailable (the predecessor's blob deleted) ---------
        orphan_digest = put_blob(b"date,ron95\n2026-09-14,1.90\n", root=scratch)
        orphan_previous = _selftest_envelope(
            observation_id="obs-fuelprice-20260915t020000z-eee55555",
            dataset_id="fuelprice_orphan",
            observed_at="2026-09-15T02:00:00Z",
            source_digest=orphan_digest,
            shape_value=shape_value,
            projection_digest=_file_projection(1, root=scratch),
            record_count=1,
        )
        orphan_current = _selftest_envelope(
            observation_id="obs-fuelprice-20260916t020000z-fff66666",
            dataset_id="fuelprice_orphan",
            observed_at="2026-09-16T02:00:00Z",
            source_digest=put_blob(b"date,ron95\n2026-09-16,1.96\n", root=scratch),
            shape_value=shape_value,
            projection_digest=_file_projection(2, root=scratch),
            record_count=2,
        )
        put_envelope("fuelprice_orphan", orphan_previous["observation_id"], orphan_previous, root=scratch)
        put_envelope("fuelprice_orphan", orphan_current["observation_id"], orphan_current, root=scratch)
        blob_path(orphan_digest, root=scratch).unlink()  # the predecessor's blob is gone
        orphan_result = diff_observations(
            orphan_previous["observation_id"], orphan_current["observation_id"], root=scratch
        )
        orphan_ok = (
            orphan_result.source_unavailable is True
            and orphan_result.source_digest_changed is None
            and "source_digest_changed" in orphan_result.unknown_dimensions
            and orphan_result.normalized_digest_changed is None
            and "normalized_digest_changed" in orphan_result.unknown_dimensions
        )
        verdict("unavailable", orphan_ok, orphan_result)
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
    print("selftest passed: unchanged, digest-changed and unavailable behaved as stated")
    return 0


def main(argv: list[str] | None = None) -> int:
    """CLI: ``--selftest``, or ``--previous ID --current ID [--root ROOT]``."""
    parser = argparse.ArgumentParser(
        prog="observation_diff.py",
        description="Bounded diff between two historical observations.",
    )
    parser.add_argument(
        "--selftest",
        action="store_true",
        help="run the three acceptance cases against a scratch store inside the worktree",
    )
    parser.add_argument(
        "--previous",
        metavar="OBS_ID",
        help="previous side: an observation id resolvable in the store",
    )
    parser.add_argument(
        "--current",
        metavar="OBS_ID",
        help="current side: an observation id resolvable in the store",
    )
    parser.add_argument(
        "--root",
        type=Path,
        metavar="ROOT",
        help="absolute observation store root (default: DATAPULSE_OBSERVATION_ROOT or the configured default)",
    )
    arguments = parser.parse_args(argv)

    if arguments.selftest:
        return _selftest()
    if not arguments.previous or not arguments.current:
        parser.error("--previous and --current are required unless --selftest is given")

    try:
        result = diff_observations(arguments.previous, arguments.current, root=arguments.root)
    except ObservationDiffError as error:
        print(f"ERROR {error}", file=sys.stderr)
        return 2
    print(json.dumps(result.to_dict(), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
