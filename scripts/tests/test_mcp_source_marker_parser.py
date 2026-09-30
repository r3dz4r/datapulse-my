"""Regression coverage for removing server-marker generation authority."""

from __future__ import annotations

import asyncio
import json
import shutil
from pathlib import Path

import pytest

from scripts import gen_mcp_reference


ROOT = gen_mcp_reference.ROOT
STALE_MARKER = "a" * 40
DERIVED_SHA = "b" * 40
DERIVED_DATE = "2026-09-08"


def test_generation_ignores_a_stale_checked_in_server_marker(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A stale server literal cannot override the revision derived from MCP history."""
    fixture_root = tmp_path / "repo"
    shutil.copytree(
        ROOT,
        fixture_root,
        ignore=shutil.ignore_patterns(".git", ".venv", "__pycache__", ".pytest_cache"),
    )
    (fixture_root / "mcp" / "server.py").write_text(
        "import os\n"
        'SOURCE_COMMIT_SHA = os.getenv("DATAPULSE_MCP_SOURCE_SHA", "'
        + STALE_MARKER
        + '")\n',
        encoding="utf-8",
    )
    rendered: dict[Path, str] = {}

    def capture_outputs(outputs: dict[Path, str], *, check: bool = False) -> bool:
        assert check is False
        rendered.update(outputs)
        return False

    monkeypatch.delenv("DATAPULSE_SOURCE_COMMIT_SHA", raising=False)
    monkeypatch.delenv("DATAPULSE_SOURCE_COMMIT_DATE", raising=False)
    monkeypatch.setattr(gen_mcp_reference, "newest_mcp_sha", lambda root: DERIVED_SHA)
    monkeypatch.setattr(
        gen_mcp_reference,
        "_source_commit_date",
        lambda root, sha: DERIVED_DATE,
    )
    monkeypatch.setattr(gen_mcp_reference, "publish_text_outputs", capture_outputs)

    changed = asyncio.run(gen_mcp_reference.generate(fixture_root))

    assert changed is False
    assert DERIVED_SHA != STALE_MARKER
    assert json.loads(rendered[fixture_root / "mcp.json"])["server"]["source_commit_sha"] == DERIVED_SHA
    assert json.loads(rendered[fixture_root / "agent.json"])["source"] == {
        "commit_sha": DERIVED_SHA,
        "commit_date": DERIVED_DATE,
    }
