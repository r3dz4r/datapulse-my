"""Tests for ``scripts/derive_expectations.py``.

The rules worth guarding hardest are the negative ones: an absent fact must
never be read as zero, a payload with no date column must not be confused with
a row probed before the fact change, and a malformed input must still produce a
valid report. The audit must also flag a guard that can no longer fire without
flagging legitimate oscillation.
"""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import date, timedelta
from pathlib import Path

import pytest

from scripts.derive_expectations import (
    build_audit,
    classify_dataset,
    parse_iso_date,
)

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "derive_expectations.py"
REAL_MANIFEST = ROOT / "datapulse.json"
REAL_HEALTH = ROOT / "health" / "latest.json"

AS_OF = date(2026, 9, 27)
AS_OF_TEXT = AS_OF.isoformat()


# --- fixture helpers --------------------------------------------------------


def _row(
    dataset_id: str,
    *,
    newest: object = None,
    oldest: object = None,
    distinct: object = None,
    rows_per_date: object = None,
    gap: object = None,
    dimension: object = None,
    record_count: object = 100,
) -> dict:
    return {
        "dataset_id": dataset_id,
        "newest_date": newest,
        "oldest_date": oldest,
        "distinct_dates": distinct,
        "rows_per_date": rows_per_date,
        "largest_gap_days": gap,
        "dimension_cardinality": dimension,
        "record_count": record_count,
    }


def _closed_row(dataset_id: str, *, record_count: int, newest: str = "2025-05-31") -> dict:
    return _row(
        dataset_id,
        newest=newest,
        oldest="2020-01-25",
        distinct=1954,
        rows_per_date={"min": 17, "mean": 17.0, "max": 17},
        gap=1,
        dimension={"state": 17},
        record_count=record_count,
    )


def _open_row(dataset_id: str, *, record_count: int, newest: str = "2026-09-24") -> dict:
    return _row(
        dataset_id,
        newest=newest,
        oldest="2017-03-30",
        distinct=480,
        rows_per_date={"min": 1, "mean": 1.998, "max": 2},
        gap=32,
        dimension={"series_type": 2},
        record_count=record_count,
    )


def _windowed_row(dataset_id: str, *, record_count: int, newest: str = "2026-09-24") -> dict:
    return _row(
        dataset_id,
        newest=newest,
        oldest="2020-01-01",
        distinct=50,
        rows_per_date={"min": 1, "mean": 2.4, "max": 5},
        gap=1,
        dimension={"state": 16},
        record_count=record_count,
    )


def _write(path: Path, payload: object) -> Path:
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _write_jsonl(path: Path, rows: list[object]) -> Path:
    path.write_text(
        "\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8"
    )
    return path


def _run(
    manifest: Path,
    health: Path,
    *,
    report: Path | None = None,
    history: Path | None = None,
    as_of: str | None = None,
) -> subprocess.CompletedProcess[str]:
    command = [
        sys.executable,
        str(SCRIPT),
        "--manifest",
        str(manifest),
        "--health",
        str(health),
        "--quiet",
    ]
    if report is not None:
        command += ["--report", str(report)]
    if history is not None:
        command += ["--history", str(history)]
    if as_of is not None:
        command += ["--as-of", as_of]
    return subprocess.run(command, capture_output=True, text=True, check=False)


def _report_of(completed: subprocess.CompletedProcess[str], path: Path) -> dict:
    assert completed.returncode == 0, completed.stderr
    return json.loads(path.read_text(encoding="utf-8"))


# --- date parsing and the fact contract ------------------------------------


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("2026-09-27", date(2026, 9, 27)),
        ("2026-09-27T23:59:59Z", date(2026, 9, 27)),
        ("2026-09-27 08:00:00", date(2026, 9, 27)),
        ("01/08/2026", None),
        ("2026-09", None),
        ("2026-13-01", None),
        ("", None),
        (None, None),
        (20260927, None),
    ],
)
def test_parse_iso_date_never_guesses(value: object, expected: date | None) -> None:
    assert parse_iso_date(value) == expected


def test_no_facts_and_no_date_column_are_different_findings() -> None:
    pre_change = _row("pre_change", record_count=20)
    pre_change_all_null = _row(
        "all_null", distinct=None, rows_per_date=None, dimension=None, record_count=20
    )
    no_date_shape = _row(
        "no_date",
        distinct=0,
        rows_per_date=None,
        dimension={"name": 2},
        record_count=20,
    )
    brief_no_date = _row(
        "brief_no_date",
        distinct=10,
        rows_per_date={"min": 2, "mean": 2.0, "max": 2},
        dimension=None,
        record_count=20,
    )

    for row in (pre_change, pre_change_all_null):
        entry = classify_dataset(row["dataset_id"], row, as_of=AS_OF, history_counts={})
        assert entry["classification"] == "unknown"
        assert entry["reason"] == "no_facts"
        assert entry["proposed_expected_record_count"] is None

    for row in (no_date_shape, brief_no_date):
        entry = classify_dataset(row["dataset_id"], row, as_of=AS_OF, history_counts={})
        assert entry["classification"] == "unknown"
        assert entry["reason"] == "no_date_column"
        assert entry["proposed_expected_record_count"] is None


def test_absent_facts_are_never_read_as_zero() -> None:
    # No newest date at all: the empty rows_per_date must not become a window.
    row = _row("absent", record_count=500)
    entry = classify_dataset("absent", row, as_of=AS_OF, history_counts={})
    assert entry["classification"] == "unknown"
    assert entry["reason"] == "no_facts"
    assert entry["proposed_expected_record_count"] is None

    # A present newest date with an absent rows_per_date stays open, not windowed.
    row = _row("nodim", newest="2026-09-24", record_count=500)
    entry = classify_dataset("nodim", row, as_of=AS_OF, history_counts={})
    assert entry["classification"] == "open"
    assert entry["proposed_expected_record_count"] == 450


# --- classification rules ---------------------------------------------------


def test_closed_series_proposes_the_observed_count() -> None:
    covid = _closed_row("covid_cases", record_count=33218, newest="2025-05-31")
    crop = _closed_row(
        "dosm_crops_district_production", record_count=11002, newest="2017-01-01"
    )

    covid_entry = classify_dataset(
        covid["dataset_id"], covid, as_of=AS_OF, history_counts={}
    )
    crop_entry = classify_dataset(crop["dataset_id"], crop, as_of=AS_OF, history_counts={})

    assert covid_entry["classification"] == "closed"
    assert covid_entry["proposed_expected_record_count"] == 33218
    assert crop_entry["classification"] == "closed"
    assert crop_entry["proposed_expected_record_count"] == 11002


def test_the_180_day_boundary_is_strict() -> None:
    boundary = AS_OF - timedelta(days=180)
    beyond = AS_OF - timedelta(days=181)

    at_boundary = classify_dataset(
        "boundary",
        _closed_row("boundary", record_count=100, newest=boundary.isoformat()),
        as_of=AS_OF,
        history_counts={},
    )
    past_boundary = classify_dataset(
        "past",
        _closed_row("past", record_count=100, newest=beyond.isoformat()),
        as_of=AS_OF,
        history_counts={},
    )

    assert at_boundary["classification"] == "open"
    assert past_boundary["classification"] == "closed"


def test_open_series_retains_a_tenth() -> None:
    fuel = _open_row("fuelprice", record_count=959)
    entry = classify_dataset("fuelprice", fuel, as_of=AS_OF, history_counts={})

    assert entry["classification"] == "open"
    assert entry["proposed_expected_record_count"] == 863  # floor(959 * 0.9)

    tiny = classify_dataset(
        "tiny",
        _open_row("tiny", record_count=1, newest="2026-09-24"),
        as_of=AS_OF,
        history_counts={},
    )
    assert tiny["proposed_expected_record_count"] == 1  # never 0


def test_windowed_without_history_proposes_nothing() -> None:
    entry = classify_dataset(
        "windowed",
        _windowed_row("windowed", record_count=100),
        as_of=AS_OF,
        history_counts={},
    )

    assert entry["classification"] == "windowed"
    assert entry["reason"] == "windowed_needs_history"
    assert entry["proposed_expected_record_count"] is None


def test_windowed_uses_the_minimum_across_history() -> None:
    entry = classify_dataset(
        "windowed",
        _windowed_row("windowed", record_count=100),
        as_of=AS_OF,
        history_counts={"windowed": [40, 12, 30]},
    )

    assert entry["classification"] == "windowed"
    assert entry["reason"] == "windowed_history"
    assert entry["proposed_expected_record_count"] == 12
    assert entry["history_observations"] == 3


def test_oscillation_below_three_x_is_open() -> None:
    row = _open_row("fuelprice", record_count=959)
    entry = classify_dataset("fuelprice", row, as_of=AS_OF, history_counts={})
    assert entry["classification"] == "open"


def test_missing_or_unparseable_observed_is_unknown() -> None:
    missing = _row("missing", newest="2026-09-24", record_count=None)
    missing_entry = classify_dataset(
        "missing", missing, as_of=AS_OF, history_counts={}
    )
    assert missing_entry["classification"] == "unknown"
    assert missing_entry["reason"] == "observed_record_count_missing"
    assert missing_entry["proposed_expected_record_count"] is None

    text_count = _row("text_count", newest="2026-09-24", record_count="100")
    text_entry = classify_dataset(
        "text_count", text_count, as_of=AS_OF, history_counts={}
    )
    assert text_entry["classification"] == "unknown"
    assert text_entry["reason"] == "observed_record_count_not_numeric"
    assert text_entry["proposed_expected_record_count"] is None

    unparseable = _row("bad_date", newest="01/08/2026", record_count=50)
    unparseable_entry = classify_dataset(
        "bad_date", unparseable, as_of=AS_OF, history_counts={}
    )
    assert unparseable_entry["classification"] == "unknown"
    assert unparseable_entry["reason"] == "unparseable_newest_date"
    assert unparseable_entry["proposed_expected_record_count"] is None


# --- the audit --------------------------------------------------------------


def test_audit_computes_required_loss_and_bands() -> None:
    manifest = {
        "equal": {"id": "equal", "expected_record_count": 100},
        "half": {"id": "half", "expected_record_count": 100},
        "boundary_60": {"id": "boundary_60", "expected_record_count": 100},
        "boundary_80": {"id": "boundary_80", "expected_record_count": 100},
        "dead_guard": {"id": "dead_guard", "expected_record_count": 10},
        "ninetieth": {"id": "ninetieth", "expected_record_count": 20},
        "above": {"id": "above", "expected_record_count": 101},
    }
    health = {
        "equal": {"dataset_id": "equal", "record_count": 100},
        "half": {"dataset_id": "half", "record_count": 50},
        "boundary_60": {"dataset_id": "boundary_60", "record_count": 125},
        "boundary_80": {"dataset_id": "boundary_80", "record_count": 250},
        "dead_guard": {"dataset_id": "dead_guard", "record_count": 100},
        "ninetieth": {"dataset_id": "ninetieth", "record_count": 100},
        "above": {"dataset_id": "above", "record_count": 100},
    }

    audit = build_audit(manifest, health)
    by_id = {entry["dataset_id"]: entry for entry in audit["datasets"]}

    assert audit["audited"] == 7
    assert by_id["equal"]["required_loss"] == 0.5
    assert by_id["half"]["required_loss"] == 0.0
    assert by_id["boundary_60"]["band"] == "50-60%"
    assert by_id["boundary_80"]["band"] == "60-80%"
    assert by_id["dead_guard"]["required_loss"] == 0.95
    assert by_id["dead_guard"]["flags"] == ["guard_unreachable"]
    # required_loss exactly 0.90 is still guard_unreachable.
    assert by_id["ninetieth"]["flags"] == ["guard_unreachable"]
    assert by_id["ninetieth"]["band"] == "80-90%"
    assert audit["flagged"] == 2
    assert audit["guard_unreachable"] == ["dead_guard", "ninetieth"]
    # "half" (expected 100 > observed 50) is both a band-<=50% case and above.
    assert audit["expectation_above_observed"] == ["above", "half"]
    assert sum(audit["bands"].values()) == 7


def test_audit_ignores_non_numeric_expected_or_observed() -> None:
    manifest = {
        "no_expected": {"id": "no_expected"},
        "string_expected": {"id": "string_expected", "expected_record_count": "100"},
        "valid": {"id": "valid", "expected_record_count": 100},
    }
    health = {
        "no_expected": {"dataset_id": "no_expected", "record_count": 10},
        "string_expected": {"dataset_id": "string_expected", "record_count": 10},
        "valid": {"dataset_id": "valid", "record_count": 100},
        "absent": {"dataset_id": "absent", "record_count": 5},
    }

    audit = build_audit(manifest, health)

    assert audit["audited"] == 1
    assert [entry["dataset_id"] for entry in audit["datasets"]] == ["valid"]


def test_audit_uses_authored_manifest_value_not_health_copy() -> None:
    manifest = {"ds": {"id": "ds", "expected_record_count": 100}}
    health = {"ds": {"dataset_id": "ds", "expected_record_count": 9999, "record_count": 100}}

    audit = build_audit(manifest, health)

    assert audit["datasets"][0]["expected_record_count"] == 100
    assert audit["datasets"][0]["required_loss"] == 0.5


# --- end to end -------------------------------------------------------------


def test_derivation_skips_datasets_absent_from_either_file(tmp_path: Path) -> None:
    manifest = _write(
        tmp_path / "manifest.json",
        {
            "datasets": [
                {"id": "shared", "expected_record_count": 100},
                {"id": "only_manifest", "expected_record_count": 5},
            ]
        },
    )
    health = _write(
        tmp_path / "health.json",
        {
            "datasets": [
                _open_row("shared", record_count=100),
                _open_row("only_health", record_count=100),
            ]
        },
    )
    report_path = tmp_path / "report.json"

    report = _report_of(_run(manifest, health, report=report_path), report_path)
    skipped = {item["dataset_id"]: item["reason"] for item in report["derivation"]["skipped"]}

    assert skipped == {
        "only_manifest": "absent_from_health",
        "only_health": "absent_from_manifest",
    }
    assert report["derivation"]["classified"] == 1


def test_windowed_history_file_supplies_the_minimum(tmp_path: Path) -> None:
    manifest = _write(
        tmp_path / "manifest.json",
        {"datasets": [{"id": "windowed", "expected_record_count": 50}]},
    )
    health = _write(
        tmp_path / "health.json",
        {"datasets": [_windowed_row("windowed", record_count=100)]},
    )
    history = _write_jsonl(
        tmp_path / "history.jsonl",
        [
            {"dataset_id": "windowed", "record_count": 40},
            {"dataset_id": "windowed", "record_count": 12},
            {"dataset_id": "other", "record_count": 1},
            {"datasets": [{"dataset_id": "windowed", "record_count": 30}]},
        ],
    )
    report_path = tmp_path / "report.json"

    report = _report_of(
        _run(manifest, health, report=report_path, history=history, as_of=AS_OF_TEXT),
        report_path,
    )
    entry = report["derivation"]["datasets"][0]

    assert entry["classification"] == "windowed"
    assert entry["proposed_expected_record_count"] == 12
    assert entry["history_observations"] == 3
    assert report["history"]["observations"] == 4


def test_malformed_inputs_still_emit_a_valid_report(tmp_path: Path) -> None:
    manifest = _write(
        tmp_path / "manifest.json",
        {
            "datasets": [
                None,
                "not a row",
                {"id": "good", "expected_record_count": 100},
                {"id": "bad_type", "expected_record_count": "many"},
            ]
        },
    )
    (tmp_path / "empty.json").write_text("", encoding="utf-8")
    (tmp_path / "broken.json").write_text("{not json", encoding="utf-8")
    health_ok = _write(
        tmp_path / "health.json",
        {
            "datasets": [
                None,
                "not a row",
                _open_row("good", record_count=100),
                {"dataset_id": 42, "record_count": 1},
            ]
        },
    )

    for health in (tmp_path / "empty.json", tmp_path / "broken.json", health_ok):
        report_path = tmp_path / "report.json"
        completed = _run(manifest, health, report=report_path, as_of=AS_OF_TEXT)
        assert completed.returncode == 0, completed.stderr
        report = json.loads(report_path.read_text(encoding="utf-8"))
        assert report["schema"] == "datapulse/v1/expectation-derivation"

    # Empty/broken health cannot classify anything but must not crash.
    report_path = tmp_path / "report-empty.json"
    report = _report_of(
        _run(manifest, tmp_path / "empty.json", report=report_path, as_of=AS_OF_TEXT),
        report_path,
    )
    assert report["derivation"]["classified"] == 0
    assert {item["reason"] for item in report["input_errors"]} >= {"empty"}

    # Malformed rows in either file are skipped with a stated reason.
    report = _report_of(
        _run(manifest, health_ok, report=report_path, as_of=AS_OF_TEXT), report_path
    )
    skipped_reasons = {item["reason"] for item in report["derivation"]["skipped"]}
    assert "malformed_manifest_entry" in skipped_reasons
    assert "malformed_health_row" in skipped_reasons


def test_report_is_deterministic(tmp_path: Path) -> None:
    manifest = _write(
        tmp_path / "manifest.json",
        {
            "datasets": [
                {"id": "open", "expected_record_count": 945},
                {"id": "closed", "expected_record_count": 10000},
                {"id": "windowed", "expected_record_count": 50},
            ]
        },
    )
    health = _write(
        tmp_path / "health.json",
        {
            "datasets": [
                _open_row("open", record_count=959),
                _closed_row("closed", record_count=33218),
                _windowed_row("windowed", record_count=100),
            ]
        },
    )
    history = _write_jsonl(
        tmp_path / "history.jsonl", [{"dataset_id": "windowed", "record_count": 9}]
    )

    first = tmp_path / "first.json"
    second = tmp_path / "second.json"
    for report_path in (first, second):
        completed = _run(
            manifest,
            health,
            report=report_path,
            history=history,
            as_of=AS_OF_TEXT,
        )
        assert completed.returncode == 0

    assert first.read_bytes() == second.read_bytes()


def test_script_never_writes_manifest_or_health(tmp_path: Path) -> None:
    manifest = _write(
        tmp_path / "manifest.json",
        {"datasets": [{"id": "dead", "expected_record_count": 10}]},
    )
    health = _write(
        tmp_path / "health.json",
        {"datasets": [_open_row("dead", record_count=100)]},
    )
    history = _write_jsonl(
        tmp_path / "history.jsonl", [{"dataset_id": "dead", "record_count": 100}]
    )

    before = {
        path: (path.stat().st_mtime_ns, path.read_bytes())
        for path in (manifest, health)
    }
    report_path = tmp_path / "report.json"

    # Every mode: report, gate (no report), history, explicit as-of.
    assert _run(manifest, health, report=report_path, as_of=AS_OF_TEXT).returncode == 0
    assert _run(manifest, health, as_of=AS_OF_TEXT).returncode == 1
    assert (
        _run(
            manifest,
            health,
            report=tmp_path / "report-history.json",
            history=history,
            as_of=AS_OF_TEXT,
        ).returncode
        == 0
    )
    assert _run(manifest, health).returncode == 1

    after = {
        path: (path.stat().st_mtime_ns, path.read_bytes())
        for path in (manifest, health)
    }
    assert after == before


def test_exit_status_is_the_gate_without_a_report(tmp_path: Path) -> None:
    flagged_manifest = _write(
        tmp_path / "flagged.json",
        {"datasets": [{"id": "dead", "expected_record_count": 10}]},
    )
    flagged_health = _write(
        tmp_path / "flagged-health.json",
        {"datasets": [_open_row("dead", record_count=100)]},
    )
    clean_manifest = _write(
        tmp_path / "clean.json",
        {"datasets": [{"id": "ok", "expected_record_count": 100}]},
    )
    clean_health = _write(
        tmp_path / "clean-health.json",
        {"datasets": [_open_row("ok", record_count=100)]},
    )

    assert _run(flagged_manifest, flagged_health, as_of=AS_OF_TEXT).returncode == 1
    assert _run(clean_manifest, clean_health, as_of=AS_OF_TEXT).returncode == 0
    # Report mode always writes and exits 0 so the report can be inspected.
    report_path = tmp_path / "report.json"
    assert (
        _run(flagged_manifest, flagged_health, report=report_path, as_of=AS_OF_TEXT).returncode
        == 0
    )
    assert report_path.exists()


@pytest.mark.skipif(
    not (REAL_MANIFEST.exists() and REAL_HEALTH.exists()),
    reason="real pipeline artifacts are not present",
)
def test_real_files_reproduce_the_committed_audit_shape(tmp_path: Path) -> None:
    report_path = tmp_path / "report.json"

    report = _report_of(
        _run(REAL_MANIFEST, REAL_HEALTH, report=report_path), report_path
    )

    assert report["derivation"]["counts"] == {
        "unknown": 418,
        "closed": 0,
        "windowed": 0,
        "open": 0,
    }
    assert all(
        entry["reason"] == "no_facts"
        for entry in report["derivation"]["datasets"]
    )
    assert report["audit"]["audited"] == 230
    assert report["audit"]["bands"] == {
        "<=50%": 140,
        "50-60%": 77,
        "60-80%": 7,
        "80-90%": 5,
        ">90%": 1,
    }
    assert report["audit"]["flagged"] == 1
    assert report["audit"]["guard_unreachable"] == ["organ_pledges_state"]
    # The brief's "one flagged dataset" counts dead guards. This second,
    # distinct finding is dosm_arc_dosm (expected 316 > observed 309).
    assert report["audit"]["expectation_above_observed"] == ["dosm_arc_dosm"]
