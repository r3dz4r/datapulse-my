"""Tests for the deterministic local agent-task evaluator."""

from __future__ import annotations

import json
import sys
from pathlib import Path


MCP_DIR = Path(__file__).resolve().parents[1]
FIXTURE_PATH = Path(__file__).with_name("fixtures") / "agent_task_cases.json"
sys.path.insert(0, str(MCP_DIR))

import agent_task_suite  # noqa: E402


def _fixture() -> dict[str, object]:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def _result(report: dict[str, object], task_id: str) -> dict[str, object]:
    for row in report["tasks"]:
        if row["task_id"] == task_id:
            return row
    raise AssertionError(f"Missing task result {task_id}")


def test_fixture_has_a_closed_schema_and_required_taxonomy() -> None:
    fixture = _fixture()
    agent_task_suite.validate_suite(fixture)

    tasks = fixture["tasks"]
    assert 10 <= len(tasks) <= 15
    assert {task["task_id"] for task in tasks} == {
        "discover_currentness_source",
        "select_search_verify_provenance",
        "bind_evidence_receipt_citation",
        "supported_claim",
        "partial_claim",
        "unsupported_claim",
        "unknown_claim",
        "stale_and_discontinued_abstention",
        "unreachable_abstention",
        "reference_outcome",
        "unknown_freshness_outcome",
        "conflicting_observations",
        "malformed_out_of_catalogue",
        "redundant_call_accounting",
        "offline_external_verification",
    }


def test_report_is_byte_stable_and_machine_readable() -> None:
    fixture = _fixture()
    first = agent_task_suite.run_suite(fixture)
    second = agent_task_suite.run_suite(fixture)

    assert json.dumps(first, sort_keys=True, separators=(",", ":")) == json.dumps(
        second, sort_keys=True, separators=(",", ":")
    )
    assert first["schema"] == "datapulse/v1/agent-task-suite-report"
    assert first["aggregate"]["task_count"] == 15


def test_runner_loads_the_checked_in_fixture_path() -> None:
    assert agent_task_suite.run_fixture(FIXTURE_PATH) == agent_task_suite.run_suite(_fixture())


def test_positive_supported_case_passes_every_measurement() -> None:
    result = _result(agent_task_suite.run_suite(_fixture()), "supported_claim")

    assert result["outcome"] == "supported"
    assert result["passed"] is True
    assert result["scores"] == {
        "workflow": 1,
        "outcome": 1,
        "citation": 1,
        "efficiency": 1,
        "external_verification": 1,
        "total": 5,
    }


def test_abstention_and_unknown_results_remain_explicit() -> None:
    report = agent_task_suite.run_suite(_fixture())

    stale = _result(report, "stale_and_discontinued_abstention")
    unknown = _result(report, "unknown_claim")
    assert stale["outcome"] == "unsupported"
    assert stale["action"] == "abstain"
    assert unknown["outcome"] == "unknown"
    assert unknown["action"] == "abstain"
    assert report["aggregate"]["outcomes"]["unknown"] >= 1


def test_unsupported_claim_and_citation_mismatch_fail_closed() -> None:
    fixture = _fixture()
    task = next(task for task in fixture["tasks"] if task["task_id"] == "supported_claim")
    attempt = dict(task["attempt"])
    citation = dict(attempt["citation"])
    citation["receipt_digest"] = "sha256:not-bound"
    attempt["citation"] = citation

    result = agent_task_suite.evaluate_task(task, attempt)

    assert result["scores"]["citation"] == 0
    assert result["passed"] is False


def test_redundant_calls_are_counted_and_reduce_efficiency() -> None:
    result = _result(agent_task_suite.run_suite(_fixture()), "redundant_call_accounting")

    assert result["redundant_calls"] == 1
    assert result["scores"]["efficiency"] == 0
    assert result["passed"] is False


def test_aggregate_metrics_count_passes_outcomes_and_efficiency() -> None:
    aggregate = agent_task_suite.run_suite(_fixture())["aggregate"]

    assert aggregate["passed_tasks"] == 14
    assert aggregate["failed_tasks"] == 1
    assert aggregate["total_redundant_calls"] == 1
    assert aggregate["outcomes"] == {
        "supported": 5,
        "partial": 3,
        "unsupported": 4,
        "unknown": 3,
    }


def test_external_verifier_case_uses_only_the_offline_contract() -> None:
    result = _result(agent_task_suite.run_suite(_fixture()), "offline_external_verification")

    assert result["scores"]["external_verification"] == 1
    assert result["external_verification"] == "passed"
