#!/usr/bin/env python3
"""Embed generated dashboard inputs into docs/index.html."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


class EmbedError(RuntimeError):
    """Raised when dashboard data cannot be embedded safely."""


def _load(path: Path) -> object:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise EmbedError(f"cannot read {path}: {error}") from error


def _dump(document: object) -> str:
    return json.dumps(document, ensure_ascii=False, separators=(",", ":")).replace(
        "</", "<\\/"
    )


def embed(
    html_path: Path,
    manifest_path: Path,
    health_path: Path,
    filters_path: Path,
    sections_path: Path,
) -> None:
    try:
        html = html_path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as error:
        raise EmbedError(f"cannot read {html_path}: {error}") from error

    data = (
        '<script id="embedded-data">\n'
        "    window.__DATAPULSE_DATA__ = {"
        f"health: {_dump(_load(health_path))}, "
        f"manifest: {_dump(_load(manifest_path))}, "
        f"dashboardFilters: {_dump(_load(filters_path))}, "
        f"dashboardSections: {_dump(_load(sections_path))}"
        "};\n"
        "  </script>"
    )
    marker = '<script id="embedded-data">'
    start = html.find(marker)
    if start >= 0:
        try:
            end = html.index("</script>", start) + len("</script>")
        except ValueError as error:
            raise EmbedError(f"{html_path}: embedded-data script is not closed") from error
        html = html[:start] + data + html[end:]
    elif "</body>" in html:
        html = html.replace("</body>", f"  {data}\n</body>", 1)
    else:
        raise EmbedError(f"{html_path}: cannot find embedded-data block or </body>")

    try:
        html_path.write_text(html, encoding="utf-8", newline="\n")
    except (OSError, UnicodeError) as error:
        raise EmbedError(f"cannot write {html_path}: {error}") from error


def parse_args() -> argparse.Namespace:
    root = Path(__file__).resolve().parent.parent
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--html", type=Path, default=root / "docs/index.html")
    parser.add_argument("--manifest", type=Path, default=root / "datapulse.json")
    parser.add_argument("--health", type=Path, default=root / "health/latest.json")
    parser.add_argument(
        "--filters", type=Path, default=root / "docs/.dashboard_filters.json"
    )
    parser.add_argument(
        "--sections", type=Path, default=root / "docs/.dashboard_sections.json"
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        embed(args.html, args.manifest, args.health, args.filters, args.sections)
    except EmbedError as error:
        print(f"embed_dashboard_data.py: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
