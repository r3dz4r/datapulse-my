#!/usr/bin/env python3
"""Embed generated dashboard inputs into docs/index.html."""

from __future__ import annotations

import argparse
import json
import os
import re
import stat
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path


class EmbedError(RuntimeError):
    """Raised when dashboard data cannot be embedded safely."""


CHANGELOG_BEGIN = "<!-- BEGIN changelog-strip -->"
CHANGELOG_END = "<!-- END changelog-strip -->"


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


def _atomic_write_text(path: Path, content: str) -> None:
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", dir=path.parent
    )
    try:
        os.fchmod(descriptor, stat.S_IMODE(path.stat().st_mode))
        with os.fdopen(
            descriptor, "w", encoding="utf-8", newline="\n"
        ) as temporary_file:
            temporary_file.write(content)
            temporary_file.flush()
            os.fsync(temporary_file.fileno())
        os.replace(temporary_name, path)
    except BaseException:
        try:
            os.unlink(temporary_name)
        except FileNotFoundError:
            pass
        raise


def update_changelog_strip(html: str, manifest: object, health: object) -> str:
    if not isinstance(manifest, dict) or not isinstance(manifest.get("datasets"), list):
        raise EmbedError("manifest must contain a datasets array")
    if not isinstance(health, dict) or not isinstance(health.get("checked_at"), str):
        raise EmbedError("health checked_at must be an ISO-8601 string")

    checked_at = health["checked_at"]
    try:
        observed_at = datetime.fromisoformat(checked_at.replace("Z", "+00:00"))
    except ValueError as error:
        raise EmbedError("health checked_at must be an ISO-8601 string") from error
    if observed_at.tzinfo is None:
        raise EmbedError("health checked_at must include a UTC offset")

    shipped_date = observed_at.astimezone(timezone.utc).date().isoformat()
    dataset_count = len(manifest["datasets"])
    replacement = (
        f"{CHANGELOG_BEGIN}\n"
        '    <aside class="changelog-strip" aria-label="Recently shipped">\n'
        "      <strong>Recently shipped</strong>\n"
        f'      <span><time datetime="{shipped_date}">{shipped_date}</time> · '
        f"{dataset_count} datasets tracked</span>\n"
        '      <a href="/catalog-snapshot.json">Machine-readable catalog snapshot</a>\n'
        '      <a href="/health/latest.json">Latest trust snapshot →</a>\n'
        '      <a href="/release-verification.md">Reproducible build proof</a>\n'
        '      <a class="chip" href="/trust-layer-notebook.ipynb" '
        'title="Open the canonical Colab notebook: verify before you use">Trust Layer notebook</a>\n'
        '      <a class="chip" href="#camofox">Browser-dependent</a>\n'
        '      <a class="chip" href="#legal">Legal</a>\n'
        "    </aside>\n"
        f"    {CHANGELOG_END}"
    )
    pattern = re.compile(
        rf"{re.escape(CHANGELOG_BEGIN)}.*?{re.escape(CHANGELOG_END)}", re.DOTALL
    )
    updated, replacements = pattern.subn(replacement, html)
    if replacements != 1:
        raise EmbedError(
            "dashboard must contain exactly one complete changelog-strip marker block"
        )
    return updated


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

    manifest = _load(manifest_path)
    health = _load(health_path)
    html = update_changelog_strip(html, manifest, health)
    html = _replace_dataset_counts(html, health)
    data = (
        '<script id="embedded-data">\n'
        "    window.__DATAPULSE_DATA__ = {"
        f"health: {_dump(health)}, "
        f"manifest: {_dump(manifest)}, "
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
        _atomic_write_text(html_path, html)
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
