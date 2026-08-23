"""Fixture contracts for deterministic, conservative evidence coverage."""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
import gen_evidence_coverage as coverage
from gen_drift import MIN_RECORD_SAMPLE_DAYS, MIN_RECORD_SPAN_DAYS
from gen_record_evidence import build_record_evidence, write_record_evidence
from gen_trends import MIN_HISTORY_SPAN_DAYS, MIN_SAMPLE_DAYS
NOW = datetime(2026, 8, 24, 12, tzinfo=timezone.utc)


def _write(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value) + "\n", encoding="utf-8")


def _manifest() -> dict[str, object]:
    return {
        "datasets": [
            {"id": "alpha", "name": "Alpha", "refresh_frequency": "daily", "record_evidence_schema": "record-evidence/v1", "url": "https://example.test/alpha"},
            {"id": "beta", "name": "Beta", "refresh_frequency": "daily", "url": "https://example.test/beta"},
            {"id": "gamma", "name": "Gamma", "refresh_frequency": "daily", "record_evidence_schema": "record-evidence/v1", "url": "https://example.test/gamma"},
        ]
    }


def _trend(dataset_id: str, trend: str, samples: int) -> dict[str, object]:
    return {"dataset_id": dataset_id, "trend": trend, "trend_sample_days": samples}


def _drift(dataset_id: str, verdict: str) -> dict[str, object]:
    return {"dataset_id": dataset_id, "verdict": verdict}


def _fixture_inputs(tmp_path: Path) -> dict[str, Path]:
    paths = {
        "manifest": tmp_path / "datapulse.json",
        "trends": tmp_path / "health/trends.json",
        "drift": tmp_path / "health/drift.json",
        "history": tmp_path / "health/history.jsonl",
        "daily": tmp_path / "health/history_daily.json",
        "receipts": tmp_path / "record-evidence",
    }
    _write(paths["manifest"], _manifest())
    _write(paths["trends"], {"schema": "datapulse/v1/dataset-trends", "generated_at": "2026-08-24T12:00:00Z", "datasets": [_trend("alpha", "stable", 4), _trend("beta", "insufficient_data", 1), _trend("gamma", "recovering", 3)]})
    _write(paths["drift"], {"schema": "datapulse/v1/dataset-drift", "generated_at": "2026-08-24T12:00:00Z", "datasets": [_drift("alpha", "stable"), _drift("beta", "insufficient_data"), _drift("gamma", "drift_detected")]})
    paths["history"].parent.mkdir(parents=True, exist_ok=True)
    paths["history"].write_text(
        "\n".join(
            json.dumps({"dataset_id": dataset_id, "observed_at": observed})
            for dataset_id, observed in (
                ("alpha", "2026-08-22T00:00:00Z"),
                ("alpha", "2026-08-23T00:00:00Z"),
                ("beta", "2026-08-23T00:00:00Z"),
            )
        ) + "\n",
        encoding="utf-8",
    )
    _write(paths["daily"], {"schema": "datapulse/v1/health-history-daily", "generated_at": "2026-08-24T12:00:00Z", "retention_days": 7, "compacted_cycles": ["2026-08-20"], "aggregates": [{"dataset_id": "gamma", "latest_observation": {"observed_at": "2026-08-21T00:00:00Z"}}]})
    envelope = build_record_evidence(_manifest()["datasets"][0], b"id,name\n1,Alpha\n", run_date=NOW.date(), observed_at=NOW, source_last_modified=None)
    write_record_evidence(envelope, paths["receipts"])
    return paths


def _generate(paths: dict[str, Path]) -> dict[str, object]:
    return coverage.generate(
        json.loads(paths["manifest"].read_text(encoding="utf-8")),
        trends_path=paths["trends"], drift_path=paths["drift"], history_path=paths["history"],
        daily_path=paths["daily"], receipts_root=paths["receipts"], now=NOW,
    )


def test_complete_fixture_reports_all_four_evidence_families(tmp_path: Path) -> None:
    payload = _generate(_fixture_inputs(tmp_path))

    assert payload["schema"] == "datapulse/v1/evidence-coverage"
    assert payload["generated_at"] == "2026-08-24T12:00:00Z"
    assert payload["dataset_denominator"] == 3
    assert payload["trend_evidence"]["evaluable_datasets"] == 2
    assert payload["trend_evidence"]["insufficient_datasets"] == 1
    assert payload["trend_evidence"]["sample_day_distribution"] == {"1": 1, "3": 1, "4": 1}
    assert payload["drift_evidence"]["evaluable_datasets"] == 2
    assert payload["retained_history"]["raw"]["dataset_day_count"] == 3
    assert payload["retained_history"]["compacted"]["datasets_with_observations"] == 1
    assert payload["record_evidence"]["eligible_manifest_datasets"] == 2
    assert payload["record_evidence"]["datasets_with_valid_latest_receipts"] == 1
    assert payload["record_evidence"]["receipt_count"] == 1
    assert payload["record_evidence"]["coverage_pct"] == 50.0
    assert payload["consistency_checks"]["valid"] is True


def test_zero_legacy_and_malformed_evidence_is_conservative(tmp_path: Path) -> None:
    paths = _fixture_inputs(tmp_path)
    paths["history"].write_text("not-json\n", encoding="utf-8")
    _write(paths["daily"], {"schema": "datapulse/v1/health-history-daily", "retention_days": 7, "compacted_cycles": [], "aggregates": [{"dataset_id": "alpha", "date": "2026-08-20", "record_count": {"mean": 1}}]})
    _write(paths["trends"], {"schema": "wrong", "datasets": []})
    _write(paths["drift"], {"schema": "wrong", "datasets": []})
    (paths["receipts"] / "alpha" / "latest.json").write_text("{broken", encoding="utf-8")
    (paths["receipts"] / "alpha" / "2026-08-24.json").write_text("{broken", encoding="utf-8")
    (paths["receipts"] / "alpha" / "broken.json").write_text("{}", encoding="utf-8")

    payload = _generate(paths)

    assert payload["trend_evidence"]["evaluable_datasets"] == 0
    assert payload["trend_evidence"]["insufficient_datasets"] == 3
    assert payload["drift_evidence"]["evaluable_datasets"] == 0
    assert payload["retained_history"]["raw"] == {"datasets_with_observations": 0, "observation_count": 0, "dataset_day_count": 0}
    assert payload["retained_history"]["compacted"] == {"datasets_with_observations": 0, "observation_count": 0, "dataset_day_count": 0}
    assert payload["record_evidence"]["datasets_with_valid_latest_receipts"] == 0
    assert payload["record_evidence"]["receipt_count"] == 0
    assert payload["record_evidence"]["coverage_pct"] == 0.0


def test_zero_history_daily_aggregates_and_receipts_are_zero_coverage(tmp_path: Path) -> None:
    paths = _fixture_inputs(tmp_path)
    paths["history"].write_text("", encoding="utf-8")
    _write(paths["daily"], {"schema": "datapulse/v1/health-history-daily", "retention_days": 7, "compacted_cycles": [], "aggregates": []})
    for receipt in (paths["receipts"] / "alpha").glob("*.json"):
        receipt.unlink()

    payload = _generate(paths)

    assert payload["retained_history"]["raw"]["observation_count"] == 0
    assert payload["retained_history"]["compacted"]["observation_count"] == 0
    assert payload["record_evidence"] == {
        "eligible_manifest_datasets": 2,
        "datasets_with_valid_latest_receipts": 0,
        "receipt_count": 0,
        "coverage_pct": 0.0,
    }


def test_denominator_thresholds_and_deterministic_cli_output(tmp_path: Path) -> None:
    paths = _fixture_inputs(tmp_path)
    output = tmp_path / "coverage.json"
    command = ["python3", str(ROOT / "scripts/gen_evidence_coverage.py"), "--manifest", str(paths["manifest"]), "--trends", str(paths["trends"]), "--drift", str(paths["drift"]), "--history", str(paths["history"]), "--daily", str(paths["daily"]), "--record-evidence", str(paths["receipts"]), "--output", str(output), "--now", "2026-08-24T12:00:00Z"]

    first = subprocess.run(command, capture_output=True, text=True, check=False)
    assert first.returncode == 0, first.stderr
    first_bytes = output.read_bytes()
    second = subprocess.run(command, capture_output=True, text=True, check=False)
    assert second.returncode == 0, second.stderr
    payload = json.loads(output.read_text(encoding="utf-8"))

    assert output != ROOT / "health/evidence-coverage.json"
    assert output.read_bytes() == first_bytes
    assert payload["trend_evidence"]["requirements"] == {"minimum_sample_days": MIN_SAMPLE_DAYS, "minimum_history_span_days": MIN_HISTORY_SPAN_DAYS}
    assert payload["drift_evidence"]["requirements"]["minimum_record_sample_days"] == MIN_RECORD_SAMPLE_DAYS
    assert payload["drift_evidence"]["requirements"]["minimum_record_span_days"] == MIN_RECORD_SPAN_DAYS
