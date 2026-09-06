"""Deterministic answerability coverage for local citation evidence candidates."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from fastmcp import Client
import pytest


MCP_DIR = Path(__file__).resolve().parents[1]
FIXTURE_PATH = Path(__file__).with_name("fixtures") / "answerability_cases.json"
sys.path.insert(0, str(MCP_DIR))

import answerability_benchmark  # noqa: E402
import server  # noqa: E402


def _fixture() -> dict[str, object]:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def test_fixture_cases_match_the_local_evidence_policy() -> None:
    fixture = _fixture()

    for case in fixture["cases"]:
        assert isinstance(case, dict)
        result = answerability_benchmark.evaluate_candidate(case)
        assert result == {**case["expected"], "category": case["category"]}


def test_fixture_report_is_byte_stable() -> None:
    first = answerability_benchmark.run_benchmark(FIXTURE_PATH)
    second = answerability_benchmark.run_benchmark(FIXTURE_PATH)

    assert json.dumps(first, sort_keys=True, separators=(",", ":")) == json.dumps(
        second, sort_keys=True, separators=(",", ":")
    )


def test_fresh_and_stale_evidence_conflict_before_a_fresh_answer() -> None:
    result = answerability_benchmark.evaluate_candidate(
        {
            "category": "conflicting_evidence",
            "request": {"dataset_id": "fuelprice", "scope": "latest price"},
            "evidence": [
                {"dataset_id": "fuelprice", "status": "fresh"},
                {"dataset_id": "fuelprice", "status": "stale"},
            ],
        }
    )

    assert result["action"] == "abstain"
    assert result["reason"] == "conflicting_evidence"


def test_missing_dataset_identity_abstains_even_with_fresh_evidence() -> None:
    result = answerability_benchmark.evaluate_candidate(
        {
            "category": "underspecified",
            "request": {"scope": "latest price"},
            "evidence": [{"dataset_id": "fuelprice", "status": "fresh"}],
        }
    )

    assert result["action"] == "abstain"
    assert result["reason"] == "underspecified"


@pytest.mark.parametrize(
    "status", ["stale", "discontinued", "degraded", "browser-dependent", "unreachable", "unknown"]
)
def test_each_unsafe_status_abstains(status: str) -> None:
    result = answerability_benchmark.evaluate_candidate(
        {
            "category": "unsafe_status",
            "request": {"dataset_id": "fuelprice", "scope": "latest price"},
            "evidence": [{"dataset_id": "fuelprice", "status": status}],
        }
    )

    assert result["action"] == "abstain"
    assert result["reason"] == "unsafe_evidence"


@pytest.mark.parametrize("status", ["aging", "unknown-freshness"])
def test_each_uncertain_freshness_status_warns(status: str) -> None:
    result = answerability_benchmark.evaluate_candidate(
        {
            "category": "uncertain_freshness",
            "request": {"dataset_id": "fuelprice", "scope": "latest price"},
            "evidence": [{"dataset_id": "fuelprice", "status": status}],
        }
    )

    assert result["action"] == "warn"
    assert result["reason"] == "uncertain_freshness"


@pytest.mark.anyio
async def test_importing_the_benchmark_does_not_change_mcp_discovery_surface() -> None:
    async with Client(server.mcp) as client:
        tools = await client.list_tools_mcp()
        resources = await client.list_resources_mcp()

    assert len(tools.tools) == 18
    assert len(resources.resources) == 8
