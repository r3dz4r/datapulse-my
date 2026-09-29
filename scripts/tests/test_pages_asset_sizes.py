from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


SCRIPT = Path(__file__).parents[1] / "check_pages_asset_sizes.py"
MIB = 1024 * 1024


def run_guard(site_dir: Path, limit: int) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), str(site_dir), "--limit-bytes", str(limit)],
        capture_output=True,
        text=True,
        check=False,
    )


def read_manifest(site_dir: Path) -> dict[str, object]:
    return json.loads((site_dir / "excluded-assets.json").read_text(encoding="utf-8"))


def test_under_limit_files_pass_and_write_empty_manifest(tmp_path: Path) -> None:
    site_dir = tmp_path / "_site"
    site_dir.mkdir()
    (site_dir / "small.txt").write_bytes(b"small")

    result = run_guard(site_dir, 1 * MIB)

    assert result.returncode == 0, result.stderr
    assert (site_dir / "small.txt").is_file()
    assert read_manifest(site_dir)["excluded_assets"] == []


def test_oversized_file_is_removed_only_from_staged_site_and_recorded(tmp_path: Path) -> None:
    site_dir = tmp_path / "_site"
    site_dir.mkdir()
    oversized = site_dir / "health" / "history_daily.json"
    oversized.parent.mkdir()
    size = MIB + 1
    oversized.write_bytes(b"x" * size)

    result = run_guard(site_dir, MIB)

    assert result.returncode == 0, result.stderr
    assert not oversized.exists()
    assert "health/history_daily.json" in result.stdout
    assert "1.0 MiB" in result.stdout
    manifest = read_manifest(site_dir)
    assert manifest["size_limit_bytes"] == MIB
    assert manifest["excluded_assets"] == [
        {
            "path": "health/history_daily.json",
            "size_bytes": size,
            "limit_bytes": MIB,
            "timestamp": manifest["excluded_assets"][0]["timestamp"],
        }
    ]


def test_file_exactly_at_limit_is_kept(tmp_path: Path) -> None:
    site_dir = tmp_path / "_site"
    site_dir.mkdir()
    exact_limit = site_dir / "at-limit.bin"
    exact_limit.write_bytes(b"x" * MIB)

    result = run_guard(site_dir, MIB)

    assert result.returncode == 0, result.stderr
    assert exact_limit.is_file()
    assert read_manifest(site_dir)["excluded_assets"] == []


def test_missing_site_directory_fails_without_writing_manifest(tmp_path: Path) -> None:
    site_dir = tmp_path / "missing-site"

    result = run_guard(site_dir, MIB)

    assert result.returncode != 0
    assert str(site_dir) in result.stderr
    assert not (site_dir / "excluded-assets.json").exists()
