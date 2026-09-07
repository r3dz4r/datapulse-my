"""Deterministic, offline evaluation of local DataPulse agent task traces.

This module is deliberately separate from the public MCP server.  It scores
fixture-supplied traces against closed workflow, outcome, citation, and call
budget contracts; it never asks a model to judge an answer or fetches a URL.
"""

from __future__ import annotations

import argparse
import contextlib
import io
import json
import sys
from collections import Counter
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any


OUTCOMES = frozenset({"supported", "partial", "unsupported", "unknown"})
REQUIRED_TASK_FIELDS = frozenset(
    {
        "task_id",
        "prompt",
        "workflows",
        "expected",
        "citation_requirements",
        "scoring",
        "attempt",
    }
)


def _is_list_of_strings(value: object) -> bool:
    return isinstance(value, list) and all(isinstance(item, str) and item for item in value)


def validate_suite(suite: Mapping[str, object]) -> None:
    """Reject malformed task fixtures before they can influence scoring."""
    if suite.get("schema") != "datapulse/v1/agent-task-suite":
        raise ValueError("Task suite schema must be datapulse/v1/agent-task-suite")
    tasks = suite.get("tasks")
    if not isinstance(tasks, list) or not 10 <= len(tasks) <= 15:
        raise ValueError("Task suite must contain 10 to 15 tasks")
    seen: set[str] = set()
    for task in tasks:
        if not isinstance(task, Mapping) or not REQUIRED_TASK_FIELDS.issubset(task):
            raise ValueError("Each task must include the required task contract fields")
        task_id = task.get("task_id")
        if not isinstance(task_id, str) or not task_id or task_id in seen:
            raise ValueError("Task ids must be non-empty and unique")
        seen.add(task_id)
        if not isinstance(task.get("prompt"), str) or not task["prompt"].strip():
            raise ValueError("Each task prompt must be non-empty")
        workflows = task.get("workflows")
        if not isinstance(workflows, list) or not workflows or not all(_is_list_of_strings(path) for path in workflows):
            raise ValueError("Each task must declare bounded workflow alternatives")
        expected = task.get("expected")
        if not isinstance(expected, Mapping) or expected.get("outcome") not in OUTCOMES:
            raise ValueError("Each task must declare a closed expected outcome")
        if expected.get("action") not in {"answer", "warn", "abstain"} or not isinstance(expected.get("reason"), str):
            raise ValueError("Each task must declare an action and reason")
        citation = task.get("citation_requirements")
        if not isinstance(citation, Mapping) or not isinstance(citation.get("required"), bool):
            raise ValueError("Each task must declare citation requirements")
        fields = citation.get("fields", [])
        if not _is_list_of_strings(fields):
            raise ValueError("Citation requirement fields must be strings")
        scoring = task.get("scoring")
        if not isinstance(scoring, Mapping) or not isinstance(scoring.get("max_calls"), int) or scoring["max_calls"] < 1:
            raise ValueError("Each task must declare a positive max_calls score bound")
        attempt = task.get("attempt")
        if not isinstance(attempt, Mapping) or not _is_list_of_strings(attempt.get("calls")):
            raise ValueError("Each task must provide a fixture attempt with calls")


def _workflow_score(task: Mapping[str, object], attempt: Mapping[str, object]) -> int:
    calls = attempt.get("calls")
    workflows = task.get("workflows")
    if not _is_list_of_strings(calls) or not isinstance(workflows, list):
        return 0
    return int(any(calls == workflow for workflow in workflows))


def _outcome_score(task: Mapping[str, object], attempt: Mapping[str, object]) -> int:
    expected = task["expected"]
    outcome = attempt.get("outcome")
    return int(
        isinstance(expected, Mapping)
        and isinstance(outcome, Mapping)
        and all(outcome.get(field) == expected.get(field) for field in ("outcome", "action", "reason"))
    )


def _citation_score(task: Mapping[str, object], attempt: Mapping[str, object]) -> int:
    requirements = task["citation_requirements"]
    if not isinstance(requirements, Mapping):
        return 0
    required = requirements.get("required")
    citation = attempt.get("citation")
    if required is False:
        return int(citation is None)
    if not isinstance(citation, Mapping):
        return 0
    fields = requirements.get("fields", [])
    if not _is_list_of_strings(fields) or any(not isinstance(citation.get(field), str) or not citation[field] for field in fields):
        return 0
    evidence = attempt.get("evidence")
    if requirements.get("bind_receipt") is True:
        return int(
            isinstance(evidence, Mapping)
            and isinstance(citation.get("receipt_digest"), str)
            and citation.get("receipt_digest") == evidence.get("receipt_digest")
        )
    return 1


def _offline_verifier_score(task: Mapping[str, object], attempt: Mapping[str, object]) -> tuple[int, str]:
    if task.get("offline_external_verifier") is not True:
        return 1, "not_applicable"
    if attempt.get("external_verification") != "self_test":
        return 0, "not_requested"
    # The existing verifier's self-test has a valid signature and a deliberately
    # tampered signature.  It performs no HTTP calls and keeps the contract independent.
    repository_root = str(Path(__file__).resolve().parents[1])
    if repository_root not in sys.path:
        sys.path.insert(0, repository_root)
    from scripts.verify_external import VerificationError, self_test

    try:
        with contextlib.redirect_stdout(io.StringIO()):
            self_test()
    except VerificationError:
        return 0, "failed"
    return 1, "passed"


def _redundant_calls(calls: Sequence[str]) -> int:
    """Count repeated tool invocations; workflow repetition needs explicit justification."""
    counts = Counter(calls)
    return sum(count - 1 for count in counts.values() if count > 1)


def evaluate_task(task: Mapping[str, object], attempt: Mapping[str, object] | None = None) -> dict[str, object]:
    """Score one supplied trace with no semantic or model-based judgement."""
    actual = attempt if attempt is not None else task["attempt"]
    if not isinstance(actual, Mapping):
        raise ValueError("Task attempt must be an object")
    calls = actual.get("calls")
    if not _is_list_of_strings(calls):
        raise ValueError("Task attempt calls must be strings")
    external_score, external_status = _offline_verifier_score(task, actual)
    scores = {
        "workflow": _workflow_score(task, actual),
        "outcome": _outcome_score(task, actual),
        "citation": _citation_score(task, actual),
        "efficiency": int(len(calls) <= task["scoring"]["max_calls"]),  # validated above
        "external_verification": external_score,
    }
    scores["total"] = sum(scores.values())
    outcome = actual.get("outcome")
    return {
        "task_id": task["task_id"],
        "passed": scores["total"] == 5,
        "outcome": outcome.get("outcome") if isinstance(outcome, Mapping) else "unknown",
        "action": outcome.get("action") if isinstance(outcome, Mapping) else "abstain",
        "reason": outcome.get("reason") if isinstance(outcome, Mapping) else "malformed_attempt",
        "call_count": len(calls),
        "redundant_calls": _redundant_calls(calls),
        "external_verification": external_status,
        "scores": scores,
    }


def run_suite(suite: Mapping[str, object]) -> dict[str, object]:
    """Return a deterministic, machine-readable report for all fixture tasks."""
    validate_suite(suite)
    tasks = suite["tasks"]
    assert isinstance(tasks, list)
    results = [evaluate_task(task) for task in tasks if isinstance(task, Mapping)]
    outcomes = Counter(str(result["outcome"]) for result in results)
    passed = sum(result["passed"] is True for result in results)
    return {
        "schema": "datapulse/v1/agent-task-suite-report",
        "tasks": results,
        "aggregate": {
            "task_count": len(results),
            "passed_tasks": passed,
            "failed_tasks": len(results) - passed,
            "outcomes": {outcome: outcomes[outcome] for outcome in sorted(OUTCOMES)},
            "total_calls": sum(int(result["call_count"]) for result in results),
            "total_redundant_calls": sum(int(result["redundant_calls"]) for result in results),
            "mean_score": sum(int(result["scores"]["total"]) for result in results) / len(results),
        },
    }


def run_fixture(fixture_path: Path) -> dict[str, object]:
    """Load and evaluate one checked-in JSON fixture without network access."""
    fixture: Any = json.loads(fixture_path.read_text(encoding="utf-8"))
    if not isinstance(fixture, Mapping):
        raise ValueError("Task suite fixture must be a JSON object")
    return run_suite(fixture)


def main() -> None:
    """Print the deterministic report for a local task-suite fixture."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("fixture", type=Path, help="checked-in agent task-suite JSON fixture")
    args = parser.parse_args()
    print(json.dumps(run_fixture(args.fixture), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
