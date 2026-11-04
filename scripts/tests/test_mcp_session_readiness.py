"""MCP sync readiness against a stateless streamable-HTTP server.

mcp/server.py runs ``mcp.run(transport="http", stateless_http=True)`` (def5579):
the SDK then builds a fresh transport per request with ``mcp_session_id=None``
and never sends an ``Mcp-Session-Id`` header. The readiness check must accept
that server and still refuse — and roll back — one whose follow-up requests
fail or whose tools lack the read-only annotations.
"""

from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest

from scripts.tests.test_mcp_source_sync import _readiness_fixture, _run_readiness_sync


ANNOTATED_TOOLS = {
    "tools": [
        {
            "name": "probe",
            "annotations": {
                "readOnlyHint": True,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": True,
            },
        }
    ]
}


class _SessionStub(BaseHTTPRequestHandler):
    """Serves HEAD's identity (v1.2.3+aaaaaaa, see _readiness_fixture).

    ``issue_session`` set: a stateful server that issues that id and answers 400
    to any follow-up not carrying it. Unset: a stateless server that never sends
    the header. ``tools_status`` / ``tools_result`` shape the tools/list answer.
    """

    issue_session: str | None = None
    tools_status = 200
    tools_result: dict[str, object] = ANNOTATED_TOOLS
    seen_session_headers: list[str | None] = []

    def do_POST(self) -> None:  # noqa: N802
        length = int(self.headers.get("Content-Length", "0"))
        request = json.loads(self.rfile.read(length))
        method = request["method"]
        if method != "initialize":
            sent = self.headers.get("Mcp-Session-Id")
            type(self).seen_session_headers.append(sent)
            if self.issue_session is not None and sent != self.issue_session:
                self._reply(400, None)
                return
        if method == "initialize":
            self._reply(
                200,
                {
                    "protocolVersion": "2025-03-26",
                    "capabilities": {},
                    "serverInfo": {"name": "DataPulse MY", "version": "v1.2.3+aaaaaaa"},
                },
                request["id"],
                session=self.issue_session,
            )
        elif method == "notifications/initialized":
            self._reply(202, None)
        else:
            self._reply(self.tools_status, self.tools_result, request["id"])

    def _reply(
        self,
        status: int,
        result: dict[str, object] | None,
        request_id: int | None = None,
        session: str | None = None,
    ) -> None:
        self.send_response(status)
        if session is not None:
            self.send_header("Mcp-Session-Id", session)
        encoded = b""
        if result is not None:
            payload = json.dumps({"jsonrpc": "2.0", "id": request_id, "result": result})
            encoded = f"data: {payload}\n\n".encode("utf-8")
            self.send_header("Content-Type", "text/event-stream")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def log_message(self, format: str, *args: object) -> None:
        return


def _sync(
    tmp_path: Path,
    issue_session: str | None,
    tools_status: int = 200,
    tools_result: dict[str, object] = ANNOTATED_TOOLS,
):
    source, deployed, env = _readiness_fixture(tmp_path)
    _SessionStub.issue_session = issue_session
    _SessionStub.tools_status = tools_status
    _SessionStub.tools_result = tools_result
    _SessionStub.seen_session_headers = []
    server = HTTPServer(("127.0.0.1", 0), _SessionStub)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        result = _run_readiness_sync(
            source,
            deployed,
            f"http://127.0.0.1:{server.server_port}/mcp",
            env,
            budget="5",
            timeout=30,
        )
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
    return result, deployed, list(_SessionStub.seen_session_headers)


def test_stateless_server_without_session_id_is_accepted(tmp_path: Path) -> None:
    result, deployed, seen = _sync(tmp_path, issue_session=None)

    assert "omitted Mcp-Session-Id" not in result.stderr
    assert result.returncode == 0, result.stderr
    assert "rolling back failed deployment" not in result.stdout
    assert "deployment complete" in result.stdout
    assert "session=stateless" in result.stdout
    assert "a" * 40 in deployed.read_text(encoding="utf-8")
    # notifications/initialized and tools/list were both sent, with no session header.
    assert seen == [None, None]


def test_stateful_server_session_id_is_still_echoed(tmp_path: Path) -> None:
    result, _deployed, seen = _sync(tmp_path, issue_session="stateful-session")

    assert result.returncode == 0, result.stderr
    assert "deployment complete" in result.stdout
    assert "session=stateful" in result.stdout
    assert seen == ["stateful-session", "stateful-session"]


@pytest.mark.parametrize(
    ("tools_status", "tools_result", "failure"),
    [
        (500, {"error": "boom"}, "MCP tools/list verification failed"),
        (200, {"tools": []}, "live tools/list is missing the complete read-only annotations"),
        (
            200,
            {"tools": [{"name": "probe", "annotations": {"readOnlyHint": False}}]},
            "live tools/list is missing the complete read-only annotations",
        ),
    ],
)
def test_unhealthy_stateless_server_is_refused_and_rolled_back(
    tmp_path: Path, tools_status: int, tools_result: dict[str, object], failure: str
) -> None:
    result, deployed, _seen = _sync(
        tmp_path, issue_session=None, tools_status=tools_status, tools_result=tools_result
    )

    assert result.returncode != 0
    assert failure in result.stderr
    assert "rolling back failed deployment" in result.stdout
    assert "rollback complete" in result.stdout
    assert "deployment complete" not in result.stdout
    assert deployed.read_text(encoding="utf-8") == "old deployed source\n"
