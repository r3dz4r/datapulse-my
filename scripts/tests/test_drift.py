"""Deterministic tests for schema and record-count drift generation."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
SPEC = importlib.util.spec_from_file_location("gen_drift", ROOT / "scripts/gen_drift.py")
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def _row(dataset_id: str, day: int, **extra: object) -> dict:
    return {"dataset_id": dataset_id, "observed_at": f"2026-08-{day:02d}T12:00:00Z", "cycle": f"2026-08-{day:02d}T20:00", "probe_outcome": "success", **extra}


def _history(tmp_path: Path, rows: list[dict]) -> Path:
    path = tmp_path / "history.jsonl"
    path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
    return path


def _daily(tmp_path: Path, aggregates: list[dict]) -> Path:
    path = tmp_path / "history_daily.json"
    path.write_text(json.dumps({"schema": "datapulse/v1/health-history-daily", "aggregates": aggregates}), encoding="utf-8")
    return path


def _daily_observation(dataset_id: str, day: int, **fields: object) -> dict:
    return {"dataset_id": dataset_id, "date": f"2026-08-{day:02d}", "latest_observation": {"observed_at": f"2026-08-{day:02d}T12:00:00Z", "probe_outcome": "success", **fields}, "latest_successful_observation": {"observed_at": f"2026-08-{day:02d}T12:00:00Z", "probe_outcome": "success", **fields}}


def _manifest() -> dict:
    return {"datasets": [{"id": "shape", "name": "Shape"}, {"id": "record", "name": "Record", "expected_record_count": 100}, {"id": "stable", "name": "Stable"}, {"id": "short", "name": "Short"}]}


def _latest() -> dict:
    return {"checked_at": "2026-08-12T12:00:00Z", "datasets": [{"dataset_id": "shape", "record_count": 110, "column_count": 3, "content_shape_changed": False}, {"dataset_id": "record", "record_count": 40, "column_count": 2, "content_shape_changed": False}, {"dataset_id": "stable", "record_count": 103, "column_count": 4, "content_shape_changed": False}, {"dataset_id": "short", "record_count": None, "column_count": None, "content_shape_changed": False}]}


def test_classifies_shape_record_stable_and_insufficient(tmp_path: Path) -> None:
    rows = [_row("shape", 10, shape_hash="shape-v1:a", column_count=2, record_count=100), _row("shape", 11, shape_hash="shape-v1:b", column_count=3, record_count=110), _row("record", 10, shape_hash="shape-v1:r", column_count=2, record_count=100), _row("record", 12, shape_hash="shape-v1:r", column_count=2, record_count=40), _row("stable", 10, shape_hash="shape-v1:s", column_count=4, record_count=100), _row("stable", 12, shape_hash="shape-v1:s", column_count=4, record_count=103), _row("short", 12)]
    result = MODULE.generate(_manifest(), _history(tmp_path, rows), _latest())
    by_id = {row["dataset_id"]: row for row in result["datasets"]}
    assert by_id["shape"]["verdict"] == "drift_detected"
    assert by_id["shape"]["shape_change_count"] == 1
    assert by_id["shape"]["column_count_changed"] is True
    assert by_id["shape"]["record_trend"] == "growing"
    assert by_id["record"]["verdict"] == "record_count_drift"
    assert by_id["record"]["record_count_within_tolerance"] is False
    assert by_id["record"]["record_trend"] == "shrinking"
    assert by_id["record"]["record_change_pct"] == -60.0
    assert by_id["stable"]["verdict"] == "stable"
    assert by_id["short"]["verdict"] == "insufficient_data"


def test_missing_expectation_is_not_record_count_drift(tmp_path: Path) -> None:
    manifest = {"datasets": [{"id": "x", "name": "X"}]}
    latest = {"checked_at": "2026-08-12T12:00:00Z", "datasets": [{"dataset_id": "x", "record_count": 1, "record_count_within_tolerance": False}]}
    result = MODULE.generate(manifest, _history(tmp_path, [_row("x", 10, shape_hash="shape-v1:x", record_count=1), _row("x", 12, shape_hash="shape-v1:x", record_count=1)]), latest)["datasets"][0]
    assert result["verdict"] == "stable"
    assert result["record_count_within_tolerance"] is None


def test_pre_window_baseline_counts_first_in_window_change(tmp_path: Path) -> None:
    manifest = {"datasets": [{"id": "x", "name": "X"}]}
    latest = {"checked_at": "2026-08-31T12:00:00Z", "datasets": [{"dataset_id": "x", "content_shape_changed": False}]}
    rows = [{**_row("x", 2, shape_hash="shape-v1:old"), "observed_at": "2026-07-01T12:00:00Z", "cycle": "2026-07-01T20:00"}, _row("x", 2, shape_hash="shape-v1:new")]
    result = MODULE.generate(manifest, _history(tmp_path, rows), latest)["datasets"][0]
    assert result["shape_change_count"] == 1
    assert result["last_shape_change_at"] == "2026-08-02T12:00:00Z"


def test_daily_structural_boundary_change_and_legacy_absence(tmp_path: Path) -> None:
    manifest = {"datasets": [{"id": "x", "name": "X"}, {"id": "legacy", "name": "Legacy"}]}
    latest = {"checked_at": "2026-08-12T12:00:00Z", "datasets": [{"dataset_id": "x", "content_shape_changed": False}, {"dataset_id": "legacy", "content_shape_changed": False}]}
    history = _history(tmp_path, [_row("x", 12, shape_hash="shape-v1:new", column_count=3)])
    _daily(tmp_path, [
        _daily_observation("x", 10, shape_hash="shape-v1:old", column_count=2, record_count=100),
        {"dataset_id": "legacy", "date": "2026-08-10", "record_count": {"mean": 100}},
    ])
    by_id = {row["dataset_id"]: row for row in MODULE.generate(manifest, history, latest)["datasets"]}
    assert by_id["x"]["verdict"] == "drift_detected"
    assert by_id["x"]["shape_change_count"] == 1
    assert by_id["legacy"]["verdict"] == "insufficient_data"


def test_daily_record_count_evidence_contributes_to_trend(tmp_path: Path) -> None:
    manifest = {"datasets": [{"id": "x", "name": "X", "expected_record_count": 100}]}
    latest = {"checked_at": "2026-08-12T12:00:00Z", "datasets": [{"dataset_id": "x", "record_count": 40}]}
    history = _history(tmp_path, [_row("x", 12, record_count=40)])
    _daily(tmp_path, [_daily_observation("x", 10, record_count=100)])

    result = MODULE.generate(manifest, history, latest)["datasets"][0]

    assert result["verdict"] == "record_count_drift"
    assert result["record_trend"] == "shrinking"
    assert result["record_sample_days"] == 2


def test_raw_history_takes_precedence_over_daily_overlap(tmp_path: Path) -> None:
    manifest = {"datasets": [{"id": "x", "name": "X"}]}
    latest = {"checked_at": "2026-08-12T12:00:00Z", "datasets": [{"dataset_id": "x"}]}
    history = _history(tmp_path, [_row("x", 12, shape_hash="shape-v1:new")])
    _daily(tmp_path, [_daily_observation("x", 12, shape_hash="shape-v1:old")])

    result = MODULE.generate(manifest, history, latest)["datasets"][0]

    assert result["verdict"] == "insufficient_data"
    assert result["shape_sample_count"] == 1


def test_cli_writes_complete_artifact_and_skips_malformed_lines(tmp_path: Path) -> None:
    manifest = tmp_path / "datapulse.json"
    manifest.write_text(json.dumps({"datasets": [{"id": "x", "name": "X"}]}), encoding="utf-8")
    latest = tmp_path / "latest.json"
    latest.write_text(json.dumps({"checked_at": "2026-08-12T12:00:00Z", "datasets": [{"dataset_id": "x"}]}), encoding="utf-8")
    history = _history(tmp_path, [_row("x", 12, shape_hash="shape-v1:x")])
    history.open("a", encoding="utf-8").write("not-json\n")
    destination = tmp_path / "health/drift.json"
    completed = subprocess.run(["python3", str(ROOT / "scripts/gen_drift.py"), "--manifest", str(manifest), "--history", str(history), "--latest", str(latest), "--output", str(destination)], capture_output=True, text=True, check=False)
    assert completed.returncode == 0, completed.stderr
    payload = json.loads(destination.read_text(encoding="utf-8"))
    assert payload["schema"] == "datapulse/v1/dataset-drift"
    assert payload["summary"]["datasets_total"] == 1
    first = destination.read_bytes()
    second = subprocess.run(completed.args, capture_output=True, text=True, check=False)
    assert second.returncode == 0, second.stderr
    assert destination.read_bytes() == first
