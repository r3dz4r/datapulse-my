"""Pure local policy checks for DataPulse citation-evidence benchmark cases.

This module is intentionally not part of the public MCP server.  It evaluates
only the presence and published freshness status of supplied evidence; it does
not infer a dataset's substantive truth, licence permission, regulatory status,
or real-world absence.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
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


def _result(category: object, action: str, reason: str) -> dict[str, object]:
    """Return the fixed, JSON-serialisable answerability result shape."""
    return {
        "action": action,
        "reason": reason,
        "evidence_required": True,
        "category": category if isinstance(category, str) else "unknown",
    }


def _has_required_request_shape(candidate: Mapping[str, object]) -> bool:
    """Require an exact dataset identity and non-empty request scope."""
    request = candidate.get("request")
    if not isinstance(request, Mapping):
        return False
    return all(
        isinstance(request.get(field), str) and bool(request[field].strip())
        for field in ("dataset_id", "scope")
    )


def _evidence_classes(candidate: Mapping[str, object]) -> set[str]:
    """Classify statuses conservatively while preserving unrecognised unknowns."""
    evidence = candidate.get("evidence")
    if not isinstance(evidence, Sequence) or isinstance(evidence, (str, bytes)):
        return set()

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


def evaluate_candidate(candidate: Mapping[str, object]) -> dict[str, object]:
    """Evaluate one local citation-evidence candidate using fixed precedence.

    Precedence is request shape, no record, conflicting safety classes, unsafe
    evidence, uncertain freshness, reference-only evidence, then fresh support.
    A fresh item can therefore never override a malformed request or unsafe
    conflicting evidence.
    """
    category = candidate.get("category")
    if not _has_required_request_shape(candidate):
        return _result(category, "abstain", "underspecified")

    evidence = candidate.get("evidence")
    if not isinstance(evidence, Sequence) or isinstance(evidence, (str, bytes)) or not evidence:
        return _result(category, "abstain", "no_supported_record")

    classes = _evidence_classes(candidate)
    if len(classes) > 1:
        return _result(category, "abstain", "conflicting_evidence")
    if "unsafe" in classes:
        return _result(category, "abstain", "unsafe_evidence")
    if "uncertain" in classes:
        return _result(category, "warn", "uncertain_freshness")
    if "reference" in classes:
        return _result(category, "warn", "reference_only")
    if "supported" in classes:
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
