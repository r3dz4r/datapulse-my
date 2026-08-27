#!/usr/bin/env python3
"""Generate canonical sitemap and marker-owned public discovery blocks."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from xml.sax.saxutils import escape

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.public_surface_generation import (
    GenerationError,
    load_public_surfaces,
    publish_text_outputs,
    replace_owned_block,
)


MARKER = "public-discovery"

# Hand-authored prose may still reference the retired apex or GitHub Pages
# origins in markdown link targets; those links are current-origin facts and
# are rewritten to the canonical website origin on every regeneration.
STALE_ORIGIN_LINK_RE = re.compile(
    r"\]\(https://(?:data-pulse\.my|r3dz4r\.github\.io/datapulse-my)"
    r"(?P<path>/[^)\s]*)?\)"
)


def canonicalize_origin_links(text: str, website: str) -> str:
    """Rewrite stale website-origin markdown link targets to the canonical origin."""
    return STALE_ORIGIN_LINK_RE.sub(
        lambda match: f"]({website}{match.group('path') or ''})", text
    )


def _url(origin: str, path: str) -> str:
    return origin + path if path != "/" else origin + "/"


def render_sitemap(config: dict) -> str:
    """Render configured public paths in declared order."""
    origin = config["origins"]["website"]
    urls = [*config["pages"], *config["artifacts"]]
    lines = ['<?xml version="1.0" encoding="UTF-8"?>', '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    lines.extend(f"  <url><loc>{escape(_url(origin, path))}</loc></url>" for path in urls)
    lines.append("</urlset>")
    return "\n".join(lines) + "\n"


def render_discovery_block(config: dict, target: str) -> str:
    """Render the target-specific list from the same canonical origins."""
    website = config["origins"]["website"]
    mcp = config["origins"]["mcp"]
    links = [
        ("LLM index", f"{website}/llms.txt"),
        ("Agent manifest", f"{website}/agent.json"),
        ("MCP advertisement", f"{website}/mcp.json"),
        ("Sitemap", f"{website}/sitemap.xml"),
        ("MCP endpoint", f"{mcp}/mcp"),
    ]
    if target == "robots.txt":
        return "\n".join(f"# {label}: {url}" for label, url in links[:-1]) + f"\nSitemap: {website}/sitemap.xml"
    return "\n".join(f"- [{label}]({url})" for label, url in links)


def generate(root: Path, *, check: bool = False, validate_only: bool = False) -> bool:
    """Validate and render every discovery output before the first write."""
    config = load_public_surfaces(root)
    outputs: dict[Path, str] = {root / "sitemap.xml": render_sitemap(config)}
    for relative in ("README.md", "llms.txt", "robots.txt"):
        path = root / relative
        try:
            original = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as error:
            raise GenerationError(f"cannot read {path}: {error}") from error
        outputs[path] = replace_owned_block(original, MARKER, render_discovery_block(config, relative))
    website = config["origins"]["website"]
    for relative in ("README.md", "llms.txt"):
        outputs[root / relative] = canonicalize_origin_links(outputs[root / relative], website)
    if validate_only:
        return False
    return publish_text_outputs(outputs, check=check)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--validate-only", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        changed = generate(args.root, check=args.check, validate_only=args.validate_only)
    except GenerationError as error:
        print(f"gen_public_discovery.py: {error}", file=sys.stderr)
        return 1
    if args.check and changed:
        print("gen_public_discovery.py: outputs are stale", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
