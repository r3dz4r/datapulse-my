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


def test_audit_flags_an_expectation_above_the_observed_count() -> None:
    # The live shape of dosm_arc_dosm: 316 expected against 309 observed. It is
    # a fixture finding rather than a live one because the observed count grows
    # and clears the finding, while the rule itself must stay pinned.
    manifest = {"dosm_arc_dosm": {"id": "dosm_arc_dosm", "expected_record_count": 316}}
    health = {"dosm_arc_dosm": {"dataset_id": "dosm_arc_dosm", "record_count": 309}}

    audit = build_audit(manifest, health)

    assert audit["expectation_above_observed"] == ["dosm_arc_dosm"]
    assert audit["flagged"] == 0


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


# --- invariants that hold for any health file -------------------------------


# The six facts the probe records. Pinned here rather than imported so the live
# test still guards the six-field contract if the script's own tuple drifts.
_LIVE_FACTS = (
    "newest_date",
    "oldest_date",
    "distinct_dates",
    "rows_per_date",
    "largest_gap_days",
    "dimension_cardinality",
)

# The audit's band labels, plus the bucket a zero/zero row can land in.
_LIVE_BANDS = ("<=50%", "50-60%", "60-80%", "80-90%", ">90%", "undefined")

# The six live rows main's pipeline has populated (measured 2026-09-27). They
# force the classification paths in a copy of the real health file so the live
# test still exercises `open`, `windowed`, and `no_date_column` even while the
# branch's committed health file carries no facts yet.
_MEASURED_FACTS: dict[str, dict] = {
    "exchangerates_daily_0900": {
        "newest_date": "2026-09-25",
        "oldest_date": "2003-05-02",
        "distinct_dates": 5738,
        "rows_per_date": {"min": 2, "mean": 2.9998, "max": 3},
        "largest_gap_days": 7,
        "dimension_cardinality": {"rate_type": 3},
        "record_count": 17213,
    },
    "exchangerates_daily_1130": {
        "newest_date": "2026-09-25",
        "oldest_date": "2003-05-02",
        "distinct_dates": 5726,
        "rows_per_date": {"min": 2, "mean": 2.0, "max": 2},
        "largest_gap_days": 7,
        "dimension_cardinality": {"rate_type": 2},
        "record_count": 11452,
    },
    "exchangerates_daily_1200": {
        "newest_date": "2026-09-25",
        "oldest_date": "1997-01-02",
        "distinct_dates": 7325,
        "rows_per_date": {"min": 1, "mean": 2.5635, "max": 3},
        "largest_gap_days": 7,
        "dimension_cardinality": {"rate_type": 3},
        "record_count": 18778,
    },
    "exchangerates_daily_1700": {
        "newest_date": "2026-09-25",
        "oldest_date": "2003-05-02",
        "distinct_dates": 5749,
        "rows_per_date": {"min": 3, "mean": 3.0, "max": 3},
        "largest_gap_days": 7,
        "dimension_cardinality": {"rate_type": 3},
        "record_count": 17247,
    },
    "bnm_kl_usd_myr": {
        "newest_date": None,
        "oldest_date": None,
        "distinct_dates": 0,
        "rows_per_date": None,
        "largest_gap_days": None,
        "dimension_cardinality": {},
        "record_count": 2,
    },
    "bnm_interbank_swap": {
        "newest_date": None,
        "oldest_date": None,
        "distinct_dates": 0,
        "rows_per_date": None,
        "largest_gap_days": None,
        "dimension_cardinality": {},
        "record_count": 2,
    },
}


def _ids_from(payload: object, key: str) -> set[str]:
    if not isinstance(payload, dict):
        return set()
    rows = payload.get("datasets")
    if not isinstance(rows, list):
        return set()
    return {
        row[key]
        for row in rows
        if isinstance(row, dict) and isinstance(row.get(key), str) and row[key]
    }


def _assert_partition(report: dict, manifest: object, health: object) -> None:
    """Nothing dropped, nothing classified twice, buckets cover the classified set."""
    derivation = report["derivation"]
    manifest_ids = _ids_from(manifest, "id")
    health_ids = _ids_from(health, "dataset_id")
    classified = [entry["dataset_id"] for entry in derivation["datasets"]]
    skipped = [
        item["dataset_id"]
        for item in derivation["skipped"]
        if item["dataset_id"] is not None
    ]

    assert derivation["classified"] == len(classified)
    assert sum(derivation["counts"].values()) == derivation["classified"]
    assert len(classified) == len(set(classified))
    assert len(skipped) == len(set(skipped))
    assert set(classified).isdisjoint(skipped)
    # Every dataset in either input is accounted for exactly once, and a dataset
    # only reaches classification when both inputs carry it.
    assert set(classified) | set(skipped) == manifest_ids | health_ids
    assert set(classified) == manifest_ids & health_ids
    assert derivation["classified"] + len(skipped) == len(manifest_ids | health_ids)
    for dataset_id in manifest_ids:
        appearances = classified.count(dataset_id) + skipped.count(dataset_id)
        assert appearances == 1, f"{dataset_id} appears {appearances} times"


def _assert_absence_implies_unknown(report: dict) -> None:
    """A row with no usable date is `unknown`, and the reason names which kind."""
    for entry in report["derivation"]["datasets"]:
        facts = entry["facts"]
        if all(facts.get(field) is None for field in _LIVE_FACTS):
            assert entry["classification"] == "unknown"
            assert entry["reason"] == "no_facts"
            assert entry["proposed_expected_record_count"] is None
        elif facts.get("newest_date") is None:
            # Some evidence exists but there is no date to read. An empty
            # distinct_dates/dimension_cardinality is present-and-empty
            # evidence, not absence, which is why the reason differs.
            assert entry["classification"] == "unknown"
            assert entry["reason"] == "no_date_column"
            assert entry["proposed_expected_record_count"] is None


def _assert_proposal_bounds(report: dict) -> None:
    """Every proposal sits strictly above half the observed count and at or below it.

    That is the property that lets the served truncation floor (expected * 0.5)
    still fire while leaving room for the 10% retention cushion to matter.
    """
    for entry in report["derivation"]["datasets"]:
        proposed = entry["proposed_expected_record_count"]
        if proposed is None:
            continue
        observed = entry["observed_record_count"]
        assert observed is not None, entry["dataset_id"]
        assert proposed <= observed, (entry["dataset_id"], proposed, observed)
        assert proposed > observed / 2, (entry["dataset_id"], proposed, observed)


def _assert_audit_shape(report: dict) -> None:
    audit = report["audit"]
    audited = [entry["dataset_id"] for entry in audit["datasets"]]
    guard = set(audit["guard_unreachable"])
    above = set(audit["expectation_above_observed"])

    assert audit["audited"] == len(audited)
    assert len(audited) == len(set(audited))
    assert set(audit["bands"]) <= set(_LIVE_BANDS)
    assert sum(audit["bands"].values()) == audit["audited"]
    assert audit["flagged"] == len(guard)
    assert guard <= set(audited)
    assert above <= set(audited)

    by_id = {entry["dataset_id"]: entry for entry in audit["datasets"]}
    for dataset_id in guard:
        required_loss = by_id[dataset_id]["required_loss"]
        assert required_loss is not None, dataset_id
        assert required_loss >= 0.9, (dataset_id, required_loss)
    for dataset_id in above:
        entry = by_id[dataset_id]
        assert entry["expected_record_count"] > entry["observed_record_count"], dataset_id
    # The flag lists and the per-row flags must agree in both directions.
    for entry in audit["datasets"]:
        assert ("guard_unreachable" in entry["flags"]) == (entry["dataset_id"] in guard)
        assert ("expectation_above_observed" in entry["flags"]) == (
            entry["dataset_id"] in above
        )


@pytest.fixture(scope="module")
def real_report(tmp_path_factory: pytest.TempPathFactory) -> dict:
    if not (REAL_MANIFEST.exists() and REAL_HEALTH.exists()):
        pytest.skip("real pipeline artifacts are not present")
    report_path = tmp_path_factory.mktemp("real") / "report.json"
    return _report_of(_run(REAL_MANIFEST, REAL_HEALTH, report=report_path), report_path)


def test_real_files_derivation_is_a_complete_partition(real_report: dict) -> None:
    manifest = json.loads(REAL_MANIFEST.read_text(encoding="utf-8"))
    health = json.loads(REAL_HEALTH.read_text(encoding="utf-8"))
    _assert_partition(real_report, manifest, health)


def test_real_files_absence_implies_unknown(real_report: dict) -> None:
    _assert_absence_implies_unknown(real_report)


def test_real_files_proposals_stay_within_bounds(real_report: dict) -> None:
    _assert_proposal_bounds(real_report)


def test_real_files_audit_shape_is_self_consistent(real_report: dict) -> None:
    _assert_audit_shape(real_report)


def test_real_files_organ_pledges_state_guard_is_unreachable(real_report: dict) -> None:
    # A live membership worth keeping: it needs a 95.2% loss, so it survives any
    # plausible movement. dosm_arc_dosm is deliberately absent here - at 316
    # expected against 309 observed a growing count clears it, so its
    # above-observed case lives in the fixture test instead.
    assert "organ_pledges_state" in real_report["audit"]["guard_unreachable"]


def test_real_files_with_injected_facts_cover_every_classification_path(
    tmp_path: Path,
) -> None:
    if not (REAL_MANIFEST.exists() and REAL_HEALTH.exists()):
        pytest.skip("real pipeline artifacts are not present")

    health = json.loads(REAL_HEALTH.read_text(encoding="utf-8"))
    rows = health["datasets"]
    by_id = {
        row["dataset_id"]: row
        for row in rows
        if isinstance(row, dict) and isinstance(row.get("dataset_id"), str)
    }
    for dataset_id, measured in _MEASURED_FACTS.items():
        row = by_id.get(dataset_id)
        if row is None:
            row = {"dataset_id": dataset_id}
            rows.append(row)
            by_id[dataset_id] = row
        row.update(measured)

    injected = _write(tmp_path / "health.json", health)
    report_path = tmp_path / "report.json"
    report = _report_of(
        _run(REAL_MANIFEST, injected, report=report_path, as_of=AS_OF_TEXT),
        report_path,
    )

    manifest = json.loads(REAL_MANIFEST.read_text(encoding="utf-8"))
    _assert_partition(report, manifest, health)
    _assert_absence_implies_unknown(report)
    _assert_proposal_bounds(report)
    _assert_audit_shape(report)

    expected = {
        "exchangerates_daily_0900": ("open", "open"),
        "exchangerates_daily_1130": ("open", "open"),
        "exchangerates_daily_1200": ("windowed", "windowed_needs_history"),
        "exchangerates_daily_1700": ("open", "open"),
        "bnm_kl_usd_myr": ("unknown", "no_date_column"),
        "bnm_interbank_swap": ("unknown", "no_date_column"),
    }
    by_dataset = {
        entry["dataset_id"]: entry for entry in report["derivation"]["datasets"]
    }
    for dataset_id, (classification, reason) in expected.items():
        entry = by_dataset[dataset_id]
        assert entry["classification"] == classification, dataset_id
        assert entry["reason"] == reason, dataset_id
