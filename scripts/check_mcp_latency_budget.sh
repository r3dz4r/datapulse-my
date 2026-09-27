#!/usr/bin/env bash
# Measure the MCP server's latency budget against a deliberately slow stub
# upstream. This proves the bound by observation: it stands up the real tool
# handler, points its upstream at a stub that holds every response open, and
# asserts the call returns inside the declared budget. It never greps the
# source for a constant.
#
# Exit 0 when both checks pass; non-zero otherwise.
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"

python3 - <<'PY'
from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

REPO = Path.cwd()
sys.path.insert(0, str(REPO / "mcp"))

# Keep the harness self-contained and quiet: usage telemetry goes to a temp
# directory, and the expected timeout traceback is not an acceptance signal.
os.environ.setdefault(
    "DATAPULSE_USAGE_DIR", tempfile.mkdtemp(prefix="datapulse-harness-usage-")
)
logging.getLogger("fastmcp").setLevel(logging.CRITICAL)
logging.getLogger("uvicorn.error").setLevel(logging.CRITICAL)

# The stub holds every response for this long. It is deliberately longer than
# the per-call read budget so the handler must cut the call off.
STUB_DELAY_SECONDS = 2.5

REQUESTS: list[str] = []


class _QuietStubServer(ThreadingHTTPServer):
    daemon_threads = True

    def handle_error(self, request: object, client_address: object) -> None:
        # The handler is still sleeping when the bounded client disconnects.
        exc = sys.exc_info()[1]
        if not isinstance(exc, (BrokenPipeError, ConnectionResetError)):
            super().handle_error(request, client_address)


class StubHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802
        path = self.path.split("?", 1)[0].lstrip("/")
        REQUESTS.append(path)
        body = self._body(path)
        time.sleep(STUB_DELAY_SECONDS)
        try:
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            return

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

    def log_message(self, *args: object) -> None:
        return


httpd = _QuietStubServer(("127.0.0.1", 0), StubHandler)
threading.Thread(target=httpd.serve_forever, daemon=True).start()
stub_base = f"http://127.0.0.1:{httpd.server_address[1]}"

# Import after the stub exists; the import-time manifest probe reads the
# committed datapulse.json locally and never touches the network.
import server  # noqa: E402
from fastmcp import Client  # noqa: E402
from fastmcp.exceptions import ToolError  # noqa: E402

# FastMCP logs the expected timeout traceback at ERROR before masking it into a
# ToolError; the harness outcome is the measured wall-clock, so silence it.
logging.disable(logging.CRITICAL)

server.DATA_BASE = stub_base

budget = server.TOOL_HANDLER_BUDGET_SECONDS
read_budget = server.UPSTREAM_READ_TIMEOUT_SECONDS
print(f"declared per-call read budget : {read_budget:g}s")
print(f"declared per-handler budget   : {budget:g}s")
print(f"stub response delay           : {STUB_DELAY_SECONDS:g}s")

failures: list[str] = []


async def check_local_artefacts() -> None:
    """Published artefacts answer without touching the upstream at all."""
    REQUESTS.clear()
    os.environ.pop("DATAPULSE_DISABLE_LOCAL_ARTIFACTS", None)
    os.environ["DATAPULSE_ARTIFACT_ROOT"] = str(REPO)
    has_artefacts = (REPO / "datapulse.json").is_file() and (
        REPO / "health" / "latest.json"
    ).is_file()
    if not has_artefacts:
        print("local-artefact check          : SKIP (artefacts not present)")
        return
    started = time.monotonic()
    async with Client(server.mcp) as client:
        result = await client.call_tool("search_datasets", {"query": "fuel"})
    elapsed = time.monotonic() - started
    served_locally = not REQUESTS
    print(
        f"local-artefact check          : {elapsed:.2f}s, "
        f"{len(REQUESTS)} upstream request(s), {len(result.data)} match(es)"
    )
    if not served_locally:
        failures.append("published artefacts were not served locally")
    if elapsed >= budget:
        failures.append(f"local read took {elapsed:.2f}s >= budget {budget:g}s")


async def check_bounded_slow_upstream() -> None:
    """A chained handler is cut off by the total budget, not the old 30s ceiling."""
    REQUESTS.clear()
    os.environ["DATAPULSE_DISABLE_LOCAL_ARTIFACTS"] = "1"
    outcome = "returned"
    started = time.monotonic()
    try:
        async with Client(server.mcp) as client:
            await client.call_tool("get_data_passport", {"dataset_id": "fuelprice"})
    except ToolError as exc:
        outcome = f"{exc.__class__.__name__}: {exc}"
    elapsed = time.monotonic() - started
    print(
        f"slow-upstream check           : {elapsed:.2f}s "
        f"({len(REQUESTS)} upstream request(s)); outcome={outcome}"
    )
    if not REQUESTS:
        failures.append("slow-upstream check never reached the stub")
    if elapsed > budget + 2.0:
        failures.append(
            f"slow upstream returned in {elapsed:.2f}s, above "
            f"{budget + 2.0:g}s (budget {budget:g}s + 2s slack)"
        )
    if elapsed >= 30.0:
        failures.append(f"slow upstream still stalled for {elapsed:.2f}s")


async def main() -> int:
    await check_local_artefacts()
    await check_bounded_slow_upstream()
    if failures:
        for failure in failures:
            print(f"FAIL: {failure}", file=sys.stderr)
        return 1
    print(
        f"PASS: measured handler return inside the {budget:g}s budget "
        f"(per-call read {read_budget:g}s)"
    )
    return 0


try:
    raise SystemExit(asyncio.run(main()))
finally:
    httpd.shutdown()
    httpd.server_close()
PY
