"""Tests for deriving the llms.txt dataset count from the manifest."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
GENERATOR = ROOT / "scripts/gen_llms_summary.py"


def _write_fixture(root: Path, *, count: int = 3, include_mcp_line: bool = True) -> bytes:
    manifest = {"datasets": [{"id": f"dataset-{index}"} for index in range(count)]}
    (root / "datapulse.json").write_text(
        json.dumps(manifest) + "\n", encoding="utf-8"
    )

    lines = [
        "# Fixture\n",
        "> a machine-readable manifest of 42 official datasets, fresh metadata\n",
        "Unrelated content stays byte-identical.\n",
        "Agents can query the 42-dataset catalogue natively.\n",
    ]
    if include_mcp_line:
        lines.append("The endpoint serves tools over the 42-dataset catalogue.\n")
    content = "".join(lines).encode("utf-8")
    (root / "llms.txt").write_bytes(content)
    return content


def _run(root: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["python3", str(GENERATOR), "--root", str(root)],
        capture_output=True,
        text=True,
        check=False,
    )


def test_updates_count_from_manifest(tmp_path: Path) -> None:
    before = _write_fixture(tmp_path)

    result = _run(tmp_path)

    assert result.returncode == 0, result.stderr
    expected = before.replace(b"42 official datasets", b"3 official datasets")
    expected = expected.replace(b"42-dataset catalogue", b"3-dataset catalogue")
    assert (tmp_path / "llms.txt").read_bytes() == expected


def test_idempotent_second_run(tmp_path: Path) -> None:
    _write_fixture(tmp_path)

    first = _run(tmp_path)
    after_first = (tmp_path / "llms.txt").read_bytes()
    second = _run(tmp_path)

    assert first.returncode == second.returncode == 0, first.stderr or second.stderr
    assert (tmp_path / "llms.txt").read_bytes() == after_first


def test_missing_pattern_fails(tmp_path: Path) -> None:
    _write_fixture(tmp_path, include_mcp_line=False)

    result = _run(tmp_path)

    assert result.returncode != 0
    assert "catalogue" in result.stderr


def test_rejects_invalid_root(tmp_path: Path) -> None:
    result = _run(tmp_path / "does-not-exist")

    assert result.returncode != 0
