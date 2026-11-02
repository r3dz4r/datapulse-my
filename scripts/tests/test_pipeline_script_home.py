"""Contract checks for the repository-owned DataPulse pipeline entry point."""
from __future__ import annotations

import os
import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "datapulse-pipeline.sh"


def test_pipeline_script_is_executable_and_syntax_valid() -> None:
    assert SCRIPT.is_file()
    assert os.access(SCRIPT, os.X_OK)
    subprocess.run(["bash", "-n", str(SCRIPT)], check=True, cwd=REPO_ROOT)


def test_pipeline_defaults_to_checkout_when_invoked_elsewhere(tmp_path: Path) -> None:
    completed = subprocess.run(
        ["bash", "-c", 'source "$1"; printf "%s\\n" "$DEFAULT_REPO"', "bash", str(SCRIPT)],
        check=True,
        capture_output=True,
        text=True,
        cwd=tmp_path,
        env={**os.environ, "DATAPULSE_REPO": ""},
    )
    assert completed.stdout.strip() == str(REPO_ROOT)
    assert "dotfiles" not in completed.stdout


def test_invalid_argument_prints_usage_without_running_pipeline(tmp_path: Path) -> None:
    """There is no help mode; assert the argument-validation refusal prints usage."""
    completed = subprocess.run(
        ["bash", str(SCRIPT), "--help"],
        capture_output=True,
        text=True,
        cwd=tmp_path,
    )
    assert completed.returncode == 2
    assert "Usage:" in completed.stderr
    assert "--run" in completed.stderr


def test_pipeline_script_has_no_dotfiles_references() -> None:
    completed = subprocess.run(
        ["grep", "-nE", "dotfiles", str(SCRIPT)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 1
    assert completed.stdout == ""
