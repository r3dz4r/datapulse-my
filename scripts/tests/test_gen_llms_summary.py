"""Tests for deriving the llms.txt dataset count from the manifest."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
GENERATOR = ROOT / "scripts/gen_llms_summary.py"


def _write_public_surface_fixture(root: Path, featured_dataset_id: str) -> None:
    config_dir = root / "config"
    config_dir.mkdir(exist_ok=True)
    (config_dir / "public-surfaces.json").write_text(
        json.dumps({
            "schema": "datapulse/v1/public-surfaces",
            "origins": {
                "website": "https://data-pulse.my",
                "mcp": "https://mcp.data-pulse.my",
                "repository": "https://github.com/r3dz4r/datapulse-my",
            },
            "pages": ["/"],
            "artifacts": ["/llms.txt"],
            "featured_dataset_ids": [featured_dataset_id],
        }) + "\n",
        encoding="utf-8",
    )
    (config_dir / "public-surfaces.schema.json").write_text(
        json.dumps({
            "type": "object",
            "required": ["schema", "origins", "pages", "artifacts", "featured_dataset_ids"],
            "properties": {
                "schema": {"const": "datapulse/v1/public-surfaces"},
                "origins": {
                    "type": "object",
                    "required": ["website", "mcp", "repository"],
                    "properties": {
                        "website": {"const": "https://data-pulse.my"},
                        "mcp": {"const": "https://mcp.data-pulse.my"},
                        "repository": {"const": "https://github.com/r3dz4r/datapulse-my"},
                    },
                    "additionalProperties": False,
                },
                "pages": {"type": "array"},
                "artifacts": {"type": "array"},
                "featured_dataset_ids": {"type": "array"},
            },
            "additionalProperties": False,
        }) + "\n",
        encoding="utf-8",
    )


def _write_fixture(root: Path, *, count: int = 3, include_mcp_line: bool = True) -> bytes:
    manifest = {"datasets": [{"id": f"dataset-{index}"} for index in range(count)]}
    (root / "datapulse.json").write_text(
        json.dumps(manifest) + "\n", encoding="utf-8"
    )
    _write_public_surface_fixture(root, "dataset-0")

    lines = [
        "# Fixture\n",
        "<!-- BEGIN catalog-summary -->\n",
        "> stale summary\n",
        "<!-- END catalog-summary -->\n",
        "Unrelated content stays byte-identical.\n",
        "## Datasets\n",
        "<!-- BEGIN featured-datasets -->\n",
        "- stale featured dataset\n",
        "<!-- END featured-datasets -->\n",
    ]
    if not include_mcp_line:
        lines[-1] = "<!-- END wrong-marker -->\n"
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
    output = (tmp_path / "llms.txt").read_text(encoding="utf-8")
    assert "> DataPulse MY publishes a machine-readable manifest of 3 official datasets." in output
    assert "Unrelated content stays byte-identical." in output
    assert "dataset-0" in output


def test_idempotent_second_run(tmp_path: Path) -> None:
    _write_fixture(tmp_path)

    first = _run(tmp_path)
    after_first = (tmp_path / "llms.txt").read_bytes()
    second = _run(tmp_path)

    assert first.returncode == second.returncode == 0, first.stderr or second.stderr
    assert (tmp_path / "llms.txt").read_bytes() == after_first


def test_removes_per_dataset_bullets_absent_from_manifest(tmp_path: Path) -> None:
    manifest = {
        "datasets": [
            {"id": "current"},
            {"id": "renamed", "canonical_id": "legacy"},
        ]
    }
    (tmp_path / "datapulse.json").write_text(
        json.dumps(manifest) + "\n", encoding="utf-8"
    )
    (tmp_path / "llms.txt").write_text(
        "\n".join(
            [
                "# Fixture",
                "<!-- BEGIN catalog-summary -->",
                "> stale summary",
                "<!-- END catalog-summary -->",
                "## Datasets",
                "<!-- BEGIN featured-datasets -->",
                "- [Current](https://example.test/data/current.md)",
                "- [Legacy](https://example.test/data/legacy.md)",
                "- [Stale](https://example.test/data/removed.md)",
                "- stale featured dataset",
                "<!-- END featured-datasets -->",
                "",
            ]
        ),
        encoding="utf-8",
    )
    _write_public_surface_fixture(tmp_path, "current")

    result = _run(tmp_path)

    assert result.returncode == 0, result.stderr
    output = (tmp_path / "llms.txt").read_text(encoding="utf-8")
    assert "data/current.md" in output
    assert "data/removed.md" not in output


def test_missing_pattern_fails(tmp_path: Path) -> None:
    _write_fixture(tmp_path, include_mcp_line=False)

    result = _run(tmp_path)

    assert result.returncode != 0
    assert "marker" in result.stderr


def test_rejects_invalid_root(tmp_path: Path) -> None:
    result = _run(tmp_path / "does-not-exist")

    assert result.returncode != 0
