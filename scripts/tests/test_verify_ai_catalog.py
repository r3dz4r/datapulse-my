from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
GENERATOR = ROOT / "scripts/gen_ai_catalog.py"
VERIFIER = ROOT / "scripts/verify_ai_catalog.py"


def _fixture_root(tmp_path: Path) -> Path:
    root = tmp_path / "catalog-root"
    root.mkdir()
    shutil.copy2(ROOT / "mcp.json", root / "mcp.json")
    shutil.copy2(ROOT / "datapulse.json", root / "datapulse.json")
    return root


def _run(script: Path, root: Path, *arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run([sys.executable, str(script), "--root", str(root), *arguments], text=True, capture_output=True, check=False)


def _generate(root: Path) -> None:
    result = _run(GENERATOR, root)
    assert result.returncode == 0, result.stderr


def test_clean_state_passes(tmp_path: Path) -> None:
    root = _fixture_root(tmp_path)
    _generate(root)
    assert _run(VERIFIER, root).returncode == 0


def test_missing_card_file_fails(tmp_path: Path) -> None:
    root = _fixture_root(tmp_path)
    _generate(root)
    (root / "docs/mcp/cards/search_datasets.json").unlink()
    result = _run(VERIFIER, root)
    assert result.returncode == 1
    assert "missing card file: docs/mcp/cards/search_datasets.json" in result.stderr


def test_modified_card_file_fails(tmp_path: Path) -> None:
    root = _fixture_root(tmp_path)
    _generate(root)
    path = root / "docs/mcp/cards/search_datasets.json"
    path.write_text(path.read_text(encoding="utf-8").replace("search_datasets", "search_datasets_tampered", 1), encoding="utf-8")
    assert _run(VERIFIER, root).returncode == 1


def test_modified_catalog_fails(tmp_path: Path) -> None:
    root = _fixture_root(tmp_path)
    _generate(root)
    path = root / "docs/ai-catalog.json"
    path.write_text(path.read_text(encoding="utf-8").replace('"1.0.0"', '"9.9.9"', 1), encoding="utf-8")
    assert _run(VERIFIER, root).returncode == 1


def test_did_in_host_field_fails(tmp_path: Path) -> None:
    root = _fixture_root(tmp_path)
    _generate(root)
    path = root / "docs/ai-catalog.json"
    catalog = json.loads(path.read_text(encoding="utf-8"))
    catalog["host"]["identifier"] = "did:web:data-pulse.my"
    path.write_text(json.dumps(catalog, indent=2) + "\n", encoding="utf-8")
    result = _run(VERIFIER, root)
    assert result.returncode == 1
    assert "must not contain an identifier" in result.stderr
