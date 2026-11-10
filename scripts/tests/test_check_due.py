#!/usr/bin/env python3
"""Exercise unreachable retry selection through check.sh with a fixed clock."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from scripts.health_policy import (
    TIER_DUE_SECONDS,
    frequency_to_tier,
    is_due,
    select_due,
)

ROOT = Path(__file__).resolve().parents[2]
NOW = datetime(2026, 10, 31, 12, tzinfo=timezone.utc)
SCHEDULE_MINUTES = {
    "30 seconds": 0.5,
    "hourly": 15,
    "daily": 1440,
    "daily (weekdays)": 60,
    "daily (weekdays, 0900 MYT)": 60,
    "daily (weekdays, 1130 MYT)": 60,
    "daily (weekdays, 1200 MYT)": 60,
    "daily (weekdays, 1700 MYT)": 60,
    "weekly": 10080,
    "monthly": 10080,
    "quarterly": 10080,
    "annual": 43200,
    "biennial to triennial (survey years)": 43200,
    "as-required": 43200,
}


@pytest.mark.parametrize(
    ("retry_minutes", "cadence_override"),
    [(None, None), (100000, None), (100000, 999999), (240, 1)],
)
def test_unreachable_retried_within_cadence_at_fixed_time(
    tmp_path: Path, retry_minutes: int | None, cadence_override: int | None,
) -> None:
    datasets = []
    previous = []
    due_ids = set()
    for index, (frequency, limit) in enumerate(SCHEDULE_MINUTES.items()):
        interval = min(retry_minutes or 240, limit, cadence_override or limit)
        for suffix, age_seconds in (("waiting", interval * 60 - 1), ("due", interval * 60)):
            dataset_id = f"dataset_{index}_{suffix}"
            source_url = f"https://example.invalid/{dataset_id}.json"
            datasets.append({"id": dataset_id, "url": source_url, "refresh_frequency": frequency})
            previous.append({
                "dataset_id": dataset_id, "url": source_url,
                "status": "unreachable", "http_status": None,
                "last_checked": (NOW - timedelta(seconds=age_seconds)).strftime("%Y-%m-%dT%H:%M:%SZ"),
            })
            if suffix == "due":
                due_ids.add(dataset_id)
    (tmp_path / "datapulse.json").write_text(json.dumps({"datasets": datasets}))
    (tmp_path / "health").mkdir()
    (tmp_path / "health/latest.json").write_text(json.dumps({"datasets": previous}))
    policy = tmp_path / "policy.json"
    policy.write_text(json.dumps({"version": 1, "defaults": {"adapter": "direct"}, "datasets": {}}))
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    real_date = shutil.which("date")
    assert real_date is not None
    (fake_bin / "date").write_text(
        '#!/bin/sh\nif [ "$*" = "-u +%s" ]; then\n'
        f'  echo {int(NOW.timestamp())}\nelse\n  exec "{real_date}" "$@"\nfi\n'
    )
    # Retrying does not require recovery: keep reporting the upstream failure.
    (fake_bin / "curl").write_text(
        '#!/bin/sh\nfor arg do\ncase "$arg" in\n'
        '  https://example.invalid/*.json) printf "%s\\n" "$arg" >> "$PROBE_ATTEMPT_LOG" ;;\n'
        'esac\ndone\nexit 7\n'
    )
    for path in fake_bin.iterdir():
        path.chmod(0o755)
    environment = os.environ.copy()
    environment.pop("RETRY_CADENCE_MINUTES", None)
    environment.update(
        PATH=f"{fake_bin}:{environment['PATH']}",
        DATAPULSE_PROBE_POLICY=str(policy),
        DATAPULSE_CHECKED_AT=NOW.strftime("%Y-%m-%dT%H:%M:%SZ"),
        PROBE_ATTEMPT_LOG=str(tmp_path / "attempts.log"),
    )
    if retry_minutes is not None:
        environment["RETRY_CADENCE_MINUTES"] = str(retry_minutes)
    command = ["bash", str(ROOT / "scripts/check.sh"), "--due"]
    if cadence_override is not None:
        command.extend(["--cadence-minutes", str(cadence_override)])
    result = subprocess.run(
        [*command, "datapulse.json"],
        cwd=tmp_path, env=environment, capture_output=True, text=True, timeout=60, check=False,
    )

    assert result.returncode == 0, result.stderr
    rows = json.loads(result.stdout)["datasets"]
    attempts = tmp_path / "attempts.log"
    retried = {Path(url).stem for url in attempts.read_text().splitlines()} if attempts.exists() else set()
    assert retried == due_ids
    assert all(row["status"] == "unreachable" for row in rows)
    daily = next(row for row in previous if row["dataset_id"] == "dataset_2_due")
    daily_age = NOW - datetime.fromisoformat(daily["last_checked"])
    assert daily_age <= timedelta(hours=24)
    if retry_minutes is None and cadence_override is None:
        assert daily_age == timedelta(hours=4)
    assert "dataset_2_due" in retried


# --- Declared-cadence selection through scripts/health_policy.py -------------


def _ago(seconds: float) -> str:
    return (NOW - timedelta(seconds=seconds)).strftime("%Y-%m-%dT%H:%M:%SZ")


def test_operator_approved_tiers() -> None:
    assert TIER_DUE_SECONDS == {
        "realtime": 900,
        "daily": 86400,
        "weekly-monthly": 604800,
        "slow": 2592000,
    }
    assert frequency_to_tier("30 seconds") == "realtime"
    assert frequency_to_tier("hourly") == "realtime"


def test_thirty_second_dataset_is_due_after_fifteen_minutes() -> None:
    assert is_due(_ago(899), NOW, "30 seconds", "rt30") is False
    assert is_due(_ago(900), NOW, "30 seconds", "rt30") is True
    assert is_due(_ago(901), NOW, "30 seconds", "rt30") is True


def test_hourly_dataset_is_due_after_fifteen_minutes() -> None:
    assert is_due(_ago(61), NOW, "hourly", "hourly") is False
    assert is_due(_ago(899), NOW, "hourly", "hourly") is False
    assert is_due(_ago(901), NOW, "hourly", "hourly") is True


def test_weekday_daily_keeps_hourly_override() -> None:
    for frequency in ("daily (weekdays)", "daily (weekdays, 1700 MYT)"):
        assert is_due(_ago(3599), NOW, frequency, "weekday") is False
        assert is_due(_ago(3600), NOW, frequency, "weekday") is True


def test_annual_dataset_is_probed_once_a_month_not_every_tick() -> None:
    # Tick at the measured cycle period (~27 cycles/day) for 90 days, feeding
    # each probe back as the next tick's last_checked like the producer does.
    tick = timedelta(seconds=86400 // 27)
    clock = NOW
    last_checked = _ago(0)
    probes = []
    for _ in range(90 * 27):
        clock += tick
        manifest = [{"id": "annual", "refresh_frequency": "annual"}]
        previous = [{"dataset_id": "annual", "status": "fresh", "last_checked": last_checked}]
        if select_due(manifest, previous, clock):
            probes.append(clock)
            last_checked = clock.strftime("%Y-%m-%dT%H:%M:%SZ")
    assert len(probes) == 3
    gaps = [later - earlier for earlier, later in zip([NOW, *probes], probes)]
    assert all(timedelta(days=30) <= gap < timedelta(days=30) + tick for gap in gaps)


def test_unknown_cadence_still_raises() -> None:
    with pytest.raises(ValueError, match="'mystery'.*'fortnightly'"):
        is_due(_ago(10), NOW, "fortnightly", "mystery")
    with pytest.raises(ValueError, match="'mystery'.*'fortnightly'"):
        select_due([{"id": "mystery", "refresh_frequency": "fortnightly"}], [], NOW)


MIXED_MANIFEST = [
    {"id": "rt30_due", "refresh_frequency": "30 seconds"},
    {"id": "rt30_wait", "refresh_frequency": "30 seconds"},
    {"id": "hourly_wait", "refresh_frequency": "hourly"},
    {"id": "hourly_due", "refresh_frequency": "hourly"},
    {"id": "weekday_due", "refresh_frequency": "daily (weekdays, 0900 MYT)"},
    {"id": "daily_wait", "refresh_frequency": "daily"},
    {"id": "monthly_wait", "refresh_frequency": "monthly"},
    {"id": "annual_wait", "refresh_frequency": "annual"},
    {"id": "annual_due", "refresh_frequency": "annual"},
    {"id": "never_probed", "refresh_frequency": "quarterly"},
    {"id": "unreachable_annual", "refresh_frequency": "annual"},
]
MIXED_PREVIOUS = [
    {"dataset_id": "rt30_due", "status": "fresh", "last_checked": _ago(900)},
    {"dataset_id": "rt30_wait", "status": "fresh", "last_checked": _ago(899)},
    {"dataset_id": "hourly_wait", "status": "fresh", "last_checked": _ago(61)},
    {"dataset_id": "hourly_due", "status": "fresh", "last_checked": _ago(901)},
    {"dataset_id": "weekday_due", "status": "fresh", "last_checked": _ago(3600)},
    {"dataset_id": "daily_wait", "status": "fresh", "last_checked": _ago(23 * 3600)},
    {"dataset_id": "monthly_wait", "status": "fresh", "last_checked": _ago(6 * 86400)},
    {"dataset_id": "annual_wait", "status": "stale", "last_checked": _ago(29 * 86400)},
    {"dataset_id": "annual_due", "status": "fresh", "last_checked": _ago(30 * 86400)},
    {"dataset_id": "unreachable_annual", "status": "unreachable", "last_checked": _ago(4 * 3600)},
]
MIXED_DUE = [
    "rt30_due", "hourly_due", "weekday_due", "annual_due", "never_probed", "unreachable_annual",
]


def test_mixed_manifest_selects_only_the_due_subset() -> None:
    selected = select_due(MIXED_MANIFEST, MIXED_PREVIOUS, NOW)
    assert [entry["id"] for entry in selected] == MIXED_DUE
    # Determinism: same inputs and clock, same due set.
    assert select_due(MIXED_MANIFEST, MIXED_PREVIOUS, NOW) == selected


def test_select_due_cli_matches_the_pure_selection(tmp_path: Path) -> None:
    manifest = tmp_path / "datapulse.json"
    previous = tmp_path / "latest.json"
    output = tmp_path / "selected.json"
    manifest.write_text(json.dumps({"schema": "kept", "datasets": MIXED_MANIFEST}))
    previous.write_text(json.dumps({"datasets": MIXED_PREVIOUS}))
    command = [
        sys.executable, str(ROOT / "scripts/health_policy.py"), "select-due",
        "--manifest", str(manifest), "--previous", str(previous),
        "--now-epoch", str(int(NOW.timestamp())), "--output", str(output),
    ]
    result = subprocess.run(command, capture_output=True, text=True, timeout=30, check=False)
    assert result.returncode == 0, result.stderr
    document = json.loads(output.read_text())
    assert document["schema"] == "kept"
    assert [entry["id"] for entry in document["datasets"]] == MIXED_DUE

    empty_previous = tmp_path / "empty.json"
    empty_previous.write_text("")
    command[command.index(str(previous))] = str(empty_previous)
    result = subprocess.run(command, capture_output=True, text=True, timeout=30, check=False)
    assert result.returncode == 0, result.stderr
    assert len(json.loads(output.read_text())["datasets"]) == len(MIXED_MANIFEST)


@pytest.mark.parametrize(
    ("retry_minutes", "cadence_override"),
    [(None, None), (100000, None), (100000, 999999), (240, 1)],
)
def test_select_due_keeps_check_sh_unreachable_retry_rules(
    retry_minutes: int | None, cadence_override: int | None,
) -> None:
    manifest, previous, due_ids = [], [], set()
    for index, (frequency, limit) in enumerate(SCHEDULE_MINUTES.items()):
        interval = min(retry_minutes or 240, limit, cadence_override or limit)
        for suffix, age_seconds in (("waiting", interval * 60 - 1), ("due", interval * 60)):
            dataset_id = f"dataset_{index}_{suffix}"
            manifest.append({"id": dataset_id, "refresh_frequency": frequency})
            previous.append({"dataset_id": dataset_id, "status": "unreachable", "last_checked": _ago(age_seconds)})
            if suffix == "due":
                due_ids.add(dataset_id)
    selected = select_due(
        manifest, previous, NOW,
        cadence_override_seconds=None if cadence_override is None else cadence_override * 60,
        retry_seconds=(retry_minutes or 240) * 60,
    )
    assert {entry["id"] for entry in selected} == due_ids
