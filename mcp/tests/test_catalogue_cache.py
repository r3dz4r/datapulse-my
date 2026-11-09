from __future__ import annotations

import sys
from pathlib import Path

from fastmcp import Client

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import server

import pytest


pytestmark = pytest.mark.anyio


async def test_catalogue_cache_ttl_retry_identity_and_tool_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    server._catalogue_cache_value = None
    server._catalogue_cache_base = None
    server._catalogue_cache_loaded_at = 0.0
    now = [100.0]
    monkeypatch.setattr(server, "monotonic", lambda: now[0])
    monkeypatch.setattr(server, "DATA_BASE", "https://cache-test.example")
    calls: list[str] = []
    fail_health = [True]
    manifest = {
        "datasets": [
            {"id": "sample", "name": "Sample dataset", "source": "Test", "licence": "CC BY 4.0"}
        ]
    }
    health = {"datasets": [{"dataset_id": "sample", "status": "fresh"}]}

    async def fetch(path: str) -> dict:
        calls.append(path)
        if path == "health/latest.json" and fail_health[0]:
            fail_health[0] = False
            raise RuntimeError("temporary fetch failure")
        return manifest if path == "datapulse.json" else health

    monkeypatch.setattr(server, "_fetch_json", fetch)
    with pytest.raises(RuntimeError, match="temporary fetch failure"):
        await server._load_catalogue()

    first = await server._load_catalogue()
    assert calls == ["datapulse.json", "health/latest.json", "datapulse.json", "health/latest.json"]
    assert await server._load_catalogue() is first
    assert calls.count("datapulse.json") == calls.count("health/latest.json") == 2

    async with Client(server.mcp) as client:
        before_expiry = await client.call_tool("find_by_licence", {"licence": "CC BY 4.0"})

    now[0] += server.CATALOGUE_CACHE_TTL_SECONDS + 1
    second = await server._load_catalogue()
    assert second is not first
    async with Client(server.mcp) as client:
        after_expiry = await client.call_tool("find_by_licence", {"licence": "CC BY 4.0"})

    assert calls.count("datapulse.json") == calls.count("health/latest.json") == 3
    assert before_expiry.data == after_expiry.data
