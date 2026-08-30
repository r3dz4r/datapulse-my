"""The agent discover-and-verify path must complete in no more than three calls."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastmcp import Client


MCP_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(MCP_DIR))

import server  # noqa: E402
from test_mcp_verify_dataset import _bundle_for, _catalogue


pytestmark = pytest.mark.anyio


async def test_search_then_verify_returns_complete_fuelprice_answer(monkeypatch: pytest.MonkeyPatch) -> None:
    manifest, health = _catalogue()

    async def load_catalogue() -> tuple[dict, dict]:
        return manifest, health

    async def fetch_bytes(_: str) -> bytes:
        return _bundle_for(manifest, health)

    monkeypatch.setattr(server, "_load_catalogue", load_catalogue)
    monkeypatch.setattr(server, "_fetch_bytes", fetch_bytes)
    monkeypatch.setattr(server, "_verify_sigstore_receipt", lambda **_: (True, "Verified OK"))

    calls = 0
    async with Client(server.mcp) as client:
        search = await client.call_tool("search_datasets", {"query": "fuel prices"})
        calls += 1
        verified = await client.call_tool("verify_dataset", {"dataset_id": "fuelprice"})
        calls += 1

    assert calls <= 3
    assert search.data[0]["id"] == "fuelprice"
    assert verified.data["dataset"]["id"] == "fuelprice"
    assert verified.data["health"]["status"] == "fresh"
    assert verified.data["evidence"]["status"] == "fresh"
    assert verified.data["signed"] is True
    assert verified.data["bundle_ref"] and verified.data["verification_hint"]
