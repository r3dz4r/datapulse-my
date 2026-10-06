#!/usr/bin/env python3
"""Render the MCP quickstart connect block in docs/learn.html from the public-surface contract."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Mapping

SCRIPT_ROOT = Path(__file__).resolve().parents[1]
if str(SCRIPT_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPT_ROOT))

from scripts.public_surface_generation import (
    GenerationError,
    load_public_surfaces,
    publish_text_outputs,
    replace_owned_block,
)


ROOT = Path(__file__).resolve().parents[1]
MARKER_NAME = "MCP-QUICKSTART"
OWNED_PAGE = Path("docs/learn.html")
# The connect block appends the same endpoint path segment as the generated
# npra-connect region; the origin itself is read from the contract.
MCP_PATH = "/mcp"
BLOCK_TEMPLATE = """\
        <div class="mcp-layout">
          <div class="code-wrap"><pre><code>{
  "mcpServers": {
    "datapulse-my": {
      "type": "http",
      "url": "%s"
    }
  }
}</code></pre></div>
          <div>
            <p class="section-lead">The read-only MCP surface gives AI systems cited catalogue context for search, freshness, drift, reconciliation, provenance, and evidence review. It complements the official source rather than replacing it.</p>
            <a class="inline-arrow" href="/mcp-reference.md">Read the MCP reference and tool schemas <span aria-hidden="true">&rarr;</span></a>
            <p class="endpoint">Endpoint: <a href="%s">%s</a></p>
          </div>
        </div>"""


def render_block(origins: Mapping[str, str]) -> str:
    """Return the quickstart region rendered solely from the canonical origins."""
    endpoint = origins["mcp"] + MCP_PATH
    return BLOCK_TEMPLATE % (endpoint, endpoint, endpoint)


def generate(root: Path = ROOT, *, check: bool = False) -> bool:
    """Render one owned region of docs/learn.html, returning whether it would change."""
    surfaces = load_public_surfaces(root)
    page = root / OWNED_PAGE
    try:
        source = page.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as error:
        raise GenerationError(f"cannot read {page}: {error}") from error
    rendered = replace_owned_block(source, MARKER_NAME, render_block(surfaces["origins"]))
    return publish_text_outputs({page: rendered}, check=check)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--check", action="store_true", help="Fail if the owned region would change.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        changed = generate(args.root, check=args.check)
    except (GenerationError, OSError, UnicodeError, ValueError) as error:
        print(f"gen_mcp_quickstart.py: {error}", file=sys.stderr)
        return 1
    relative = (args.root / OWNED_PAGE).relative_to(args.root)
    if args.check:
        if changed:
            print(f"Would update {relative}")
            return 1
        return 0
    if changed:
        print(f"Updated {relative}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
