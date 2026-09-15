"""Regression tests for failure-corpus verification."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "verify_failure_corpus.py"
CORPUS = ROOT / "notes" / "failure-corpus"
HISTORY = ROOT / "health" / "history.jsonl"
# Reviewer override: force either history mode on a machine that has the live
# health/history.jsonl, without the tests ever moving, renaming, or writing that file.
# A readable non-empty path wins; a missing or empty path forces corpus-derived mode.
OVERRIDE_ENV = "DATAPULSE_CORPUS_HISTORY"
sys.path.insert(0, str(ROOT / "scripts"))
from verify_failure_corpus import load_history, load_records, verify_records  # noqa: E402


def _usable_history(path: Path) -> bool:
    """Return whether a history file on disk can anchor verification."""
    return path.exists() and path.stat().st_size > 0


def _derived_history() -> list[dict[str, object]]:
    """Project the corpus's own evidence into the history rows the verifier reads.

    Why this exists: CI and fresh clones carry no health/history.jsonl, and this
    file used to skip wholesale in exactly that state -- which is how the
    fabricated-dataset-id regression (PR #68) stayed invisible to the gate for
    as long as it existed. The corpus is the only history a fresh clone has, so
    it stands in for the estate. This is a projection, not a probe.

    The corpus carries evidence excerpts, not a timeline, so every example row
    is re-anchored to one synthetic instant derived from the corpus itself (the
    latest most_recent_observed_at any record claims). All other fields stay
    verbatim, and cycle labels keep their original values because the
    duplicate-key check needs distinctness, not timing.

    Datasets named in affected_datasets but exemplified nowhere in the corpus
    get a bare existence row (dataset_id + observed_at only, one second before
    the anchor). Existence rows deliberately carry no status/outcome fields: they
    can never satisfy a signal predicate, only _known_dataset -- the corpus
    attests that the dataset belongs to the estate, nothing more. A fabricated
    id such as synthetic_dataset appears nowhere and still fails verification,
    which is the lie-detection these tests exist to keep.
    """
    records = load_records(CORPUS)
    observed = [
        datetime.fromisoformat(record["most_recent_observed_at"].replace("Z", "+00:00"))
        for record in records
        if isinstance(record.get("most_recent_observed_at"), str)
    ]
    anchor = max(observed)
    anchor_iso = anchor.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    existence_iso = (anchor - timedelta(seconds=1)).astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    # First pass collects every dataset the corpus exemplifies, so an existence row
    # is emitted only for ids exemplified by no record at all, regardless of file order.
    exemplified: set[str] = set()
    example_rows: list[dict[str, object]] = []
    for record in records:
        evidence = record.get("evidence")
        lines = evidence.get("example_history_lines", []) if isinstance(evidence, dict) else []
        for line in lines:
            if isinstance(line, dict) and isinstance(line.get("dataset_id"), str):
                exemplified.add(line["dataset_id"])
                row = dict(line)
                row["observed_at"] = anchor_iso
                example_rows.append(row)

    rows: list[dict[str, object]] = []
    seen: set[str] = set()

    def _add(row: dict[str, object]) -> None:
        key = json.dumps(row, sort_keys=True)
        if key not in seen:
            seen.add(key)
            rows.append(row)

    for row in example_rows:
        _add(row)
    for record in records:
        affected = record.get("affected_datasets")
        for dataset_id in affected if isinstance(affected, list) else []:
            if isinstance(dataset_id, str) and dataset_id not in exemplified:
                _add({"dataset_id": dataset_id, "observed_at": existence_iso})
    return rows


def _resolve_history() -> tuple[str, Path | None, list[dict[str, object]]]:
    """Pick the history source once so every test sees the same rows."""
    override = os.environ.get(OVERRIDE_ENV)
    if override is not None:
        override_path = Path(override)
        if _usable_history(override_path):
            return f"{OVERRIDE_ENV}={override}", override_path, load_history(override_path)
        return f"corpus-derived example lines ({OVERRIDE_ENV}={override} missing or empty)", None, _derived_history()
    if _usable_history(HISTORY):
        return "health/history.jsonl", HISTORY, load_history(HISTORY)
    return "corpus-derived example lines (health/history.jsonl unavailable)", None, _derived_history()


HISTORY_SOURCE, HISTORY_PATH, HISTORY_ROWS = _resolve_history()
# Loud on purpose: a run's reader (and the CI log) must never mistake derived
# history for real probe history. pytest surfaces captured stdout on failure.
print(f"verify-failure-corpus: history source = {HISTORY_SOURCE} ({len(HISTORY_ROWS)} rows)")


def _run(corpus: Path, history_path: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--corpus-dir", str(corpus), "--history-path", str(history_path)],
        cwd=ROOT, capture_output=True, text=True, check=False,
    )


def _copy_corpus(tmp_path: Path) -> Path:
    destination = tmp_path / "failure-corpus"
    shutil.copytree(CORPUS, destination)
    return destination


@pytest.fixture(scope="module")
def history() -> list[dict[str, object]]:
    """Load the resolved history once; individual cases only alter temporary corpus copies."""
    return HISTORY_ROWS


def test_clean_state_passes(tmp_path: Path) -> None:
    history_path = HISTORY_PATH
    if history_path is None:
        # The CLI needs a real file, so derived mode writes its rows into tmp_path;
        # the live health/history.jsonl is never created, moved, or written by tests.
        history_path = tmp_path / "corpus-derived-history.jsonl"
        history_path.write_text("".join(json.dumps(row) + "\n" for row in HISTORY_ROWS), encoding="utf-8")
    completed = _run(CORPUS, history_path)
    assert completed.returncode == 0, completed.stderr


def test_removed_record_fails(tmp_path: Path, history: list[dict[str, object]]) -> None:
    corpus = _copy_corpus(tmp_path)
    (corpus / "bnm-open-api" / "row-date-missing-200.json").unlink()
    errors = verify_records(load_records(corpus), history)
    assert any("required failure records" in error for error in errors)


def test_modified_record_fails(tmp_path: Path, history: list[dict[str, object]]) -> None:
    corpus = _copy_corpus(tmp_path)
    path = corpus / "bnm-open-api" / "schema-shape-hash-churn.json"
    record = json.loads(path.read_text(encoding="utf-8"))
    record["failure_type"] = "http_200_stale_content"
    path.write_text(json.dumps(record), encoding="utf-8")
    errors = verify_records(load_records(corpus), history)
    assert any("unexpected failure_type" in error for error in errors)


def test_lying_about_affected_datasets_fails(tmp_path: Path, history: list[dict[str, object]]) -> None:
    corpus = _copy_corpus(tmp_path)
    path = corpus / "gtfs-api" / "realtime-zero-vehicles-outside-off-peak.json"
    record = json.loads(path.read_text(encoding="utf-8"))
    record["affected_datasets"] = ["synthetic_dataset"]
    path.write_text(json.dumps(record), encoding="utf-8")
    errors = verify_records(load_records(corpus), history)
    assert any("no matching live-history signal" in error for error in errors)


def test_field_missing_fails(tmp_path: Path, history: list[dict[str, object]]) -> None:
    corpus = _copy_corpus(tmp_path)
    path = corpus / "gtfs-api" / "discontinued-line-404.json"
    record = json.loads(path.read_text(encoding="utf-8"))
    del record["severity"]
    path.write_text(json.dumps(record), encoding="utf-8")
    errors = verify_records(load_records(corpus), history)
    assert any("missing required fields" in error for error in errors)


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
