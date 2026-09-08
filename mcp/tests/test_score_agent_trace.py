"""Tests for the local independent-agent trace adapter."""

from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

import pytest


MCP_DIR = Path(__file__).resolve().parents[1]
FIXTURE_PATH = Path(__file__).with_name("fixtures") / "agent_task_cases.json"
sys.path.insert(0, str(MCP_DIR))

import score_agent_trace  # noqa: E402
import agent_task_suite  # noqa: E402


def _suite() -> dict[str, object]:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def _trace(suite: dict[str, object]) -> dict[str, object]:
    return {
        "schema": "datapulse/v1/agent-task-trace",
        "tasks": [
            {"task_id": task["task_id"], "attempt": copy.deepcopy(task["attempt"])}
            for task in suite["tasks"]
        ],
    }


def _write_json(path: Path, value: object) -> Path:
    path.write_text(json.dumps(value), encoding="utf-8")
    return path


def test_external_report_preserves_hidden_fields_without_using_strict_scoring(tmp_path: Path) -> None:
    suite = _suite()
    trace = _trace(suite)
    suite_path = _write_json(tmp_path / "suite.json", suite)
    trace_path = _write_json(tmp_path / "trace.json", trace)

    report = score_agent_trace.score_trace(suite_path, trace_path)

    assert report["schema"] == "datapulse/v1/agent-task-suite-report"
    assert report["evaluation_mode"] == "external_semantic"
    assert report["aggregate"]["passed_tasks"] == 14
    injected = score_agent_trace.inject_attempts(suite, trace)
    assert injected["tasks"][0]["prompt"] == suite["tasks"][0]["prompt"]
    assert injected["tasks"][0]["expected"] == suite["tasks"][0]["expected"]
    assert injected["tasks"][0]["workflows"] == suite["tasks"][0]["workflows"]
    assert injected["tasks"][0]["citation_requirements"] == suite["tasks"][0]["citation_requirements"]
    assert injected["tasks"][0]["scoring"] == suite["tasks"][0]["scoring"]


def test_strict_suite_retains_exact_reason_and_workflow_contract() -> None:
    suite = _suite()
    strict_report = agent_task_suite.run_suite(suite)
    changed_reason = copy.deepcopy(suite)
    changed_reason["tasks"][0]["attempt"]["outcome"]["reason"] = "plain explanation"

    assert strict_report["aggregate"]["passed_tasks"] == 14
    assert agent_task_suite.run_suite(changed_reason)["tasks"][0]["scores"]["outcome"] == 0


def test_scoring_a_trace_is_deterministic(tmp_path: Path) -> None:
    suite = _suite()
    suite_path = _write_json(tmp_path / "suite.json", suite)
    trace_path = _write_json(tmp_path / "trace.json", _trace(suite))

    first = score_agent_trace.score_trace(suite_path, trace_path)
    second = score_agent_trace.score_trace(suite_path, trace_path)

    assert json.dumps(first, sort_keys=True, separators=(",", ":")) == json.dumps(
        second, sort_keys=True, separators=(",", ":")
    )


def test_semantic_scoring_accepts_extra_in_order_calls_and_free_text_reason(tmp_path: Path) -> None:
    suite = _suite()
    trace = _trace(suite)
    attempt = trace["tasks"][1]["attempt"]
    attempt["calls"] = ["search_datasets", "verify_dataset", "get_evidence", "get_provenance"]
    attempt["outcome"]["reason"] = "The observed record supports this answer."

    report = score_agent_trace.score_trace(
        _write_json(tmp_path / "suite.json", suite), _write_json(tmp_path / "trace.json", trace)
    )

    result = report["tasks"][1]
    assert result["scores"]["workflow"] == 1
    assert result["scores"]["outcome"] == 1
    assert result["scores"]["efficiency"] == 1


def test_semantic_scoring_separates_over_budget_calls_from_ordered_workflow(tmp_path: Path) -> None:
    suite = _suite()
    trace = _trace(suite)
    attempt = trace["tasks"][1]["attempt"]
    attempt["calls"] = [
        "search_datasets",
        "get_evidence",
        "verify_dataset",
        "get_evidence",
        "get_provenance",
    ]

    report = score_agent_trace.score_trace(
        _write_json(tmp_path / "suite.json", suite), _write_json(tmp_path / "trace.json", trace)
    )

    result = report["tasks"][1]
    assert result["scores"]["workflow"] == 1
    assert result["scores"]["efficiency"] == 0
    assert result["redundant_calls"] == 1


def test_semantic_scoring_rejects_out_of_order_workflow(tmp_path: Path) -> None:
    suite = _suite()
    trace = _trace(suite)
    trace["tasks"][0]["attempt"]["calls"] = ["verify_dataset", "search_datasets", "get_provenance"]

    report = score_agent_trace.score_trace(
        _write_json(tmp_path / "suite.json", suite), _write_json(tmp_path / "trace.json", trace)
    )

    assert report["tasks"][0]["scores"]["workflow"] == 0


def test_semantic_citation_aliases_and_receipt_binding(tmp_path: Path) -> None:
    suite = _suite()
    trace = _trace(suite)
    attempt = trace["tasks"][0]["attempt"]
    attempt["citation"] = {
        "dataset": "fuelprice",
        "source_url": "datapulse://citation/fuelprice",
        "last_checked": "2026-09-06T16:55:00Z",
        "status": "USE",
        "digest": "sha256:discover",
    }

    suite_path = _write_json(tmp_path / "suite.json", suite)
    trace_path = _write_json(tmp_path / "trace.json", trace)
    assert score_agent_trace.score_trace(suite_path, trace_path)["tasks"][0]["scores"]["citation"] == 1

    attempt["citation"]["digest"] = "sha256:mismatch"
    assert score_agent_trace.score_trace(
        suite_path, _write_json(tmp_path / "mismatched-trace.json", trace)
    )["tasks"][0]["scores"]["citation"] == 0


def test_semantic_citation_roles_can_come_from_evidence(tmp_path: Path) -> None:
    suite = _suite()
    trace = _trace(suite)
    attempt = trace["tasks"][0]["attempt"]
    attempt["citation"] = {
        "dataset_id": "fuelprice",
        "evidence_url": "datapulse://citation/fuelprice",
        "receipt_digest": "sha256:discover",
    }
    attempt["evidence"] = {
        "receipt_digest": "sha256:discover",
        "observed_at": "2026-09-06T16:55:00Z",
        "verdict": "USE",
    }

    report = score_agent_trace.score_trace(
        _write_json(tmp_path / "suite.json", suite), _write_json(tmp_path / "trace.json", trace)
    )

    assert report["tasks"][0]["scores"]["citation"] == 1


def test_semantic_scoring_keeps_no_citation_tasks_citation_free(tmp_path: Path) -> None:
    suite = _suite()
    trace = _trace(suite)
    trace["tasks"][7]["attempt"]["citation"] = {"source_url": "datapulse://citation/unneeded"}

    report = score_agent_trace.score_trace(
        _write_json(tmp_path / "suite.json", suite), _write_json(tmp_path / "trace.json", trace)
    )

    assert report["tasks"][7]["scores"]["citation"] == 0


def test_semantic_scoring_fails_closed_when_required_receipt_evidence_is_missing(tmp_path: Path) -> None:
    suite = _suite()
    trace = _trace(suite)
    trace["tasks"][0]["attempt"].pop("evidence")

    report = score_agent_trace.score_trace(
        _write_json(tmp_path / "suite.json", suite), _write_json(tmp_path / "trace.json", trace)
    )

    result = report["tasks"][0]
    assert result["scores"]["citation"] == 0
    assert result["passed"] is False


def test_semantic_scoring_fails_closed_for_an_unrecognised_outcome(tmp_path: Path) -> None:
    suite = _suite()
    trace = _trace(suite)
    trace["tasks"][0]["attempt"]["outcome"]["outcome"] = "invented"

    report = score_agent_trace.score_trace(
        _write_json(tmp_path / "suite.json", suite), _write_json(tmp_path / "trace.json", trace)
    )

    result = report["tasks"][0]
    assert result["scores"]["outcome"] == 0
    assert result["passed"] is False


def test_semantic_scoring_preserves_explicit_unknown_abstention(tmp_path: Path) -> None:
    suite = _suite()

    report = score_agent_trace.score_trace(
        _write_json(tmp_path / "suite.json", suite), _write_json(tmp_path / "trace.json", _trace(suite))
    )

    result = report["tasks"][6]
    assert result["outcome"] == "unknown"
    assert result["action"] == "abstain"
    assert result["passed"] is True


def test_rejects_trace_missing_a_suite_task() -> None:
    suite = _suite()
    trace = _trace(suite)
    trace["tasks"].pop()

    with pytest.raises(ValueError, match="missing"):
        score_agent_trace.inject_attempts(suite, trace)


def test_rejects_duplicate_trace_task_id() -> None:
    suite = _suite()
    trace = _trace(suite)
    trace["tasks"].append(copy.deepcopy(trace["tasks"][0]))

    with pytest.raises(ValueError, match="unique"):
        score_agent_trace.inject_attempts(suite, trace)


def test_rejects_unknown_trace_task_id() -> None:
    suite = _suite()
    trace = _trace(suite)
    trace["tasks"][0]["task_id"] = "not-in-suite"

    with pytest.raises(ValueError, match="unknown"):
        score_agent_trace.inject_attempts(suite, trace)


def test_rejects_malformed_attempt() -> None:
    suite = _suite()
    trace = _trace(suite)
    trace["tasks"][0]["attempt"] = {"calls": ["valid", 2]}

    with pytest.raises(ValueError, match="calls"):
        score_agent_trace.inject_attempts(suite, trace)
