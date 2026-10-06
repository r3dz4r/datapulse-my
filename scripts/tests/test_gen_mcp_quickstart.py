#!/usr/bin/env python3
"""Tests for the generated MCP quickstart region on docs/learn.html."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from scripts.gen_mcp_quickstart import MARKER_NAME, render_block
from scripts.public_surface_generation import load_public_surfaces


OWNED_PAGE = ROOT / "docs/learn.html"


def _origins(mcp: str) -> dict[str, str]:
    """Return the minimal origins mapping with a caller-supplied MCP origin."""
    return {"mcp": mcp}


def test_render_block_sources_endpoint_from_the_mcp_origin() -> None:
    injected = "https://mcp.example.invalid"

    rendered = render_block(_origins(injected))

    assert f'"{injected}/mcp"' in rendered
    assert f'href="{injected}/mcp"' in rendered
    assert f">{injected}/mcp</a>" in rendered


def test_render_block_is_stable_across_calls() -> None:
    origins = _origins("https://mcp.example.invalid")

    assert render_block(origins) == render_block(origins)


def test_owned_marker_pair_appears_exactly_once_in_the_page() -> None:
    page = OWNED_PAGE.read_text(encoding="utf-8")

    assert page.count(f"<!-- BEGIN {MARKER_NAME} -->") == 1
    assert page.count(f"<!-- END {MARKER_NAME} -->") == 1


def test_committed_region_matches_the_render_from_the_contract() -> None:
    origins = load_public_surfaces(ROOT)["origins"]

    assert render_block(origins) in OWNED_PAGE.read_text(encoding="utf-8")


def test_check_mode_is_clean_for_the_committed_page() -> None:
    result = subprocess.run(
        [sys.executable, "scripts/gen_mcp_quickstart.py", "--check"],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stdout + result.stderr
