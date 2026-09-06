"""Integration coverage for the read-only citation resource template."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
from fastmcp import Client


MCP_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(MCP_DIR))

import server  # noqa: E402


pytestmark = pytest.mark.anyio


def _catalogue(status: str = "fresh") -> tuple[dict, dict]:
    return (
        {
            "datasets": [
                {
                    "id": "fuelprice",
                    "url": "https://api.data.gov.my/fuelprice",
                    "licence": "CC BY 4.0",
                }
            ]
        },
        {
            "datasets": [
                {
                    "dataset_id": "fuelprice",
                    "last_checked": "2026-09-06T01:02:03Z",
                    "status": status,
                    "first_row_hash": "shape-v1:abc123",
                }
            ]
        },
    )


async def test_citation_resource_is_discoverable_and_preserves_surface_counts() -> None:
    async with Client(server.mcp) as client:
        templates = await client.list_resource_templates_mcp()
        tools = await client.list_tools_mcp()
        resources = await client.list_resources_mcp()

    assert {template.uri_template for template in templates.resource_templates} == {
        "datapulse://{dataset_id}",
        "datapulse://citation/{dataset_id}",
    }
    assert len(tools.tools) == 18
    assert len(resources.resources) == 8


async def test_citation_resource_returns_canonical_evidence_fields(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest, health = _catalogue()

    async def load_catalogue() -> tuple[dict, dict]:
        return manifest, health

    monkeypatch.setattr(server, "_load_catalogue", load_catalogue)

    async with Client(server.mcp) as client:
        result = await client.read_resource("datapulse://citation/fuelprice")

    assert json.loads(result[0].text) == {
        "schema": "datapulse/v1/citation",
        "dataset_id": "fuelprice",
        "evidence_url": "https://www.data-pulse.my/data/fuelprice.md",
        "observed_at": "2026-09-06T01:02:03Z",
        "source_url": "https://api.data.gov.my/fuelprice",
        "status": "fresh",
        "methodology_version": None,
        "licence": "CC BY 4.0",
        "fingerprint": "shape-v1:abc123",
        "datapulse_verdict": "USE",
        "limitations": (
            "DataPulse observes source conditions; it does not certify substantive truth, "
            "legal compliance, or regulatory outcomes."
        ),
    }


@pytest.mark.parametrize(
    ("status", "verdict"),
    [("aging", "WARN"), ("reference", "REFERENCE-USE"), ("stale", "STOP")],
)
async def test_citation_resource_maps_status_to_fixed_verdict(
    monkeypatch: pytest.MonkeyPatch, status: str, verdict: str
) -> None:
    manifest, health = _catalogue(status)

    async def load_catalogue() -> tuple[dict, dict]:
        return manifest, health

    monkeypatch.setattr(server, "_load_catalogue", load_catalogue)

    async with Client(server.mcp) as client:
        result = await client.read_resource("datapulse://citation/fuelprice")

    assert json.loads(result[0].text)["datapulse_verdict"] == verdict


async def test_citation_resource_rejects_unknown_dataset(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest, health = _catalogue()

    async def load_catalogue() -> tuple[dict, dict]:
        return manifest, health

    monkeypatch.setattr(server, "_load_catalogue", load_catalogue)

    with pytest.raises(ValueError, match="^Unknown dataset id: missing$"):
        await server.citation_resource("missing")
