"""The published MCP source identity must follow default-branch MCP history."""

from __future__ import annotations

import json
import re
from pathlib import Path

from scripts.gen_mcp_reference import _source_identity

MCP_DIR = Path(__file__).resolve().parents[1]
ROOT = MCP_DIR.parents[0]
SHA_RE = re.compile(r"^[0-9a-f]{40}$")


def test_source_commit_sha_matches_derived_mcp_revision() -> None:
    """mcp.json must publish the revision used by the deployment check."""
    server = json.loads((ROOT / "mcp.json").read_text(encoding="utf-8"))["server"]
    derived_sha, derived_date = _source_identity(ROOT, None, None)

    assert SHA_RE.match(derived_sha), f"derived MCP source SHA is invalid: {derived_sha}"
    assert server["source_commit_sha"] == derived_sha
    assert server["source_commit_date"] == derived_date
