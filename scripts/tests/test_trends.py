"""Deterministic tests for per-dataset freshness trends."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
SPEC = importlib.util.spec_from_file_location("gen_trends", ROOT / "scripts/gen_trends.py")
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def _row(dataset_id: str, day: int, staleness: int, **extra: object) -> dict:
    observed_day = 10 + day
    content_day = observed_day - staleness
    return {
        "dataset_id": dataset_id,
        "observed_at": f"2026-08-{observed_day:02d}T12:00:00Z",
        "cycle": f"2026-08-{observed_day:02d}T20:00",
        "status": extra.pop("status", "fresh"),
        "probe_outcome": "success",
        "content_date": f"2026-08-{content_day:02d}T12:00:00Z",
        **extra,
    }


def _history(tmp_path: Path, rows: list[dict]) -> Path:
    path = tmp_path / "history.jsonl"
    path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
    return path


def _manifest() -> dict:
    return {
        "datasets": [
            {"id": "down", "name": "Down", "refresh_frequency": "daily"},
            {"id": "up", "name": "Up", "refresh_frequency": "daily"},
            {"id": "flat", "name": "Flat", "refresh_frequency": "daily"},
            {"id": "short", "name": "Short", "refresh_frequency": "daily"},
        ]
    }


def test_classifies_deteriorating_recovering_stable_and_insufficient(tmp_path: Path) -> None:
    rows = [
        *[_row("down", day, value, status="aging") for day, value in enumerate([2, 3, 4])],
        *[_row("up", day, value) for day, value in enumerate([4, 2, 0])],
        *[_row("flat", day, value) for day, value in enumerate([1, 1, 1])],
        *[_row("short", day, value) for day, value in enumerate([1, 2])],
    ]
    result = MODULE.generate(
        _manifest(), _history(tmp_path, rows), MODULE.parse_time("2026-08-12T12:00:00Z")
    )
    by_id = {row["dataset_id"]: row for row in result["datasets"]}

    assert by_id["down"]["trend"] == "deteriorating"
    assert by_id["down"]["slope_days_per_week"] == 7.0
    assert by_id["up"]["trend"] == "recovering"
    assert by_id["up"]["slope_days_per_week"] == -14.0
    assert by_id["flat"]["trend"] == "stable"
    assert by_id["short"]["trend"] == "insufficient_data"
    assert by_id["short"]["slope_days_per_week"] is None
    assert result["summary"]["by_trend"] == {
        "deteriorating": 1,
        "recovering": 1,
        "stable": 1,
        "insufficient_data": 1,
    }


def test_increasing_but_on_time_is_stable(tmp_path: Path) -> None:
    manifest = {"datasets": [{"id": "monthly", "name": "Monthly", "refresh_frequency": "monthly"}]}
    rows = [_row("monthly", day, value) for day, value in enumerate([2, 3, 4])]
    result = MODULE.generate(
        manifest, _history(tmp_path, rows), MODULE.parse_time("2026-08-12T12:00:00Z")
    )
    row = result["datasets"][0]
    assert row["slope_days_per_day"] == 1.0
    assert row["trend"] == "stable"
    assert "remains on time" in row["reason"]


def test_reliability_grades_and_anomaly_rate(tmp_path: Path) -> None:
    manifest = {"datasets": [{"id": "x", "name": "X", "refresh_frequency": "daily"}]}
    rows = [
        _row("x", 0, 0, anomaly_detected=False),
        _row("x", 1, 1, anomaly_detected=True),
        _row("x", 2, 3),
        _row("x", 3, 4, anomaly_detected=True, status="aging"),
    ]
    result = MODULE.generate(
        manifest, _history(tmp_path, rows), MODULE.parse_time("2026-08-13T12:00:00Z")
    )
    row = result["datasets"][0]
    assert row["publish_on_time_pct"] == 50.0
    assert row["reliability_grade"] == "D"
    assert row["reliability_sample_days"] == 4
    assert row["anomaly_rate_pct"] == 66.7
    assert row["anomaly_sample_days"] == 3
    assert MODULE.reliability_grade(95) == "A"
    assert MODULE.reliability_grade(85) == "B"
    assert MODULE.reliability_grade(70) == "C"
    assert MODULE.reliability_grade(50) == "D"
    assert MODULE.reliability_grade(49.9) == "F"
    assert MODULE.reliability_grade(None) == "insufficient_data"


def test_daily_dedup_uses_latest_successful_evaluable_row(tmp_path: Path) -> None:
    rows = [
        _row("x", 0, 0),
        {**_row("x", 0, 2), "observed_at": "2026-08-10T20:00:00Z"},
        {**_row("x", 1, 2), "probe_outcome": "error"},
    ]
    daily = MODULE.latest_daily_rows(
        _history(tmp_path, rows), generated_at=MODULE.parse_time("2026-08-11T23:00:00Z")
    )
    assert len(daily["x"]) == 1
    assert daily["x"][0]["_staleness_days"] == 2 + 8 / 24


def test_cli_writes_complete_artifact_and_skips_malformed_lines(tmp_path: Path) -> None:
    manifest = tmp_path / "datapulse.json"
    manifest.write_text(
        json.dumps({"datasets": [{"id": "x", "name": "X", "refresh_frequency": "daily"}]}),
        encoding="utf-8",
    )
    history = _history(tmp_path, [_row("x", day, value) for day, value in enumerate([0, 1, 2])])
    with history.open("a", encoding="utf-8") as output:
        output.write("not-json\n")
    destination = tmp_path / "health/trends.json"

    completed = subprocess.run(
        [
            "python3",
            str(ROOT / "scripts/gen_trends.py"),
            "--manifest",
            str(manifest),
            "--history",
            str(history),
            "--output",
            str(destination),
            "--now",
            "2026-08-12T12:00:00Z",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    payload = json.loads(destination.read_text(encoding="utf-8"))
    assert payload["schema"] == "datapulse/v1/dataset-trends"
    assert payload["generated_at"] == "2026-08-12T12:00:00Z"
    assert payload["summary"]["datasets_total"] == 1
