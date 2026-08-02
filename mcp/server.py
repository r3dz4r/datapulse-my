"""Read-only FastMCP server for the published DataPulse MY catalogue."""

from __future__ import annotations

import os
from typing import Any

import httpx
from fastmcp import FastMCP


DATA_BASE = os.getenv("DATA_BASE", "https://r3dz4r.github.io/datapulse-my").rstrip("/")
MCP_HOST = os.getenv("MCP_HOST", "127.0.0.1")
MCP_PORT = int(os.getenv("MCP_PORT", "8788"))
REQUEST_TIMEOUT_SECONDS = 30.0

mcp = FastMCP(
    "DataPulse MY",
    instructions="Read-only access to DataPulse MY's Malaysian public dataset catalogue.",
)


async def _fetch_json(path: str) -> dict[str, Any]:
    """Fetch one JSON document from the published DataPulse MY site."""
    async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT_SECONDS) as client:
        response = await client.get(f"{DATA_BASE}/{path.lstrip('/')}")
        response.raise_for_status()
        return response.json()


async def _load_manifest() -> dict[str, Any]:
    return await _fetch_json("datapulse.json")


async def _load_health() -> dict[str, Any]:
    return await _fetch_json("health/latest.json")


if __name__ == "__main__":
    mcp.run(transport="http", host=MCP_HOST, port=MCP_PORT)
