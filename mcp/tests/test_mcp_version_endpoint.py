"""HTTP identity of the MCP module loaded by the running process."""

from __future__ import annotations

import hashlib
import re
import runpy
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx
import pytest
from fastmcp import FastMCP


MCP_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(MCP_DIR))

import server  # noqa: E402


pytestmark = pytest.mark.anyio


async def _get(path: str, mcp: FastMCP = server.mcp) -> httpx.Response:
    app = mcp.http_app(middleware=server.HTTP_MIDDLEWARE)
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            return await client.get(path)


async def test_version_reports_loaded_module_identity_and_executing_file_digest() -> None:
    response = await _get("/version")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/json")
    assert response.headers["x-datapulse-request-id"]
    body = response.json()
    assert set(body) == {"schema", "server", "version", "source", "artifact", "process"}
    assert body["schema"] == "datapulse/mcp-version/v1"
    assert body["server"] == "DataPulse"
    assert body["version"] == server.SOURCE_VERSION_STRING
    assert body["source"] == {
        "commit": server.SOURCE_COMMIT_SHA,
        "commit_date": server.SOURCE_COMMIT_DATE,
        "path": "mcp/server.py",
    }
    assert re.fullmatch(r"[0-9a-f]{40}|dev", body["source"]["commit"])
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", body["source"]["commit_date"])
    assert set(body["artifact"]) == {"file", "sha256", "bytes", "digest_taken_at"}
    executing_bytes = (MCP_DIR / "server.py").read_bytes()
    assert body["artifact"]["file"] == "server.py"
    assert body["artifact"]["sha256"] == hashlib.sha256(executing_bytes).hexdigest()
    assert type(body["artifact"]["bytes"]) is int
    assert body["artifact"]["bytes"] == len(executing_bytes)
    assert set(body["process"]) == {"loaded_at"}
    digest_at = datetime.fromisoformat(body["artifact"]["digest_taken_at"].replace("Z", "+00:00"))
    loaded_at = datetime.fromisoformat(body["process"]["loaded_at"].replace("Z", "+00:00"))
    assert digest_at.utcoffset() == loaded_at.utcoffset() == timedelta(0)
    assert digest_at <= loaded_at <= datetime.now(timezone.utc)
    for forbidden in ("/home/", "/srv/", "HOME="):
        assert forbidden not in response.text
    values = [body["schema"], body["server"], body["version"]]
    for section in ("source", "artifact", "process"):
        values.extend(value for value in body[section].values() if isinstance(value, str))
    assert all(not Path(value).is_absolute() for value in values)


async def test_version_remains_frozen_without_request_time_file_or_environment_reads(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    before = await _get("/version")
    assert before.status_code == 200

    def forbidden_read(*args: object, **kwargs: object) -> None:
        pytest.fail("/version must only serialise the loaded constants")

    monkeypatch.setenv("DATAPULSE_MCP_SOURCE_SHA", "caller-controlled-override")
    monkeypatch.setenv("DATAPULSE_MCP_SOURCE_DATE", "2099-01-01")
    monkeypatch.setattr(Path, "read_bytes", forbidden_read)
    monkeypatch.setattr(Path, "read_text", forbidden_read)
    monkeypatch.setattr(server.os, "getenv", forbidden_read)
    after = await _get("/version")

    assert after.status_code == 200
    assert after.json() == before.json()


@pytest.mark.parametrize("error", [FileNotFoundError, PermissionError])
async def test_unreadable_executing_file_keeps_commit_identity_available(
    monkeypatch: pytest.MonkeyPatch, error: type[OSError],
) -> None:
    original_read_bytes = Path.read_bytes

    def unreadable(self: Path) -> bytes:
        if self == MCP_DIR / "server.py":
            raise error("executing file unavailable")
        return original_read_bytes(self)

    with monkeypatch.context() as patch:
        patch.setattr(Path, "read_bytes", unreadable)
        # Isolate the existing import-time protocol model registration too.
        patch.setattr(server.mcp_types, "Implementation", server.MCPImplementation)
        imported = runpy.run_path(str(MCP_DIR / "server.py"))
        response = await _get("/version", imported["mcp"])

    assert response.status_code == 200
    body = response.json()
    assert body["source"]["commit"] == imported["SOURCE_COMMIT_SHA"]
    assert body["source"]["commit_date"] == imported["SOURCE_COMMIT_DATE"]
    assert body["artifact"]["sha256"] is None
    assert body["artifact"]["bytes"] is None
    assert body["artifact"]["file"] == "server.py"
    assert body["artifact"]["digest_taken_at"]
    assert body["process"]["loaded_at"]


async def test_get_mcp_still_requires_the_mcp_transport_contract() -> None:
    response = await _get("/mcp")

    assert response.status_code != 200
