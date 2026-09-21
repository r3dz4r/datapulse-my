"""HTTP Accept-header compatibility tests for the MCP transport."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import httpx
import pytest


MCP_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(MCP_DIR))

import server  # noqa: E402


pytestmark = pytest.mark.anyio


INITIALIZE_REQUEST = {
    "jsonrpc": "2.0",
    "id": 1,
    "method": "initialize",
    "params": {
        "protocolVersion": "2026-07-28",
        "capabilities": {},
        "clientInfo": {"name": "accept-header-test", "version": "1"},
    },
}


async def _post_initialize(middleware: list[object], accept: str) -> httpx.Response:
    app = server.mcp.http_app(middleware=middleware)
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            return await client.post(
                "/mcp",
                headers={"Accept": accept},
                json=INITIALIZE_REQUEST,
            )


def _streamable_jsonrpc_result(response: httpx.Response) -> dict[str, object]:
    """Parse the JSON-RPC payload carried in the streamable-HTTP SSE frame."""
    assert response.headers["content-type"].startswith("text/event-stream")
    data_lines = [
        line.removeprefix("data: ")
        for line in response.text.splitlines()
        if line.startswith("data: ")
    ]
    assert len(data_lines) == 1
    message = json.loads(data_lines[0])
    assert message["jsonrpc"] == "2.0"
    assert message["id"] == INITIALIZE_REQUEST["id"]
    return message["result"]


async def test_json_only_accept_is_rejected_without_normalisation_middleware() -> None:
    response = await _post_initialize([], "application/json")

    assert response.status_code == 406


async def test_json_only_accept_is_normalised_for_the_real_mcp_http_app() -> None:
    response = await _post_initialize(server.HTTP_MIDDLEWARE, "application/json")

    assert response.status_code == 200
    result = _streamable_jsonrpc_result(response)
    assert result["serverInfo"]["name"] == "DataPulse"
    assert "protocolVersion" in result


async def test_compliant_accept_keeps_the_existing_streamable_jsonrpc_result_shape() -> None:
    baseline = await _post_initialize([], "application/json, text/event-stream")
    response = await _post_initialize(
        server.HTTP_MIDDLEWARE,
        "application/json, text/event-stream",
    )

    assert baseline.status_code == 200
    assert response.status_code == 200
    assert _streamable_jsonrpc_result(response) == _streamable_jsonrpc_result(baseline)


async def test_normalisation_preserves_accept_header_position_casing_and_media_types() -> None:
    seen_headers: list[list[tuple[bytes, bytes]]] = []

    async def downstream(scope: dict[str, object], receive: object, send: object) -> None:
        seen_headers.append(list(scope["headers"]))

    middleware = server.MCPAcceptHeaderNormalisationMiddleware(downstream)
    original_headers = [
        (b"x-test-before", b"unchanged"),
        (b"Accept", b"application/json, application/problem+json"),
        (b"x-test-after", b"unchanged"),
    ]

    await middleware(
        {"type": "http", "method": "POST", "path": "/mcp", "headers": original_headers},
        None,
        None,
    )

    assert seen_headers == [[
        (b"x-test-before", b"unchanged"),
        (b"Accept", b"application/json, application/problem+json, text/event-stream"),
        (b"x-test-after", b"unchanged"),
    ]]


async def test_normalisation_middleware_leaves_non_post_and_non_mcp_scopes_untouched() -> None:
    seen_headers: list[list[tuple[bytes, bytes]]] = []

    async def downstream(scope: dict[str, object], receive: object, send: object) -> None:
        seen_headers.append(list(scope["headers"]))

    middleware = server.MCPAcceptHeaderNormalisationMiddleware(downstream)
    original_headers = [(b"Accept", b"application/json"), (b"x-test", b"unchanged")]

    for method, path in (("GET", "/mcp"), ("POST", "/not-mcp")):
        await middleware(
            {"type": "http", "method": method, "path": path, "headers": original_headers},
            None,
            None,
        )

    assert seen_headers == [original_headers, original_headers]
