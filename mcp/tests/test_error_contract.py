"""Caller-facing tool errors use a stable, actionable contract."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import httpx
import pytest
from fastmcp import Client
from fastmcp.exceptions import ToolError


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import server  # noqa: E402


pytestmark = pytest.mark.anyio
ERROR_CODES = {
    "missing_argument", "unknown_argument", "invalid_argument",
    "unknown_dataset", "unavailable", "internal",
}


async def _failed_call(client: Client, tool: str, arguments: dict[str, Any]) -> dict[str, Any]:
    with pytest.raises(ToolError) as caught:
        await client.call_tool(tool, arguments)
    rendered = str(caught.value)
    assert "pydantic.dev" not in rendered
    assert "input_value" not in rendered
    assert "input_type" not in rendered
    assert "Traceback" not in rendered
    payload = json.loads(rendered)
    assert set(payload) == {"error"}
    error = payload["error"]
    assert set(error) == {"code", "argument", "tool", "message", "hint"}
    assert error["code"] in ERROR_CODES
    assert error["tool"] == tool
    assert isinstance(error["message"], str) and error["message"]
    assert isinstance(error["hint"], str) and error["hint"]
    return error


async def test_missing_argument_names_declared_parameter(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("DATAPULSE_USAGE_DIR", str(tmp_path))
    async with Client(server.mcp) as client:
        error = await _failed_call(client, "get_dataset", {})
    assert error["code"] == "missing_argument"
    assert error["argument"] == "dataset_id"
    assert "dataset_id" in error["hint"]


async def test_attestation_wrong_argument_points_to_reference(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("DATAPULSE_USAGE_DIR", str(tmp_path))
    async with Client(server.mcp) as client:
        error = await _failed_call(client, "verify_attestation", {"dataset_id": "fuelprice"})
    assert error["code"] == "missing_argument"
    assert error["argument"] == "reference"
    assert "reference" in error["hint"]
    assert "get_dataset" in error["hint"]
    assert "attestation_ref" in error["hint"]
    assert "fuelprice" not in json.dumps(error)


async def test_unknown_dataset_keeps_id_and_search_hint(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("DATAPULSE_USAGE_DIR", str(tmp_path))

    async def fake_load_catalogue() -> tuple[dict[str, Any], dict[str, Any]]:
        return {"datasets": []}, {"datasets": []}

    monkeypatch.setattr(server, "_load_catalogue", fake_load_catalogue)
    async with Client(server.mcp) as client:
        error = await _failed_call(client, "get_dataset", {"dataset_id": "not-a-dataset"})
    assert error["code"] == "unknown_dataset"
    assert error["argument"] == "dataset_id"
    assert "not-a-dataset" in error["message"]
    assert "search_datasets" in error["hint"]


async def test_unknown_and_invalid_arguments_have_named_errors(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("DATAPULSE_USAGE_DIR", str(tmp_path))
    async with Client(server.mcp) as client:
        unknown = await _failed_call(client, "get_dataset", {"dataset_id": "alpha", "guess": "x"})
        invalid = await _failed_call(client, "get_dataset", {"dataset_id": 42})
    assert (unknown["code"], unknown["argument"]) == ("unknown_argument", "guess")
    assert (invalid["code"], invalid["argument"]) == ("invalid_argument", "dataset_id")


async def test_unavailable_and_internal_errors_hide_diagnostics(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("DATAPULSE_USAGE_DIR", str(tmp_path))

    async def unavailable() -> tuple[dict[str, Any], dict[str, Any]]:
        raise httpx.ConnectError("private upstream diagnostic")

    async def broken() -> tuple[dict[str, Any], dict[str, Any]]:
        raise RuntimeError("private implementation diagnostic")

    monkeypatch.setattr(server, "_load_catalogue", unavailable)
    async with Client(server.mcp) as client:
        upstream = await _failed_call(client, "get_dataset", {"dataset_id": "alpha"})
        monkeypatch.setattr(server, "_load_catalogue", broken)
        internal = await _failed_call(client, "get_dataset", {"dataset_id": "alpha"})
    assert (upstream["code"], upstream["argument"]) == ("unavailable", None)
    assert (internal["code"], internal["argument"]) == ("internal", None)
    assert "private" not in json.dumps([upstream, internal])


async def test_dataset_id_aliases_return_data(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("DATAPULSE_USAGE_DIR", str(tmp_path))
    manifest = {"datasets": [{"id": "alpha", "name": "Alpha Dataset"}]}

    async def fake_load_manifest() -> dict[str, Any]:
        return manifest

    async def fake_load_reconciliation() -> dict[str, Any]:
        return {"groups": []}

    async def fake_load_catalogue() -> tuple[dict[str, Any], dict[str, Any]]:
        return manifest, {"datasets": []}

    monkeypatch.setattr(server, "_load_manifest", fake_load_manifest)
    monkeypatch.setattr(server, "_load_reconciliation", fake_load_reconciliation)
    monkeypatch.setattr(server, "_load_catalogue", fake_load_catalogue)
    async with Client(server.mcp) as client:
        reconciliation = await client.call_tool("check_reconciliation", {"dataset_id": "alpha"})
        provenance = await client.call_tool("get_provenance", {"dataset_id": "alpha"})
    assert reconciliation.data["matched_dataset_id"] == "alpha"
    assert [row["id"] for row in provenance.data] == ["alpha"]
