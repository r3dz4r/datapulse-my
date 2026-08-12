from __future__ import annotations

import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/check_no_cycle_alert.sh"


def _run(history: Path, alert: Path, now: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", str(SCRIPT), "--history", str(history), "--alert", str(alert), "--threshold-minutes", "15", "--now", now],
        capture_output=True,
        text=True,
        check=False,
    )


def test_no_cycle_alert_raises_on_missing_history(tmp_path: Path) -> None:
    history = tmp_path / "history.jsonl"
    history.write_text(json.dumps({"probe_outcome": "error", "observed_at": "2026-08-12T17:00:00Z"}) + "\n")
    alert = tmp_path / "var/log/heartbeat-FAIL"
    result = _run(history, alert, "2026-08-12T18:00:00Z")
    assert result.returncode != 0
    assert "no successful DataPulse cycle" in alert.read_text(encoding="utf-8")


def test_no_cycle_alert_silent_when_recent(tmp_path: Path) -> None:
    history = tmp_path / "history.jsonl"
    history.write_text(json.dumps({"probe_outcome": "success", "observed_at": "2026-08-12T17:55:00Z"}) + "\n")
    alert = tmp_path / "var/log/heartbeat-FAIL"
    result = _run(history, alert, "2026-08-12T18:00:00Z")
    assert result.returncode == 0
    assert not alert.exists()
