"""Integration coverage for the one-call verify-before-trust MCP path."""

from __future__ import annotations

import base64
import json
import sys
from pathlib import Path

import pytest
from fastmcp import Client


MCP_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(MCP_DIR))

import server  # noqa: E402


pytestmark = pytest.mark.anyio


def _catalogue() -> tuple[dict, dict]:
    row = {
        "dataset_id": "fuelprice", "last_checked": "2026-08-30T08:06:09Z",
        "status": "fresh", "message": "HTTP 200", "request_url": "https://example.test/fuel",
        "access_method": "direct", "http_status": 200, "content_length": 1,
        "last_modified": None, "content_freshness_date": "2026-08-30",
        "first_record_timestamp": "2026-08-30", "record_count": 1,
        "record_count_within_tolerance": True, "freshness_signal": "content-date-parse",
        "freshness_signal_source": "content_date_parse",
    }
    return (
        {"datasets": [{"id": "fuelprice", "licence": "CC BY 4.0", "name": "Fuel prices", "source": "Test source"}]},
        {"schema": "datapulse/v0.4/dataset-health", "checked_at": row["last_checked"], "datasets": [row]},
    )


def _bundle_for(manifest: dict, health: dict) -> bytes:
    row = health["datasets"][0]
    evidence = server.canonical_evidence_row(row, manifest["datasets"][0])
    statement = server.generate_per_dataset_statement("fuelprice", evidence)
    return json.dumps({
        "mediaType": "application/vnd.dev.sigstore.bundle.v0.3+json",
        "dsseEnvelope": {
            "payloadType": "application/vnd.in-toto+json",
            "payload": base64.b64encode(server.receipt_statement_bytes(statement)).decode(),
            "signatures": [{"sig": base64.b64encode(b"signature").decode()}],
        },
    }).encode()


async def test_verify_dataset_returns_signed_receipt_bundle(monkeypatch: pytest.MonkeyPatch) -> None:
    manifest, health = _catalogue()

    async def load_catalogue() -> tuple[dict, dict]:
        return manifest, health

    async def fetch_bytes(path: str) -> bytes:
        assert path == "data/fuelprice.receipt.sigstore.json"
        return _bundle_for(manifest, health)

    monkeypatch.setattr(server, "_load_catalogue", load_catalogue)
    monkeypatch.setattr(server, "_fetch_bytes", fetch_bytes)
    monkeypatch.setattr(server, "_verify_sigstore_receipt", lambda **_: (True, "Verified OK"))

    async with Client(server.mcp) as client:
        result = await client.call_tool("verify_dataset", {"dataset_id": "fuelprice"})

    assert result.data["signed"] is True
    assert result.data["health"]["dataset_id"] == "fuelprice"
    assert result.data["evidence"]["status"] == "fresh"
    assert result.data["bundle_ref"].endswith("/data/fuelprice.receipt.sigstore.json")
    assert result.data["verifier_output"] is None
