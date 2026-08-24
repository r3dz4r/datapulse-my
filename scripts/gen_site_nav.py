#!/usr/bin/env python3
"""Inject the canonical site navigation into the public HTML pages."""

from __future__ import annotations

import argparse
import sys
from html.parser import HTMLParser
from pathlib import Path

SCRIPT_ROOT = Path(__file__).resolve().parents[1]
if str(SCRIPT_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPT_ROOT))

from scripts.public_surface_generation import GenerationError, atomic_write_text, load_public_surfaces


ROOT = Path(__file__).resolve().parents[1]
BEGIN_MARKER = "<!-- BEGIN SITE-NAV (generated from assets/site-nav.html) -->"
END_MARKER = "<!-- END SITE-NAV -->"


class _NavLocator(HTMLParser):
    """Locate a complete site-nav element without matching HTML by regex."""

    def __init__(self, source: str) -> None:
        super().__init__()
        self._line_offsets = self._offsets(source)
        self.start: int | None = None
        self.end: int | None = None
        self._nav_depth = 0

    @staticmethod
    def _offsets(source: str) -> list[int]:
        offsets = [0]
        for index, char in enumerate(source):
            if char == "\n":
                offsets.append(index + 1)
        return offsets

    def _offset(self) -> int:
        line, column = self.getpos()
        return self._line_offsets[line - 1] + column

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag != "nav" or self.end is not None:
            return
        if self.start is None:
            classes = dict(attrs).get("class", "") or ""
            if "site-nav" not in classes.split():
                return
            self.start = self._offset()
            self._nav_depth = 1
            return
        self._nav_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag != "nav" or self.start is None or self.end is not None:
            return
        self._nav_depth -= 1
        if self._nav_depth == 0:
            self.end = self._offset() + len(self.get_endtag_text())

    def get_endtag_text(self) -> str:
        """Return the source end tag at the parser's current position."""
        # HTMLParser exposes the raw start tag but not the raw end tag. Its
        # position is sufficient here because an end tag cannot contain `>`.
        return "</nav>"


def find_site_nav(source: str) -> tuple[int, int] | None:
    """Return offsets for the first complete ``<nav class=site-nav>`` block."""
    locator = _NavLocator(source)
    locator.feed(source)
    locator.close()
    if locator.start is None or locator.end is None:
        return None
    return locator.start, locator.end


def canonical_nav(root: Path = ROOT) -> str:
    """Read and validate the sole canonical navigation partial."""
    partial = root / "docs/assets/site-nav.html"
    source = partial.read_text(encoding="utf-8")
    bounds = find_site_nav(source)
    if bounds is None or source[:bounds[0]].strip() or source[bounds[1]:].strip():
        raise ValueError(f"Canonical site navigation is not one complete site-nav block: {partial}")
    return source.rstrip()


def render_injected(source: str, nav: str) -> str:
    """Replace one existing site-nav block, retaining all other page content."""
    bounds = find_site_nav(source)
    if bounds is None:
        raise ValueError("page is missing its complete site-nav block")
    start, end = bounds
    line_start = source.rfind("\n", 0, start) + 1
    nav_prefix = source[line_start:start]
    indent = nav_prefix if nav_prefix.isspace() else ""
    replacement_start = start
    before = source[:start]
    if before.rstrip().endswith(BEGIN_MARKER):
        replacement_start = before.rfind(BEGIN_MARKER)
        marker_line_start = source.rfind("\n", 0, replacement_start) + 1
        marker_prefix = source[marker_line_start:replacement_start]
        indent = marker_prefix if marker_prefix.isspace() else ""

    replacement_end = end
    after = source[end:]
    end_marker_offset = after.find(END_MARKER)
    if end_marker_offset >= 0 and not after[:end_marker_offset].strip():
        replacement_end = end + end_marker_offset + len(END_MARKER)

    replacement = f"{BEGIN_MARKER}\n{nav}\n{indent}{END_MARKER}"
    return source[:replacement_start] + replacement + source[replacement_end:]


def inject_nav(path: Path, nav: str | None = None) -> bool:
    """Inject the canonical nav into one page, returning whether it changed."""
    source = path.read_text(encoding="utf-8")
    rendered = render_injected(source, nav if nav is not None else canonical_nav())
    if rendered == source:
        return False
    atomic_write_text(path, rendered)
    return True


def inject_all(root: Path = ROOT, *, check: bool = False) -> list[Path]:
    """Inject the canonical nav into the whitelisted pages beneath ``root``."""
    nav = canonical_nav(root)
    surfaces = load_public_surfaces(root)
    changed: list[Path] = []
    for declared in surfaces["pages"]:
        name = "index.html" if declared == "/" else declared.removeprefix("/")
        path = root / "docs" / name
        if not path.is_file():
            raise ValueError(f"declared navigation target is missing: {path}")
        source = path.read_text(encoding="utf-8")
        if render_injected(source, nav) == source:
            continue
        changed.append(path)
        if not check:
            inject_nav(path, nav)
    return changed


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Fail if navigation injection would change a page.")
    args = parser.parse_args()
    try:
        changed = inject_all(check=args.check)
    except (GenerationError, OSError, UnicodeError, ValueError) as error:
        print(f"Unable to inject site navigation: {error}", file=sys.stderr)
        return 1
    if args.check:
        for path in changed:
            print(f"Would update {path.relative_to(ROOT)}")
        return 1 if changed else 0
    for path in changed:
        print(f"Injected site navigation into {path.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
