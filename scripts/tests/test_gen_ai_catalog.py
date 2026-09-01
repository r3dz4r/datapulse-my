from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
GENERATOR = ROOT / "scripts/gen_ai_catalog.py"


def _fixture_root(tmp_path: Path) -> Path:
    root = tmp_path / "catalog-root"
    root.mkdir()
    shutil.copy2(ROOT / "mcp.json", root / "mcp.json")
    shutil.copy2(ROOT / "datapulse.json", root / "datapulse.json")
    return root


def _generate(root: Path, *arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(GENERATOR), "--root", str(root), *arguments],
        text=True,
        capture_output=True,
        check=False,
    )


def _catalog(root: Path) -> dict[str, object]:
    return json.loads((root / "docs/ai-catalog.json").read_text(encoding="utf-8"))


def test_no_did_field_in_host(tmp_path: Path) -> None:
    root = _fixture_root(tmp_path)
    assert _generate(root).returncode == 0
    assert "identifier" not in _catalog(root)["host"]


def test_eighteen_entries_match_mcp_json(tmp_path: Path) -> None:
    root = _fixture_root(tmp_path)
    assert _generate(root).returncode == 0
    names = [tool["name"] for tool in json.loads((root / "mcp.json").read_text())["tools"]]
    entries = _catalog(root)["entries"]
    assert len(entries) == 18
    assert [entry["displayName"] for entry in entries] == sorted(names)


def test_each_entry_has_urn_identifier(tmp_path: Path) -> None:
    root = _fixture_root(tmp_path)
    assert _generate(root).returncode == 0
    for entry in _catalog(root)["entries"]:
        assert entry["identifier"] == f"urn:air:data-pulse.my:mcp:{entry['displayName']}"


def test_capabilities_array_is_sorted(tmp_path: Path) -> None:
    root = _fixture_root(tmp_path)
    assert _generate(root).returncode == 0
    assert all(entry["capabilities"] == sorted(entry["capabilities"]) for entry in _catalog(root)["entries"])


def test_per_tool_card_files_generated(tmp_path: Path) -> None:
    root = _fixture_root(tmp_path)
    assert _generate(root).returncode == 0
    assert all((root / "docs/mcp/cards" / f"{entry['displayName']}.json").is_file() for entry in _catalog(root)["entries"])


def test_per_tool_card_identifier_matches_catalog_entry(tmp_path: Path) -> None:
    root = _fixture_root(tmp_path)
    assert _generate(root).returncode == 0
    for entry in _catalog(root)["entries"]:
        card = json.loads((root / "docs/mcp/cards" / f"{entry['displayName']}.json").read_text())
        assert card["identifier"] == entry["identifier"]


def test_byte_identical_deterministic_runs(tmp_path: Path) -> None:
    root = _fixture_root(tmp_path)
    assert _generate(root).returncode == 0
    before = {path.relative_to(root): path.read_bytes() for path in (root / "docs").rglob("*.json")}
    assert _generate(root).returncode == 0
    after = {path.relative_to(root): path.read_bytes() for path in (root / "docs").rglob("*.json")}
    assert after == before


def test_contract_version_present_and_semver(tmp_path: Path) -> None:
    root = _fixture_root(tmp_path)
    assert _generate(root).returncode == 0
    assert re.fullmatch(r"\d+\.\d+\.\d+", _catalog(root)["contract_version"])
