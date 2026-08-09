"""Read-only FastMCP server for the published DataPulse MY catalogue."""

from __future__ import annotations

import os
import re
import json
from asyncio import gather
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx
import mcp.types as mcp_types
from fastmcp import FastMCP
from mcp.types import Implementation as MCPImplementation
from pydantic import Field
from fastmcp.tools import FunctionTool
from typing_extensions import Annotated


# T29 (2026-08-09): source version marker. Set by `scripts/bump_mcp_source_version.py`
# at the start of each release build. The deployed service exposes this via the
# JSON-RPC `initialize` response's `serverInfo.version` field, alongside (or
# replacing) the legacy "v3.4.5" hand-maintained version. The verify script
# reads this field and compares to the current repo HEAD to detect drift.
SOURCE_COMMIT_SHA = os.getenv("DATAPULSE_MCP_SOURCE_SHA", "7d96b68ad62220672f47cdc5dccc6c6a97f7f9a4")
SOURCE_COMMIT_DATE = os.getenv("DATAPULSE_MCP_SOURCE_DATE", "2026-08-09")
SOURCE_VERSION_STRING = (
    f"v3.4.5+{SOURCE_COMMIT_SHA[:7]}"
    if SOURCE_COMMIT_SHA != "dev"
    else "v3.4.5-dev"
)

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
LICENCE_URLS = {
    CC_BY_4: "https://creativecommons.org/licenses/by/4.0/",
    OGL_MY: "https://www.data.gov.my/pages/terms-of-use",
}


def _manifest_dataset_count(manifest_path: Path | None = None) -> int:
    """Read the published dataset total for use in agent-facing metadata."""
    if manifest_path is None:
        manifest_path = Path(__file__).resolve().parents[1] / "datapulse.json"

    if manifest_path.is_file():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    else:
        response = httpx.get(
            f"{DATA_BASE}/datapulse.json",
            timeout=REQUEST_TIMEOUT_SECONDS,
            follow_redirects=True,
        )
        response.raise_for_status()
        manifest = response.json()

    datasets = manifest.get("datasets")
    if not isinstance(datasets, list):
        raise ValueError("datapulse.json must contain a datasets array")
    return len(datasets)


DATASET_COUNT = _manifest_dataset_count()
SEARCH_DESCRIPTION = (
    f"Search DataPulse MY's {DATASET_COUNT} Malaysian public datasets by "
    "natural-language query. "
    "Filter by licence (e.g. 'CC BY 4.0', 'Open Government Licence (Malaysia)') or "
    "source ('OpenDOSM', 'data.gov.my', 'MET Malaysia', etc.). Returns ranked "
    "matches: id, title, source, licence, status, score. Use when an agent needs to "
    "find datasets covering a topic, by an agency, or under a specific licence."
)
GET_DATASET_DESCRIPTION = (
    "Return full detail for one dataset id, including its latest health status and "
    "last-verified timestamp, content_freshness_date, and freshness_signal_source "
    "(last_modified, content_parse, or none). Use to fetch the provenance/citation "
    "metadata for a dataset found via search_datasets and distinguish "
    "unknown-freshness from proven stale data."
)
FIND_STALE_DESCRIPTION = (
    "Return datasets whose status is aging, stale, or degraded, plus datasets missing "
    "from the latest health snapshot. Use when an agent needs to know which data has "
    "a freshness or schema-validity risk."
)
GET_PROVENANCE_DESCRIPTION = (
    "Return citation-ready provenance metadata for the listed dataset ids: source "
    "steward, licence (with URL), source URL, access method (curl/Camofox), "
    "last-verified timestamp. Use when an agent needs to cite DataPulse MY data in "
    "a response and must include proper attribution and licence."
)
FIND_BY_LICENCE_DESCRIPTION = (
    "Return all datasets with the given licence, summarised. Use to enumerate what's "
    "available under a specific licence for compliance/reuse scoping."
)

class SourceImplementation(MCPImplementation):
    """Factory type for protocol server information with source markers."""

    def __new__(cls, **values: Any) -> MCPImplementation:
        return MCPImplementation(
            source_commit_sha=SOURCE_COMMIT_SHA,
            source_commit_date=SOURCE_COMMIT_DATE,
            **values,
        )


# The MCP SDK constructs serverInfo internally, so extend the protocol model it uses.
mcp_types.Implementation = SourceImplementation


mcp = FastMCP(
    "DataPulse MY",
    version=SOURCE_VERSION_STRING,
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
    query: Annotated[
        str,
        Field(
            min_length=1,
            description=(
                "Free-text search terms; natural language is allowed, e.g. "
                "'inflation cpi'."
            ),
        ),
    ],
    licence: Annotated[
        str | None,
        Field(
            description=(
                "Optional exact licence name or supported alias, e.g. 'CC BY 4.0'."
            )
        ),
    ] = None,
    source: Annotated[
        str | None,
        Field(
            description=(
                "Optional case-insensitive source-name substring, e.g. 'OpenDOSM'."
            )
        ),
    ] = None,
    limit: Annotated[
        int,
        Field(
            ge=1,
            le=50,
            description="Maximum ranked matches to return; integer from 1 to 50, e.g. 10.",
        ),
    ] = 10,
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
                "status": health_record.get("status", "unknown"),
                "score": score,
            }
        )

    matches.sort(
        key=lambda item: (
            -item["score"],
            0 if item["id"].startswith("gtfs_static_") else 1,
            item["title"],
            item["id"],
        )
    )
    return matches[:limit]


@mcp.tool(description=GET_DATASET_DESCRIPTION)
async def get_dataset(
    dataset_id: Annotated[
        str,
        Field(
            min_length=1,
            description=(
                "Canonical dataset identifier, e.g. 'dosm_cpi_state'. See the "
                "registry catalogue for valid IDs."
            ),
        ),
    ],
) -> dict[str, Any]:
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
            "status": "unknown",
            "message": "Missing from latest health snapshot",
            "staleness_days": None,
            "access_dependency": "direct",
            "expected_record_count": entry.get("expected_record_count"),
            "content_freshness_date": None,
            "freshness_signal_source": "none",
        },
    )
    content_freshness_date = health_record.get("content_freshness_date")
    freshness_signal_source = health_record.get("freshness_signal_source")
    source_aliases = {
        "last_modified": "last_modified_header",
        "content_parse": "content_date_parse",
    }
    freshness_signal_source = source_aliases.get(
        freshness_signal_source, freshness_signal_source
    )
    if freshness_signal_source not in {
        "last_modified_header",
        "content_date_parse",
        "none",
    }:
        if health_record.get("last_modified"):
            freshness_signal_source = "last_modified_header"
        elif content_freshness_date:
            freshness_signal_source = "content_date_parse"
        else:
            freshness_signal_source = "none"
    return {
        **entry,
        "status": "unknown",
        "staleness_days": None,
        "access_dependency": (
            "browser" if health_record.get("access_method") == "Camofox" else "direct"
        ),
        "expected_record_count": entry.get("expected_record_count"),
        **health_record,
        "content_freshness_date": content_freshness_date,
        "freshness_signal_source": freshness_signal_source,
        "last_verified": health.get("checked_at"),
        "schema_version": health.get("schema"),
    }


def _snapshot_age_seconds(checked_at: str | None) -> int | None:
    if not checked_at:
        return None
    checked = datetime.fromisoformat(checked_at.replace("Z", "+00:00"))
    return max(0, int((datetime.now(timezone.utc) - checked).total_seconds()))


async def find_stale(
    max_age_hours: Annotated[
        int,
        Field(
            ge=0,
            description=(
                "Maximum acceptable age of the latest health check in whole hours; "
                "non-negative integer, e.g. 72."
            ),
        ),
    ] = 24,
) -> list[dict[str, Any]]:
    """Return datasets with explicit freshness or schema-validity risks."""
    manifest, health = await _load_catalogue()
    health_records = _health_by_id(health)
    age_seconds = _snapshot_age_seconds(health.get("checked_at"))
    snapshot_is_old = age_seconds is None or age_seconds > max_age_hours * 3600
    stale: list[dict[str, Any]] = []

    for entry in manifest.get("datasets", []):
        record = health_records.get(entry["id"])
        if record is None:
            stale.append(
                {
                    "id": entry["id"],
                    "status": "unknown",
                    "message": "Missing from latest health snapshot",
                    "age_seconds": age_seconds,
                    "staleness_days": None,
                    "access_dependency": "direct",
                    "expected_record_count": entry.get("expected_record_count"),
                }
            )
        elif record.get("status") in {"aging", "stale", "degraded"} or snapshot_is_old:
            message = record.get("message", "No health message")
            if snapshot_is_old and record.get("status") not in {"aging", "stale", "degraded"}:
                message = "Latest health snapshot is older than the requested maximum age"
            stale.append(
                {
                    "id": entry["id"],
                    "status": record.get("status", "unknown"),
                    "message": message,
                    "age_seconds": age_seconds,
                    "staleness_days": record.get("staleness_days"),
                    "access_dependency": record.get("access_dependency", "direct"),
                    "expected_record_count": record.get(
                        "expected_record_count", entry.get("expected_record_count")
                    ),
                }
            )
    return stale


_find_stale_tool = FunctionTool.from_function(
    find_stale, description=FIND_STALE_DESCRIPTION
)
_find_stale_tool.parameters.setdefault("required", [])
mcp.add_tool(_find_stale_tool)


@mcp.tool(description=GET_PROVENANCE_DESCRIPTION)
async def get_provenance(
    dataset_ids: Annotated[
        list[str],
        Field(
            min_length=1,
            max_length=50,
            description=(
                "JSON array of 1 to 50 canonical dataset IDs, e.g. "
                "['fuelprice', 'pricecatcher']."
            ),
            examples=[["fuelprice", "pricecatcher"]],
        ),
    ],
) -> list[dict[str, Any]]:
    """Build provenance from manifest and health fields without inference."""
    manifest, health = await _load_catalogue()
    manifest_by_id = {item["id"]: item for item in manifest.get("datasets", [])}
    health_records = _health_by_id(health)
    unknown_ids = [dataset_id for dataset_id in dataset_ids if dataset_id not in manifest_by_id]
    if unknown_ids:
        raise ValueError(f"Unknown dataset id(s): {', '.join(unknown_ids)}")

    provenance = []
    for dataset_id in dataset_ids:
        entry = manifest_by_id[dataset_id]
        health_record = health_records.get(dataset_id, {})
        provenance.append(
            {
                "id": dataset_id,
                "steward": entry.get("steward"),
                "source": entry.get("source"),
                "licence": entry.get("licence"),
                "licence_url": LICENCE_URLS.get(entry.get("licence")),
                "url": entry.get("url"),
                "access_method": health_record.get("access_method", "unknown"),
                "last_verified": health.get("checked_at") if health_record else None,
                "schema_version": health.get("schema"),
            }
        )
    return provenance


@mcp.tool(description=FIND_BY_LICENCE_DESCRIPTION)
async def find_by_licence(
    licence: Annotated[
        str,
        Field(
            min_length=1,
            description=(
                "Exact licence name or supported alias, e.g. "
                "'Creative Commons Attribution 4.0'."
            ),
        ),
    ],
) -> dict[str, Any]:
    """Return a canonical licence label, count, and dataset summaries."""
    manifest, health = await _load_catalogue()
    canonical_licence = _canonical_licence(licence)
    health_records = _health_by_id(health)
    datasets = [
        {
            "id": entry["id"],
            "title": entry["name"],
            "source": entry["source"],
            "status": health_records.get(entry["id"], {}).get("status", "unknown"),
        }
        for entry in manifest.get("datasets", [])
        if entry.get("licence", "").casefold() == canonical_licence.casefold()
    ]
    return {
        "licence": canonical_licence,
        "count": len(datasets),
        "datasets": datasets,
    }


@mcp.resource(
    "datapulse://index",
    description=(
        "Read first; lightweight list of all DataPulse MY dataset ids with current "
        "status, title, source, licence, and namespace."
    ),
    mime_type="application/json",
)
async def dataset_index() -> str:
    """Return the lightweight live catalogue index as JSON."""
    manifest, health = await _load_catalogue()
    health_records = _health_by_id(health)
    index = [
        {
            "id": entry["id"],
            "status": health_records.get(entry["id"], {}).get("status", "unknown"),
            "title": entry["name"],
            "source": entry["source"],
            "licence": entry["licence"],
            "namespace": entry.get("namespace", "other"),
        }
        for entry in manifest.get("datasets", [])
    ]
    return json.dumps(index, ensure_ascii=False)


@mcp.resource(
    "datapulse://licences",
    description="Live count of DataPulse MY datasets grouped by licence.",
    mime_type="application/json",
)
async def licence_summary() -> str:
    """Return a licence-to-dataset-count JSON object."""
    manifest = await _load_manifest()
    summary: dict[str, int] = {}
    for entry in manifest.get("datasets", []):
        licence = entry["licence"]
        summary[licence] = summary.get(licence, 0) + 1
    return json.dumps(summary, ensure_ascii=False, sort_keys=True)


@mcp.resource(
    "datapulse://{dataset_id}",
    description="Full published manifest entry for one exact DataPulse MY dataset id.",
    mime_type="application/json",
)
async def dataset_resource(dataset_id: str) -> str:
    """Return one on-demand manifest entry without adding inferred fields."""
    manifest = await _load_manifest()
    entry = next(
        (item for item in manifest.get("datasets", []) if item.get("id") == dataset_id),
        None,
    )
    if entry is None:
        raise ValueError(f"Unknown dataset id: {dataset_id}")
    return json.dumps(entry, ensure_ascii=False)


if __name__ == "__main__":
    mcp.run(transport="http", host=MCP_HOST, port=MCP_PORT)
