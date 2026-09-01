from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from test_gen_as_of import DATE, GENERATOR, _make_root, _run


ROOT = Path(__file__).resolve().parents[2]
VERIFIER = ROOT / "scripts/verify_as_of_reproducible.py"


def _verify(root: Path, *extra: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run([sys.executable, str(VERIFIER), "--root", str(root), *extra], text=True, capture_output=True)


def _generated_root(tmp_path: Path) -> Path:
    root = _make_root(tmp_path, "bnm_open_api")
    assert _run(root, "bnm_open_api").returncode == 0
    return root


def test_clean_directory_passes(tmp_path: Path) -> None:
    root = _generated_root(tmp_path)
    assert _verify(root, "--family", "bnm_open_api", "--date", DATE).returncode == 0


def test_removed_dataset_file_fails(tmp_path: Path) -> None:
    root = _generated_root(tmp_path)
    (root / "health/as_of/bnm_open_api" / DATE / "bnm_base_rate.json").unlink()
    result = _verify(root, "--family", "bnm_open_api", "--date", DATE)
    assert result.returncode == 1
    assert "bnm_base_rate" in result.stderr


def test_modified_dataset_file_fails(tmp_path: Path) -> None:
    root = _generated_root(tmp_path)
    changed = root / "health/as_of/bnm_open_api" / DATE / "bnm_base_rate.json"
    changed.write_bytes(changed.read_bytes() + b" ")
    result = _verify(root, "--family", "bnm_open_api", "--date", DATE)
    assert result.returncode == 1
    assert "bnm_base_rate.json" in result.stderr
    assert "sha256" in result.stderr


def test_modified_manifest_fails(tmp_path: Path) -> None:
    root = _generated_root(tmp_path)
    changed = root / "health/as_of/bnm_open_api" / DATE / "_manifest.json"
    changed.write_bytes(changed.read_bytes() + b" ")
    assert _verify(root, "--family", "bnm_open_api", "--date", DATE).returncode == 1


def test_regeneration_mismatch_fails(tmp_path: Path) -> None:
    root = _generated_root(tmp_path)
    history = root / "health/history.jsonl"
    history.write_text(history.read_text() + '{"dataset_id":"bnm_opr","observed_at":"2026-09-01T12:00:00Z","status":"stale"}\n', encoding="utf-8")
    result = _verify(root, "--family", "bnm_open_api", "--date", DATE)
    assert result.returncode == 1
    assert "bnm_opr.json" in result.stderr


def test_unknown_family_exits_two(tmp_path: Path) -> None:
    root = _generated_root(tmp_path)
    result = _verify(root, "--family", "not_a_family", "--date", DATE)
    assert result.returncode == 2
