from __future__ import annotations

import json
import subprocess
import sys
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/check_heartbeat.py"


def _append(log: Path, *args: str) -> None:
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "append", *args],
        env={"DATAPULSE_TELEMETRY_FILE": str(log)},
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr


def test_heartbeat_writes_structured_line(tmp_path: Path) -> None:
    log = tmp_path / "var/log/stages.jsonl"
    _append(log, "--stage", "probe", "--duration", "1234", "--status", "success")
    row = json.loads(log.read_text(encoding="utf-8"))
    assert set(row) == {"ts", "stage", "duration_ms", "status", "cycle", "extra"}
    assert row["stage"] == "probe"
    assert row["duration_ms"] == 1234
    assert row["status"] == "success"
    datetime.fromisoformat(row["ts"].replace("Z", "+00:00"))


def test_heartbeat_rotates_daily(tmp_path: Path) -> None:
    log = tmp_path / "stages.jsonl"
    old = (datetime.now(UTC) - timedelta(days=2)).isoformat().replace("+00:00", "Z")
    log.write_text(json.dumps({"ts": old, "stage": "probe"}) + "\n", encoding="utf-8")
    _append(log, "--stage", "history", "--duration", "5", "--status", "success")
    assert not any(json.loads(line).get("ts") == old for line in log.read_text().splitlines())
    rotated = tmp_path / f"stages.{old[:10]}.jsonl"
    assert rotated.exists()
    assert json.loads(rotated.read_text(encoding="utf-8"))["ts"] == old


def test_publication_lag_recorded(tmp_path: Path) -> None:
    log = tmp_path / "stages.jsonl"
    _append(log, "--stage", "publish", "--duration", "20", "--status", "success", "--lag-ms", "4200")
    row = json.loads(log.read_text(encoding="utf-8"))
    assert row["extra"]["lag_ms"] == 4200
    assert row["extra"]["publication_lag_ms"] == 4200


def test_lock_skip_emits_skipped_status(tmp_path: Path) -> None:
    log = tmp_path / "stages.jsonl"
    lock = tmp_path / "health.lock"
    holder = subprocess.Popen(["flock", "-n", str(lock), "sleep", "0.5"])
    try:
        time.sleep(0.05)
        command = (
            f"exec 9>{lock}; if ! flock -n 9; then "
            f"DATAPULSE_TELEMETRY_FILE={log} {sys.executable} {SCRIPT} append "
            "--stage publish --duration 0 --status skipped "
            "--extra-json '{\"reason\":\"lock_busy\"}'; exit 0; fi"
        )
        result = subprocess.run(["bash", "-c", command], capture_output=True, text=True, check=False)
        assert result.returncode == 0, result.stderr
    finally:
        holder.wait(timeout=2)
    row = json.loads(log.read_text(encoding="utf-8"))
    assert row["status"] == "skipped"
    assert row["extra"]["reason"] == "lock_busy"
