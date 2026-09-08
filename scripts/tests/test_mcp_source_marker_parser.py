"""Regression coverage for checked-in MCP source-marker parsing."""

from __future__ import annotations

from pathlib import Path

from scripts.gen_mcp_reference import _checked_in_server_marker


def test_checked_in_server_marker_reader_extracts_literal_default(tmp_path: Path) -> None:
    server = tmp_path / "mcp" / "server.py"
    server.parent.mkdir()
    server.write_text(
        'import os\nSOURCE_COMMIT_SHA = os.getenv("DATAPULSE_MCP_SOURCE_SHA", "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa")\n',
        encoding="utf-8",
    )

    assert _checked_in_server_marker(tmp_path) == "a" * 40


def test_checked_in_server_marker_reader_accepts_dev_fixture_sentinel(tmp_path: Path) -> None:
    server = tmp_path / "mcp" / "server.py"
    server.parent.mkdir()
    server.write_text(
        'import os\nSOURCE_COMMIT_SHA = os.getenv("DATAPULSE_MCP_SOURCE_SHA", "dev")\n',
        encoding="utf-8",
    )

    assert _checked_in_server_marker(tmp_path) == "dev"
