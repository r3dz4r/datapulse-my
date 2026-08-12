from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/lint_docs_against_units.py"


def _run(root: Path, timer: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run([sys.executable, str(SCRIPT), "--root", str(root), "--timer", str(timer)], capture_output=True, text=True, check=False)


def _fixture(tmp_path: Path, text: str) -> tuple[Path, Path]:
    (tmp_path / "docs").mkdir()
    (tmp_path / "deploy/systemd").mkdir(parents=True)
    (tmp_path / "docs/operations.md").write_text(text, encoding="utf-8")
    (tmp_path / "README.md").write_text("Current cadence is five minutes.\n", encoding="utf-8")
    (tmp_path / "deploy/systemd/datapulse-health.service").write_text("ExecStart=/bin/true\n", encoding="utf-8")
    timer = tmp_path / "timer"
    timer.write_text("[Unit]\nDescription=Run every 5 minutes\n[Timer]\nOnCalendar=*:0/5\n", encoding="utf-8")
    return tmp_path, timer


def test_lint_catches_drift_when_added(tmp_path: Path) -> None:
    root, timer = _fixture(tmp_path, "The old 15-minute cadence is documented here.\n")
    result = _run(root, timer)
    assert result.returncode == 1
    assert "docs say '15-minute cadence'" in result.stdout


def test_lint_passes_when_synced(tmp_path: Path) -> None:
    root, timer = _fixture(tmp_path, "The timer cadence is defined by the canonical unit.\n")
    result = _run(root, timer)
    assert result.returncode == 0, result.stdout
