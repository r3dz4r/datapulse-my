"""mcp.json server.source_commit_sha and mcp/server.py SOURCE_COMMIT_SHA must agree."""

from __future__ import annotations

import json
import re
from pathlib import Path


MCP_DIR = Path(__file__).resolve().parents[1]
ROOT = MCP_DIR.parents[0]
SHA_RE = re.compile(r"^[0-9a-f]{40}$")


def _stamp_sha() -> str:
    """SHA stamped into the server source — the repo HEAD at time of last bump."""
    text = (MCP_DIR / "server.py").read_text(encoding="utf-8")
    match = re.search(
        r'SOURCE_COMMIT_SHA\s*=\s*os\.getenv\("DATAPULSE_MCP_SOURCE_SHA",\s*"([^"]+)"\)',
        text,
    )
    assert match is not None, "SOURCE_COMMIT_SHA default not found in mcp/server.py"
    return match.group(1)


def _mcp_json_sha() -> str:
    data = json.loads((ROOT / "mcp.json").read_text(encoding="utf-8"))
    return data["server"]["source_commit_sha"]


def test_source_commit_sha_stamp_agrees() -> None:
    """mcp.json server.source_commit_sha and mcp/server.py SOURCE_COMMIT_SHA must agree."""
    server_sha = _stamp_sha()
    json_sha = _mcp_json_sha()

    assert SHA_RE.match(server_sha), f"mcp/server.py SOURCE_COMMIT_SHA is not a valid SHA: {server_sha}"
    assert SHA_RE.match(json_sha), f"mcp.json source_commit_sha is not a valid SHA: {json_sha}"
    assert json_sha == server_sha, (
        f"mcp.json source_commit_sha ({json_sha[:7]}) differs from mcp/server.py SOURCE_COMMIT_SHA ({server_sha[:7]})"
    )
