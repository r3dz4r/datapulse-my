#!/usr/bin/env python3
"""Tests for scripts/gtfs_fleet_availability.py over self-written fixtures."""

from __future__ import annotations

import io
import json
from pathlib import Path
from typing import Any

from scripts import gtfs_fleet_availability as fa


def _row(dataset_id: str, cycle: str, count: Any, estimated: bool = False) -> dict[str, Any]:
    return {
        "dataset_id": dataset_id,
        "observed_at": f"{cycle}:07Z" if isinstance(cycle, str) else "2026-11-12T00:00:07Z",
        "cycle": cycle,
        "status": "fresh",
        "freshness_signal": "gtfs-realtime-header",
        "last_modified": None,
        "content_date": None,
        "record_count": count,
        "record_count_estimated": estimated,
        "http_status": 200,
    }


def _write(tmp_path: Path, rows: list[Any], name: str = "history.jsonl") -> Path:
    path = tmp_path / name
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(row if isinstance(row, str) else json.dumps(row))
            handle.write("\n")
    return path


def _run(path: Path, *extra: str) -> tuple[int, str]:
    out = io.StringIO()
    code = fa.main(["--history", str(path), *extra], stdout=out)
    return code, out.getvalue()


def _report(path: Path, *extra: str) -> dict[str, Any]:
    code, text = _run(path, *extra)
    assert code == 0
    return json.loads(text)


def test_bucket_median_ignores_estimated_rows(tmp_path: Path) -> None:
    ds = "gtfs_realtime_mybas_johor"
    path = _write(tmp_path, [
        _row(ds, "2026-11-12T03:00", 10),
        _row(ds, "2026-11-12T03:05", 20),
        _row(ds, "2026-11-12T03:10", 30),
        _row(ds, "2026-11-12T03:15", 9000, estimated=True),
        _row(ds, "2026-11-12T03:20", 9001, estimated=True),
    ])
    report = _report(path)
    assert report["schema"] == "datapulse/v1/gtfs-fleet-availability"
    [bucket] = report["buckets"]
    assert (bucket["date"], bucket["hour"]) == ("2026-11-12", 3)
    assert bucket["cycles"] == 5
    assert bucket["estimated_cycles"] == 2
    assert (bucket["vehicles_min"], bucket["vehicles_median"], bucket["vehicles_max"]) == (10, 20, 30)
    assert all(isinstance(bucket[k], int) for k in ("vehicles_min", "vehicles_median", "vehicles_max"))


def test_zero_vehicle_run_across_three_consecutive_cycles(tmp_path: Path) -> None:
    ds = "gtfs_realtime_ktmb"
    # Deliberately out of order on disk: runs are ordered by cycle, not line.
    path = _write(tmp_path, [
        _row(ds, "2026-11-12T00:55", 0),
        _row(ds, "2026-11-12T00:50", 5),
        _row(ds, "2026-11-12T01:00", 0),
        _row(ds, "2026-11-12T01:05", 0),
        _row(ds, "2026-11-12T01:10", 4),
        _row(ds, "2026-11-12T01:15", 0),
    ])
    report = _report(path)
    assert report["zero_vehicle_runs"] == [
        {"operator": "ktmb", "start_cycle": "2026-11-12T00:55", "end_cycle": "2026-11-12T01:05", "cycles": 3},
        {"operator": "ktmb", "start_cycle": "2026-11-12T01:15", "end_cycle": "2026-11-12T01:15", "cycles": 1},
    ]
    zero_by_hour = {b["hour"]: b["zero_vehicle_cycles"] for b in report["buckets"]}
    assert zero_by_hour == {0: 1, 1: 3}
    [op] = report["operators"]
    assert op["longest_zero_vehicle_run"] == 3


def test_operator_key_derivation_and_selection(tmp_path: Path) -> None:
    path = _write(tmp_path, [
        _row("gtfs_realtime_prasarana_bus_kl", "2026-11-12T03:55", 85),
        _row("gtfs_realtime_mybas_johor", "2026-11-12T03:55", 74),
        _row("air_pollution", "2026-11-12T03:55", 576),
        _row("gtfs_static_prasarana", "2026-11-12T03:55", 1),
    ])
    report = _report(path)
    assert fa.operator_key("gtfs_realtime_prasarana_bus_kl") == "prasarana_bus_kl"
    assert [o["operator"] for o in report["operators"]] == ["mybas_johor", "prasarana_bus_kl"]
    assert [o["dataset_id"] for o in report["operators"]] == [
        "gtfs_realtime_mybas_johor", "gtfs_realtime_prasarana_bus_kl",
    ]
    assert {b["operator"] for b in report["buckets"]} == {"mybas_johor", "prasarana_bus_kl"}


def test_malformed_cycle_lands_in_skipped_rows(tmp_path: Path) -> None:
    ds = "gtfs_realtime_ktmb"
    path = _write(tmp_path, [
        _row(ds, "2026-11-12T03:55", 6),
        _row(ds, "2026-11-12 03:55", 6),
        _row(ds, "2026-11-12T24:00", 6),
        _row(ds, "2026-11-12T3:55", 6),
        _row(ds, None, 6),
        '{"dataset_id": "gtfs_realtime_ktmb", "cycle": "2026-11-12T04',  # truncated line
    ])
    report = _report(path)
    assert report["skipped_rows"] == 5
    assert sum(b["cycles"] for b in report["buckets"]) == 1
    assert report["as_of"] == "2026-11-12T03:55"


def test_empty_input_produces_empty_structures(tmp_path: Path) -> None:
    path = _write(tmp_path, [])
    report = _report(path)
    assert report == {
        "schema": "datapulse/v1/gtfs-fleet-availability",
        "as_of": None,
        "since": None,
        "skipped_rows": 0,
        "operators": [],
        "buckets": [],
        "zero_vehicle_runs": [],
    }
    code, table = _run(path, "--table")
    assert code == 0
    assert "operators=0" in table


def test_output_is_byte_identical_across_runs(tmp_path: Path) -> None:
    rows = [
        _row("gtfs_realtime_mybas_kuching", "2026-11-12T05:00", 44),
        _row("gtfs_realtime_ktmb", "2026-11-11T23:55", 0),
        _row("gtfs_realtime_ktmb", "2026-11-12T00:00", 0),
        _row("gtfs_realtime_mybas_kuching", "2026-11-11T22:00", 40),
        _row("air_pollution", "2026-11-13T00:00", 1),
    ]
    first = _write(tmp_path, rows, "a.jsonl")
    second = _write(tmp_path, rows, "b.jsonl")
    assert first.read_bytes() == second.read_bytes()
    outputs = {_run(first)[1], _run(first)[1], _run(second)[1]}
    assert len(outputs) == 1
    tables = {_run(first, "--table")[1], _run(second, "--table")[1]}
    assert len(tables) == 1
    report = json.loads(outputs.pop())
    # as_of comes from the covered input, not the wall clock or non-GTFS rows.
    assert report["as_of"] == "2026-11-12T05:00"
    keys = [(b["operator"], b["date"], b["hour"]) for b in report["buckets"]]
    assert keys == sorted(keys)


def test_since_filters_by_cycle_date(tmp_path: Path) -> None:
    ds = "gtfs_realtime_ktmb"
    path = _write(tmp_path, [
        _row(ds, "2026-11-10T23:55", 0),
        _row(ds, "2026-11-11T00:00", 3),
        _row(ds, "2026-11-12T00:00", 0),
    ])
    report = _report(path, "--since", "2026-11-11")
    assert report["since"] == "2026-11-11"
    assert [b["date"] for b in report["buckets"]] == ["2026-11-11", "2026-11-12"]
    assert [r["start_cycle"] for r in report["zero_vehicle_runs"]] == ["2026-11-12T00:00"]


def test_table_sorted_by_operator_date_hour(tmp_path: Path) -> None:
    path = _write(tmp_path, [
        _row("gtfs_realtime_mybas_johor", "2026-11-12T01:00", 7),
        _row("gtfs_realtime_ktmb", "2026-11-12T02:00", 6),
        _row("gtfs_realtime_ktmb", "2026-11-11T09:00", 6),
    ])
    _, table = _run(path, "--table")
    body = [line.split()[:3] for line in table.splitlines()[1:4]]
    assert body == [
        ["ktmb", "2026-11-11", "09"],
        ["ktmb", "2026-11-12", "02"],
        ["mybas_johor", "2026-11-12", "01"],
    ]
