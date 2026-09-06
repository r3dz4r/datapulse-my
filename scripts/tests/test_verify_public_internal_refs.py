"""Regression tests for the public internal-reference verifier."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/verify_public_internal_refs.py"


def _run(root: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--root", str(root)],
        capture_output=True,
        text=True,
        check=False,
    )


def _tracked_file(root: Path, relative_path: str, content: str) -> None:
    path = root / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    subprocess.run(["git", "init", "-q"], cwd=root, check=True)
    subprocess.run(["git", "add", relative_path], cwd=root, check=True)


def test_current_repository_passes() -> None:
    result = _run(ROOT)

    assert result.returncode == 0, result.stdout + result.stderr


def test_public_markdown_reference_fails_with_stable_path_and_line(tmp_path: Path) -> None:
    root = tmp_path / "repository"
    root.mkdir()
    _tracked_file(root, "README.md", "Read [the record](notes/internal.md).\n")

    result = _run(root)

    assert result.returncode == 1
    assert result.stdout == "Public internal-reference verification failed (1 violation(s)):\n- README.md:1: prohibited internal repository reference\n"
    assert result.stderr == ""


def test_dot_relative_markdown_reference_fails(tmp_path: Path) -> None:
    root = tmp_path / "repository"
    root.mkdir()
    _tracked_file(root, "README.md", "Read [the record](./notes/internal.md).\n")

    result = _run(root)

    assert result.returncode == 1
    assert "README.md:1: prohibited internal repository reference" in result.stdout


def test_public_claims_json_reference_fails(tmp_path: Path) -> None:
    root = tmp_path / "repository"
    root.mkdir()
    _tracked_file(root, "claims/claims.json", '{"evidence_source": "analyses/private.md"}\n')

    result = _run(root)

    assert result.returncode == 1
    assert "claims/claims.json:1: prohibited internal repository reference" in result.stdout


def test_generic_prose_and_excluded_fixtures_are_allowed(tmp_path: Path) -> None:
    root = tmp_path / "repository"
    root.mkdir()
    _tracked_file(
        root,
        "README.md",
        "Our private strategy stays in notes/. Operator evidence stays in ~/dotfiles/notes/private.md.\n",
    )
    fixture = root / "scripts/tests/fixtures/internal-reference.md"
    fixture.parent.mkdir(parents=True, exist_ok=True)
    fixture.write_text("[fixture](./notes/internal.md)\n", encoding="utf-8")
    subprocess.run(["git", "add", "scripts/tests/fixtures/internal-reference.md"], cwd=root, check=True)

    result = _run(root)

    assert result.returncode == 0, result.stdout + result.stderr
