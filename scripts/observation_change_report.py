#!/usr/bin/env python3
"""Representation-level change report between two observations.

A byte change is evidence that bytes changed; it is not evidence that a
price, a schedule, or a population changed.  This module is the boundary
that keeps those two apart: :class:`ChangeReport` describes what changed
in the *captured representation* — source bytes, schema/header shape,
and the normalized projection's records — and carries no field, empty or
otherwise, in which a consumer could file a verdict about the real
world.  ``semantic_change`` exists only as the fixed constant
``"unsupported"``: a report that cannot express a semantic claim cannot
invite a consumer to fill one in.

The boundary is enforced, not implied.
:func:`assert_claim_within_boundary` accepts claims about the captured
representation and raises :class:`ClaimBoundaryError` — a typed error —
for any claim asserting that the real world changed, including a claim
derived from ``source_bytes_changed`` or ``schema_or_header_changed``
being True.  The refusal message names the claim and states that the
report cannot support it, so a refused consumer sees why instead of a
silent None.  The boundary must not refuse everything: a representation
claim ("the captured bytes changed") is accepted, because that is the
one kind of claim the report legitimately makes.

Every dimension is independently unknown-able: ``None`` means the
dimension could not be measured AND its name appears in
``unknown_dimensions``; ``False`` always means measured-and-unchanged.
Inputs that cannot be compared at all (for example a normalization
profile change between the two observations) yield ``None`` for the
record-level dimension — nothing is inferred from an incomparable pair.

``evidence`` holds digest references and counts only — never embedded
payloads, row dumps, or changed lines.  This module never imports,
consults, emits, or compares any health status: change classification
is independent of freshness classification, and the ten-status taxonomy
is out of scope by design.  Deterministic: the same inputs produce an
equal :class:`ChangeReport`.
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
    from scripts.observation_diff import (
        DiffResult,
        ObservationDiffError,
        diff_observations,
    )
    from scripts.observation_store import put_blob, put_envelope, put_normalized
except ModuleNotFoundError:  # bare form when scripts/ itself is on sys.path
    from observation_diff import (
        DiffResult,
        ObservationDiffError,
        diff_observations,
    )
    from observation_store import put_blob, put_envelope, put_normalized

__all__ = [
    "SEMANTIC_CHANGE_UNSUPPORTED",
    "ChangeReport",
    "ClaimBoundaryError",
    "assert_claim_within_boundary",
    "build_change_report",
    "main",
]

logger = logging.getLogger(__name__)

#: The only value ``ChangeReport.semantic_change`` can ever carry.  A
#: change report has no semantic verdict to give — not "none", not
#: "unknown", not null — so the field is a fixed constant and
#: ``ChangeReport.__post_init__`` refuses any other value.
SEMANTIC_CHANGE_UNSUPPORTED: Final[str] = "unsupported"

#: The report's own measurable dimensions, in canonical print order.
#: Each maps 1:1 onto a ``bool | None`` field; a dimension that is None
#: is named here in ``unknown_dimensions``, and a dimension that is
#: named is None — the pairing is enforced at construction.
_REPORT_DIMENSION_ORDER: Final[tuple[str, ...]] = (
    "source_bytes_changed",
    "normalized_records_changed",
    "schema_or_header_changed",
)

#: Closed vocabulary of terms that anchor a claim to the captured
#: representation.  A claim is accepted only when it carries at least
#: one of these AND carries none of ``_SEMANTIC_SUBJECT_TERMS``.  Kept
#: deliberately broad across everything a report can legitimately speak
#: about (bytes, digests, schema, headers, shape, projections,
#: envelopes, counts) so the boundary does not refuse the claims it
#: exists to make.
_REPRESENTATION_ANCHOR_TERMS: Final[tuple[str, ...]] = (
    "byte",
    "bytes",
    "digest",
    "digests",
    "representation",
    "representations",
    "capture",
    "captured",
    "schema",
    "header",
    "headers",
    "fingerprint",
    "fingerprints",
    "shape",
    "projection",
    "projections",
    "normalized",
    "record",
    "records",
    "envelope",
    "envelopes",
    "column",
    "columns",
    "count",
    "counts",
)

#: Closed vocabulary of real-world subjects.  Any of these in a claim
#: makes it a semantic-truth claim and refuses it, even when the claim
#: also carries representation vocabulary ("the captured price
#: changed") — naming a real-world subject is exactly the crossing the
#: boundary exists to stop.
_SEMANTIC_SUBJECT_TERMS: Final[tuple[str, ...]] = (
    "price",
    "prices",
    "population",
    "populations",
    "schedule",
    "schedules",
    "world",
    "real world",
    "real-world",
    "reality",
    "actual",
    "fact",
    "facts",
    "in fact",
    "truth",
    "in truth",
)


class ClaimBoundaryError(Exception):
    """A claim crossed the representation/world boundary.

    Raised by :func:`assert_claim_within_boundary` when a claim asserts
    a semantic truth about the real world — on its own or derived from a
    measured byte or schema change — or when a claim is not recognisable
    as a claim about the captured representation at all (unrecognised
    claims fail closed, onto the world side of the boundary).
    """


@dataclass(frozen=True)
class ChangeReport:
    """What changed in the captured representation — and nothing else.

    Each of the three dimension fields is independently unknown-able:
    ``None`` means the dimension could not be measured, and the
    dimension's name then appears in ``unknown_dimensions``.  ``False``
    always means measured-and-unchanged, never "unmeasured".

    ``semantic_change`` is the fixed constant
    :data:`SEMANTIC_CHANGE_UNSUPPORTED` and can never hold any other
    value — the report describes the representation, never the world.
    There is deliberately no health-status field of any kind: this
    report neither emits nor consults the status taxonomy.

    ``evidence`` holds digest references and counts only — never
    embedded payloads, row dumps, or changed lines.
    """

    source_bytes_changed: bool | None
    normalized_records_changed: bool | None
    schema_or_header_changed: bool | None
    semantic_change: str
    unknown_dimensions: tuple[str, ...]
    evidence: dict

    def __post_init__(self) -> None:
        """Enforce the report contract at construction.

        An inconsistent report must be unrepresentable, not merely
        discouraged: a semantic verdict smuggled in, an unknown that is
        not declared, or a measured dimension declared unknown would all
        give a consumer a lie to build on.
        """
        if self.semantic_change != SEMANTIC_CHANGE_UNSUPPORTED:
            raise ValueError(
                "semantic_change must always be "
                f"{SEMANTIC_CHANGE_UNSUPPORTED!r}; a change report carries "
                f"no semantic verdict (got {self.semantic_change!r})"
            )
        if not isinstance(self.evidence, dict):
            raise ValueError(
                "evidence must be a dict of digest references and counts, "
                f"got {type(self.evidence).__name__}"
            )
        measured: dict[str, bool | None] = {
            "source_bytes_changed": self.source_bytes_changed,
            "normalized_records_changed": self.normalized_records_changed,
            "schema_or_header_changed": self.schema_or_header_changed,
        }
        for name, value in measured.items():
            if value is not None and not isinstance(value, bool):
                raise ValueError(
                    f"{name} must be a bool or None, got {type(value).__name__}"
                )
        if len(set(self.unknown_dimensions)) != len(self.unknown_dimensions):
            raise ValueError(
                f"unknown_dimensions carries duplicates: {self.unknown_dimensions}"
            )
        foreign = [
            name for name in self.unknown_dimensions if name not in _REPORT_DIMENSION_ORDER
        ]
        if foreign:
            raise ValueError(
                f"unknown_dimensions names dimensions this report does not "
                f"carry: {foreign}"
            )
        for name, value in measured.items():
            if value is None and name not in self.unknown_dimensions:
                raise ValueError(
                    f"{name} is None but is not declared in unknown_dimensions; "
                    "unknown is explicit, never implicit"
                )
            if value is not None and name in self.unknown_dimensions:
                raise ValueError(
                    f"{name} is measured ({value}) but is declared in "
                    "unknown_dimensions; False means measured-and-unchanged"
                )

    def to_dict(self) -> dict:
        """Return a JSON-serializable dict view of this report."""
        return asdict(self)


def build_change_report(
    previous: Mapping[str, Any] | str,
    current: Mapping[str, Any] | str,
    *,
    root: Path | str | None = None,
) -> ChangeReport:
    """Build the representation-level change report between two observations.

    Takes the same inputs :func:`scripts.observation_diff.diff_observations`
    takes — envelopes (mappings) or observation ids resolvable in the store
    at ``root`` — and derives the report from the resulting
    :class:`~scripts.observation_diff.DiffResult`:

    - ``source_bytes_changed`` follows the diff's ``source_digest_changed``
      (bytes are named by their digest; the reference is the measurement).
    - ``schema_or_header_changed`` follows the diff's dimension of that name.
    - ``normalized_records_changed`` is True only when the record-level
      dimensions are known AND at least one of added/removed/modified is
      non-zero; False only when they are known and all three are zero;
      None — and declared in ``unknown_dimensions`` — when they are
      unknown, including when the inputs are incomparable.

    Raises the diff module's typed errors (``DiffInputError``,
    ``EnvelopeResolutionError``) unchanged for unusable or unresolvable
    sides.  Deterministic: the same inputs produce an equal report.
    """
    result = diff_observations(previous, current, root=root)

    source_bytes_changed: bool | None = result.source_digest_changed
    schema_or_header_changed: bool | None = result.schema_or_header_changed

    record_level = (result.records_added, result.records_removed, result.records_modified)
    if result.incomparable or any(value is None for value in record_level):
        # Nothing is inferred from an incomparable or partially unmeasured
        # pair: a count across incomparable inputs would describe the
        # profile change, not the source.  Unknown is explicit, never False.
        normalized_records_changed: bool | None = None
    else:
        normalized_records_changed = any(record_level)

    measured: dict[str, bool | None] = {
        "source_bytes_changed": source_bytes_changed,
        "normalized_records_changed": normalized_records_changed,
        "schema_or_header_changed": schema_or_header_changed,
    }
    unknown_dimensions = tuple(
        name for name in _REPORT_DIMENSION_ORDER if measured[name] is None
    )

    # Digest references, profile/format designations, counts, and the two
    # structural flags that explain why a dimension may be withheld —
    # bounded by construction, nothing embedded.
    evidence: dict[str, Any] = {
        "previous_observation_id": result.evidence.get("previous_observation_id"),
        "current_observation_id": result.evidence.get("current_observation_id"),
        "previous_source_digest": result.evidence.get("previous_source_digest"),
        "current_source_digest": result.evidence.get("current_source_digest"),
        "previous_normalized_digest": result.evidence.get("previous_normalized_digest"),
        "current_normalized_digest": result.evidence.get("current_normalized_digest"),
        "previous_shape_fingerprint": result.evidence.get("previous_shape_fingerprint"),
        "current_shape_fingerprint": result.evidence.get("current_shape_fingerprint"),
        "previous_profile": result.evidence.get("previous_profile"),
        "current_profile": result.evidence.get("current_profile"),
        "previous_format": result.evidence.get("previous_format"),
        "current_format": result.evidence.get("current_format"),
        "record_count": dict(result.record_count),
        "records_added": result.records_added,
        "records_removed": result.records_removed,
        "records_modified": result.records_modified,
        "incomparable": result.incomparable,
        "source_unavailable": result.source_unavailable,
    }

    report = ChangeReport(
        source_bytes_changed=source_bytes_changed,
        normalized_records_changed=normalized_records_changed,
        schema_or_header_changed=schema_or_header_changed,
        semantic_change=SEMANTIC_CHANGE_UNSUPPORTED,
        unknown_dimensions=unknown_dimensions,
        evidence=evidence,
    )
    logger.debug(
        "change report %s -> %s: source_bytes_changed=%s "
        "normalized_records_changed=%s schema_or_header_changed=%s "
        "unknown_dimensions=%s",
        evidence["previous_observation_id"],
        evidence["current_observation_id"],
        report.source_bytes_changed,
        report.normalized_records_changed,
        report.schema_or_header_changed,
        report.unknown_dimensions,
    )
    return report


def _contains_term(lowered_claim: str, term: str) -> bool:
    """Whole-word, case-insensitive containment for a closed-vocabulary term."""
    return re.search(rf"\b{re.escape(term)}\b", lowered_claim) is not None


def assert_claim_within_boundary(report: ChangeReport, claim: str) -> None:
    """Assert that ``claim`` stays on the representation side of the boundary.

    Accepts (returns without raising) claims about the captured
    representation — bytes, digests, schema, headers, projections,
    counts.  Raises :class:`ClaimBoundaryError` for any claim asserting
    that the real world changed — a semantic truth — including when it
    is derived from ``source_bytes_changed`` or
    ``schema_or_header_changed`` being True: a byte or schema change is
    evidence that the representation changed, not that the world did.
    The error message names the claim and states that the report cannot
    support it.

    Acceptance is category-level, not truth-level: a recognised
    representation claim is accepted even when the report's measured
    value for it is False or None — the truth of a representation claim
    is read from the report's fields, never from this function.  Claims
    that name a real-world subject (price, population, schedule, ...)
    are refused even when wrapped in representation vocabulary, and
    claims recognisable as neither fail closed onto the world side.
    """
    if not isinstance(report, ChangeReport):
        raise TypeError(
            "assert_claim_within_boundary expects a ChangeReport, got "
            f"{type(report).__name__}"
        )
    lowered = claim.lower()
    # Real-world subjects take precedence: naming one is the crossing,
    # and wrapping it in capture vocabulary does not make it measurable.
    for term in _SEMANTIC_SUBJECT_TERMS:
        if _contains_term(lowered, term):
            raise ClaimBoundaryError(
                f"claim {claim!r} names {term!r}, a real-world subject, so it "
                "asserts a semantic truth; this change report describes only "
                "the captured representation (source bytes, schema/header "
                "shape, normalized records) and cannot support it — a byte "
                "or schema change is evidence that the representation "
                "changed, not that the world did"
            )
    for term in _REPRESENTATION_ANCHOR_TERMS:
        if _contains_term(lowered, term):
            logger.debug("claim within boundary: %r (anchored by %r)", claim, term)
            return None
    # Unrecognised claims fail closed, onto the world side: the boundary
    # must be impossible to cross by accident, and vocabulary it has never
    # been introduced to cannot be assumed to be representation-safe.
    raise ClaimBoundaryError(
        f"claim {claim!r} is not recognised as a claim about the captured "
        "representation (no representation term — bytes, digest, schema, "
        "header, projection, ... — appears in it), and unrecognised claims "
        "are treated as claims about the world; this report cannot support it"
    )


# ---------------------------------------------------------------------------
# Selftest — one labelled verdict per case, against a scratch store
# ---------------------------------------------------------------------------

_SHAPE_FINGERPRINT_LIMITATION: Final[str] = (
    "Structural fingerprint over keys, types, and headers only; it is not "
    "a digest of the source content."
)


def _selftest_envelope(
    *,
    observation_id: str,
    dataset_id: str,
    observed_at: str,
    source_digest: str | None,
    shape_value: str,
    projection_digest: str | None,
    record_count: int | None,
    profile_name: str = "fuelprice_csv",
    profile_version: str = "v1",
    projection_format: str | None = None,
) -> dict[str, Any]:
    """A minimal envelope carrying exactly the members the diff reads.

    Mirrors the envelope contract observation_diff's own selftest
    demonstrates, so the scratch store exercises the real resolution
    paths rather than a parallel fixture format.
    """
    transform = (
        f"observation_normalize profile {profile_name}/{profile_version}; projection_digest {projection_digest}"
        if projection_digest is not None
        else None
    )
    effective_format = (
        projection_format
        if projection_format is not None
        else ("csv" if projection_digest is not None else None)
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
            "format": effective_format,
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


def _file_projection(record_ids: list[str], *, root: Path) -> str:
    """File a projection exposing exactly ``record_ids`` and return its digest."""
    return put_normalized(
        {
            "format": "csv",
            "record_count": len(record_ids),
            "columns": ["date", "ron95"],
            "dropped_fields": [],
            "deduped_rows": 0,
            "record_ids": list(record_ids),
        },
        root=root,
    )


def _selftest() -> int:
    """Six cases, one verdict each.

    ``unchanged``, ``bytes-changed``, ``schema-changed`` and
    ``incomparable`` assert the specific field values the report must
    produce for each input shape; ``representation-claim-accepted`` and
    ``semantic-claim-refused`` are the boundary proof — a
    representation-level claim must be accepted, and a semantic-truth
    claim derived only from a byte change must be refused with a typed
    error whose message is printed as the case's verdict.  Builds a
    scratch store inside the worktree (the production store root is
    never touched), removes it, and exits 0 only if all six held.
    """
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")
    worktree = Path(__file__).resolve().parents[1]
    scratch = Path(tempfile.mkdtemp(prefix=".observation-change-report-selftest-", dir=worktree))
    outcomes: list[tuple[str, bool, str]] = []

    try:
        shape_value = hashlib.sha256(b"date,ron95").hexdigest()
        wider_shape = hashlib.sha256(b"date,ron95,ron97").hexdigest()
        stable_id = "sha256:" + hashlib.sha256(b"record-stable").hexdigest()
        extra_id = "sha256:" + hashlib.sha256(b"record-extra").hexdigest()

        # -- case 1: unchanged (identical bytes and projection) ---------
        same_digest = put_blob(b"date,ron95\n2026-09-15,1.95\n", root=scratch)
        same_projection = _file_projection([stable_id], root=scratch)
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
        unchanged_report = build_change_report(unchanged_previous, unchanged_current, root=scratch)
        unchanged_ok = (
            unchanged_report.source_bytes_changed is False
            and unchanged_report.semantic_change == SEMANTIC_CHANGE_UNSUPPORTED
            # Determinism: the same inputs produce an equal report.
            and unchanged_report == build_change_report(unchanged_previous, unchanged_current, root=scratch)
        )
        outcomes.append(
            (
                "unchanged",
                unchanged_ok,
                f"source_bytes_changed={unchanged_report.source_bytes_changed} "
                f"semantic_change={unchanged_report.semantic_change!r} "
                f"normalized_records_changed={unchanged_report.normalized_records_changed} "
                f"schema_or_header_changed={unchanged_report.schema_or_header_changed}",
            )
        )

        # -- case 2: bytes-changed (same schema, different bytes, by id) -
        # The temptation case: bytes measurably differ, and the report
        # still carries no semantic verdict to draw from.
        previous_digest = put_blob(b"date,ron95\n2026-09-15,1.95\n", root=scratch)
        current_digest = put_blob(b"date,ron95\n2026-09-16,1.96\n", root=scratch)
        bytes_previous = _selftest_envelope(
            observation_id="obs-fuelprice-20260915t020000z-ccc33333",
            dataset_id="fuelprice_revised",
            observed_at="2026-09-15T02:00:00Z",
            source_digest=previous_digest,
            shape_value=shape_value,
            projection_digest=_file_projection([stable_id], root=scratch),
            record_count=1,
        )
        bytes_current = _selftest_envelope(
            observation_id="obs-fuelprice-20260916t020000z-ddd44444",
            dataset_id="fuelprice_revised",
            observed_at="2026-09-16T02:00:00Z",
            source_digest=current_digest,
            shape_value=shape_value,
            projection_digest=_file_projection([stable_id, extra_id], root=scratch),
            record_count=2,
        )
        put_envelope("fuelprice_revised", bytes_previous["observation_id"], bytes_previous, root=scratch)
        put_envelope("fuelprice_revised", bytes_current["observation_id"], bytes_current, root=scratch)
        # Ids, not envelopes: proves the report derives from the store-resolved diff.
        bytes_report = build_change_report(
            bytes_previous["observation_id"], bytes_current["observation_id"], root=scratch
        )
        bytes_ok = (
            bytes_report.source_bytes_changed is True
            and bytes_report.semantic_change == SEMANTIC_CHANGE_UNSUPPORTED
        )
        outcomes.append(
            (
                "bytes-changed",
                bytes_ok,
                f"source_bytes_changed={bytes_report.source_bytes_changed} "
                f"schema_or_header_changed={bytes_report.schema_or_header_changed} "
                f"semantic_change={bytes_report.semantic_change!r}",
            )
        )

        # -- case 3: schema-changed (shape fingerprint differs) ----------
        schema_previous = _selftest_envelope(
            observation_id="obs-fuelprice-20260915t020000z-55e95e95",
            dataset_id="fuelprice_schema",
            observed_at="2026-09-15T02:00:00Z",
            source_digest=same_digest,
            shape_value=shape_value,
            projection_digest=_file_projection([stable_id], root=scratch),
            record_count=1,
        )
        schema_current = _selftest_envelope(
            observation_id="obs-fuelprice-20260916t020000z-66f066f0",
            dataset_id="fuelprice_schema",
            observed_at="2026-09-16T02:00:00Z",
            source_digest=same_digest,
            shape_value=wider_shape,
            projection_digest=_file_projection([stable_id], root=scratch),
            record_count=1,
        )
        schema_report = build_change_report(schema_previous, schema_current, root=scratch)
        schema_ok = (
            schema_report.schema_or_header_changed is True
            and schema_report.semantic_change == SEMANTIC_CHANGE_UNSUPPORTED
        )
        outcomes.append(
            (
                "schema-changed",
                schema_ok,
                f"schema_or_header_changed={schema_report.schema_or_header_changed} "
                f"semantic_change={schema_report.semantic_change!r}",
            )
        )

        # -- case 4: incomparable (profile version differs) --------------
        # The current side gained a record id, but the pair is
        # incomparable, so nothing about the records may be inferred.
        incomparable_previous = _selftest_envelope(
            observation_id="obs-fuelprice-20260915t020000z-77a177a1",
            dataset_id="fuelprice_profile",
            observed_at="2026-09-15T02:00:00Z",
            source_digest=same_digest,
            shape_value=shape_value,
            projection_digest=_file_projection([stable_id], root=scratch),
            record_count=1,
            profile_version="v1",
        )
        incomparable_current = _selftest_envelope(
            observation_id="obs-fuelprice-20260916t020000z-88b288b2",
            dataset_id="fuelprice_profile",
            observed_at="2026-09-16T02:00:00Z",
            source_digest=same_digest,
            shape_value=shape_value,
            projection_digest=_file_projection([stable_id, extra_id], root=scratch),
            record_count=2,
            profile_version="v2",
        )
        incomparable_report = build_change_report(
            incomparable_previous, incomparable_current, root=scratch
        )
        incomparable_ok = (
            incomparable_report.normalized_records_changed is None
            and "normalized_records_changed" in incomparable_report.unknown_dimensions
        )
        outcomes.append(
            (
                "incomparable",
                incomparable_ok,
                f"normalized_records_changed={incomparable_report.normalized_records_changed} "
                f"unknown_dimensions={incomparable_report.unknown_dimensions} "
                f"semantic_change={incomparable_report.semantic_change!r}",
            )
        )

        # -- case 5: representation-claim-accepted ------------------------
        # On the bytes-changed report: the boundary must accept the one
        # kind of claim the report legitimately makes.
        try:
            assert_claim_within_boundary(bytes_report, "the captured bytes changed")
            accepted_ok = True
            accepted_detail = (
                "assert_claim_within_boundary(bytes_report, 'the captured bytes "
                "changed') returned without raising"
            )
        except ClaimBoundaryError as error:
            accepted_ok = False
            accepted_detail = f"refused a representation claim: {error}"
        outcomes.append(("representation-claim-accepted", accepted_ok, accepted_detail))

        # -- case 6: semantic-claim-refused -------------------------------
        # Also on the bytes-changed report: the claim is exactly the one
        # a byte change would tempt a consumer into, and it must raise.
        try:
            assert_claim_within_boundary(bytes_report, "the price increased")
            refused_ok = False
            refused_detail = "no ClaimBoundaryError raised for a semantic-truth claim"
        except ClaimBoundaryError as error:
            refused_ok = True
            # The message is the verdict: the run log shows WHY it was refused.
            refused_detail = str(error)
        outcomes.append(("semantic-claim-refused", refused_ok, refused_detail))
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
    print("selftest passed: all six cases behaved as stated")
    return 0


def main(argv: list[str] | None = None) -> int:
    """CLI: ``--selftest``, or ``--previous ID --current ID [--root ROOT]``."""
    parser = argparse.ArgumentParser(
        prog="observation_change_report.py",
        description=(
            "Representation-level change report between two observations; "
            "refuses claims about the real world."
        ),
    )
    parser.add_argument(
        "--selftest",
        action="store_true",
        help="run the six acceptance cases against a scratch store inside the worktree",
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
        report = build_change_report(arguments.previous, arguments.current, root=arguments.root)
    except ObservationDiffError as error:
        print(f"ERROR {error}", file=sys.stderr)
        return 2
    print(json.dumps(report.to_dict(), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
