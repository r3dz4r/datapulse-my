#!/usr/bin/env python3
"""Compare a deployed MCP server's source marker with a repository HEAD."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


DEFAULT_ENDPOINT = "https://mcp.data-pulse.my/mcp"
ACCEPT = "application/json, text/event-stream"
PROTOCOL_VERSION = "2025-03-26"


def repo_sha(repo_path: Path) -> str:
    return subprocess.check_output(
        ["git", "-C", str(repo_path), "rev-parse", "HEAD"], text=True
    ).strip()


def _decode_response(payload: bytes) -> dict[str, Any]:
    text = payload.decode("utf-8")
    if not text.strip():
        return {}
    if text.lstrip().startswith("{"):
        return json.loads(text)
    for line in text.splitlines():
        if line.startswith("data: "):
            message = json.loads(line.removeprefix("data: "))
            if isinstance(message, dict):
                return message
    raise ValueError("MCP endpoint returned neither JSON nor a JSON SSE event")


def _post(
    endpoint: str,
    message: dict[str, Any],
    *,
    session_id: str | None = None,
) -> tuple[dict[str, Any], str | None]:
    headers = {
        "Accept": ACCEPT,
        "Content-Type": "application/json",
        "User-Agent": "DataPulse-MCP-Deployment-Verify/1.0",
    }
    if session_id is not None:
        headers["Mcp-Session-Id"] = session_id
    request = Request(
        endpoint,
        data=json.dumps(message, separators=(",", ":")).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    with urlopen(request, timeout=15) as response:
        return _decode_response(response.read()), response.headers.get("Mcp-Session-Id")


def deployed_source_sha(endpoint: str) -> str:
    initialized, session_id = _post(
        endpoint,
        {
            "jsonrpc": "2.0",
            "method": "initialize",
            "params": {
                "protocolVersion": PROTOCOL_VERSION,
                "capabilities": {},
                "clientInfo": {"name": "verify-mcp-deployment", "version": "1"},
            },
            "id": 1,
        },
    )
    if not session_id:
        raise ValueError("initialize response omitted Mcp-Session-Id")
    server_info = initialized.get("result", {}).get("serverInfo", {})
    deployed_sha = server_info.get("source_commit_sha")

    _post(
        endpoint,
        {"jsonrpc": "2.0", "method": "notifications/initialized"},
        session_id=session_id,
    )
    tools, _ = _post(
        endpoint,
        {"jsonrpc": "2.0", "method": "tools/list", "id": 2},
        session_id=session_id,
    )
    if not isinstance(tools.get("result", {}).get("tools"), list):
        raise ValueError("tools/list response omitted the tools array")
    return deployed_sha if isinstance(deployed_sha, str) else "<missing>"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--endpoint", default=DEFAULT_ENDPOINT)
    parser.add_argument("--repo-path", type=Path, default=Path.cwd())
    parser.add_argument(
        "--deployed-path",
        type=Path,
        help="Accepted for deployment-tool compatibility; endpoint introspection is authoritative.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        local_sha = repo_sha(args.repo_path)
        deployed_sha = deployed_source_sha(args.endpoint)
    except (HTTPError, URLError, TimeoutError, OSError, ValueError) as error:
        print(f"UNREACHABLE: {error}")
        return 2

    if deployed_sha == local_sha:
        print(f"OK: deployed matches repo HEAD {local_sha}")
        return 0
    print(f"MISMATCH: deployed={deployed_sha} repo={local_sha}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
