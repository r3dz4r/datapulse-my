"""Integration coverage for the read-only citation resource template."""

from __future__ import annotations

import base64
import json
import hashlib
import re
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
                    "message": "HTTP 200",
                    "request_url": "https://api.data.gov.my/fuelprice",
                    "access_method": "direct",
                    "http_status": 200,
                    "content_length": 1,
                    "last_modified": None,
                    "content_freshness_date": "2026-09-06",
                    "first_record_timestamp": "2026-09-06",
                    "record_count": 1,
                    "record_count_within_tolerance": True,
                    "freshness_signal": "content-date-parse",
                    "freshness_signal_source": "content_date_parse",
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
    assert len(tools.tools) == 19
    assert len(resources.resources) == 8
    citation_template = next(
        template
        for template in templates.resource_templates
        if template.uri_template == "datapulse://citation/{dataset_id}"
    )
    assert "receipt/evidence digest when available" in citation_template.description
    assert "unknown-freshness" in citation_template.description


async def test_citation_resource_returns_canonical_evidence_fields(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest, health = _catalogue()

    async def load_catalogue() -> tuple[dict, dict]:
        return manifest, health

    monkeypatch.setattr(server, "_load_catalogue", load_catalogue)

    async with Client(server.mcp) as client:
        result = await client.read_resource("datapulse://citation/fuelprice")

    citation = json.loads(result[0].text)
    canonical_evidence = server.canonical_evidence_row(
        health["datasets"][0], manifest["datasets"][0]
    )
    expected_digest = (
        f"sha256:{hashlib.sha256(server.receipt_statement_bytes(canonical_evidence)).hexdigest()}"
    )
    assert re.fullmatch(r"sha256:[0-9a-f]{64}", citation["receipt_digest"])
    assert citation["receipt_digest"] == expected_digest
    assert citation == {
        "schema": "datapulse/v1/citation",
        "dataset_id": "fuelprice",
        "evidence_url": "https://www.data-pulse.my/data/fuelprice.md",
        "receipt_evidence_url": "https://www.data-pulse.my/data/fuelprice.receipt.evidence.json",
        "receipt_digest": expected_digest,
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
        "citation_guidance": (
            "Cite dataset_id, source_url or evidence_url, observed_at, status or "
            "datapulse_verdict, licence/attribution, and a receipt/evidence digest when available."
        ),
    }


async def test_citation_receipt_digest_matches_verify_dataset(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest, health = _catalogue()

    async def load_catalogue() -> tuple[dict, dict]:
        return manifest, health

    async def fetch_bytes(path: str) -> bytes:
        assert path == "data/fuelprice.receipt.sigstore.json"
        evidence = server.canonical_evidence_row(health["datasets"][0], manifest["datasets"][0])
        statement = server.generate_per_dataset_statement("fuelprice", evidence)
        return json.dumps(
            {
                "mediaType": "application/vnd.dev.sigstore.bundle.v0.3+json",
                "dsseEnvelope": {
                    "payloadType": "application/vnd.in-toto+json",
                    "payload": base64.b64encode(
                        server.receipt_statement_bytes(statement)
                    ).decode(),
                    "signatures": [{"sig": base64.b64encode(b"signature").decode()}],
                },
            }
        ).encode()

    monkeypatch.setattr(server, "_load_catalogue", load_catalogue)
    monkeypatch.setattr(server, "_fetch_bytes", fetch_bytes)
    monkeypatch.setattr(server, "_verify_sigstore_receipt", lambda **_: (True, "Verified OK"))

    async with Client(server.mcp) as client:
        verification = await client.call_tool("verify_dataset", {"dataset_id": "fuelprice"})
        citation = await client.read_resource("datapulse://citation/fuelprice")

    assert json.loads(citation[0].text)["receipt_digest"] == verification.data["receipt_digest"]


async def test_citation_resource_falls_back_to_schema_fingerprint(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest, health = _catalogue()
    health["datasets"][0]["first_row_hash"] = None
    health["datasets"][0]["schema_fingerprint"] = "schema-v1:abc123"

    async def load_catalogue() -> tuple[dict, dict]:
        return manifest, health

    monkeypatch.setattr(server, "_load_catalogue", load_catalogue)

    async with Client(server.mcp) as client:
        result = await client.read_resource("datapulse://citation/fuelprice")

    assert json.loads(result[0].text)["fingerprint"] == "schema-v1:abc123"


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
