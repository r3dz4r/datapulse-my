"""Score a supplied independent-agent trace against an explicit local suite."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import agent_task_suite


TRACE_SCHEMA = "datapulse/v1/agent-task-trace"
TRACE_FIELDS = frozenset({"schema", "tasks"})
TRACE_TASK_FIELDS = frozenset({"task_id", "attempt"})
EVALUATION_MODE = "external_semantic"

# Independent agents only see the public MCP responses, whose equivalent
# citation fields use several documented names.  These groups intentionally
# describe evidence roles rather than fixture-private field spellings.
CITATION_ALIASES = {
    "dataset_id": ("dataset_id", "dataset", "dataset_identifier", "identifier"),
    "evidence_url": ("evidence_url", "source_url", "source_evidence_url", "url"),
    "observed_at": ("observed_at", "last_checked", "checked_at", "observation_time"),
    "datapulse_verdict": ("datapulse_verdict", "verdict", "datapulse_status", "status"),
    "licence": ("licence", "license", "licence_url", "license_url"),
    "receipt_digest": ("receipt_digest", "evidence_receipt_digest", "digest"),
}


def _load_json_object(path: Path, label: str) -> dict[str, object]:
    """Load one explicit JSON object path without selecting any defaults."""
    value: Any = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be a JSON object")
    return value


def _validate_attempt(attempt: object) -> None:
    """Validate the attempt shape consumed by the existing evaluator."""
    if not isinstance(attempt, Mapping):
        raise ValueError("Trace attempt must be an object")
    calls = attempt.get("calls")
    if not isinstance(calls, list) or not all(isinstance(call, str) and call for call in calls):
        raise ValueError("Trace attempt calls must be non-empty strings")


def inject_attempts(suite: Mapping[str, object], trace: Mapping[str, object]) -> dict[str, object]:
    """Copy a suite and replace only fixture attempts with supplied trace attempts."""
    agent_task_suite.validate_suite(suite)
    if set(trace) != TRACE_FIELDS or trace.get("schema") != TRACE_SCHEMA:
        raise ValueError(f"Trace schema must be {TRACE_SCHEMA} with only schema and tasks fields")
    trace_tasks = trace.get("tasks")
    if not isinstance(trace_tasks, list):
        raise ValueError("Trace tasks must be a list")

    attempts: dict[str, Mapping[str, object]] = {}
    for entry in trace_tasks:
        if not isinstance(entry, Mapping) or set(entry) != TRACE_TASK_FIELDS:
            raise ValueError("Each trace task must contain only task_id and attempt")
        task_id = entry.get("task_id")
        if not isinstance(task_id, str) or not task_id:
            raise ValueError("Trace task ids must be non-empty strings")
        if task_id in attempts:
            raise ValueError("Trace task ids must be unique")
        attempt = entry.get("attempt")
        _validate_attempt(attempt)
        assert isinstance(attempt, Mapping)
        attempts[task_id] = attempt

    suite_tasks = suite["tasks"]
    assert isinstance(suite_tasks, list)
    suite_ids = {str(task["task_id"]) for task in suite_tasks if isinstance(task, Mapping)}
    unknown_ids = sorted(set(attempts) - suite_ids)
    if unknown_ids:
        raise ValueError(f"Trace contains unknown task ids: {', '.join(unknown_ids)}")
    missing_ids = sorted(suite_ids - set(attempts))
    if missing_ids:
        raise ValueError(f"Trace is missing suite task ids: {', '.join(missing_ids)}")

    injected_tasks = []
    for task in suite_tasks:
        assert isinstance(task, Mapping)
        injected = dict(task)
        injected["attempt"] = dict(attempts[str(task["task_id"])])
        injected_tasks.append(injected)
    injected_suite = dict(suite)
    injected_suite["tasks"] = injected_tasks
    return injected_suite


def _is_subsequence(expected: list[str], actual: list[str]) -> bool:
    """Return whether an expected workflow appears in the observed call order."""
    expected_index = 0
    for call in actual:
        if expected_index < len(expected) and call == expected[expected_index]:
            expected_index += 1
    return expected_index == len(expected)


def _workflow_score(task: Mapping[str, object], attempt: Mapping[str, object]) -> int:
    """Accept a declared workflow in order while efficiency scores extra calls."""
    calls = attempt.get("calls")
    workflows = task.get("workflows")
    scoring = task.get("scoring")
    if (
        not isinstance(calls, list)
        or not isinstance(workflows, list)
        or not isinstance(scoring, Mapping)
    ):
        return 0
    return int(
        any(isinstance(workflow, list) and _is_subsequence(workflow, calls) for workflow in workflows)
    )


def _outcome_score(task: Mapping[str, object], attempt: Mapping[str, object]) -> int:
    """Require the closed outcome/action pair and any explanatory reason text."""
    expected = task.get("expected")
    outcome = attempt.get("outcome")
    return int(
        isinstance(expected, Mapping)
        and isinstance(outcome, Mapping)
        and outcome.get("outcome") == expected.get("outcome")
        and outcome.get("action") == expected.get("action")
        and isinstance(outcome.get("reason"), str)
        and bool(outcome["reason"].strip())
    )


def _citation_value(citation: Mapping[str, object], required_field: str) -> object:
    """Return a non-empty value from the deterministic alias group for one role."""
    for alias in CITATION_ALIASES.get(required_field, (required_field,)):
        value = citation.get(alias)
        if isinstance(value, str) and value.strip():
            return value
    return None


def _citation_role_value(
    citation: Mapping[str, object], evidence: Mapping[str, object], required_field: str
) -> object:
    """Resolve one role from citation first, then the supplied evidence."""
    value = _citation_value(citation, required_field)
    return value if value is not None else _citation_value(evidence, required_field)


def _citation_score(task: Mapping[str, object], attempt: Mapping[str, object]) -> int:
    """Score evidence roles and declared receipt binding without hidden field names."""
    requirements = task.get("citation_requirements")
    if not isinstance(requirements, Mapping):
        return 0
    citation = attempt.get("citation")
    if requirements.get("required") is False:
        return int(citation is None)
    if citation is None:
        citation = {}
    elif not isinstance(citation, Mapping):
        return 0
    evidence = attempt.get("evidence")
    if not isinstance(evidence, Mapping):
        evidence = {}
    fields = requirements.get("fields")
    if not isinstance(fields, list) or any(
        _citation_role_value(citation, evidence, field) is None for field in fields
    ):
        return 0
    if requirements.get("bind_receipt") is not True:
        return 1
    receipt_digest = _citation_value(citation, "receipt_digest")
    evidence_receipt_digest = _citation_value(evidence, "receipt_digest")
    return int(
        isinstance(receipt_digest, str)
        and bool(receipt_digest.strip())
        and isinstance(evidence_receipt_digest, str)
        and bool(evidence_receipt_digest.strip())
        and receipt_digest == evidence_receipt_digest
    )


def _evaluate_task(task: Mapping[str, object]) -> dict[str, object]:
    """Score one external attempt using the adapter's public semantic contract."""
    attempt = task["attempt"]
    assert isinstance(attempt, Mapping)
    calls = attempt["calls"]
    assert isinstance(calls, list)
    scoring = task["scoring"]
    assert isinstance(scoring, Mapping)
    external_score, external_status = agent_task_suite._offline_verifier_score(task, attempt)
    scores = {
        "workflow": _workflow_score(task, attempt),
        "outcome": _outcome_score(task, attempt),
        "citation": _citation_score(task, attempt),
        "efficiency": int(len(calls) <= scoring["max_calls"]),
        "external_verification": external_score,
    }
    scores["total"] = sum(scores.values())
    outcome = attempt.get("outcome")
    return {
        "task_id": task["task_id"],
        "passed": scores["total"] == 5,
        "outcome": outcome.get("outcome") if isinstance(outcome, Mapping) else "unknown",
        "action": outcome.get("action") if isinstance(outcome, Mapping) else "abstain",
        "reason": outcome.get("reason") if isinstance(outcome, Mapping) else "malformed_attempt",
        "call_count": len(calls),
        "redundant_calls": sum(count - 1 for count in Counter(calls).values() if count > 1),
        "external_verification": external_status,
        "scores": scores,
    }


def _semantic_report(suite: Mapping[str, object]) -> dict[str, object]:
    """Build the stable suite report shape for external semantic evaluation."""
    tasks = suite["tasks"]
    assert isinstance(tasks, list)
    results = [_evaluate_task(task) for task in tasks if isinstance(task, Mapping)]
    outcomes = Counter(str(result["outcome"]) for result in results)
    passed = sum(result["passed"] is True for result in results)
    return {
        "schema": "datapulse/v1/agent-task-suite-report",
        "evaluation_mode": EVALUATION_MODE,
        "tasks": results,
        "aggregate": {
            "task_count": len(results),
            "passed_tasks": passed,
            "failed_tasks": len(results) - passed,
            "outcomes": {outcome: outcomes[outcome] for outcome in sorted(agent_task_suite.OUTCOMES)},
            "total_calls": sum(int(result["call_count"]) for result in results),
            "total_redundant_calls": sum(int(result["redundant_calls"]) for result in results),
            "mean_score": sum(int(result["scores"]["total"]) for result in results) / len(results),
        },
    }


def score_trace(suite_path: Path, trace_path: Path) -> dict[str, object]:
    """Load explicit local inputs and return the external semantic report."""
    suite = _load_json_object(suite_path, "Task suite")
    trace = _load_json_object(trace_path, "Trace")
    return _semantic_report(inject_attempts(suite, trace))


def main() -> None:
    """Print one stable report for explicitly supplied local paths."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--suite", required=True, type=Path, help="checked-in agent task-suite JSON fixture")
    parser.add_argument("--trace", required=True, type=Path, help="external agent trace JSON")
    args = parser.parse_args()
    print(json.dumps(score_trace(args.suite, args.trace), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
