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
    (root / "scripts").mkdir()
    shutil.copy2(ROOT / "scripts/mcp-representative-queries.json", root / "scripts/mcp-representative-queries.json")
    subprocess.run(["git", "-C", str(root), "init", "--quiet"], check=True)
    subprocess.run(["git", "-C", str(root), "config", "user.email", "test@example.invalid"], check=True)
    subprocess.run(["git", "-C", str(root), "config", "user.name", "Test User"], check=True)
    subprocess.run(["git", "-C", str(root), "add", "."], check=True)
    subprocess.run(["git", "-C", str(root), "commit", "--quiet", "-m", "fixture"], check=True)
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


def test_card_with_nonexistent_source_commit_fails(tmp_path: Path) -> None:
    root = _fixture_root(tmp_path)
    _generate(root)
    path = root / "docs/mcp/cards/search_datasets.json"
    card = json.loads(path.read_text(encoding="utf-8"))
    card["source"]["commit_sha"] = "f" * 40
    path.write_text(json.dumps(card, indent=2) + "\n", encoding="utf-8")
    result = _run(VERIFIER, root)
    assert result.returncode == 1
    assert "card source.commit_sha is not a repository commit: docs/mcp/cards/search_datasets.json" in result.stderr


def test_changed_card_description_fails_with_same_source_stamp(tmp_path: Path) -> None:
    root = _fixture_root(tmp_path)
    _generate(root)
    path = root / "docs/mcp/cards/search_datasets.json"
    card = json.loads(path.read_text(encoding="utf-8"))
    original_stamp = card["source"]["commit_sha"]
    card["description"] += " drift"
    card["source"]["commit_sha"] = original_stamp
    path.write_text(json.dumps(card, indent=2) + "\n", encoding="utf-8")
    result = _run(VERIFIER, root)
    assert result.returncode == 1
    assert "card bytes differ from deterministic generator output: docs/mcp/cards/search_datasets.json" in result.stderr


def test_modified_well_known_copy_fails(tmp_path: Path) -> None:
    root = _fixture_root(tmp_path)
    _generate(root)
    path = root / "docs/.well-known/ard.json"
    path.write_bytes(path.read_bytes() + b" ")
    result = _run(VERIFIER, root)
    assert result.returncode == 1
    assert "well-known ARD manifest is not byte-identical" in result.stderr


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


def test_removed_representative_query_fails(tmp_path: Path) -> None:
    root = _fixture_root(tmp_path)
    _generate(root)
    path = root / "docs/ai-catalog.json"
    catalog = json.loads(path.read_text(encoding="utf-8"))
    catalog["entries"][0]["representativeQueries"] = ["only one query"]
    path.write_text(json.dumps(catalog, indent=2) + "\n", encoding="utf-8")
    result = _run(VERIFIER, root)
    assert result.returncode == 1
    assert "must contain 2-5 representativeQueries" in result.stderr


def test_altered_trust_manifest_identity_domain_fails(tmp_path: Path) -> None:
    root = _fixture_root(tmp_path)
    _generate(root)
    path = root / "docs/ai-catalog.json"
    catalog = json.loads(path.read_text(encoding="utf-8"))
    catalog["entries"][0]["trustManifest"]["identity"] = "https://wrong.example"
    path.write_text(json.dumps(catalog, indent=2) + "\n", encoding="utf-8")
    result = _run(VERIFIER, root)
    assert result.returncode == 1
    assert "trustManifest identity domain does not align with URN publisher" in result.stderr


def test_url_and_data_presence_is_exclusive(tmp_path: Path) -> None:
    root = _fixture_root(tmp_path)
    _generate(root)
    path = root / "docs/ai-catalog.json"
    catalog = json.loads(path.read_text(encoding="utf-8"))
    catalog["entries"][0]["data"] = {"unexpected": True}
    path.write_text(json.dumps(catalog, indent=2) + "\n", encoding="utf-8")
    result = _run(VERIFIER, root)
    assert result.returncode == 1
    assert "must contain exactly one of url or data" in result.stderr


def test_missing_well_known_copy_fails(tmp_path: Path) -> None:
    root = _fixture_root(tmp_path)
    _generate(root)
    (root / "docs/.well-known/ard.json").unlink()
    result = _run(VERIFIER, root)
    assert result.returncode == 1
    assert "missing well-known ARD manifest" in result.stderr


def test_pinned_ard_spec_version_fails_when_mutated(tmp_path: Path) -> None:
    root = _fixture_root(tmp_path)
    _generate(root)
    path = root / "docs/ai-catalog.json"
    catalog = json.loads(path.read_text(encoding="utf-8"))
    catalog["ard_spec_version"] = "0.9"
    path.write_text(json.dumps(catalog, indent=2) + "\n", encoding="utf-8")
    result = _run(VERIFIER, root)
    assert result.returncode == 1
    assert "catalog ard_spec_version must equal 0.91" in result.stderr


def test_missing_authored_query_corpus_entry_fails(tmp_path: Path) -> None:
    root = _fixture_root(tmp_path)
    _generate(root)
    path = root / "scripts/mcp-representative-queries.json"
    corpus = json.loads(path.read_text(encoding="utf-8"))
    del corpus["check_reconciliation"]
    path.write_text(json.dumps(corpus, indent=2) + "\n", encoding="utf-8")
    result = _run(VERIFIER, root)
    assert result.returncode == 1
    assert "is missing an authored representative query corpus" in result.stderr
