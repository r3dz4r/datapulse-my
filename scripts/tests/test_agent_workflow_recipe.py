"""Pins the four-call agent workflow recipe against the live mcp.json and public index."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]

RECIPE_TOOLS = (
    "search_datasets",
    "get_dataset",
    "verify_dataset",
    "get_provenance",
    "trust_verdict",
)

COSIGN_ANCHOR = (
    "--certificate-identity "
    "https://github.com/r3dz4r/datapulse-my/.github/workflows/"
    "deploy-cloudflare-pages.yml@refs/heads/main"
)


def _mcp_document() -> dict:
    path = ROOT / "mcp.json"
    assert path.is_file(), f"missing MCP advertisement at {path}"
    return json.loads(path.read_text(encoding="utf-8"))


def test_mcp_json_parses() -> None:
    document = _mcp_document()
    assert isinstance(document, dict), "mcp.json must parse as a JSON object"


def test_recipe_tools_in_mcp_advertisement() -> None:
    document = _mcp_document()
    tools = document.get("tools")
    assert isinstance(tools, list) and tools, "mcp.json tools must be a non-empty list"
    names = {tool.get("name") for tool in tools if isinstance(tool, dict)}
    missing = [name for name in RECIPE_TOOLS if name not in names]
    assert not missing, f"recipe tools missing from mcp.json advertisement: {missing}"
    published_count = len(tools)
    assert published_count >= len(RECIPE_TOOLS)


def test_manifest_is_loadable() -> None:
    path = ROOT / "datapulse.json"
    assert path.is_file(), f"missing dataset manifest at {path}"
    document = json.loads(path.read_text(encoding="utf-8"))
    datasets = document.get("datasets")
    assert isinstance(datasets, list) and datasets, "datapulse.json datasets must be non-empty"


def test_recipe_in_llms_txt() -> None:
    path = ROOT / "llms.txt"
    assert path.is_file(), f"missing LLM index at {path}"
    text = path.read_text(encoding="utf-8")
    assert COSIGN_ANCHOR in text, "offline cosign anchor missing from llms.txt"
    for name in RECIPE_TOOLS:
        assert name in text, f"recipe tool {name!r} missing from llms.txt"


def test_recipe_doc_exists_and_complete() -> None:
    path = ROOT / "docs" / "agent-workflow-malaysia-public-data.md"
    assert path.is_file(), f"missing recipe doc at {path}"
    text = path.read_text(encoding="utf-8")
    for name in RECIPE_TOOLS:
        assert name in text, f"recipe tool {name!r} missing from recipe doc"
    assert "verify-blob-attestation" in text, "cosign command name missing from recipe doc"


def test_recipe_doc_not_truncated() -> None:
    path = ROOT / "docs" / "agent-workflow-malaysia-public-data.md"
    size = path.stat().st_size
    if size < 2000:
        pytest.fail(f"recipe doc shrank to {size} bytes; expected >= 2000")
