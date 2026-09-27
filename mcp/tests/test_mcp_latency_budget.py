"""Latency-budget regression tests for the read-only MCP server.

These tests fail on the pre-fix server: the named budget constants and the
colocated-artefact fast path did not exist, so a slow upstream could hold a
client response for the full 30s per-call ceiling (and a multiple of it across
a chain of calls).
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

import httpx
import pytest
from fastmcp import Client
from fastmcp.exceptions import ToolError


MCP_DIR = Path(__file__).resolve().parents[1]
REPO_DIR = MCP_DIR.parent
sys.path.insert(0, str(MCP_DIR))

import server  # noqa: E402


pytestmark = pytest.mark.anyio


@pytest.fixture(autouse=True)
def isolated_usage_dir(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("DATAPULSE_USAGE_DIR", str(tmp_path / "usage"))
    server._VERIFY_CACHE.clear()


def test_named_budget_constants_are_tight() -> None:
    assert 0 < server.UPSTREAM_CONNECT_TIMEOUT_SECONDS < 5
    assert 0 < server.UPSTREAM_READ_TIMEOUT_SECONDS < 5
    assert 0 < server.TOOL_HANDLER_BUDGET_SECONDS < 10
    assert isinstance(server.UPSTREAM_TIMEOUT, httpx.Timeout)
    assert server.UPSTREAM_TIMEOUT.read == server.UPSTREAM_READ_TIMEOUT_SECONDS
    # The old ceiling was a single 30s timeout; the tail must now be far inside it.
    assert server.TOOL_HANDLER_BUDGET_SECONDS < 30


async def test_published_artefacts_are_served_without_network(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DATAPULSE_ARTIFACT_ROOT", str(REPO_DIR))
    monkeypatch.delenv("DATAPULSE_DISABLE_LOCAL_ARTIFACTS", raising=False)
    # Point DATA_BASE somewhere unroutable: a network fallback would be visible.
    monkeypatch.setattr(server, "DATA_BASE", "http://127.0.0.1:1")

    async def forbidden(*_: Any, **__: Any) -> Any:
        raise AssertionError("published artefact should have been read locally")

    monkeypatch.setattr(server, "_fetch_remote_json", forbidden)

    manifest = await server._fetch_json("datapulse.json")
    health = await server._fetch_json("health/latest.json")

    assert isinstance(manifest["datasets"], list) and manifest["datasets"]
    assert isinstance(health["datasets"], list) and health["datasets"]

    async with Client(server.mcp) as client:
        result = await client.call_tool("get_freshness_summary", {})

    assert result.data["dataset_total"] == len(health["datasets"])
    assert sum(result.data["counts"].values()) <= result.data["dataset_total"]


@pytest.mark.skipif(
    hasattr(os, "geteuid") and os.geteuid() == 0,
    reason="root can read a mode-000 file",
)
async def test_unreadable_local_artefact_falls_back_to_upstream(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    (tmp_path / "health").mkdir()
    unreadable = tmp_path / "health" / "latest.json"
    unreadable.write_text("{}", encoding="utf-8")
    unreadable.chmod(0o000)
    monkeypatch.setattr(server, "_local_artifact_roots", lambda: (tmp_path,))

    sentinel = {"datasets": [{"dataset_id": "remote"}]}

    async def remote(_: str) -> dict:
        return sentinel

    monkeypatch.setattr(server, "_fetch_remote_json", remote)

    assert await server._fetch_json("health/latest.json") == sentinel


async def test_verify_evidence_reports_unverified_within_budget(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest = {
        "datasets": [
            {
                "id": "sample",
                "url": "https://api.data.gov.my/data-catalogue?id=sample",
                "source": "data.gov.my",
            }
        ]
    }
    health = {
        "datasets": [
            {
                "dataset_id": "sample",
                "request_url": "https://api.data.gov.my/data-catalogue?id=sample",
                "access_dependency": "direct",
            }
        ]
    }

    async def load_catalogue() -> tuple[dict, dict]:
        return manifest, health

    async def exhausted(_: str) -> dict:
        raise server._ToolBudgetExceeded("budget spent")

    monkeypatch.setattr(server, "_load_catalogue", load_catalogue)
    monkeypatch.setattr(server, "_fetch_live_receipts", exhausted)

    result = await server.verify_evidence("sample")

    assert result["verdict"] == "not_verifiable"
    assert result["unverified_within_budget"] is True
    assert result["budget_seconds"] == server.TOOL_HANDLER_BUDGET_SECONDS
    assert any("unverified within budget" in detail for detail in result["details"])


class _SlowUpstream:
    """Threaded HTTP stub that holds every response for ``delay`` seconds."""

    def __init__(self, delay: float) -> None:
        self.delay = delay
        self.requests: list[str] = []
        upstream = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:  # noqa: N802
                path = self.path.split("?", 1)[0].lstrip("/")
                upstream.requests.append(path)
                body = upstream._body(path)
                time.sleep(upstream.delay)
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *args: object) -> None:
                return

        self._server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self._server.daemon_threads = True
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()

    @property
    def base_url(self) -> str:
        return f"http://127.0.0.1:{self._server.server_address[1]}"

    @staticmethod
    def _body(path: str) -> bytes:
        if path == "datapulse.json":
            return json.dumps(
                {"datasets": [{"id": "fuelprice", "name": "Fuel", "source": "Test"}]}
            ).encode()
        if path == "health/latest.json":
            return json.dumps(
                {"datasets": [{"dataset_id": "fuelprice", "status": "fresh"}]}
            ).encode()
        return b"{}"

    def close(self) -> None:
        self._server.shutdown()
        self._server.server_close()


async def test_handler_budget_cuts_off_a_slow_upstream(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    upstream = _SlowUpstream(delay=2.5)
    try:
        monkeypatch.setenv("DATAPULSE_DISABLE_LOCAL_ARTIFACTS", "1")
        monkeypatch.setattr(server, "DATA_BASE", upstream.base_url)

        started = time.monotonic()
        errored = False
        try:
            async with Client(server.mcp) as client:
                await client.call_tool("get_data_passport", {"dataset_id": "fuelprice"})
        except ToolError:
            errored = True
        elapsed = time.monotonic() - started
    finally:
        upstream.close()

    # A chained handler must be cut off by the total budget even though each
    # individual upstream response is under the old 30s ceiling.
    assert elapsed <= server.TOOL_HANDLER_BUDGET_SECONDS + 2.0, elapsed
    assert elapsed < 30, elapsed
    assert errored, "slow upstream must fail fast rather than return stale data"
    assert upstream.requests, "the stub upstream was never called"


async def test_direct_loader_calls_stay_under_the_per_call_budget(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    upstream = _SlowUpstream(delay=30.0)
    try:
        monkeypatch.setenv("DATAPULSE_DISABLE_LOCAL_ARTIFACTS", "1")
        monkeypatch.setattr(server, "DATA_BASE", upstream.base_url)

        started = time.monotonic()
        with pytest.raises(httpx.TimeoutException):
            await server._fetch_json("datapulse.json")
        elapsed = time.monotonic() - started
    finally:
        upstream.close()

    assert elapsed < 10, elapsed
    assert upstream.requests == ["datapulse.json"]
