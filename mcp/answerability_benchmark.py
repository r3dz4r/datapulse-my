"""Pure local policy checks for DataPulse citation-evidence benchmark cases.

This module is intentionally not part of the public MCP server.  It evaluates
only the presence and published freshness status of supplied evidence; it does
not infer a dataset's substantive truth, licence permission, regulatory status,
or real-world absence.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


UNSAFE_STATUSES = frozenset(
    {
        "stale",
        "discontinued",
        "degraded",
        "browser-dependent",
        "unreachable",
        "unknown",
    }
)
UNCERTAIN_STATUSES = frozenset({"aging", "unknown-freshness"})
SUPPORTED_STATUS = "fresh"
REFERENCE_STATUS = "reference"


def _result(category: object, action: str, reason: str, **additions: object) -> dict[str, object]:
    """Return the fixed, JSON-serialisable answerability result shape."""
    result: dict[str, object] = {
        "action": action,
        "reason": reason,
        "evidence_required": True,
        "category": category if isinstance(category, str) else "unknown",
    }
    result.update(additions)
    return result


def _has_required_request_shape(candidate: Mapping[str, object]) -> bool:
    """Require an exact dataset identity and non-empty request scope."""
    request = candidate.get("request")
    if not isinstance(request, Mapping):
        return False
    return all(
        isinstance(request.get(field), str) and bool(request[field].strip())
        for field in ("dataset_id", "scope")
    )


def _evidence_classes(evidence: Sequence[object]) -> set[str]:
    """Classify statuses conservatively while preserving unrecognised unknowns."""
    classes: set[str] = set()
    for item in evidence:
        if not isinstance(item, Mapping):
            classes.add("unsafe")
            continue
        status = item.get("status")
        if not isinstance(status, str):
            classes.add("unsafe")
            continue
        normalized = status.strip().lower().replace("_", "-")
        if normalized == SUPPORTED_STATUS:
            classes.add("supported")
        elif normalized in UNCERTAIN_STATUSES:
            classes.add("uncertain")
        elif normalized == REFERENCE_STATUS:
            classes.add("reference")
        else:
            # Explicitly named unsafe statuses and unrecognised statuses both
            # fail closed; neither establishes a semantic conclusion.
            classes.add("unsafe")
    return classes


def _parse_observed_at(value: object) -> datetime | None:
    """Parse ISO dates consistently without assigning a real-world meaning."""
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _select_temporal_evidence(
    candidate: Mapping[str, object], evidence: Sequence[object]
) -> tuple[Sequence[object], bool, bool, bool, bool]:
    """Select the canonical vintage and report invalid or conflicting requests.

    The boolean tuple is ``(is_temporal, invalid, conflicting, beyond_latest)``.
    Legacy un-timestamped candidates deliberately retain aggregate evaluation.
    """
    request = candidate.get("request")
    if not isinstance(request, Mapping):
        return evidence, False, False, False, False

    has_as_of = "as_of_date" in request
    has_explicit_selection = "selected_observed_at" in request
    has_observed_at = any(isinstance(item, Mapping) and "observed_at" in item for item in evidence)
    if not (has_as_of or has_explicit_selection or has_observed_at):
        return evidence, False, False, False, False

    observations: list[tuple[datetime, object]] = []
    for item in evidence:
        if not isinstance(item, Mapping):
            return evidence, True, True, False, False
        observed_at = _parse_observed_at(item.get("observed_at"))
        if observed_at is None:
            return evidence, True, True, False, False
        observations.append((observed_at, item))

    latest_observed_at = max(observed_at for observed_at, _ in observations)
    as_of = _parse_observed_at(request.get("as_of_date")) if has_as_of else None
    if has_as_of and as_of is None:
        return evidence, True, True, False, False

    explicit_selection = (
        _parse_observed_at(request.get("selected_observed_at")) if has_explicit_selection else None
    )
    if has_explicit_selection and explicit_selection is None:
        return evidence, True, True, False, False
    if explicit_selection is not None and explicit_selection not in {
        observed_at for observed_at, _ in observations
    }:
        return evidence, True, True, False, False
    if as_of is None and explicit_selection is not None and explicit_selection != latest_observed_at:
        return evidence, True, False, True, False

    selected_observed_at = latest_observed_at
    beyond_latest = False
    if as_of is not None:
        eligible = [observed_at for observed_at, _ in observations if observed_at <= as_of]
        if not eligible:
            return (), True, False, False, False
        selected_observed_at = max(eligible)
        beyond_latest = as_of > latest_observed_at

    return (
        tuple(item for observed_at, item in observations if observed_at == selected_observed_at),
        True,
        False,
        False,
        beyond_latest,
    )


def evaluate_candidate(candidate: Mapping[str, object]) -> dict[str, object]:
    """Evaluate one local citation-evidence candidate using fixed precedence.

    Precedence is request shape, no record, conflicting safety classes, unsafe
    evidence, temporal selection, then per-status verdicts. Timestamped
    evidence is selected at the requested vintage before classification, while
    un-timestamped legacy cases retain their aggregate safety checks.
    """
    category = candidate.get("category")
    if not _has_required_request_shape(candidate):
        return _result(category, "abstain", "underspecified")

    evidence = candidate.get("evidence")
    if not isinstance(evidence, Sequence) or isinstance(evidence, (str, bytes)) or not evidence:
        return _result(category, "abstain", "no_supported_record")

    selected_evidence, is_temporal, invalid_temporal, temporal_conflict, beyond_latest = (
        _select_temporal_evidence(candidate, evidence)
    )
    if invalid_temporal:
        return _result(category, "abstain", "unsafe_evidence")
    if temporal_conflict:
        return _result(category, "abstain", "conflicting_evidence")
    if not selected_evidence:
        return _result(category, "abstain", "no_supported_record")

    classes = _evidence_classes(selected_evidence)
    if len(classes) > 1:
        return _result(category, "abstain", "conflicting_evidence")
    if "unsafe" in classes:
        return _result(category, "abstain", "unsafe_evidence")
    if "uncertain" in classes:
        return _result(category, "warn", "uncertain_freshness")
    if "reference" in classes:
        return _result(category, "warn", "reference_only")
    if "supported" in classes:
        request = candidate.get("request")
        as_of = request.get("as_of_date") if isinstance(request, Mapping) else None
        observed_at = selected_evidence[0].get("observed_at") if isinstance(selected_evidence[0], Mapping) else None
        if is_temporal and isinstance(as_of, str) and isinstance(observed_at, str):
            selected_time = _parse_observed_at(observed_at)
            evidence_times = [
                _parse_observed_at(item.get("observed_at"))
                for item in evidence
                if isinstance(item, Mapping)
            ]
            latest_time = max(time for time in evidence_times if time is not None)
            if selected_time is not None and selected_time < latest_time:
                return _result(
                    category,
                    "answer",
                    "historical_evidence",
                    historical=True,
                    observed_at=observed_at,
                )
        if beyond_latest:
            return _result(category, "answer", "supported_evidence", as_of_beyond_latest=True)
        return _result(category, "answer", "supported_evidence")
    return _result(category, "abstain", "no_supported_record")


def run_benchmark(fixture_path: Path) -> dict[str, object]:
    """Load a benchmark fixture and return its ordered, deterministic report."""
    fixture: Any = json.loads(fixture_path.read_text(encoding="utf-8"))
    cases = fixture.get("cases") if isinstance(fixture, Mapping) else None
    if not isinstance(cases, list):
        raise ValueError("Benchmark fixture must contain a cases list")

    results: list[dict[str, object]] = []
    for case in cases:
        if not isinstance(case, Mapping):
            raise ValueError("Each benchmark case must be an object")
        name = case.get("name")
        if not isinstance(name, str) or not name:
            raise ValueError("Each benchmark case must have a name")
        results.append({"name": name, "result": evaluate_candidate(case)})

    return {"schema": "datapulse/v1/answerability-benchmark-report", "cases": results}
