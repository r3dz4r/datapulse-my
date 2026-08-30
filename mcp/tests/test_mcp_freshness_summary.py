"""Integration coverage for the catalogue freshness glance tool."""

from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

import pytest
from fastmcp import Client


MCP_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(MCP_DIR))

import server  # noqa: E402


pytestmark = pytest.mark.anyio


async def test_freshness_summary_returns_four_counts_and_checked_at(monkeypatch: pytest.MonkeyPatch) -> None:
    health = {
        "checked_at": "2026-08-30T08:06:09Z",
        "datasets": [
            {"dataset_id": "fresh", "status": "fresh"},
            {"dataset_id": "aging", "status": "aging"},
            {"dataset_id": "stale", "status": "stale"},
            {"dataset_id": "reference", "status": "reference"},
        ],
    }

    async def load_health() -> dict:
        return health

    monkeypatch.setattr(server, "_load_health", load_health)
    async with Client(server.mcp) as client:
        result = await client.call_tool("get_freshness_summary", {})

    assert result.data["counts"] == {"fresh": 1, "aging": 1, "stale": 1, "reference": 1}
    assert sum(result.data["counts"].values()) == result.data["dataset_total"]
    assert datetime.fromisoformat(result.data["checked_at"].replace("Z", "+00:00"))
