"""Read-only contract tests for the bounded Dataset Passport MCP tool."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastmcp import Client


MCP_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(MCP_DIR))
import server  # noqa: E402


pytestmark = pytest.mark.anyio


async def test_get_data_passport_returns_only_published_passport(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []

    async def fetch(path: str) -> dict:
        calls.append(path)
        if path == "datapulse.json":
            return {"datasets": [{"id": "fuelprice"}]}
        if path == "health/latest.json":
            return {"datasets": [{"dataset_id": "fuelprice", "status": "fresh"}]}
        assert path == "data/passports/fuelprice.json"
        return {"schema": "datapulse/v1/dataset-passport", "identity": {"dataset_id": "fuelprice"}}

    monkeypatch.setattr(server, "_fetch_json", fetch)
    async with Client(server.mcp) as client:
        result = await client.call_tool("get_data_passport", {"dataset_id": "fuelprice"})
    assert result.data["evidence_available"] is True
    assert result.data["passport"]["schema"] == "datapulse/v1/dataset-passport"
    assert calls == ["datapulse.json", "health/latest.json", "data/passports/fuelprice.json"]


async def test_get_data_passport_projects_current_health_evidence(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fetch(path: str) -> dict:
        if path == "datapulse.json":
            return {"datasets": [{"id": "fuelprice", "expected_record_count": None}]}
        if path == "health/latest.json":
            return {"datasets": [{
                "dataset_id": "fuelprice", "status": "degraded", "last_checked": "2026-09-10T02:28:19Z",
                "expected_record_count": None, "record_count_within_tolerance": False,
            }]}
        assert path == "data/passports/fuelprice.json"
        return {
            "schema": "datapulse/v1/dataset-passport",
            "identity": {"dataset_id": "fuelprice", "observed_verified_at": "2026-09-08T14:16:20Z"},
            "health_evidence": {"status": "fresh", "last_checked": "2026-09-08T14:16:20Z"},
        }

    monkeypatch.setattr(server, "_fetch_json", fetch)
    result = await server.get_data_passport("fuelprice")
    assert result["passport"]["health_evidence"]["status"] == "degraded"
    assert result["passport"]["health_evidence"]["last_checked"] == "2026-09-10T02:28:19Z"
    assert result["passport"]["health_evidence"]["expected_record_count"] is None
    assert result["passport"]["health_evidence"]["record_count_within_tolerance"] is None
    assert result["passport"]["identity"]["observed_verified_at"] == "2026-09-10T02:28:19Z"


async def test_get_data_passport_returns_explicit_unknown_without_artifact_fetch(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fetch(path: str) -> dict:
        assert path == "datapulse.json"
        return {"datasets": [{"id": "fuelprice"}]}

    monkeypatch.setattr(server, "_fetch_json", fetch)
    assert await server.get_data_passport("not-a-dataset") == {
        "dataset_id": "not-a-dataset", "evidence_available": False, "error": "unknown_dataset_id"
    }


async def test_get_data_passport_rejects_oversized_artifact(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fetch(path: str) -> dict:
        if path == "datapulse.json":
            return {"datasets": [{"id": "fuelprice"}]}
        if path == "health/latest.json":
            return {"datasets": [{"dataset_id": "fuelprice", "status": "fresh"}]}
        return {"schema": "datapulse/v1/dataset-passport", "padding": "x" * 262_145}

    monkeypatch.setattr(server, "_fetch_json", fetch)
    result = await server.get_data_passport("fuelprice")
    assert result["error"] == "passport_exceeds_response_bound"
