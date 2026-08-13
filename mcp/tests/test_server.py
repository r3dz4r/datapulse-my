"""Live-data integration tests for the DataPulse MY FastMCP server."""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest
from fastmcp import Client


MCP_DIR = Path(__file__).resolve().parents[1]
REPO_DIR = MCP_DIR.parent
sys.path.insert(0, str(MCP_DIR))

import server  # noqa: E402


pytestmark = pytest.mark.anyio


TOOL_PARAMETERS = {
    "search_datasets": {"query", "licence", "source", "limit"},
    "get_dataset": {"dataset_id"},
    "find_stale": {"max_age_hours"},
    "get_provenance": {"dataset_ids"},
    "find_by_licence": {"licence"},
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
    "get_provenance": "Build Citation-Ready Provenance",
    "find_by_licence": "Scope Reusable Data by Licence",
}


@pytest.fixture(scope="module")
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture(scope="module")
def live_data() -> tuple[dict, dict]:
    return (
        json.loads((REPO_DIR / "datapulse.json").read_text(encoding="utf-8")),
        json.loads((REPO_DIR / "health/latest.json").read_text(encoding="utf-8")),
    )


@pytest.fixture(autouse=True)
def local_catalogue(monkeypatch: pytest.MonkeyPatch) -> None:
    manifest = json.loads((REPO_DIR / "datapulse.json").read_text(encoding="utf-8"))
    health = json.loads((REPO_DIR / "health/latest.json").read_text(encoding="utf-8"))

    async def fake_load_catalogue() -> tuple[dict, dict]:
        return manifest, health

    async def fake_load_manifest() -> dict:
        return manifest

    async def fake_load_health() -> dict:
        return health

    monkeypatch.setattr(server, "_load_catalogue", fake_load_catalogue)
    monkeypatch.setattr(server, "_load_manifest", fake_load_manifest)
    monkeypatch.setattr(server, "_load_health", fake_load_health)


async def test_tool_schemas_are_agent_ready(live_data: tuple[dict, dict]) -> None:
    manifest, _ = live_data
    tools = {tool.name: tool for tool in await server.mcp.list_tools()}

    assert set(tools) == set(TOOL_PARAMETERS)
    for tool_name, parameter_names in TOOL_PARAMETERS.items():
        schema = tools[tool_name].parameters
        assert "required" in schema
        assert set(schema["properties"]) == parameter_names
        assert (
            tools[tool_name].annotations.model_dump(exclude_none=True)
            == EXPECTED_TOOL_ANNOTATIONS
        )
        for parameter in schema["properties"].values():
            assert parameter["description"]
            assert "e.g." in parameter["description"]

    assert tools["find_stale"].parameters["required"] == []
    assert tools["get_provenance"].parameters["properties"]["dataset_ids"][
        "examples"
    ] == [["fuelprice", "pricecatcher"]]
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
