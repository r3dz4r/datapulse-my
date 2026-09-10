"""Regression tests for failure-corpus verification."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "verify_failure_corpus.py"
CORPUS = ROOT / "notes" / "failure-corpus"
HISTORY = ROOT / "health" / "history.jsonl"
SKIP_NO_HISTORY = pytest.mark.skipif(
    not HISTORY.exists() or HISTORY.stat().st_size == 0,
    reason="health/history.jsonl unavailable (CI or freshly cloned worktree)",
)
sys.path.insert(0, str(ROOT / "scripts"))
from verify_failure_corpus import load_history, load_records, verify_records  # noqa: E402


def _run(corpus: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--corpus-dir", str(corpus), "--history-path", str(HISTORY)],
        cwd=ROOT, capture_output=True, text=True, check=False,
    )


def _copy_corpus(tmp_path: Path) -> Path:
    destination = tmp_path / "failure-corpus"
    shutil.copytree(CORPUS, destination)
    return destination


@pytest.fixture(scope="module")
def history() -> list[dict[str, object]]:
    """Load immutable history once; individual cases only alter temporary corpus copies."""
    return load_history(HISTORY)


@SKIP_NO_HISTORY
def test_clean_state_passes() -> None:
    completed = _run(CORPUS)
    assert completed.returncode == 0, completed.stderr


@SKIP_NO_HISTORY
def test_removed_record_fails(tmp_path: Path, history: list[dict[str, object]]) -> None:
    corpus = _copy_corpus(tmp_path)
    (corpus / "bnm-open-api" / "row-date-missing-200.json").unlink()
    errors = verify_records(load_records(corpus), history)
    assert any("required failure records" in error for error in errors)


@SKIP_NO_HISTORY
def test_modified_record_fails(tmp_path: Path, history: list[dict[str, object]]) -> None:
    corpus = _copy_corpus(tmp_path)
    path = corpus / "bnm-open-api" / "schema-shape-hash-churn.json"
    record = json.loads(path.read_text(encoding="utf-8"))
    record["failure_type"] = "http_200_stale_content"
    path.write_text(json.dumps(record), encoding="utf-8")
    errors = verify_records(load_records(corpus), history)
    assert any("unexpected failure_type" in error for error in errors)


@SKIP_NO_HISTORY
def test_lying_about_affected_datasets_fails(tmp_path: Path, history: list[dict[str, object]]) -> None:
    corpus = _copy_corpus(tmp_path)
    path = corpus / "gtfs-api" / "realtime-zero-vehicles-outside-off-peak.json"
    record = json.loads(path.read_text(encoding="utf-8"))
    record["affected_datasets"] = ["synthetic_dataset"]
    path.write_text(json.dumps(record), encoding="utf-8")
    errors = verify_records(load_records(corpus), history)
    assert any("no matching live-history signal" in error for error in errors)


@SKIP_NO_HISTORY
def test_field_missing_fails(tmp_path: Path, history: list[dict[str, object]]) -> None:
    corpus = _copy_corpus(tmp_path)
    path = corpus / "gtfs-api" / "discontinued-line-404.json"
    record = json.loads(path.read_text(encoding="utf-8"))
    del record["severity"]
    path.write_text(json.dumps(record), encoding="utf-8")
    errors = verify_records(load_records(corpus), history)
    assert any("missing required fields" in error for error in errors)


@SKIP_NO_HISTORY
def test_duplicate_observation_key_requires_distinct_cycles(
    tmp_path: Path, history: list[dict[str, object]]
) -> None:
    corpus = _copy_corpus(tmp_path)
    synthetic_history = [
        {
            "dataset_id": "synthetic_dataset",
            "observed_at": "2026-09-02T16:31:05Z",
            "cycle": "2026-09-02T16:30",
        },
        {
            "dataset_id": "synthetic_dataset",
            "observed_at": "2026-09-02T16:31:05Z",
            "cycle": "2026-09-02T16:35",
        },
    ]
    errors = verify_records(load_records(corpus), synthetic_history)
    assert not any("duplicate observation key" in error for error in errors)

    errors = verify_records(load_records(corpus), synthetic_history[:1])
    assert any("duplicate observation key" in error for error in errors)


@SKIP_NO_HISTORY
def test_zero_vehicle_outside_off_peak_requires_successful_observation(
    tmp_path: Path, history: list[dict[str, object]]
) -> None:
    corpus = _copy_corpus(tmp_path)
    record_path = corpus / "gtfs-api" / "realtime-zero-vehicles-outside-off-peak.json"
    record = json.loads(record_path.read_text(encoding="utf-8"))
    record["affected_datasets"] = ["gtfs_realtime_prasarana_bus_kl"]
    record_path.write_text(json.dumps(record), encoding="utf-8")
    synthetic_history = [
        {
            "dataset_id": "gtfs_realtime_prasarana_bus_kl",
            "observed_at": "2026-09-02T16:31:05Z",
            "probe_outcome": "success",
            "record_count": 0,
        }
    ]
    errors = verify_records(load_records(corpus), synthetic_history)
    assert not any("realtime_zero_vehicles_outside_off_peak" in error for error in errors)

    synthetic_history[0]["record_count"] = 1
    errors = verify_records(load_records(corpus), synthetic_history)
    assert any("realtime_zero_vehicles_outside_off_peak" in error for error in errors)
