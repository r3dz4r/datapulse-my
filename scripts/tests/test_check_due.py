#!/usr/bin/env python3
"""Exercise unreachable retry selection through check.sh with a fixed clock."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest


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
