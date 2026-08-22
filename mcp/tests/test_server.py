"""Live-data integration tests for the DataPulse MY FastMCP server."""

from __future__ import annotations

import json
import base64
import hashlib
import sys
import httpx
from datetime import datetime, timezone
from importlib.metadata import version as package_version
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastmcp import Client
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat


MCP_DIR = Path(__file__).resolve().parents[1]
REPO_DIR = MCP_DIR.parent
sys.path.insert(0, str(MCP_DIR))

import server  # noqa: E402

LOAD_TRENDS = server._load_trends
LOAD_DRIFT = server._load_drift
LOAD_RECONCILIATION = server._load_reconciliation


pytestmark = pytest.mark.anyio


TOOL_PARAMETERS = {
    "search_datasets": {"query", "licence", "source", "limit"},
    "get_dataset": {"dataset_id"},
    "find_stale": {"max_age_hours"},
    "find_anomalies": {"limit", "mode", "min_reliability"},
    "find_deteriorating": {"limit", "min_anomaly_rate"},
    "find_recovering": {"limit"},
    "find_unreliable": {"limit", "at_or_below_grade"},
    "find_schema_drift": {"limit", "min_change_count"},
    "check_reconciliation": {"dataset_name"},
    "get_provenance": {"dataset_ids"},
    "get_evidence": {"dataset_id"},
    "verify_evidence": {"dataset_id"},
    "trust_verdict": {"dataset_id"},
    "verify_attestation": {"reference", "replay_chain"},
    "find_by_licence": {"licence"},
    "usage_summary": {"buyer_id", "since", "until"},
}

EXPECTED_TOOL_ANNOTATIONS = {
    "readOnlyHint": True,
    "destructiveHint": False,
    "idempotentHint": True,
    "openWorldHint": True,
}

EXPECTED_TOOL_TITLES = {
    "search_datasets": "Discover Malaysian Public Data",
    "get_dataset": "Inspect Dataset Health and Details",
    "find_stale": "Identify Freshness and Schema Risks",
    "find_anomalies": "Identify Dataset Update Anomalies",
    "find_deteriorating": "Identify Deteriorating Dataset Trends",
    "find_recovering": "Identify Recovering Dataset Trends",
    "find_unreliable": "Identify Unreliable Dataset Publishing",
    "find_schema_drift": "Identify Schema and Content Drift",
    "check_reconciliation": "Check Cross-Source Reconciliation",
    "get_provenance": "Build Citation-Ready Provenance",
    "get_evidence": "Inspect Published Evidence Receipts",
    "verify_evidence": "Re-verify Source Transport Evidence",
    "trust_verdict": "Aggregate a Signed Trust Verdict",
    "verify_attestation": "Verify a Signed Probe Attestation",
    "find_by_licence": "Scope Reusable Data by Licence",
    "usage_summary": "Summarize Buyer Tool Usage",
}


def test_pinned_fastmcp_and_mcp_protocol_versions() -> None:
    assert package_version("fastmcp") == server.FASTMCP_VERSION == "4.0.0b3"
    mcp_version = package_version("mcp")
    assert int(mcp_version.split(".", 1)[0]) >= 2

    from mcp_types.version import (
        HANDSHAKE_PROTOCOL_VERSIONS,
        LATEST_PROTOCOL_VERSION,
        MODERN_PROTOCOL_VERSIONS,
    )

    assert LATEST_PROTOCOL_VERSION == "2026-07-28"
    assert MODERN_PROTOCOL_VERSIONS == ("2026-07-28",)
    assert "2025-11-25" in HANDSHAKE_PROTOCOL_VERSIONS


def test_generated_mcp_catalogue_uses_current_protocol_and_wire_annotations() -> None:
    discovery = json.loads((REPO_DIR / "mcp.json").read_text(encoding="utf-8"))

    assert discovery["mcp_version"] == "2026-07-28"
    assert {tool["name"] for tool in discovery["tools"]} == set(TOOL_PARAMETERS)
    assert all(
        tool.get("annotations") == EXPECTED_TOOL_ANNOTATIONS
        for tool in discovery["tools"]
    )


async def test_modern_and_legacy_clients_preserve_discovery_surface_and_cache_hints() -> None:
    async with Client(server.mcp) as modern:
        tools = await modern.list_tools_mcp()
        resources = await modern.list_resources_mcp()
        templates = await modern.list_resource_templates_mcp()
        index = await modern.read_resource_mcp("datapulse://index")

        assert modern.protocol_version == "2026-07-28"
        for result in (tools, resources, templates, index):
            assert result.ttl_ms == 300_000
            assert result.cache_scope == "public"

        assert len(tools.tools) == 16
        assert len(resources.resources) == 8
        assert len(templates.resource_templates) == 1

    async with Client(server.mcp, mode="legacy") as legacy:
        assert legacy.protocol_version == "2025-11-25"
        assert len(await legacy.list_tools()) == 16
        assert len(await legacy.list_resources()) == 8
        assert len(await legacy.list_resource_templates()) == 1


def install_attestation_fixture(monkeypatch: pytest.MonkeyPatch, *, tamper: str | None = None, anchored: bool = True) -> None:
    private = Ed25519PrivateKey.generate()
    public64 = base64.b64encode(private.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)).decode()
    previous = "0" * 64
    payload = {"schema":"datapulse/v1/probe-attestation","date":"2026-08-15","observed_at":"2026-08-15T00:00:00Z","dataset_id":"sample","source_url":"https://example.test/data","observed_request_url":"https://example.test/data","access_dependency":"direct","probe_count_14d":1,"probe_count_24h":1,"last_status":"fresh","last_staleness_days":0,"content_fingerprint":None,"browser_receipt":{"available":False,"reason":None},"previous_chain_head":previous,"key_id":"ed25519-test","signer_pubkey_base64":public64}
    canonical = server._canonical_json
    link = hashlib.sha256(bytes.fromhex(previous) + canonical(payload)).hexdigest()
    envelope = {"schema":"datapulse/v1/probe-attestation-envelope","payload":payload,"signature_base64":base64.b64encode(private.sign(canonical(payload))).decode(),"chain_link":link,"verification_level":"L1-capable"}
    if tamper == "signature_base64": envelope["signature_base64"] = "A" * 88
    if tamper == "chain_link": envelope["chain_link"] = "0" * 64
    links = [{"dataset_id":"sample","chain_link":link}]
    head_payload = {"schema":"datapulse/v1/daily-chain-head","date":"2026-08-15","previous_chain_head":previous,"dataset_count":1,"dataset_links_sha256":hashlib.sha256(canonical(links)).hexdigest(),"key_id":"ed25519-test"}
    head_value = hashlib.sha256(bytes.fromhex(previous) + canonical(head_payload)).hexdigest()
    head = {"schema":"datapulse/v1/daily-chain-head-envelope","payload":head_payload,"signature_base64":base64.b64encode(private.sign(canonical(head_payload))).decode(),"chain_head":head_value,"dataset_links":links,"anchor":{"tag":None,"commit":None,"anchored":False}}
    index = {"schema":"datapulse/v1/attestation-index","date":"2026-08-15","chain_head_ref":"attestations/2026-08-15/chain_head.json","attestations":{"sample":"attestations/2026-08-15/sample.json"}}
    scores = {"schema":"datapulse/v1/trust-scores","methodology_version":3,"datasets":[{"dataset_id":"sample","methodology_version":3,"score":90.0,"components":{"freshness":90},"component_availability":{"freshness":{"available":True,"reason":"classified"}},"observed_at":payload["observed_at"]}]}
    registry = {"schema":"datapulse/v1/probe-key-registry","keys":[{"key_id":"ed25519-test","algorithm":"Ed25519","public_key_base64":public64,"not_before":"2026-01-01T00:00:00Z","not_after":"2027-01-01T00:00:00Z","status":"active"}]}
    chain_index = {"schema":"datapulse/v1/chain-index","heads":{head_value:"attestations/2026-08-15/chain_head.json"},"anchors":({head_value:{"tag":"v0.8.0","commit":"a"*40}} if anchored else {})}
    async def load_attestations(): return index, head, scores
    async def fetch(path: str): return {"attestations/2026-08-15/sample.json":envelope,"attestations/2026-08-15/chain_head.json":head,".well-known/datapulse-probe-keys.json":registry,"attestations/chain-index.json":chain_index}[path]
    monkeypatch.setattr(server, "_load_attestations", load_attestations)
    monkeypatch.setattr(server, "_fetch_json", fetch)


async def test_verify_attestation_l1_passes(monkeypatch: pytest.MonkeyPatch) -> None:
    install_attestation_fixture(monkeypatch)
    result = await server.verify_attestation("sample", False)
    assert result["levels"]["L1"]["satisfied"] is True
    assert result["levels"]["L2"]["covered"] is False and result["levels"]["L3"]["covered"] is False


@pytest.mark.parametrize("field", ["signature_base64", "chain_link"])
async def test_verify_attestation_l1_rejects_tamper(monkeypatch: pytest.MonkeyPatch, field: str) -> None:
    install_attestation_fixture(monkeypatch, tamper=field)
    assert (await server.verify_attestation("sample", False))["levels"]["L1"]["satisfied"] is False


async def test_verify_attestation_l2_replays_to_anchor(monkeypatch: pytest.MonkeyPatch) -> None:
    install_attestation_fixture(monkeypatch)
    async def valid_git_anchor(anchor: dict, expected_head: str) -> bool: return True
    monkeypatch.setattr(server, "_verify_git_anchor", valid_git_anchor)
    result = await server.verify_attestation("sample", True)
    assert result["levels"]["L2"]["covered"] is True and result["levels"]["L2"]["satisfied"] is True


async def test_trust_verdict_is_join_only(monkeypatch: pytest.MonkeyPatch) -> None:
    install_attestation_fixture(monkeypatch)
    async def catalogue(): return ({"datasets":[{"id":"sample","name":"Sample","source":"Agency"}]}, {"datasets":[{"dataset_id":"sample","status":"fresh","last_checked":"2026-08-15T00:00:00Z"}]})
    async def trends(): return {"datasets":[{"dataset_id":"sample","trend":"stable"}]}
    async def drift(): return {"datasets":[{"dataset_id":"sample","verdict":"stable"}]}
    async def recon(): return {"groups":[]}
    monkeypatch.setattr(server, "_load_catalogue", catalogue); monkeypatch.setattr(server, "_load_trends", trends); monkeypatch.setattr(server, "_load_drift", drift); monkeypatch.setattr(server, "_load_reconciliation", recon)
    result = await server.trust_verdict("sample")
    assert result["score"]["methodology_version"] == 3
    assert result["score"]["component_availability"] == {"freshness":{"available":True,"reason":"classified"}}
    assert result["verified_live_at"] is None


async def test_find_schema_drift_filters_limits_and_ranks(monkeypatch: pytest.MonkeyPatch) -> None:
    manifest = {"datasets": [{"id": "structural", "name": "Structural"}, {"id": "record", "name": "Record"}, {"id": "stable", "name": "Stable"}]}
    base = {"shape_changed_recently": False, "shape_change_count": 0, "last_shape_change_at": None, "column_count_changed": False, "column_change_count": 0, "record_trend": "stable", "record_change_pct": 0.0, "record_count": 100, "column_count": 2, "expected_record_count": 100, "record_count_within_tolerance": True, "reason": "fixture"}
    drift = {"schema": "datapulse/v1/dataset-drift", "datasets": [{**base, "dataset_id": "record", "verdict": "record_count_drift", "record_count_within_tolerance": False}, {**base, "dataset_id": "structural", "verdict": "drift_detected", "shape_changed_recently": True, "shape_change_count": 2}, {**base, "dataset_id": "stable", "verdict": "stable"}]}
    async def fake_load_manifest() -> dict: return manifest
    async def fake_load_drift() -> dict: return drift
    monkeypatch.setattr(server, "_load_manifest", fake_load_manifest)
    monkeypatch.setattr(server, "_load_drift", fake_load_drift)
    async with Client(server.mcp) as client:
        all_drift = await client.call_tool("find_schema_drift", {"limit": 50})
        structural = await client.call_tool("find_schema_drift", {"limit": 1, "min_change_count": 1})
    assert [row["id"] for row in all_drift.data] == ["structural", "record"]
    assert [row["id"] for row in structural.data] == ["structural"]
    assert set(all_drift.data[0]) == {"id", "title", "verdict", "shape_changed_recently", "shape_change_count", "last_shape_change_at", "column_count_changed", "column_change_count", "record_trend", "record_change_pct", "record_count", "column_count", "expected_record_count", "record_count_within_tolerance", "reason"}


async def test_schema_drift_tool_matches_live_artifact(live_drift: dict) -> None:
    expected = sum(row["verdict"] in {"drift_detected", "record_count_drift"} for row in live_drift["datasets"])
    async with Client(server.mcp) as client:
        result = await client.call_tool("find_schema_drift", {"limit": 200})
    assert len(result.data) == min(expected, 200)


async def test_drift_resource_returns_complete_published_artifact(live_drift: dict) -> None:
    async with Client(server.mcp) as client:
        result = await client.read_resource("datapulse://drift")
    assert json.loads(result[0].text) == live_drift


async def test_load_drift_rejects_unsupported_schema(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_fetch_json(path: str) -> dict:
        assert path == "health/drift.json"
        return {"schema": "wrong", "datasets": []}
    monkeypatch.setattr(server, "_fetch_json", fake_fetch_json)
    with pytest.raises(ValueError, match="unsupported schema"):
        await LOAD_DRIFT()


async def test_load_drift_reports_missing_publication(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_fetch_json(path: str) -> dict:
        request = httpx.Request("GET", f"https://example.test/{path}")
        response = httpx.Response(404, request=request)
        raise httpx.HTTPStatusError("missing", request=request, response=response)
    monkeypatch.setattr(server, "_fetch_json", fake_fetch_json)
    with pytest.raises(RuntimeError, match="Pages deployment completes"):
        await LOAD_DRIFT()


async def test_check_reconciliation_resolves_id_and_exact_name(monkeypatch: pytest.MonkeyPatch) -> None:
    manifest = {"datasets": [{"id": "alpha", "name": "Alpha Dataset"}, {"id": "beta", "name": "Beta Dataset"}]}
    group = {"group_key": "seed:pair", "verdict": "discrepancy", "members": [{"id": "alpha"}, {"id": "beta"}]}
    reconciliation = {"schema": "datapulse/v1/dataset-reconciliation", "groups": [group]}
    async def fake_load_manifest() -> dict: return manifest
    async def fake_load_reconciliation() -> dict: return reconciliation
    monkeypatch.setattr(server, "_load_manifest", fake_load_manifest)
    monkeypatch.setattr(server, "_load_reconciliation", fake_load_reconciliation)
    async with Client(server.mcp) as client:
        by_id = await client.call_tool("check_reconciliation", {"dataset_name": "alpha"})
        by_name = await client.call_tool("check_reconciliation", {"dataset_name": "Alpha Dataset"})
    assert by_id.data == {"matched_dataset_id": "alpha", "group": group}
    assert by_name.data == by_id.data


async def test_check_reconciliation_returns_single_source(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_load_manifest() -> dict: return {"datasets": [{"id": "only", "name": "Only Dataset"}]}
    async def fake_load_reconciliation() -> dict: return {"schema": "datapulse/v1/dataset-reconciliation", "groups": []}
    monkeypatch.setattr(server, "_load_manifest", fake_load_manifest)
    monkeypatch.setattr(server, "_load_reconciliation", fake_load_reconciliation)
    async with Client(server.mcp) as client:
        result = await client.call_tool("check_reconciliation", {"dataset_name": "only"})
    assert result.data["matched_dataset_id"] == "only"
    assert result.data["verdict"] == "single_source"
    assert result.data["group"] is None


async def test_reconciliation_tool_matches_live_exact_url_group(live_reconciliation: dict) -> None:
    expected = next(group for group in live_reconciliation["groups"] if {member["id"] for member in group["members"]} == {"interestrates", "dgm_interest_rates"})
    async with Client(server.mcp) as client:
        result = await client.call_tool("check_reconciliation", {"dataset_name": "interestrates"})
    assert result.data["matched_dataset_id"] == "interestrates"
    assert result.data["group"] == expected
    assert expected["grouping_method"] == "exact_url"


async def test_reconciliation_resource_returns_complete_published_artifact(live_reconciliation: dict) -> None:
    async with Client(server.mcp) as client:
        result = await client.read_resource("datapulse://reconciliation")
    assert json.loads(result[0].text) == live_reconciliation


async def test_load_reconciliation_rejects_unsupported_schema(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_fetch_json(path: str) -> dict:
        assert path == "health/reconciliation.json"
        return {"schema": "wrong", "groups": []}
    monkeypatch.setattr(server, "_fetch_json", fake_fetch_json)
    with pytest.raises(ValueError, match="unsupported schema"):
        await LOAD_RECONCILIATION()


async def test_load_reconciliation_reports_missing_publication(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_fetch_json(path: str) -> dict:
        request = httpx.Request("GET", f"https://example.test/{path}")
        response = httpx.Response(404, request=request)
        raise httpx.HTTPStatusError("missing", request=request, response=response)
    monkeypatch.setattr(server, "_fetch_json", fake_fetch_json)
    with pytest.raises(RuntimeError, match="Pages deployment completes"):
        await LOAD_RECONCILIATION()


@pytest.fixture(scope="module")
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture(scope="module")
def live_data() -> tuple[dict, dict]:
    return (
        json.loads((REPO_DIR / "datapulse.json").read_text(encoding="utf-8")),
        json.loads((REPO_DIR / "health/latest.json").read_text(encoding="utf-8")),
    )


@pytest.fixture(scope="module")
def live_trends() -> dict:
    return json.loads((REPO_DIR / "health/trends.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def live_drift() -> dict:
    return json.loads((REPO_DIR / "health/drift.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def live_reconciliation() -> dict:
    return json.loads((REPO_DIR / "health/reconciliation.json").read_text(encoding="utf-8"))


@pytest.fixture(autouse=True)
def local_catalogue(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    server._VERIFY_CACHE.clear()
    monkeypatch.setenv("DATAPULSE_USAGE_DIR", str(tmp_path / "usage"))
    manifest = json.loads((REPO_DIR / "datapulse.json").read_text(encoding="utf-8"))
    health = json.loads((REPO_DIR / "health/latest.json").read_text(encoding="utf-8"))
    trends = json.loads((REPO_DIR / "health/trends.json").read_text(encoding="utf-8"))
    drift = json.loads((REPO_DIR / "health/drift.json").read_text(encoding="utf-8"))
    reconciliation = json.loads((REPO_DIR / "health/reconciliation.json").read_text(encoding="utf-8"))

    async def fake_load_catalogue() -> tuple[dict, dict]:
        return manifest, health

    async def fake_load_manifest() -> dict:
        return manifest

    async def fake_load_health() -> dict:
        return health

    async def fake_load_trends() -> dict:
        return trends

    async def fake_load_drift() -> dict:
        return drift

    async def fake_load_reconciliation() -> dict:
        return reconciliation

    monkeypatch.setattr(server, "_load_catalogue", fake_load_catalogue)
    monkeypatch.setattr(server, "_load_manifest", fake_load_manifest)
    monkeypatch.setattr(server, "_load_health", fake_load_health)
    monkeypatch.setattr(server, "_load_trends", fake_load_trends)
    monkeypatch.setattr(server, "_load_drift", fake_load_drift)
    monkeypatch.setattr(server, "_load_reconciliation", fake_load_reconciliation)


async def test_tool_schemas_are_agent_ready(live_data: tuple[dict, dict]) -> None:
    manifest, _ = live_data
    tools = {tool.name: tool for tool in await server.mcp.list_tools()}

    assert set(tools) == set(TOOL_PARAMETERS)
    for tool_name, parameter_names in TOOL_PARAMETERS.items():
        schema = tools[tool_name].parameters
        assert "required" in schema
        assert set(schema["properties"]) == parameter_names
        assert (
            tools[tool_name].annotations.model_dump(by_alias=True, exclude_none=True)
            == EXPECTED_TOOL_ANNOTATIONS
        )
        for parameter in schema["properties"].values():
            assert parameter["description"]
            assert "e.g." in parameter["description"]

    assert tools["find_stale"].parameters["required"] == []
    assert tools["find_anomalies"].parameters["required"] == []
    assert tools["find_deteriorating"].parameters["required"] == []
    assert tools["find_recovering"].parameters["required"] == []
    assert tools["find_unreliable"].parameters["required"] == []
    assert tools["find_schema_drift"].parameters["required"] == []
    assert tools["find_schema_drift"].parameters["properties"]["limit"]["examples"] == [10, 50]
    assert tools["find_schema_drift"].parameters["properties"]["min_change_count"]["examples"] == [0, 1]
    assert tools["check_reconciliation"].parameters["required"] == ["dataset_name"]
    assert tools["check_reconciliation"].parameters["properties"]["dataset_name"]["examples"] == ["interestrates", "Monthly Interest Rates"]
    assert tools["find_deteriorating"].parameters["properties"]["limit"]["examples"] == [10, 50]
    assert tools["find_deteriorating"].parameters["properties"]["min_anomaly_rate"]["examples"] == [25.0, 50.0]
    assert tools["find_recovering"].parameters["properties"]["limit"]["examples"] == [10, 50]
    assert tools["get_provenance"].parameters["properties"]["dataset_ids"][
        "examples"
    ] == [["fuelprice", "pricecatcher"]]
    assert tools["get_evidence"].parameters["required"] == ["dataset_id"]
    assert tools["verify_evidence"].parameters["required"] == ["dataset_id"]
    assert tools["get_evidence"].parameters["properties"]["dataset_id"]["examples"] == ["fuelprice"]
    assert tools["verify_evidence"].parameters["properties"]["dataset_id"]["examples"] == ["fuelprice"]
    assert tools["search_datasets"].parameters["properties"]["query"]["examples"] == [
        "inflation cpi"
    ]
    assert tools["search_datasets"].parameters["properties"]["licence"]["examples"] == [
        "CC BY 4.0",
        "Open Government Licence (Malaysia)",
    ]
    assert tools["search_datasets"].parameters["properties"]["source"]["examples"] == [
        "OpenDOSM",
        "data.gov.my",
        "MET Malaysia",
    ]
    assert tools["get_dataset"].parameters["properties"]["dataset_id"]["examples"] == [
        "dosm_cpi_state"
    ]
    assert tools["find_stale"].parameters["properties"]["max_age_hours"]["examples"] == [
        24,
        72,
    ]
    assert tools["find_anomalies"].parameters["properties"]["limit"]["examples"] == [
        10,
        50,
    ]
    assert tools["find_anomalies"].parameters["properties"]["mode"]["examples"] == [
        "rolling_14d",
        "cadence_fallback",
    ]
    assert tools["find_anomalies"].parameters["properties"]["min_reliability"][
        "examples"
    ] == ["A", "C"]
    assert tools["find_unreliable"].parameters["properties"]["limit"][
        "examples"
    ] == [10, 50]
    assert tools["find_unreliable"].parameters["properties"]["at_or_below_grade"][
        "examples"
    ] == ["C", "F"]
    assert tools["find_by_licence"].parameters["properties"]["licence"]["examples"] == [
        "Creative Commons Attribution 4.0",
        "CC BY 4.0",
        "OGL",
    ]
    assert f"{len(manifest['datasets'])} Malaysian public datasets" in tools[
        "search_datasets"
    ].description


async def test_tools_list_exposes_display_and_publisher_metadata() -> None:
    async with Client(server.mcp) as client:
        listed_tools = await client.list_tools()

    tools = {tool.name: tool for tool in listed_tools}
    assert set(tools) == set(EXPECTED_TOOL_TITLES)

    for tool_name, expected_title in EXPECTED_TOOL_TITLES.items():
        payload = tools[tool_name].model_dump(by_alias=True, exclude_none=True)
        assert payload["title"] == expected_title
        assert payload["icons"] == [
            {
                "src": "https://data-pulse.my/badges/status-fresh.svg",
                "mimeType": "image/svg+xml",
                "sizes": ["110x20"],
            }
        ]
        assert payload["_meta"] == {
            "publisher": "DataPulse MY",
            "publisher_url": "https://data-pulse.my/",
            "version": server.SOURCE_VERSION_STRING,
            "repository_url": "https://github.com/r3dz4r/datapulse-my",
            "dataset_count": server.DATASET_COUNT,
            "fastmcp": {"tags": []},
        }


def test_dataset_count_is_derived_from_manifest(tmp_path: Path) -> None:
    manifest_path = tmp_path / "datapulse.json"
    manifest_path.write_text(
        json.dumps({"datasets": [{"id": "one"}, {"id": "two"}]}),
        encoding="utf-8",
    )

    assert server._manifest_dataset_count(manifest_path) == 2


def test_dataset_count_follows_published_manifest_redirect(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    class RedirectedManifestResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return {"datasets": [{"id": "redirected"}]}

    def fake_get(url: str, *, timeout: float, follow_redirects: bool):
        assert url == f"{server.DATA_BASE}/datapulse.json"
        assert timeout == server.REQUEST_TIMEOUT_SECONDS
        assert follow_redirects is True
        return RedirectedManifestResponse()

    monkeypatch.setattr(server.httpx, "get", fake_get)

    assert server._manifest_dataset_count(tmp_path / "missing.json") == 1


@pytest.mark.anyio
async def test_fetch_json_follows_redirects(monkeypatch: pytest.MonkeyPatch) -> None:
    class RedirectedResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return {"ok": True}

    class FakeAsyncClient:
        def __init__(self, *args, **kwargs) -> None:
            self.timeout = kwargs.get("timeout")

        async def __aenter__(self) -> "FakeAsyncClient":
            return self

        async def __aexit__(self, *exc) -> None:
            return None

        async def get(self, url: str, **kwargs) -> RedirectedResponse:
            assert url == f"{server.DATA_BASE}/datapulse.json"
            assert kwargs.get("follow_redirects") is True
            return RedirectedResponse()

    monkeypatch.setattr(server.httpx, "AsyncClient", FakeAsyncClient)

    result = await server._fetch_json("datapulse.json")
    assert result == {"ok": True}


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


async def test_tool_call_logs_sanitized_usage(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level("INFO", logger=server.logger.name)

    async with Client(server.mcp) as client:
        await client.call_tool("search_datasets", {"query": "fuel"})

    records = [record.getMessage() for record in caplog.records if record.name == server.logger.name]
    tool_logs = [record for record in records if record.startswith("mcp-tool:")]
    assert len(tool_logs) == 1
    assert "tool=search_datasets" in tool_logs[0]
    assert '"query":"fuel"' in tool_logs[0]
    assert "timestamp=" in tool_logs[0]
    assert server._sanitise_tool_arg({"api_key": "should-not-appear"}) == {
        "api_key": "[REDACTED]"
    }


async def test_usage_jsonl_sink_and_summary(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("DATAPULSE_USAGE_DIR", str(tmp_path))
    request = SimpleNamespace(headers={"x-buyer-id": "buyer-a", "x-request-id": "request-1"}, client=SimpleNamespace(host="127.0.0.1"))
    monkeypatch.setattr(server, "get_http_request", lambda: request)
    context = SimpleNamespace(message=SimpleNamespace(name="trust_verdict", arguments={"dataset_id": "fuelprice", "api_key": "secret"}), timestamp=datetime.now(timezone.utc))
    result = await server.ToolUsageLoggingMiddleware().on_call_tool(context, lambda _: _result({"score": {"score": 92.0, "methodology_version": 2}}))
    assert result["score"]["score"] == 92.0
    record = json.loads(next(tmp_path.glob("*.jsonl")).read_text(encoding="utf-8"))
    assert record["buyer_id"] == "buyer-a" and record["args"]["api_key"] == "[REDACTED]"
    day = datetime.now(timezone.utc).date().isoformat()
    (tmp_path / "2026-08-01.jsonl").write_text(json.dumps({"buyer_id": "buyer-a", "tool": "search_datasets", "args": {}, "result_summary": {}}) + "\n", encoding="utf-8")
    (tmp_path / "2026-08-02.jsonl").write_text("\n".join(json.dumps(row) for row in [
        {"buyer_id": "buyer-a", "tool": "get_dataset", "args": {"dataset_id": "fuelprice"}, "result_summary": {}},
        {"buyer_id": "buyer-a", "tool": "trust_verdict", "args": {"dataset_id": "cpi"}, "result_summary": {"score": 76}},
        {"buyer_id": "other", "tool": "trust_verdict", "args": {"dataset_id": "ignored"}, "result_summary": {"score": 100}},
    ]) + "\n", encoding="utf-8")
    (tmp_path / "2026-08-03.jsonl").write_text(json.dumps({"buyer_id": "other", "tool": "get_dataset", "args": {}, "result_summary": {}}) + "\n", encoding="utf-8")
    summary = await server.usage_summary("buyer-a", "2026-08-01", "2026-08-03")
    assert summary == {"total_calls": 3, "by_tool": {"search_datasets": 1, "get_dataset": 1, "trust_verdict": 1}, "by_dataset": {"fuelprice": 1, "cpi": 1}, "trust_distribution": {"75-89": 1}}
    with pytest.raises(ValueError): await server.usage_summary("buyer-a", "2026-08-03", "2026-08-02")
    with pytest.raises(ValueError): await server.usage_summary("buyer-a", "invalid", day)


async def _result(value: dict) -> dict:
    return value


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


async def test_get_dataset_surfaces_namespace(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest = json.loads((REPO_DIR / "datapulse.json").read_text(encoding="utf-8"))
    health = json.loads((REPO_DIR / "health/latest.json").read_text(encoding="utf-8"))
    dataset_id = manifest["datasets"][0]["id"]
    expected_namespace = manifest["datasets"][0]["namespace"]
    manifest["datasets"][0].pop("namespace")

    async def fake_load_catalogue() -> tuple[dict, dict]:
        return manifest, health

    monkeypatch.setattr(server, "_load_catalogue", fake_load_catalogue)

    async with Client(server.mcp) as client:
        result = await client.call_tool("get_dataset", {"dataset_id": dataset_id})

    assert result.data["namespace"] == expected_namespace


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
                "content_freshness_date": "2026-07-22",
                "freshness_signal_source": "content_date_parse",
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
    assert result.data["content_freshness_date"] == "2026-07-22"
    assert result.data["freshness_signal_source"] == "content_date_parse"


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
        "unknown-freshness",
        "reference",
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


async def test_find_stale_excludes_reference_when_snapshot_is_old(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest = {"datasets": [{"id": "lookup", "name": "Lookup"}]}
    health = {
        "checked_at": "2020-01-01T00:00:00+00:00",
        "datasets": [
            {
                "dataset_id": "lookup",
                "status": "reference",
                "message": "Reference data verified",
            }
        ],
    }

    async def fake_load_catalogue() -> tuple[dict, dict]:
        return manifest, health

    monkeypatch.setattr(server, "_load_catalogue", fake_load_catalogue)

    async with Client(server.mcp) as client:
        result = await client.call_tool("find_stale", {"max_age_hours": 24})

    assert result.data == []


async def test_find_anomalies_matches_live_health(
    live_data: tuple[dict, dict], live_trends: dict
) -> None:
    manifest, health = live_data
    manifest_ids = {item["id"] for item in manifest["datasets"]}
    trends_by_id = {item["dataset_id"]: item for item in live_trends["datasets"]}
    expected_count = sum(
        item["dataset_id"] in manifest_ids and item.get("anomaly_detected") is True
        for item in health["datasets"]
    )

    async with Client(server.mcp) as client:
        result = await client.call_tool("find_anomalies", {"limit": 50})

    assert len(result.data) == min(expected_count, 50)
    assert all(
        set(item)
        == {
            "id",
            "title",
            "status",
            "staleness_days",
            "mode",
            "latest_days",
            "threshold_days",
            "severity_ratio",
            "anomaly_detection",
            "publish_on_time_pct",
            "reliability_grade",
            "reliability_sample_days",
        }
        for item in result.data
    )
    assert all(item["id"] in manifest_ids for item in result.data)
    assert all(
        item["anomaly_detection"]
        == next(
            record["anomaly_detection"]
            for record in health["datasets"]
            if record["dataset_id"] == item["id"]
        )
        for item in result.data
    )
    assert [item["severity_ratio"] for item in result.data] == sorted(
        (item["severity_ratio"] for item in result.data), reverse=True
    )
    assert all(
        item["reliability_grade"] == trends_by_id[item["id"]]["reliability_grade"]
        and item["publish_on_time_pct"] == trends_by_id[item["id"]]["publish_on_time_pct"]
        and item["reliability_sample_days"] == trends_by_id[item["id"]]["reliability_sample_days"]
        for item in result.data
    )


async def test_find_anomalies_filters_limits_and_ranks_by_threshold_ratio(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest = {
        "datasets": [
            {"id": "long-delay", "name": "Long Delay"},
            {"id": "high-ratio", "name": "High Ratio"},
            {"id": "rolling", "name": "Rolling"},
            {"id": "normal", "name": "Normal"},
        ]
    }
    health = {
        "datasets": [
            {
                "dataset_id": "long-delay",
                "status": "stale",
                "staleness_days": 100,
                "anomaly_detected": True,
                "anomaly_detection": {
                    "mode": "cadence_fallback",
                    "latest_days": 100.0,
                    "threshold_days": 50,
                },
            },
            {
                "dataset_id": "high-ratio",
                "status": "stale",
                "staleness_days": 12,
                "anomaly_detected": True,
                "anomaly_detection": {
                    "mode": "cadence_fallback",
                    "latest_days": 12.0,
                    "threshold_days": 2,
                },
            },
            {
                "dataset_id": "rolling",
                "status": "aging",
                "staleness_days": 8,
                "anomaly_detected": True,
                "anomaly_detection": {
                    "mode": "rolling_14d",
                    "latest_days": 8.0,
                    "threshold_days": 4.0,
                },
            },
            {
                "dataset_id": "normal",
                "status": "fresh",
                "staleness_days": 1,
                "anomaly_detected": False,
                "anomaly_detection": {
                    "mode": "cadence_fallback",
                    "latest_days": 1.0,
                    "threshold_days": 2,
                },
            },
        ]
    }

    async def fake_load_catalogue() -> tuple[dict, dict]:
        return manifest, health

    monkeypatch.setattr(server, "_load_catalogue", fake_load_catalogue)

    async with Client(server.mcp) as client:
        result = await client.call_tool(
            "find_anomalies", {"limit": 1, "mode": "cadence_fallback"}
        )

    assert [item["id"] for item in result.data] == ["high-ratio"]
    assert result.data[0]["severity_ratio"] == 6.0


async def test_find_anomalies_filters_by_minimum_reliability(monkeypatch: pytest.MonkeyPatch) -> None:
    manifest = {"datasets": [{"id": key, "name": key} for key in ("a", "c", "d", "unknown")]}
    health = {"datasets": [{"dataset_id": key, "status": "stale", "staleness_days": days, "anomaly_detected": True, "anomaly_detection": {"mode": "cadence_fallback", "latest_days": days, "threshold_days": 1.0}} for key, days in (("a", 2.0), ("c", 3.0), ("d", 10.0), ("unknown", 20.0))]}
    trends = {"datasets": [{"dataset_id": "a", "reliability_grade": "A", "publish_on_time_pct": 100.0, "reliability_sample_days": 4}, {"dataset_id": "c", "reliability_grade": "C", "publish_on_time_pct": 75.0, "reliability_sample_days": 4}, {"dataset_id": "d", "reliability_grade": "D", "publish_on_time_pct": 50.0, "reliability_sample_days": 4}, {"dataset_id": "unknown", "reliability_grade": "insufficient_data", "publish_on_time_pct": None, "reliability_sample_days": 0}]}
    async def fake_load_catalogue() -> tuple[dict, dict]: return manifest, health
    async def fake_load_trends() -> dict: return trends
    monkeypatch.setattr(server, "_load_catalogue", fake_load_catalogue)
    monkeypatch.setattr(server, "_load_trends", fake_load_trends)
    async with Client(server.mcp) as client:
        result = await client.call_tool("find_anomalies", {"limit": 50, "min_reliability": "c"})
    assert [item["id"] for item in result.data] == ["c", "a"]
    assert [item["reliability_grade"] for item in result.data] == ["C", "A"]
    with pytest.raises(ValueError, match="Unknown minimum reliability grade"):
        await server.find_anomalies(min_reliability="unknown")


async def test_find_unreliable_filters_limits_and_ranks(monkeypatch: pytest.MonkeyPatch) -> None:
    manifest = {"datasets": [{"id": grade.casefold(), "name": f"Grade {grade}"} for grade in ("A", "B", "C", "D", "F")]}
    trends = {"datasets": [{"dataset_id": grade.casefold(), "reliability_grade": grade, "publish_on_time_pct": pct, "reliability_sample_days": 4, "latest_status": "stale", "trend": "deteriorating", "reason": "fixture"} for grade, pct in (("A", 100.0), ("B", 90.0), ("C", 75.0), ("D", 50.0), ("F", 25.0))]}
    async def fake_load_manifest() -> dict: return manifest
    async def fake_load_trends() -> dict: return trends
    monkeypatch.setattr(server, "_load_manifest", fake_load_manifest)
    monkeypatch.setattr(server, "_load_trends", fake_load_trends)
    async with Client(server.mcp) as client:
        default = await client.call_tool("find_unreliable", {"limit": 50})
        grade_d = await client.call_tool("find_unreliable", {"limit": 2, "at_or_below_grade": "d"})
    assert [item["id"] for item in default.data] == ["f", "d", "c"]
    assert [item["id"] for item in grade_d.data] == ["f", "d"]
    assert set(default.data[0]) == {"id", "title", "reliability_grade", "publish_on_time_pct", "reliability_sample_days", "latest_status", "trend", "reason"}


async def test_find_unreliable_matches_live_artifact(live_trends: dict) -> None:
    expected = sum(row["reliability_grade"] in {"C", "D", "F"} for row in live_trends["datasets"])
    async with Client(server.mcp) as client:
        result = await client.call_tool("find_unreliable", {"limit": 200})
    assert len(result.data) == min(expected, 200)
    assert all(row["reliability_grade"] in {"C", "D", "F"} and row["reliability_sample_days"] > 0 for row in result.data)


def _trend_fixture() -> tuple[dict, dict]:
    manifest = {
        "datasets": [
            {"id": "fast", "name": "Fast"},
            {"id": "anomalous", "name": "Anomalous"},
            {"id": "recovered", "name": "Recovered"},
        ]
    }
    base = {
        "latest_status": "aging",
        "cadence_days": 1,
        "latest_staleness_days": 4,
        "trend_sample_days": 4,
        "history_span_days": 3.0,
        "publish_on_time_pct": 50.0,
        "reliability_grade": "D",
        "reliability_sample_days": 4,
        "anomaly_sample_days": 4,
        "reason": "fixture",
    }
    trends = {
        "schema": "datapulse/v1/dataset-trends",
        "datasets": [
            {**base, "dataset_id": "fast", "trend": "deteriorating", "slope_days_per_week": 7.0, "anomaly_rate_pct": 25.0},
            {**base, "dataset_id": "anomalous", "trend": "deteriorating", "slope_days_per_week": 3.5, "anomaly_rate_pct": 75.0},
            {**base, "dataset_id": "recovered", "trend": "recovering", "slope_days_per_week": -14.0, "anomaly_rate_pct": 0.0},
        ],
    }
    return manifest, trends


async def test_find_deteriorating_filters_limits_and_ranks(monkeypatch: pytest.MonkeyPatch) -> None:
    manifest, trends = _trend_fixture()

    async def fake_load_manifest() -> dict:
        return manifest

    async def fake_load_trends() -> dict:
        return trends

    monkeypatch.setattr(server, "_load_manifest", fake_load_manifest)
    monkeypatch.setattr(server, "_load_trends", fake_load_trends)
    async with Client(server.mcp) as client:
        ranked = await client.call_tool("find_deteriorating", {"limit": 2})
        filtered = await client.call_tool(
            "find_deteriorating", {"limit": 2, "min_anomaly_rate": 50.0}
        )

    assert [row["id"] for row in ranked.data] == ["fast", "anomalous"]
    assert [row["id"] for row in filtered.data] == ["anomalous"]
    assert set(ranked.data[0]) == {
        "id", "title", "trend", "latest_status", "cadence_days",
        "latest_staleness_days", "slope_days_per_week", "trend_sample_days",
        "history_span_days", "publish_on_time_pct", "reliability_grade",
        "reliability_sample_days", "anomaly_rate_pct", "anomaly_sample_days", "reason",
    }


async def test_find_recovering_returns_most_negative_slope_first(monkeypatch: pytest.MonkeyPatch) -> None:
    manifest, trends = _trend_fixture()
    manifest["datasets"].append({"id": "recovering-slow", "name": "Recovering Slow"})
    trends["datasets"].append(
        {**trends["datasets"][-1], "dataset_id": "recovering-slow", "slope_days_per_week": -3.5}
    )

    async def fake_load_manifest() -> dict:
        return manifest

    async def fake_load_trends() -> dict:
        return trends

    monkeypatch.setattr(server, "_load_manifest", fake_load_manifest)
    monkeypatch.setattr(server, "_load_trends", fake_load_trends)
    async with Client(server.mcp) as client:
        result = await client.call_tool("find_recovering", {"limit": 50})

    assert [row["id"] for row in result.data] == ["recovered", "recovering-slow"]


async def test_trend_tools_match_live_artifact(live_trends: dict) -> None:
    expected_deteriorating = sum(
        row["trend"] == "deteriorating" for row in live_trends["datasets"]
    )
    expected_recovering = sum(
        row["trend"] == "recovering" for row in live_trends["datasets"]
    )
    async with Client(server.mcp) as client:
        deteriorating = await client.call_tool("find_deteriorating", {"limit": 200})
        recovering = await client.call_tool("find_recovering", {"limit": 200})
    assert len(deteriorating.data) == min(expected_deteriorating, 200)
    assert len(recovering.data) == min(expected_recovering, 200)


async def test_trends_resource_returns_complete_published_artifact(live_trends: dict) -> None:
    async with Client(server.mcp) as client:
        result = await client.read_resource("datapulse://trends")
    assert json.loads(result[0].text) == live_trends


async def test_load_trends_rejects_unsupported_schema(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_fetch_json(path: str) -> dict:
        assert path == "health/trends.json"
        return {"schema": "wrong", "datasets": []}

    monkeypatch.setattr(server, "_fetch_json", fake_fetch_json)
    with pytest.raises(ValueError, match="unsupported schema"):
        await LOAD_TRENDS()


async def test_get_provenance_returns_citation_fields(live_data: tuple[dict, dict]) -> None:
    manifest, health = live_data
    dataset_ids = [item["id"] for item in manifest["datasets"][:2]]

    async with Client(server.mcp) as client:
        result = await client.call_tool("get_provenance", {"dataset_ids": dataset_ids})

    assert [item["id"] for item in result.data] == dataset_ids
    assert all("evidence" in item for item in result.data)
    assert all(item["last_verified"] == next(row["last_checked"] for row in health["datasets"] if row["dataset_id"] == item["id"]) for item in result.data)
    assert all(item["licence_url"].startswith("https://") for item in result.data)


async def test_get_evidence_projects_complete_published_receipt(monkeypatch: pytest.MonkeyPatch) -> None:
    row = {field: f"value-{field}" for field in server.EVIDENCE_FIELDS}
    manifest = {"datasets": [{"id": "sample"}]}
    health = {"schema": "datapulse/v0.4/dataset-health", "checked_at": "snapshot", "datasets": [{**row, "dataset_id": "sample"}]}
    async def load() -> tuple[dict, dict]: return manifest, health
    monkeypatch.setattr(server, "_load_catalogue", load)
    result = await server.get_evidence("sample")
    assert result["evidence"] == {field: row[field] for field in server.EVIDENCE_FIELDS}


async def test_get_evidence_keeps_missing_receipts_explicit(monkeypatch: pytest.MonkeyPatch) -> None:
    async def load() -> tuple[dict, dict]: return {"datasets": [{"id": "sample"}]}, {"datasets": []}
    monkeypatch.setattr(server, "_load_catalogue", load)
    result = await server.get_evidence("sample")
    assert result["evidence_available"] is False
    assert set(result["evidence"]) == set(server.EVIDENCE_FIELDS)
    assert all(value is None for value in result["evidence"].values())


async def test_get_provenance_includes_compact_receipts_and_row_probe_time(monkeypatch: pytest.MonkeyPatch) -> None:
    url = "https://api.data.gov.my/data-catalogue?id=sample"
    manifest = {"datasets": [{"id": "sample", "steward": "Agency", "source": "Publisher", "licence": server.CC_BY_4, "url": url}]}
    row = {"dataset_id": "sample", "last_checked": "row-time", "access_method": "direct", "http_status": 200, "request_url": url, "access_dependency": "direct", "freshness_signal_source": "content_date_parse", "content_freshness_date": "2026-08-14", "record_count": 10, "first_row_hash": "shape-v1:abc", "anomaly_detected": False, "status": "fresh"}
    health = {"schema": "schema", "checked_at": "snapshot", "datasets": [row]}
    async def load() -> tuple[dict, dict]: return manifest, health
    monkeypatch.setattr(server, "_load_catalogue", load)
    result = await server.get_provenance(["sample"])
    assert result[0]["last_verified"] == "row-time"
    assert result[0]["evidence"] == {**{field: row.get(field) for field in server.COMPACT_EVIDENCE_FIELDS}, "available": True, "snapshot_checked_at": "snapshot"}


def install_fake_live_http(monkeypatch: pytest.MonkeyPatch, responses: list[httpx.Response | Exception]) -> list[httpx.Request]:
    requests: list[httpx.Request] = []
    class FakeAsyncClient:
        def __init__(self, *args, **kwargs) -> None: assert kwargs["timeout"] == server.REQUEST_TIMEOUT_SECONDS
        async def __aenter__(self): return self
        async def __aexit__(self, *exc): return None
        def build_request(self, method: str, url: str) -> httpx.Request:
            request = httpx.Request(method, url); requests.append(request); return request
        async def send(self, request: httpx.Request, *, stream: bool) -> httpx.Response:
            assert stream is True
            outcome = responses.pop(0)
            if isinstance(outcome, Exception): raise outcome
            outcome.request = request
            return outcome
    monkeypatch.setattr(server.httpx, "AsyncClient", FakeAsyncClient)
    return requests


def _verification_fixture(url: str) -> tuple[dict, dict]:
    return ({"datasets": [{"id": "sample", "url": url, "source": "data.gov.my"}]}, {"datasets": [{"dataset_id": "sample", "last_checked": "now", "request_url": url, "access_dependency": "direct", "http_status": 200, "last_modified": "2026-08-14T01:02:03Z", "content_length": 123}]})


async def test_verify_evidence_matches_transport_and_marks_content_unverified(monkeypatch: pytest.MonkeyPatch) -> None:
    url = "https://api.data.gov.my/data-catalogue?id=sample"
    manifest, health = _verification_fixture(url)
    async def load() -> tuple[dict, dict]: return manifest, health
    monkeypatch.setattr(server, "_load_catalogue", load)
    requests = install_fake_live_http(monkeypatch, [httpx.Response(200, headers={"Last-Modified": "Fri, 14 Aug 2026 01:02:03 GMT", "Content-Length": "123"})])
    result = await server.verify_evidence("sample")
    assert [request.url for request in requests] == [httpx.URL(url)]
    assert result["verdict"] == "match" and result["last_modified_match"] is True
    assert result["content_date_match"] is None and result["record_count_match"] is None and result["first_row_hash_match"] is None


async def test_verify_evidence_reports_transport_mismatch(monkeypatch: pytest.MonkeyPatch) -> None:
    url = "https://api.data.gov.my/data-catalogue?id=sample"; manifest, health = _verification_fixture(url)
    async def load() -> tuple[dict, dict]: return manifest, health
    monkeypatch.setattr(server, "_load_catalogue", load)
    install_fake_live_http(monkeypatch, [httpx.Response(200, headers={"Last-Modified": "Sat, 15 Aug 2026 01:02:03 GMT", "Content-Length": "456"})])
    result = await server.verify_evidence("sample")
    assert result["verdict"] == "mismatch"


async def test_verify_evidence_reports_timeout_as_unreachable(monkeypatch: pytest.MonkeyPatch) -> None:
    url = "https://api.data.gov.my/data-catalogue?id=sample"; manifest, health = _verification_fixture(url)
    async def load() -> tuple[dict, dict]: return manifest, health
    monkeypatch.setattr(server, "_load_catalogue", load)
    install_fake_live_http(monkeypatch, [httpx.ReadTimeout("timed out", request=httpx.Request("GET", url))])
    result = await server.verify_evidence("sample")
    assert result["verdict"] == "unreachable" and result["live_http_status"] is None


async def test_verify_evidence_refuses_browser_without_httpx(monkeypatch: pytest.MonkeyPatch) -> None:
    async def load() -> tuple[dict, dict]: return {"datasets": [{"id": "browser", "url": "https://www.eperolehan.gov.my/a", "source": "ePerolehan"}]}, {"datasets": [{"dataset_id": "browser", "access_dependency": "browser", "access_method": "Camofox"}]}
    class ForbiddenClient:
        def __init__(self, *args, **kwargs): raise AssertionError("unexpected HTTP")
    monkeypatch.setattr(server, "_load_catalogue", load); monkeypatch.setattr(server.httpx, "AsyncClient", ForbiddenClient)
    result = await server.verify_evidence("browser")
    assert result["verdict"] == "not_verifiable"


async def test_verify_evidence_refuses_unapproved_redirect(monkeypatch: pytest.MonkeyPatch) -> None:
    url = "https://api.data.gov.my/data-catalogue?id=sample"; manifest, health = _verification_fixture(url)
    async def load() -> tuple[dict, dict]: return manifest, health
    monkeypatch.setattr(server, "_load_catalogue", load)
    install_fake_live_http(monkeypatch, [httpx.Response(302, headers={"Location": "https://example.com/private"})])
    result = await server.verify_evidence("sample")
    assert result["verdict"] == "not_verifiable" and "example.com" in result["details"][0]


async def test_verify_evidence_uses_cache_without_force_bypass(monkeypatch: pytest.MonkeyPatch) -> None:
    url = "https://api.data.gov.my/data-catalogue?id=sample"; manifest, health = _verification_fixture(url)
    async def load() -> tuple[dict, dict]: return manifest, health
    monkeypatch.setattr(server, "_load_catalogue", load)
    requests = install_fake_live_http(monkeypatch, [httpx.Response(200)])
    first = await server.verify_evidence("sample"); second = await server.verify_evidence("sample")
    assert len(requests) == 1 and first["cached"] is False and second["cached"] is True


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
    assert len(payload) == len(manifest["datasets"])
    assert all(
        set(item) == {"id", "status", "title", "source", "licence", "namespace"}
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


async def test_anomalies_resource_matches_tool_shape_and_order(
    live_data: tuple[dict, dict],
) -> None:
    manifest, health = live_data
    manifest_ids = {item["id"] for item in manifest["datasets"]}
    expected_count = sum(
        item["dataset_id"] in manifest_ids and item.get("anomaly_detected") is True
        for item in health["datasets"]
    )

    async with Client(server.mcp) as client:
        tool_result = await client.call_tool("find_anomalies", {"limit": 200})
        resource_result = await client.read_resource("datapulse://anomalies")

    payload = json.loads(resource_result[0].text)
    assert len(payload) == expected_count
    assert payload[:200] == tool_result.data
    assert all(item["anomaly_detection"] for item in payload)


async def test_reliability_resource_returns_live_grade_counts(live_trends: dict) -> None:
    async with Client(server.mcp) as client:
        result = await client.read_resource("datapulse://reliability")
    assert json.loads(result[0].text) == live_trends["summary"]["by_reliability_grade"]


async def test_dataset_resource_template_returns_full_manifest_entry(
    live_data: tuple[dict, dict],
) -> None:
    manifest, _ = live_data
    expected = manifest["datasets"][0]

    async with Client(server.mcp) as client:
        result = await client.read_resource(f"datapulse://{expected['id']}")

    assert json.loads(result[0].text) == expected


def test_met_weather_uses_content_freshness() -> None:
    health = json.loads((REPO_DIR / "health/latest.json").read_text(encoding="utf-8"))
    weather = next(
        item for item in health["datasets"] if item["dataset_id"] == "met_weather"
    )

    assert weather["last_modified"] is None
    assert weather["content_freshness_date"]
    assert weather["freshness_signal_source"] == "content_date_parse"
    # The live snapshot can age between health runs without changing the
    # content-date freshness signal this test is checking.
    assert weather["status"] in {"fresh", "aging"}


def test_pricecatcher_last_modified_from_header() -> None:
    health = json.loads((REPO_DIR / "health/latest.json").read_text(encoding="utf-8"))
    pricecatcher = next(
        item for item in health["datasets"] if item["dataset_id"] == "pricecatcher"
    )

    assert pricecatcher["last_modified"]
    assert pricecatcher["freshness_signal_source"] == "last_modified_header"


def test_fuelprice_content_freshness_date() -> None:
    health = json.loads((REPO_DIR / "health/latest.json").read_text(encoding="utf-8"))
    fuelprice = next(
        item for item in health["datasets"] if item["dataset_id"] == "fuelprice"
    )
    sample = json.loads((REPO_DIR / "samples/fuelprice.json").read_text(encoding="utf-8"))

    observed_date = datetime.fromisoformat(fuelprice["content_freshness_date"])
    captured_sample_date = datetime.fromisoformat(sample["date"])
    assert observed_date >= captured_sample_date
    assert fuelprice["freshness_signal_source"] == "content_date_parse"


def test_browser_content_freshness_extraction() -> None:
    health = json.loads((REPO_DIR / "health/latest.json").read_text(encoding="utf-8"))
    browser_dataset_ids = {
        "doe_apims",
        "doe_rqims",
        "doe_mqims",
        "kkm_idengue",
        "eperolehan-diklankan",
    }
    browser_datasets = [
        item for item in health["datasets"] if item["dataset_id"] in browser_dataset_ids
    ]

    assert any(item["content_freshness_date"] for item in browser_datasets)


def test_headerless_direct_datasets_distinguish_reference_data() -> None:
    manifest = json.loads((REPO_DIR / "datapulse.json").read_text(encoding="utf-8"))
    health = json.loads((REPO_DIR / "health/latest.json").read_text(encoding="utf-8"))
    reference_ids = {
        item["id"] for item in manifest["datasets"] if item.get("data_type") == "reference"
    }
    headerless_without_content_date = [
        item
        for item in health["datasets"]
        if item.get("http_status") == 200
        and item.get("access_dependency") == "direct"
        and item.get("last_modified") is None
        and item.get("content_freshness_date") is None
    ]

    assert headerless_without_content_date
    assert all(
        item["freshness_signal_source"] == "none"
        and item["status"]
        == ("reference" if item["dataset_id"] in reference_ids else "unknown-freshness")
        for item in headerless_without_content_date
    )


def test_gtfs_static_ktmb_in_manifest() -> None:
    manifest = json.loads((REPO_DIR / "datapulse.json").read_text(encoding="utf-8"))
    entry = next(item for item in manifest["datasets"] if item["id"] == "gtfs_static_ktmb")

    assert entry["source"] == "data.gov.my (GTFS API)"
    assert entry["steward"] == "Keretapi Tanah Melayu Berhad (KTMB)"
    assert entry["url"] == "https://api.data.gov.my/gtfs-static/ktmb"
    assert entry["licence"] == "Creative Commons Attribution 4.0"
    assert entry["namespace"] == "transport"


def test_gtfs_realtime_in_manifest() -> None:
    manifest = json.loads((REPO_DIR / "datapulse.json").read_text(encoding="utf-8"))
    entry = next(item for item in manifest["datasets"] if item["id"] == "gtfs_realtime_ktmb")

    assert entry["url"] == "https://api.data.gov.my/gtfs-realtime/vehicle-position/ktmb"
    assert entry["refresh_frequency"] == "30 seconds"
    assert entry["namespace"] == "transport"


async def test_search_datasets_transport_namespace(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest = json.loads((REPO_DIR / "datapulse.json").read_text(encoding="utf-8"))
    health = json.loads((REPO_DIR / "health/latest.json").read_text(encoding="utf-8"))

    async def fake_load_catalogue() -> tuple[dict, dict]:
        return manifest, health

    monkeypatch.setattr(server, "_load_catalogue", fake_load_catalogue)
    async with Client(server.mcp) as client:
        result = await client.call_tool("search_datasets", {"query": "ktmb"})

    assert result.data[0]["id"] == "gtfs_static_ktmb"


async def test_get_dataset_gtfs_has_calendar_signal(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest = json.loads((REPO_DIR / "datapulse.json").read_text(encoding="utf-8"))
    health = json.loads((REPO_DIR / "health/latest.json").read_text(encoding="utf-8"))

    async def fake_load_catalogue() -> tuple[dict, dict]:
        return manifest, health

    monkeypatch.setattr(server, "_load_catalogue", fake_load_catalogue)
    async with Client(server.mcp) as client:
        result = await client.call_tool(
            "get_dataset", {"dataset_id": "gtfs_static_ktmb"}
        )

    # GTFS freshness may be signalled by a parsed content date or by the
    # provider's Last-Modified header as the live catalogue changes.
    assert result.data["content_freshness_date"] or result.data["last_modified"]
    assert result.data["freshness_signal_source"] in {
        "content_date_parse",
        "last_modified_header",
    }


async def test_gtfs_namespace_present_in_index_resource(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest = json.loads((REPO_DIR / "datapulse.json").read_text(encoding="utf-8"))
    health = json.loads((REPO_DIR / "health/latest.json").read_text(encoding="utf-8"))

    async def fake_load_catalogue() -> tuple[dict, dict]:
        return manifest, health

    monkeypatch.setattr(server, "_load_catalogue", fake_load_catalogue)
    async with Client(server.mcp) as client:
        result = await client.read_resource("datapulse://index")

    payload = json.loads(result[0].text)
    assert any(
        item["id"] == "gtfs_static_ktmb" and item["namespace"] == "transport"
        for item in payload
    )
