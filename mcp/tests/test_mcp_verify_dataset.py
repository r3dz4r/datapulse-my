"""Integration coverage for the one-call verify-before-trust MCP path."""

from __future__ import annotations

import base64
import hashlib
import json
import re
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
    catalogue_loads = 0

    async def load_catalogue() -> tuple[dict, dict]:
        nonlocal catalogue_loads
        catalogue_loads += 1
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
    canonical_evidence = server.canonical_evidence_row(
        health["datasets"][0], manifest["datasets"][0]
    )
    expected_digest = (
        f"sha256:{hashlib.sha256(server.receipt_statement_bytes(canonical_evidence)).hexdigest()}"
    )
    assert re.fullmatch(r"sha256:[0-9a-f]{64}", result.data["receipt_digest"])
    assert result.data["receipt_digest"] == expected_digest
    assert result.data["bundle_ref"].endswith("/data/fuelprice.receipt.sigstore.json")
    assert result.data["verifier_output"] is None
    hint = result.data["verification_hint"]
    assert "tmpdir=$(mktemp -d)" in hint
    assert "trap 'rm -rf \"$tmpdir\"' EXIT" in hint
    assert "curl --fail --location --proto '=https' --proto-redir '=https' --silent --show-error" in hint
    assert result.data["bundle_ref"] in hint
    assert result.data["provenance_artifact_url"] in hint
    assert '"$tmpdir/receipt.sigstore.json"' in hint
    assert '"$tmpdir/receipt.evidence.json"' in hint
    assert f"--certificate-identity {server.SIGSTORE_CERTIFICATE_IDENTITY}" in hint
    assert f"--certificate-oidc-issuer {server.SIGSTORE_CERTIFICATE_OIDC_ISSUER}" in hint
    assert f"--type {server.PER_DATASET_RECEIPT_PREDICATE_TYPE}" in hint
    assert catalogue_loads == 1


async def test_verify_dataset_loads_published_catalogue_once(monkeypatch: pytest.MonkeyPatch) -> None:
    manifest, health = _catalogue()
    loads = 0

    async def load_catalogue() -> tuple[dict, dict]:
        nonlocal loads
        loads += 1
        return manifest, health

    async def fetch_bytes(_: str) -> bytes:
        return _bundle_for(manifest, health)

    monkeypatch.setattr(server, "_load_catalogue", load_catalogue)
    monkeypatch.setattr(server, "_fetch_bytes", fetch_bytes)
    monkeypatch.setattr(server, "_verify_sigstore_receipt", lambda **_: (True, "Verified OK"))

    result = await server.verify_dataset("fuelprice")

    assert loads == 1
    assert result["signed"] is True


def test_receipt_digest_changes_when_canonical_evidence_changes() -> None:
    manifest, health = _catalogue()
    canonical_evidence = server.canonical_evidence_row(
        health["datasets"][0], manifest["datasets"][0]
    )
    digest = hashlib.sha256(server.receipt_statement_bytes(canonical_evidence)).hexdigest()

    changed_evidence = {**canonical_evidence, "status": "stale"}
    changed_digest = hashlib.sha256(
        server.receipt_statement_bytes(changed_evidence)
    ).hexdigest()

    assert changed_digest != digest
