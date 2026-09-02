"""Contract tests for the hand-authored failure corpus."""

from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CORPUS = ROOT / "notes" / "failure-corpus"
REQUIRED_FIELDS = {
    "schema", "failure_id", "family", "failure_type", "severity",
    "first_observed_at", "most_recent_observed_at", "affected_datasets",
    "evidence", "impact_on_claim_or_decision", "resolution_or_quarantine",
    "rule_or_policy_change", "regression_test", "served_verification",
    "recorded_at", "recorded_by",
}
FAMILIES = {"bnm_open_api", "gtfs_api", "cross-family"}
FAILURE_TYPES = {
    "http_200_stale_content", "schema_shape_hash_churn", "row_date_missing_200",
    "realtime_zero_vehicles_off_peak", "discontinued_line_404",
}


def _records() -> list[dict[str, object]]:
    return [json.loads(path.read_text(encoding="utf-8")) for path in sorted(CORPUS.rglob("*.json"))]


def _parse_iso8601(value: object) -> None:
    assert isinstance(value, str)
    datetime.fromisoformat(value.replace("Z", "+00:00"))


def test_each_failure_record_has_required_fields() -> None:
    records = _records()
    assert len(records) == 7
    for record in records:
        assert REQUIRED_FIELDS <= record.keys()
        assert isinstance(record["affected_datasets"], list)
        evidence = record["evidence"]
        assert isinstance(evidence, dict)
        assert isinstance(evidence["example_history_lines"], list)


def test_family_enum() -> None:
    assert {record["family"] for record in _records()} <= FAMILIES


def test_failure_type_enum() -> None:
    assert {record["failure_type"] for record in _records()} <= FAILURE_TYPES


def test_severity_enum() -> None:
    assert {record["severity"] for record in _records()} <= {"low", "medium", "high"}


def test_dates_parse() -> None:
    for record in _records():
        for key in ("recorded_at", "first_observed_at", "most_recent_observed_at"):
            _parse_iso8601(record[key])
        served = record["served_verification"]
        assert isinstance(served, dict)
        _parse_iso8601(served["last_verified"])


def test_cross_family_corpus_baseline() -> None:
    history = [json.loads(line) for line in (ROOT / "health" / "history.jsonl").read_text().splitlines()]
    latest_at = max(record["observed_at"] for record in history)
    latest = [record for record in history if record["observed_at"] == latest_at]
    actual = 100 * sum(record.get("status") == "stale" and record.get("http_status") == 200 for record in latest) / len(latest)
    cross_family = next(record for record in _records() if record["family"] == "cross-family")
    evidence = cross_family["evidence"]
    assert isinstance(evidence, dict)
    signals = evidence["live_signals"]
    assert isinstance(signals, dict)
    assert abs(actual - float(signals["stale_http_200_pct"])) <= 5
