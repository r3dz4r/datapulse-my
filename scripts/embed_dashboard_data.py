#!/usr/bin/env python3
"""Embed generated dashboard inputs into docs/index.html."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path


class EmbedError(RuntimeError):
    """Raised when dashboard data cannot be embedded safely."""


def _load(path: Path) -> object:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise EmbedError(f"cannot read {path}: {error}") from error


def _load_optional(path: Path | None) -> object:
    return _load(path) if path is not None and path.exists() else {}


def _dump(document: object) -> str:
    return json.dumps(document, ensure_ascii=False, separators=(",", ":")).replace(
        "</", "<\\/"
    )


DATASET_COUNT_PATTERNS = (
    r"\b\d+(?= Malaysian public datasets\b)",
    r"\b\d+(?= official datasets\b)",
    r"\b\d+(?= datasets verified\b)",
    r"\b\d+(?= licence-declared datasets\b)",
    r"\b\d+(?=-dataset catalogue\b)",
    r"\b\d+(?= datasets probed\b)",
    r"(?<=Five of )\d+(?= datasets\b)",
)


def _replace_dataset_counts(html: str, health: object) -> str:
    if not isinstance(health, dict):
        return html
    summary = health.get("_trust_summary")
    if not isinstance(summary, dict) or "datasets_total" not in summary:
        return html
    count = summary["datasets_total"]
    if isinstance(count, bool) or not isinstance(count, int) or count < 0:
        raise EmbedError("health _trust_summary.datasets_total must be a non-negative integer")
    for pattern in DATASET_COUNT_PATTERNS:
        html = re.sub(pattern, str(count), html)
    return html


def embed(
    html_path: Path,
    manifest_path: Path,
    health_path: Path,
    filters_path: Path,
    sections_path: Path,
    attestations_path: Path | None = None,
) -> None:
    try:
        html = html_path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as error:
        raise EmbedError(f"cannot read {html_path}: {error}") from error

    health = _load(health_path)
    html = _replace_dataset_counts(html, health)
    data = (
        '<script id="embedded-data">\n'
        "    window.__DATAPULSE_DATA__ = {"
        f"health: {_dump(health)}, "
        f"manifest: {_dump(_load(manifest_path))}, "
        f"dashboardFilters: {_dump(_load(filters_path))}, "
        f"dashboardSections: {_dump(_load(sections_path))}, "
        f"attestations: {_dump(_load_optional(attestations_path))}"
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
    parser.add_argument(
        "--attestations", type=Path, default=root / "attestations/latest/index.json"
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        embed(args.html, args.manifest, args.health, args.filters, args.sections, args.attestations)
    except EmbedError as error:
        print(f"embed_dashboard_data.py: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
