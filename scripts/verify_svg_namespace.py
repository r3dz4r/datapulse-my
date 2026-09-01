#!/usr/bin/env python3
"""Verify that every tracked SVG declares the standard SVG namespace."""

from __future__ import annotations

import argparse
import re
import subprocess
from pathlib import Path
from urllib.parse import urlparse


SVG_OPEN_TAG = re.compile(r"<svg\b[^>]*>", re.IGNORECASE | re.DOTALL)
XMLNS_ATTRIBUTE = re.compile(r"\bxmlns\s*=\s*(?:\"([^\"]*)\"|'([^']*)')", re.IGNORECASE)
ENTITY_ESCAPE = re.compile(r"&#(?:\d+|x[0-9a-f]+);|&colon;", re.IGNORECASE)
EXPECTED_NAMESPACE = "http://www.w3.org/2000/svg"


def tracked_svgs(root: Path) -> list[Path]:
    result = subprocess.run(
        ["git", "-C", str(root), "ls-files", "--", "*.svg"],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(f"unable to list tracked SVG files: {result.stderr.strip()}")
    return [root / relative_path for relative_path in result.stdout.splitlines() if relative_path]


def verify_svg_namespace(root: Path) -> list[str]:
    errors: list[str] = []
    try:
        paths = tracked_svgs(root)
    except RuntimeError as exc:
        return [str(exc)]

    for path in paths:
        relative_path = path.relative_to(root).as_posix()
        try:
            source = path.read_text(encoding="utf-8")
        except OSError as exc:
            errors.append(f"{relative_path}: cannot read SVG: {exc}")
            continue
        svg_match = SVG_OPEN_TAG.search(source)
        if svg_match is None:
            errors.append(f"{relative_path}: missing first <svg> element")
            continue
        xmlns_match = XMLNS_ATTRIBUTE.search(svg_match.group(0))
        if xmlns_match is None:
            errors.append(f"{relative_path}: first <svg> element is missing xmlns attribute")
            continue
        namespace = xmlns_match.group(1) or xmlns_match.group(2) or ""
        if ENTITY_ESCAPE.search(namespace):
            errors.append(f"{relative_path}: xmlns attribute contains an HTML entity escape: {namespace}")
        if namespace != EXPECTED_NAMESPACE:
            errors.append(f"{relative_path}: xmlns attribute must be {EXPECTED_NAMESPACE!r}, got {namespace!r}")
        parsed = urlparse(namespace)
        if not parsed.scheme or not parsed.netloc:
            errors.append(f"{relative_path}: xmlns attribute is not a valid absolute URI: {namespace!r}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    errors = verify_svg_namespace(args.root.resolve())
    if errors:
        print(f"SVG namespace verification failed ({len(errors)} invariant(s)):")
        for error in errors:
            print(f"- {error}")
        return 1
    print("SVG namespace verification passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
