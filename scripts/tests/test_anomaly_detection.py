"""Deterministic tests for the freshness anomaly annotator."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("gen_anomaly", ROOT / "scripts/gen_anomaly.py")
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def _snapshot(latest: float | None = 3, status: str = "fresh") -> dict:
    return {"checked_at": "2026-08-15T12:00:00Z", "datasets": [{"dataset_id": "x", "status": status, "staleness_days": latest}]}


def _manifest(frequency: str = "daily") -> dict:
    return {"datasets": [{"id": "x", "refresh_frequency": frequency}]}


def _history(tmp_path: Path, values: list[float], *, same_day: bool = False) -> Path:
    rows = []
    for index, value in enumerate(values):
        day = 14 - (0 if same_day else index)
        observed = f"2026-08-{day:02d}T10:00:00Z"
        rows.append({"dataset_id": "x", "observed_at": observed, "probe_outcome": "success", "last_modified": f"2026-08-{day:02d}T10:00:00Z", "content_date": f"2026-08-{day:02d}T10:00:00Z" if value == 0 else None})
        if value:
            rows[-1]["last_modified"] = f"2026-08-{day:02d}T10:00:00Z"
            rows[-1]["observed_at"] = f"2026-08-{day:02d}T10:00:00Z"
    path = tmp_path / "history.jsonl"
    path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
    return path


def test_fallback_is_strictly_above_threshold_and_skips_as_required(tmp_path: Path) -> None:
    history = _history(tmp_path, [])
    equal = MODULE.annotate(_snapshot(2), _manifest(), history)
    above = MODULE.annotate(_snapshot(2.1), _manifest(), history)
    skipped = MODULE.annotate(_snapshot(100), _manifest("as-required"), history)
    assert equal["datasets"][0]["anomaly_detected"] is False
    assert above["datasets"][0]["anomaly_detected"] is True
    assert skipped["datasets"][0]["anomaly_detection"]["mode"] == "not_evaluated"


def test_missing_signal_and_reference_are_not_evaluated(tmp_path: Path) -> None:
    history = _history(tmp_path, [])
    assert MODULE.annotate(_snapshot(None), _manifest(), history)["datasets"][0]["anomaly_detection"]["mode"] == "not_evaluated"
    assert MODULE.annotate(_snapshot(10, "reference"), _manifest(), history)["datasets"][0]["anomaly_detected"] is False


def test_fourteen_prior_days_activate_rolling_and_exclude_current(tmp_path: Path) -> None:
    rows = []
    for day in range(1, 15):
        rows.append({"dataset_id": "x", "observed_at": f"2026-08-{day:02d}T12:00:00Z", "probe_outcome": "success", "last_modified": f"2026-08-{day:02d}T12:00:00Z"})
    rows.append({"dataset_id": "x", "observed_at": "2026-08-15T11:00:00Z", "probe_outcome": "success", "last_modified": "2026-07-01T00:00:00Z"})
    path = tmp_path / "history.jsonl"
    path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
    result = MODULE.annotate(_snapshot(1), _manifest(), path)
    details = result["datasets"][0]["anomaly_detection"]
    assert details["mode"] == "rolling_14d"
    assert details["sample_days"] == 14
    assert details["threshold_days"] == 0
    assert result["datasets"][0]["anomaly_detected"] is True


def test_daily_deduplication_uses_latest_successful_observation(tmp_path: Path) -> None:
    rows = [
        {"dataset_id": "x", "observed_at": "2026-08-14T08:00:00Z", "probe_outcome": "success", "content_date": "2026-08-14"},
        {"dataset_id": "x", "observed_at": "2026-08-14T10:00:00Z", "probe_outcome": "success", "content_date": "2026-08-13"},
    ]
    path = tmp_path / "history.jsonl"
    path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
    values = MODULE.prior_daily_values(path, {"x"}, MODULE.parse_time("2026-08-15T12:00:00Z"))
    assert values["x"] == [1 + 10 / 24]
