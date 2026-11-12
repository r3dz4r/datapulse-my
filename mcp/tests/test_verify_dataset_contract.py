"""verify_dataset returns an honest, self-describing verdict for every outcome.

The coverage manifest and the bundle fetch are faked in memory; no test touches
the network or a real cosign.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import httpx
import pytest
from fastmcp import Client


MCP_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(MCP_DIR))

import server  # noqa: E402
from test_mcp_verify_dataset import _bundle_for, _catalogue  # noqa: E402


pytestmark = pytest.mark.anyio

LEGACY_KEYS = {
    "dataset_id", "dataset", "health", "evidence", "receipt_digest", "signed",
    "verifier_output", "bundle_ref", "statement_ref", "certificate_identity",
    "certificate_oidc_issuer", "verification_hint", "provenance_artifact_url",
}
REF_KEYS = ("bundle_ref", "statement_ref", "provenance_artifact_url")


def _coverage(*, signed: list[str], unsigned: list[dict[str, str]] | None = None) -> dict[str, Any]:
    unsigned = unsigned or []
    return {
        "schema": "datapulse/v1/receipt-coverage",
        "generated_at": "2026-11-13T00:00:00Z",
        "total": len(signed) + len(unsigned),
        "signed_count": len(signed),
        "signed": signed,
        "unsigned": unsigned,
    }


def _not_found(path: str) -> httpx.HTTPStatusError:
    request = httpx.Request("GET", f"https://example.test/{path}")
    return httpx.HTTPStatusError("404", request=request, response=httpx.Response(404, request=request))


class Fakes:
    """In-memory published site: one coverage manifest and one bundle source."""

    def __init__(self, monkeypatch: pytest.MonkeyPatch) -> None:
        self.manifest, self.health = _catalogue()
        self.coverage: dict[str, Any] | Exception = _coverage(signed=["fuelprice"])
        self.bundle: bytes | Exception = _bundle_for(self.manifest, self.health)
        self.verifier: tuple[bool, str] = (True, "Verified OK")
        self.bundle_fetches: list[str] = []
        self.verifier_calls = 0

        async def load_catalogue() -> tuple[dict, dict]:
            return self.manifest, self.health

        async def fetch_json(path: str) -> dict:
            assert path == "data/receipts-manifest.json", path
            if isinstance(self.coverage, Exception):
                raise self.coverage
            return self.coverage

        async def fetch_bytes(path: str) -> bytes:
            self.bundle_fetches.append(path)
            if isinstance(self.bundle, Exception):
                raise self.bundle
            return self.bundle

        def verify(**_: Any) -> tuple[bool, str]:
            self.verifier_calls += 1
            return self.verifier

        monkeypatch.setattr(server, "_load_catalogue", load_catalogue)
        monkeypatch.setattr(server, "_fetch_json", fetch_json)
        monkeypatch.setattr(server, "_fetch_bytes", fetch_bytes)
        monkeypatch.setattr(server, "_verify_sigstore_receipt", verify)

    async def call(self, include_proof_steps: bool) -> dict[str, Any]:
        async with Client(server.mcp) as client:
            result = await client.call_tool(
                "verify_dataset", {"dataset_id": "fuelprice", "include_proof_steps": include_proof_steps}
            )
        return result.data


@pytest.fixture
def fakes(monkeypatch: pytest.MonkeyPatch) -> Fakes:
    return Fakes(monkeypatch)


def _assert_reason(data: dict[str, Any], code: str, include_proof_steps: bool) -> None:
    assert LEGACY_KEYS <= set(data)
    assert isinstance(data["signed"], bool)
    reason = data["reason"]
    assert reason["code"] == code
    assert isinstance(reason["message"], str) and reason["message"].strip()
    assert data["signed"] is (code == server.RECEIPT_VERIFIED)
    if include_proof_steps:
        assert isinstance(data["verifier_output"], str) and data["verifier_output"]
    else:
        assert data["verifier_output"] is None


both = pytest.mark.parametrize("include_proof_steps", [False, True])


@both
async def test_published_and_verified(fakes: Fakes, include_proof_steps: bool) -> None:
    data = await fakes.call(include_proof_steps)

    _assert_reason(data, server.RECEIPT_VERIFIED, include_proof_steps)
    assert data["signed"] is True
    assert data["receipt_coverage"]["state"] == "listed_signed"
    for key in REF_KEYS:
        assert data[key].startswith("https://")
    assert data["bundle_ref"] in data["verification_hint"]
    assert fakes.bundle_fetches == ["data/fuelprice.receipt.sigstore.json"]


@both
async def test_published_but_signature_rejected(fakes: Fakes, include_proof_steps: bool) -> None:
    fakes.verifier = (False, "Error: none of the expected identities matched")

    data = await fakes.call(include_proof_steps)

    _assert_reason(data, server.RECEIPT_VERIFICATION_FAILED, include_proof_steps)
    assert data["signed"] is False
    assert data["bundle_ref"].endswith("/data/fuelprice.receipt.sigstore.json")
    assert "none of the expected identities" not in data["reason"]["message"]


@both
async def test_published_but_payload_does_not_bind_statement(fakes: Fakes, include_proof_steps: bool) -> None:
    fakes.health["datasets"][0]["status"] = "stale"  # bundle was signed over the old row

    data = await fakes.call(include_proof_steps)

    _assert_reason(data, server.RECEIPT_VERIFICATION_FAILED, include_proof_steps)
    assert fakes.verifier_calls == 0


@both
async def test_listed_signed_but_bundle_unreachable(fakes: Fakes, include_proof_steps: bool) -> None:
    fakes.bundle = _not_found("data/fuelprice.receipt.sigstore.json")

    data = await fakes.call(include_proof_steps)

    _assert_reason(data, server.RECEIPT_VERIFICATION_FAILED, include_proof_steps)
    assert "HTTPStatusError" in data["reason"]["message"]


@both
async def test_receipt_not_published_for_this_dataset(fakes: Fakes, include_proof_steps: bool) -> None:
    fakes.coverage = _coverage(signed=["deaths"], unsigned=[{"id": "fuelprice", "reason": "signing_failed"}])

    data = await fakes.call(include_proof_steps)

    _assert_reason(data, server.RECEIPT_NOT_PUBLISHED, include_proof_steps)
    assert data["signed"] is False
    assert "signing_failed" in data["reason"]["message"]
    assert data["receipt_coverage"]["state"] == "listed_unsigned"
    assert data["receipt_coverage"]["unsigned_reason"] == "signing_failed"
    for key in REF_KEYS:
        assert data[key] is None
    assert data["verification_hint"] is None
    assert fakes.bundle_fetches == []
    assert fakes.verifier_calls == 0
    # The digest and evidence still describe the published health row.
    assert data["receipt_digest"].startswith("sha256:")


@both
async def test_dataset_absent_from_manifest_is_not_published(fakes: Fakes, include_proof_steps: bool) -> None:
    fakes.coverage = _coverage(signed=["deaths"])

    data = await fakes.call(include_proof_steps)

    _assert_reason(data, server.RECEIPT_NOT_PUBLISHED, include_proof_steps)
    assert data["receipt_coverage"]["state"] == "not_listed"
    assert all(data[key] is None for key in REF_KEYS)
    assert fakes.bundle_fetches == []


@both
@pytest.mark.parametrize(
    "coverage",
    [
        _not_found("data/receipts-manifest.json"),
        httpx.ConnectError("offline"),
        json.JSONDecodeError("spa fallback", "<html>", 0),
        {"schema": "something/else", "signed": ["fuelprice"], "unsigned": []},
        {"schema": "datapulse/v1/receipt-coverage", "signed": "fuelprice", "unsigned": []},
    ],
    ids=["http-404", "connect-error", "html-fallback", "wrong-schema", "malformed"],
)
async def test_coverage_manifest_unavailable(fakes: Fakes, include_proof_steps: bool, coverage: Any) -> None:
    fakes.coverage = coverage
    fakes.bundle = _not_found("data/fuelprice.receipt.sigstore.json")

    data = await fakes.call(include_proof_steps)

    _assert_reason(data, server.RECEIPT_COVERAGE_UNAVAILABLE, include_proof_steps)
    assert data["signed"] is False
    assert data["receipt_coverage"]["state"] == "unavailable"


@both
async def test_manifest_unavailable_still_verifies_a_published_bundle(fakes: Fakes, include_proof_steps: bool) -> None:
    fakes.coverage = _not_found("data/receipts-manifest.json")

    data = await fakes.call(include_proof_steps)

    _assert_reason(data, server.RECEIPT_VERIFIED, include_proof_steps)
    assert data["receipt_coverage"]["state"] == "unavailable"


@both
async def test_server_without_cosign_reports_verifier_unavailable(fakes: Fakes, include_proof_steps: bool) -> None:
    fakes.verifier = (False, server._COSIGN_UNAVAILABLE_OUTPUT)

    data = await fakes.call(include_proof_steps)

    _assert_reason(data, server.RECEIPT_VERIFIER_UNAVAILABLE, include_proof_steps)
    assert data["signed"] is False


async def test_signed_is_true_only_on_the_verified_path(fakes: Fakes) -> None:
    observed: dict[str, bool] = {}
    scenarios = {
        "verified": lambda: None,
        "rejected": lambda: setattr(fakes, "verifier", (False, "bad signature")),
        "unpublished": lambda: setattr(fakes, "coverage", _coverage(signed=[])),
        "unavailable": lambda: (
            setattr(fakes, "coverage", _not_found("m")), setattr(fakes, "bundle", _not_found("b"))
        ),
    }
    for label, arrange in scenarios.items():
        fakes.coverage = _coverage(signed=["fuelprice"])
        fakes.bundle = _bundle_for(fakes.manifest, fakes.health)
        fakes.verifier = (True, "Verified OK")
        arrange()
        data = await fakes.call(False)
        observed[label] = data["signed"]
        assert data["signed"] is (data["reason"]["code"] == server.RECEIPT_VERIFIED)
    assert observed == {"verified": True, "rejected": False, "unpublished": False, "unavailable": False}


async def test_coverage_manifest_is_read_from_the_local_artifact_path_first(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "data").mkdir()
    (tmp_path / "data/receipts-manifest.json").write_text(
        json.dumps(_coverage(signed=[], unsigned=[{"id": "fuelprice", "reason": "signer_unavailable"}])),
        encoding="utf-8",
    )
    monkeypatch.setenv("DATAPULSE_ARTIFACT_ROOT", str(tmp_path))

    async def forbidden_remote(path: str) -> dict:
        raise AssertionError(f"remote fetch attempted for {path}")

    monkeypatch.setattr(server, "_fetch_remote_json", forbidden_remote)

    coverage = await server._load_receipt_coverage()

    assert coverage is not None
    assert coverage["signed"] == frozenset()
    assert coverage["unsigned"] == {"fuelprice": "signer_unavailable"}


async def test_coverage_manifest_falls_back_to_the_published_site(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATAPULSE_DISABLE_LOCAL_ARTIFACTS", "1")
    requested: list[str] = []

    async def remote(path: str) -> dict:
        requested.append(path)
        return _coverage(signed=["fuelprice"])

    monkeypatch.setattr(server, "_fetch_remote_json", remote)

    coverage = await server._load_receipt_coverage()

    assert requested == ["data/receipts-manifest.json"]
    assert coverage is not None and coverage["signed"] == frozenset({"fuelprice"})
