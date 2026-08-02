"""Read-only FastMCP server for the published DataPulse MY catalogue."""

from __future__ import annotations

import os
import re
from asyncio import gather
from typing import Any

import httpx
from fastmcp import FastMCP
from pydantic import Field
from typing_extensions import Annotated


DATA_BASE = os.getenv("DATA_BASE", "https://r3dz4r.github.io/datapulse-my").rstrip("/")
MCP_HOST = os.getenv("MCP_HOST", "127.0.0.1")
MCP_PORT = int(os.getenv("MCP_PORT", "8788"))
REQUEST_TIMEOUT_SECONDS = 30.0
CC_BY_4 = "Creative Commons Attribution 4.0"
OGL_MY = "Open Government Licence (Malaysia)"
LICENCE_ALIASES = {
    "cc by 4.0": CC_BY_4,
    "creative commons attribution 4.0": CC_BY_4,
    "ogl": OGL_MY,
    "open government licence (malaysia)": OGL_MY,
}

SEARCH_DESCRIPTION = (
    "Search DataPulse MY's 92 Malaysian public datasets by natural-language query. "
    "Filter by licence (e.g. 'CC BY 4.0', 'Open Government Licence (Malaysia)') or "
    "source ('OpenDOSM', 'data.gov.my', 'MET Malaysia', etc.). Returns ranked "
    "matches: id, title, source, licence, status, score. Use when an agent needs to "
    "find datasets covering a topic, by an agency, or under a specific licence."
)
GET_DATASET_DESCRIPTION = (
    "Return full detail for one dataset id, including its latest health status and "
    "last-verified timestamp. Use to fetch the provenance/citation metadata for a "
    "dataset found via search_datasets."
)

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


async def _load_catalogue() -> tuple[dict[str, Any], dict[str, Any]]:
    manifest, health = await gather(_load_manifest(), _load_health())
    return manifest, health


def _health_by_id(health: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {item["dataset_id"]: item for item in health.get("datasets", [])}


def _canonical_licence(licence: str) -> str:
    value = licence.strip()
    return LICENCE_ALIASES.get(value.casefold(), value)


def _search_score(entry: dict[str, Any], query: str) -> int:
    """Score query terms with title weighted above an optional description."""
    title = entry.get("name", "").casefold()
    description = entry.get("description", "").casefold()
    normalised_query = " ".join(query.casefold().split())
    terms = re.findall(r"[a-z0-9]+", normalised_query)
    score = sum(5 * title.count(term) + description.count(term) for term in terms)
    if normalised_query == " ".join(title.split()):
        score += 100
    elif normalised_query and normalised_query in title:
        score += 15
    return score


@mcp.tool(description=SEARCH_DESCRIPTION)
async def search_datasets(
    query: Annotated[str, Field(min_length=1)],
    licence: str | None = None,
    source: str | None = None,
    limit: Annotated[int, Field(ge=1, le=50)] = 10,
) -> list[dict[str, Any]]:
    """Rank live manifest matches.

    Known limitation: the current published manifest has no ``description``
    field, so scoring uses titles only until descriptions are published.
    """
    manifest, health = await _load_catalogue()
    health_records = _health_by_id(health)
    requested_licence = _canonical_licence(licence) if licence else None
    requested_source = source.casefold().strip() if source else None
    matches: list[dict[str, Any]] = []

    for entry in manifest.get("datasets", []):
        if requested_licence and entry.get("licence", "").casefold() != requested_licence.casefold():
            continue
        if requested_source and requested_source not in entry.get("source", "").casefold():
            continue
        score = _search_score(entry, query)
        if score == 0:
            continue
        health_record = health_records.get(entry["id"], {})
        matches.append(
            {
                "id": entry["id"],
                "title": entry["name"],
                "source": entry["source"],
                "licence": entry["licence"],
                "status": health_record.get("status", "missing"),
                "score": score,
            }
        )

    matches.sort(key=lambda item: (-item["score"], item["title"], item["id"]))
    return matches[:limit]


@mcp.tool(description=GET_DATASET_DESCRIPTION)
async def get_dataset(dataset_id: str) -> dict[str, Any]:
    """Merge one exact manifest entry with its current health record."""
    manifest, health = await _load_catalogue()
    entry = next(
        (item for item in manifest.get("datasets", []) if item.get("id") == dataset_id),
        None,
    )
    if entry is None:
        raise ValueError(f"Unknown dataset id: {dataset_id}")

    health_record = _health_by_id(health).get(
        dataset_id,
        {
            "dataset_id": dataset_id,
            "status": "missing",
            "message": "Missing from latest health snapshot",
        },
    )
    return {
        **entry,
        **health_record,
        "last_verified": health.get("checked_at"),
        "schema_version": health.get("schema"),
    }


if __name__ == "__main__":
    mcp.run(transport="http", host=MCP_HOST, port=MCP_PORT)
