"""Tests for the tracked SVG namespace verifier."""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/verify_svg_namespace.py"
FIXTURES = Path(__file__).parent / "fixtures/svg_namespace/valid"


def run_verifier(root: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--root", str(root)],
        capture_output=True,
        text=True,
        check=False,
    )


def tracked_fixture(tmp_path: Path, fixture_name: str) -> Path:
    root = tmp_path / "repository"
    (root / "assets").mkdir(parents=True)
    shutil.copy2(FIXTURES / fixture_name, root / "assets/brand.svg")
    subprocess.run(["git", "init", "-q"], cwd=root, check=True)
    subprocess.run(["git", "add", "assets/brand.svg"], cwd=root, check=True)
    return root


def test_current_repository_passes() -> None:
    result = run_verifier(ROOT)

    assert result.returncode == 0, result.stdout + result.stderr


def test_broken_tracked_svg_fails_with_file_and_namespace(tmp_path: Path) -> None:
    root = tracked_fixture(tmp_path, "broken_brand.svg")

    result = run_verifier(root)

    assert result.returncode == 1
    message = result.stdout + result.stderr
    assert "assets/brand.svg" in message
    assert "xmlns" in message
    assert "http&#58;//www.w3.org/2000/svg" in message


def test_fixed_tracked_svg_passes(tmp_path: Path) -> None:
    root = tracked_fixture(tmp_path, "fixed_brand.svg")

    result = run_verifier(root)

    assert result.returncode == 0, result.stdout + result.stderr
