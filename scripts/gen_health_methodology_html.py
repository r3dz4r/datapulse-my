#!/usr/bin/env python3
"""Render public documentation pages from Markdown with Pandoc."""

from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import NamedTuple

try:  # Support both ``python scripts/...`` and package imports in tests.
    from scripts import gen_site_nav
except ImportError:
    import gen_site_nav


ROOT = Path(__file__).resolve().parents[1]

# The health-methodology page keeps its bespoke hero template. These module
# constants are retained for backward compatibility (existing tests patch them).
SOURCE = ROOT / "docs/health-methodology.md"
TEMPLATE = ROOT / "scripts/templates/health-methodology.html.tmpl"
OUTPUT = ROOT / "docs/health-methodology.html"

# The generic documentation chrome shared by the three other doc pages.
GENERIC_TEMPLATE = ROOT / "scripts/templates/docs-page.html.tmpl"


class DocPage(NamedTuple):
    """One documentation page the generator can render."""

    key: str
    source: Path
    template: Path
    output: Path


def docs_manifest() -> list[DocPage]:
    """Return the ordered registry of doc pages, in render order."""
    return [
        DocPage("health-methodology", SOURCE, TEMPLATE, OUTPUT),
        DocPage(
            "mcp-reference",
            ROOT / "docs/mcp-reference.md",
            GENERIC_TEMPLATE,
            ROOT / "docs/mcp-reference.html",
        ),
        DocPage(
            "agent-quickstart",
            ROOT / "docs/agent-quickstart.md",
            GENERIC_TEMPLATE,
            ROOT / "docs/agent-quickstart.html",
        ),
        DocPage(
            "datapulse-intro",
            ROOT / "docs/datapulse-intro.md",
            GENERIC_TEMPLATE,
            ROOT / "docs/datapulse-intro.html",
        ),
    ]


def extract_title(source: Path) -> str:
    """Return the first ATX level-one heading from a Markdown document."""
    for line in source.read_text(encoding="utf-8").splitlines():
        if line.startswith("# ") and line[2:].strip():
            return line[2:].strip()
    raise ValueError(f"Source has no level-one title: {source}")


def pandoc_command(pandoc: str, source: Path, template: Path, output: Path, title: str) -> list[str]:
    return [
        pandoc,
        "--standalone",
        "--from=gfm",
        "--to=html5",
        f"--metadata=title:{title}",
        f"--template={template}",
        "--output",
        str(output),
        str(source),
    ]


# Each page template's hero carries the single page ``<h1>`` (``id="hero-title"``).
# Pandoc still emits the document's first Markdown ``#`` heading as a leading
# ``<h1 id="...">...``; strip that duplicate heading (and the blank line around it)
# so the body starts at the first ``<h2>`` section, exactly like NPRA/dashboard
# content sections. The negative lookahead keeps the hero ``<h1>`` intact.
_PAGE_HEADING_PATTERN = re.compile(
    r'\s*<h1(?![^>]*\bid=["\']hero-title["\'])[^>]*>[^<]*</h1>\s*', re.IGNORECASE
)


def strip_page_heading(html: str) -> str:
    """Remove the leading Pandoc page heading that duplicates the hero h1."""
    return _PAGE_HEADING_PATTERN.sub("", html, count=1)


# The documentation tables are wider than the mobile viewport. Render each
# balanced ``<table>`` inside a scrollable ``.table-wrap`` container so the page
# itself never overflows on phones (body{overflow-x:hidden} would otherwise clip
# them). The tables are flat/non-nested, so a single non-greedy regex over
# balanced pairs is safe.
_TABLE_PATTERN = re.compile(r"(<table>.*?</table>)", re.DOTALL)


def _wrap_tables(html: str) -> str:
    """Wrap every rendered table in a horizontal-scroll container."""
    return _TABLE_PATTERN.sub(r'<div class="table-wrap">\1</div>', html)


def _render_entry(entry: DocPage, pandoc: str) -> int:
    """Render one manifest entry to its output path atomically."""
    for label, path in (("source", entry.source), ("template", entry.template)):
        if not path.is_file():
            print(f"{entry.key} {label} is missing: {path}", file=sys.stderr)
            return 1

    try:
        title = extract_title(entry.source)
    except (OSError, UnicodeError, ValueError) as error:
        print(error, file=sys.stderr)
        return 1

    entry.output.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{entry.output.name}.", suffix=".tmp", dir=entry.output.parent
    )
    os.close(descriptor)
    temporary = Path(temporary_name)
    try:
        subprocess.run(
            pandoc_command(pandoc, entry.source, entry.template, temporary, title),
            check=True,
        )
        body = temporary.read_text(encoding="utf-8")
        body = strip_page_heading(body)
        body = _wrap_tables(body)
        temporary.write_text(body, encoding="utf-8")
        os.replace(temporary, entry.output)
    except subprocess.CalledProcessError as error:
        print(f"Pandoc failed while rendering {entry.source}: {error}", file=sys.stderr)
        temporary.unlink(missing_ok=True)
        return error.returncode or 1
    except OSError as error:
        print(f"Unable to render {entry.key} HTML: {error}", file=sys.stderr)
        temporary.unlink(missing_ok=True)
        return 1

    try:
        gen_site_nav.inject_nav(entry.output)
    except (OSError, UnicodeError, ValueError) as error:
        print(f"Unable to inject site navigation: {error}", file=sys.stderr)
        return 1

    print(f"Rendered {entry.output.relative_to(ROOT)}")
    return 0


def main(argv: list[str] | None = None) -> int:
    """Render all manifest entries, or a single entry named by ``key``."""
    entries = docs_manifest()
    keys = [entry.key for entry in entries]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "key",
        nargs="?",
        choices=keys,
        help="Render a single documentation page by key; omit to render all.",
    )
    args = parser.parse_args([] if argv is None else argv)
    selected = [entry for entry in entries if args.key is None or entry.key == args.key]

    pandoc = shutil.which("pandoc")
    if pandoc is None:
        print("Pandoc executable not found; install pandoc 3.1.3 before rendering.", file=sys.stderr)
        return 1

    for entry in selected:
        code = _render_entry(entry, pandoc)
        if code != 0:
            return code
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
