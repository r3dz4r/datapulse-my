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


def _case(name: str) -> dict[str, object]:
    for case in _fixture()["cases"]:
        if isinstance(case, dict) and case.get("name") == name:
            return case
    raise AssertionError(f"Missing fixture case: {name}")


def _evaluate_case(name: str) -> dict[str, object]:
    return answerability_benchmark.evaluate_candidate(_case(name))


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


def test_as_of_current_fresh() -> None:
    result = _evaluate_case("as_of_current_fresh")

    assert result["action"] == "answer"
    assert result["reason"] == "supported_evidence"


def test_as_of_historical_valid_is_visibly_historical() -> None:
    result = _evaluate_case("as_of_historical_valid")

    assert result["action"] == "answer"
    assert result["reason"] == "historical_evidence"
    assert result["historical"] is True
    assert result["observed_at"] == "2026-08-30T17:15:00Z"


def test_as_of_before_first_observation_abstains() -> None:
    result = _evaluate_case("as_of_before_first_observation")

    assert result["action"] == "abstain"
    assert result["reason"] == "no_supported_record"


def test_stale_presented_as_current_abstains() -> None:
    result = _evaluate_case("stale_presented_as_current")

    assert result["action"] == "abstain"
    assert result["reason"] == "unsafe_evidence"


def test_superseded_stale_selection_abstains() -> None:
    result = _evaluate_case("superseded_stale_selection")

    assert result["action"] == "abstain"
    assert result["reason"] == "conflicting_evidence"


def test_temporal_reference_only_warns() -> None:
    result = _evaluate_case("temporal_reference_only")

    assert result["action"] == "warn"
    assert result["reason"] == "reference_only"


def test_temporal_uncertain_warns() -> None:
    result = _evaluate_case("temporal_uncertain")

    assert result["action"] == "warn"
    assert result["reason"] == "uncertain_freshness"


def test_future_as_of_date_uses_latest_evidence_without_future_claim() -> None:
    result = _evaluate_case("future_as_of_date")

    assert result["action"] == "answer"
    assert result["reason"] == "supported_evidence"
    assert result["as_of_beyond_latest"] is True


def _assert_claim_case(name: str, verdict: str, action: str, reason: str) -> None:
    result = _evaluate_case(name)

    assert result["claim_verdict"] == verdict
    assert result["action"] == action
    assert result["reason"] == reason


def test_claim_supported_use() -> None:
    _assert_claim_case("claim_supported_use", "supported", "answer", "supported_claim")


def test_claim_partial_warn() -> None:
    _assert_claim_case("claim_partial_warn", "partial", "warn", "partial_claim")


def test_claim_unsupported_stop() -> None:
    _assert_claim_case("claim_unsupported_stop", "unsupported", "abstain", "unsupported_claim")


def test_claim_semantic_truth_blocked() -> None:
    _assert_claim_case("claim_semantic_truth_blocked", "unsupported", "abstain", "outside_evidence_scope")


def test_claim_licence_supported() -> None:
    _assert_claim_case("claim_licence_supported", "supported", "answer", "supported_claim")


def test_claim_licence_unobserved() -> None:
    _assert_claim_case("claim_licence_unobserved", "unknown", "abstain", "licence_unobserved")


def test_claim_malformed_citation() -> None:
    _assert_claim_case("claim_malformed_citation", "unknown", "abstain", "malformed_citation")


def test_claim_unclassified_type() -> None:
    _assert_claim_case("claim_unclassified_type", "unknown", "abstain", "unclassified_claim")


def test_claim_overclaim_degrade() -> None:
    _assert_claim_case("claim_overclaim_degrade", "partial", "warn", "overclaim")


def test_semantic_truth_precedes_a_use_citation() -> None:
    result = answerability_benchmark.evaluate_claim(
        {
            "category": "claim_support",
            "claim": "The data is accurate.",
            "claim_type": "semantic_truth",
            "citation": {"dataset_id": "fuelprice", "datapulse_verdict": "USE"},
        }
    )

    assert result["claim_verdict"] == "unsupported"
    assert result["action"] == "abstain"
    assert result["reason"] == "outside_evidence_scope"


def test_overclaim_degrades_exactly_one_verdict_level() -> None:
    result = answerability_benchmark.evaluate_claim(
        {
            "category": "claim_support",
            "claim": "The authoritative fuel price dataset was reachable.",
            "claim_type": "availability_observed",
            "asserted": {"observed_at": "2026-09-06T16:55:00Z"},
            "citation": {
                "dataset_id": "fuelprice",
                "observed_at": "2026-09-06T16:55:00Z",
                "datapulse_verdict": "USE",
            },
        }
    )

    assert result["claim_verdict"] == "partial"
    assert result["action"] == "warn"
    assert result["reason"] == "overclaim"


def test_stale_only_as_of_date_still_abstains_before_temporal_verdict() -> None:
    result = answerability_benchmark.evaluate_candidate(
        {
            "category": "temporal_precedence",
            "request": {"dataset_id": "currency_in_circulation", "scope": "circulation", "as_of_date": "2026-09-07"},
            "evidence": [{"dataset_id": "currency_in_circulation", "status": "stale", "observed_at": "2026-09-06T16:55:00Z"}],
        }
    )

    assert result["action"] == "abstain"
    assert result["reason"] == "unsafe_evidence"


def test_explicit_superseded_stale_selection_conflicts_with_newer_fresh_evidence() -> None:
    result = answerability_benchmark.evaluate_candidate(
        {
            "category": "temporal_precedence",
            "request": {
                "dataset_id": "dgm_payments_transactions_fpx",
                "scope": "payment transactions",
                "selected_observed_at": "2026-08-30T17:15:00Z",
            },
            "evidence": [
                {"dataset_id": "dgm_payments_transactions_fpx", "status": "stale", "observed_at": "2026-08-30T17:15:00Z"},
                {"dataset_id": "dgm_payments_transactions_fpx", "status": "fresh", "observed_at": "2026-09-06T16:55:00Z"},
            ],
        }
    )

    assert result["action"] == "abstain"
    assert result["reason"] == "conflicting_evidence"


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
