"""Live-data integration tests for the DataPulse MY FastMCP server."""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import httpx
import pytest
from fastmcp import Client


MCP_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(MCP_DIR))

import server  # noqa: E402


pytestmark = pytest.mark.anyio


@pytest.fixture(scope="module")
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture(scope="module")
async def live_data() -> tuple[dict, dict]:
    async with httpx.AsyncClient(timeout=30.0) as client:
        manifest_response = await client.get(f"{server.DATA_BASE}/datapulse.json")
        health_response = await client.get(f"{server.DATA_BASE}/health/latest.json")
        manifest_response.raise_for_status()
        health_response.raise_for_status()
        return manifest_response.json(), health_response.json()


async def test_search_datasets_returns_ranked_live_results() -> None:
    async with Client(server.mcp) as client:
        result = await client.call_tool(
            "search_datasets",
            {"query": "labour state", "licence": "CC BY 4.0", "source": "OpenDOSM"},
        )

    assert result.data
    assert len(result.data) <= 10
    assert set(result.data[0]) == {
        "id",
        "title",
        "source",
        "licence",
        "status",
        "score",
    }
    scores = [item["score"] for item in result.data]
    assert scores == sorted(scores, reverse=True)
    assert all("OpenDOSM" in item["source"] for item in result.data)
    assert all(item["licence"] == "Creative Commons Attribution 4.0" for item in result.data)


async def test_search_datasets_exact_title_scores_above_partial() -> None:
    async with Client(server.mcp) as client:
        exact = await client.call_tool(
            "search_datasets", {"query": "Malaysian Fuel Prices"}
        )
        partial = await client.call_tool("search_datasets", {"query": "Fuel Prices"})

    exact_match = next(item for item in exact.data if item["id"] == "fuelprice")
    partial_match = next(item for item in partial.data if item["id"] == "fuelprice")
    assert exact_match["score"] > partial_match["score"]
    assert exact.data[0]["id"] == "fuelprice"


async def test_get_dataset_merges_manifest_and_health(live_data: tuple[dict, dict]) -> None:
    manifest, health = live_data
    dataset_id = manifest["datasets"][0]["id"]

    async with Client(server.mcp) as client:
        result = await client.call_tool("get_dataset", {"dataset_id": dataset_id})

    assert result.data["id"] == dataset_id
    assert result.data["name"]
    assert result.data["status"]
    assert result.data["last_verified"] == health["checked_at"]


async def test_get_dataset_surfaces_trust_taxonomy_details(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest = {
        "datasets": [
            {"id": "sample", "name": "Sample", "expected_record_count": 100}
        ]
    }
    health = {
        "schema": "datapulse/v0.2/dataset-health",
        "checked_at": "2026-08-03T00:00:00Z",
        "datasets": [
            {
                "dataset_id": "sample",
                "status": "aging",
                "staleness_days": 12,
                "access_dependency": "direct",
                "expected_record_count": 100,
            }
        ],
    }

    async def fake_load_catalogue() -> tuple[dict, dict]:
        return manifest, health

    monkeypatch.setattr(server, "_load_catalogue", fake_load_catalogue)

    async with Client(server.mcp) as client:
        result = await client.call_tool("get_dataset", {"dataset_id": "sample"})

    assert result.data["status"] == "aging"
    assert result.data["staleness_days"] == 12
    assert result.data["access_dependency"] == "direct"
    assert result.data["expected_record_count"] == 100


async def test_find_stale_matches_live_health(live_data: tuple[dict, dict]) -> None:
    manifest, health = live_data
    checked_at = datetime.fromisoformat(health["checked_at"].replace("Z", "+00:00"))
    snapshot_age = (datetime.now(timezone.utc) - checked_at).total_seconds()
    health_by_id = {item["dataset_id"]: item for item in health["datasets"]}
    expected_ids = {
        item["id"]
        for item in manifest["datasets"]
        if item["id"] not in health_by_id
        or health_by_id[item["id"]].get("status") in {"aging", "stale", "degraded"}
        or snapshot_age > 24 * 3600
    }

    async with Client(server.mcp) as client:
        result = await client.call_tool("find_stale", {"max_age_hours": 24})

    assert {item["id"] for item in result.data} == expected_ids
    assert all(
        set(item)
        == {
            "id",
            "status",
            "message",
            "age_seconds",
            "staleness_days",
            "access_dependency",
            "expected_record_count",
        }
        for item in result.data
    )


async def test_find_stale_returns_only_freshness_or_schema_risks(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    statuses = [
        "fresh",
        "aging",
        "stale",
        "degraded",
        "browser-dependent",
        "unreachable",
        "unknown",
    ]
    manifest = {
        "datasets": [
            {"id": status, "name": status, "expected_record_count": 10}
            for status in statuses
        ]
    }
    health = {
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "datasets": [
            {
                "dataset_id": status,
                "status": status,
                "message": f"{status} signal",
                "staleness_days": index,
                "access_dependency": "browser" if status == "browser-dependent" else "direct",
                "expected_record_count": 10,
            }
            for index, status in enumerate(statuses)
        ],
    }

    async def fake_load_catalogue() -> tuple[dict, dict]:
        return manifest, health

    monkeypatch.setattr(server, "_load_catalogue", fake_load_catalogue)

    async with Client(server.mcp) as client:
        result = await client.call_tool("find_stale", {"max_age_hours": 24})

    assert [item["status"] for item in result.data] == ["aging", "stale", "degraded"]
    assert all(
        {"staleness_days", "access_dependency", "expected_record_count"} <= set(item)
        for item in result.data
    )


async def test_get_provenance_returns_citation_fields(live_data: tuple[dict, dict]) -> None:
    manifest, health = live_data
    dataset_ids = [item["id"] for item in manifest["datasets"][:2]]

    async with Client(server.mcp) as client:
        result = await client.call_tool("get_provenance", {"dataset_ids": dataset_ids})

    assert [item["id"] for item in result.data] == dataset_ids
    assert all(
        set(item)
        == {
            "id",
            "steward",
            "source",
            "licence",
            "licence_url",
            "url",
            "access_method",
            "last_verified",
            "schema_version",
        }
        for item in result.data
    )
    assert all(item["last_verified"] == health["checked_at"] for item in result.data)
    assert all(item["licence_url"].startswith("https://") for item in result.data)


async def test_find_by_licence_returns_summary(live_data: tuple[dict, dict]) -> None:
    manifest, _ = live_data
    expected_count = sum(
        item["licence"] == "Creative Commons Attribution 4.0"
        for item in manifest["datasets"]
    )

    async with Client(server.mcp) as client:
        result = await client.call_tool("find_by_licence", {"licence": "CC BY 4.0"})

    assert result.data["licence"] == "Creative Commons Attribution 4.0"
    assert result.data["count"] == expected_count
    assert len(result.data["datasets"]) == expected_count
    assert all(
        set(item) == {"id", "title", "source", "status"}
        for item in result.data["datasets"]
    )


async def test_index_resource_returns_all_live_datasets(live_data: tuple[dict, dict]) -> None:
    manifest, _ = live_data

    async with Client(server.mcp) as client:
        result = await client.read_resource("datapulse://index")

    payload = json.loads(result[0].text)
    assert len(payload) == len(manifest["datasets"]) == 92
    assert all(
        set(item) == {"id", "status", "title", "source", "licence"}
        for item in payload
    )


async def test_licences_resource_returns_live_counts(live_data: tuple[dict, dict]) -> None:
    manifest, _ = live_data
    expected = {
        licence: sum(item["licence"] == licence for item in manifest["datasets"])
        for licence in {item["licence"] for item in manifest["datasets"]}
    }

    async with Client(server.mcp) as client:
        result = await client.read_resource("datapulse://licences")

    assert json.loads(result[0].text) == expected


async def test_dataset_resource_template_returns_full_manifest_entry(
    live_data: tuple[dict, dict],
) -> None:
    manifest, _ = live_data
    expected = manifest["datasets"][0]

    async with Client(server.mcp) as client:
        result = await client.read_resource(f"datapulse://{expected['id']}")

    assert json.loads(result[0].text) == expected
