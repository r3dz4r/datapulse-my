#!/usr/bin/env python3
"""Stamp the repo HEAD into MCP source for deployment introspection."""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SERVER_PY = ROOT / "mcp/server.py"
MCP_JSON = ROOT / "mcp.json"


def current_sha() -> str:
    return subprocess.check_output(
        ["git", "-C", str(ROOT), "rev-parse", "HEAD"], text=True
    ).strip()


def current_sha_short() -> str:
    return current_sha()[:7]


def current_date() -> str:
    return subprocess.check_output(
        [
            "git",
            "-C",
            str(ROOT),
            "show",
            "-s",
            "--format=%cd",
            "--date=short",
            "HEAD",
        ],
        text=True,
    ).strip()


def stamp_server_py(sha: str, date: str) -> None:
    text = SERVER_PY.read_text(encoding="utf-8")
    stamped_sha, sha_count = re.subn(
        r'SOURCE_COMMIT_SHA\s*=\s*os\.getenv\("DATAPULSE_MCP_SOURCE_SHA",\s*"[^"]*"\)',
        f'SOURCE_COMMIT_SHA = os.getenv("DATAPULSE_MCP_SOURCE_SHA", "{sha}")',
        text,
    )
    stamped_text, date_count = re.subn(
        r'SOURCE_COMMIT_DATE\s*=\s*os\.getenv\("DATAPULSE_MCP_SOURCE_DATE",\s*"[^"]*"\)',
        f'SOURCE_COMMIT_DATE = os.getenv("DATAPULSE_MCP_SOURCE_DATE", "{date}")',
        stamped_sha,
    )
    if sha_count != 1 or date_count != 1:
        raise RuntimeError("expected exactly one MCP source SHA and date marker")
    SERVER_PY.write_text(stamped_text, encoding="utf-8")


def stamp_mcp_json(sha: str, date: str) -> None:
    data = json.loads(MCP_JSON.read_text(encoding="utf-8"))
    data["server"]["source_commit_sha"] = sha
    data["server"]["source_commit_date"] = date
    MCP_JSON.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    sha = current_sha()
    date = current_date()
    stamp_server_py(sha, date)
    stamp_mcp_json(sha, date)
    print(f"Stamped source_commit_sha={sha[:7]} date={date}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
