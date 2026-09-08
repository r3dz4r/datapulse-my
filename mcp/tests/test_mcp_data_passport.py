"""Read-only contract tests for the bounded Dataset Passport MCP tool."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastmcp import Client


MCP_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(MCP_DIR))
import server  # noqa: E402


pytestmark = pytest.mark.anyio


async def test_get_data_passport_returns_only_published_passport(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []

    async def fetch(path: str) -> dict:
        calls.append(path)
        if path == "datapulse.json":
            return {"datasets": [{"id": "fuelprice"}]}
        assert path == "data/passports/fuelprice.json"
        return {"schema": "datapulse/v1/dataset-passport", "identity": {"dataset_id": "fuelprice"}}

    monkeypatch.setattr(server, "_fetch_json", fetch)
    async with Client(server.mcp) as client:
        result = await client.call_tool("get_data_passport", {"dataset_id": "fuelprice"})
    assert result.data["evidence_available"] is True
    assert result.data["passport"]["schema"] == "datapulse/v1/dataset-passport"
    assert calls == ["datapulse.json", "data/passports/fuelprice.json"]


async def test_get_data_passport_returns_explicit_unknown_without_artifact_fetch(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fetch(path: str) -> dict:
        assert path == "datapulse.json"
        return {"datasets": [{"id": "fuelprice"}]}

    monkeypatch.setattr(server, "_fetch_json", fetch)
    assert await server.get_data_passport("not-a-dataset") == {
        "dataset_id": "not-a-dataset", "evidence_available": False, "error": "unknown_dataset_id"
    }


async def test_get_data_passport_rejects_oversized_artifact(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fetch(path: str) -> dict:
        if path == "datapulse.json":
            return {"datasets": [{"id": "fuelprice"}]}
        return {"schema": "datapulse/v1/dataset-passport", "padding": "x" * 262_145}

    monkeypatch.setattr(server, "_fetch_json", fetch)
    result = await server.get_data_passport("fuelprice")
    assert result["error"] == "passport_exceeds_response_bound"
