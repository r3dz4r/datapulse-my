#!/usr/bin/env python3
"""Render README.md's data-derived blocks from canonical local inputs."""

from __future__ import annotations

import argparse
from collections import Counter
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.public_surface_generation import (
    GenerationError,
    load_json,
    publish_text_outputs,
    replace_owned_block,
)


OWNED_MARKERS = (
    "readme-hero",
    "readme-cover",
    "readme-health",
    "readme-licences",
    "readme-inventory",
    "readme-cadence",
)
EXTERNAL_MARKERS = ("mcp-tools", "public-discovery")
STATUS_LABELS = (
    ("fresh", "fresh"),
    ("aging", "aging"),
    ("stale", "stale"),
    ("discontinued", "discontinued"),
    ("degraded", "degraded"),
    ("browser_dependent", "browser-dependent"),
    ("unreachable", "unreachable"),
    ("unknown", "unknown"),
    ("unknown_freshness", "unknown-freshness"),
    ("reference", "reference"),
)


def _string(value: object, *, field: str) -> str:
    if not isinstance(value, str) or not value:
        raise GenerationError(f"{field} must be a non-empty string")
    return value


def _datasets(root: Path) -> list[dict[str, Any]]:
    value = load_json(root / "datapulse.json").get("datasets")
    if not isinstance(value, list):
        raise GenerationError("datapulse.json: datasets must be an array")
    datasets: list[dict[str, Any]] = []
    ids: set[str] = set()
    for index, row in enumerate(value):
        if not isinstance(row, dict):
            raise GenerationError(f"datapulse.json: datasets[{index}] must be an object")
        dataset_id = _string(row.get("id"), field=f"datapulse.json: datasets[{index}].id")
        if dataset_id in ids:
            raise GenerationError(f"datapulse.json: duplicate dataset id {dataset_id!r}")
        ids.add(dataset_id)
        datasets.append(row)
    return datasets


def _licence_name(row: dict[str, Any]) -> str:
    licence = row.get("licence")
    if isinstance(licence, dict):
        return _string(licence.get("name"), field=f"dataset {row.get('id')!r} licence.name")
    return _string(licence, field=f"dataset {row.get('id')!r} licence")


def _external_body(text: str, marker: str) -> str:
    begin = f"<!-- BEGIN {marker} -->"
    end = f"<!-- END {marker} -->"
    if text.count(begin) != 1 or text.count(end) != 1:
        raise GenerationError(f"expected exactly one external {marker!r} block in README.md")
    start = text.index(begin) + len(begin)
    finish = text.index(end)
    if finish < start:
        raise GenerationError(f"reversed external {marker!r} markers in README.md")
    body = text[start:finish].strip("\n")
    # Validate every README marker before carrying another generator's body forward.
    replace_owned_block(text, marker, body)
    return body


def _replace(text: str, marker: str, rendered: str) -> str:
    """Use the shared strict marker validator, preserving inline table cells."""
    begin = f"<!-- BEGIN {marker} -->"
    end = f"<!-- END {marker} -->"
    start = text.index(begin) + len(begin)
    finish = text.index(end)
    inline = "\n" not in text[start:finish]
    updated = replace_owned_block(text, marker, rendered)
    if inline:
        return updated.replace(f"{begin}\n{rendered.rstrip()}\n{end}", f"{begin}{rendered.rstrip()}{end}")
    return updated


def _render_hero(datasets: list[dict[str, Any]]) -> str:
    gtfs = sum(1 for row in datasets if _string(row.get("id"), field="dataset id").startswith("gtfs_"))
    return (
        f"**{len(datasets)} official Malaysian datasets** — including **{gtfs} GTFS transit feeds (KTMB,\n"
        "Prasarana, BAS.MY)** — with declared licences and an honest ten-status trust\n"
        "taxonomy instead of a blanket green checkmark."
    )


def _health_summary(root: Path, dataset_count: int) -> dict[str, Any]:
    summary = load_json(root / "health/latest.json").get("_trust_summary")
    if not isinstance(summary, dict):
        raise GenerationError("health/latest.json: _trust_summary must be an object")
    total = summary.get("datasets_total")
    statuses = summary.get("by_status")
    if not isinstance(total, int) or total < 0 or not isinstance(statuses, dict):
        raise GenerationError("health/latest.json: invalid _trust_summary")
    if total != dataset_count:
        raise GenerationError(f"health/latest.json datasets_total {total} does not match manifest {dataset_count}")
    return summary


def _render_health(root: Path, dataset_count: int) -> str:
    summary = _health_summary(root, dataset_count)
    total = summary["datasets_total"]
    statuses = summary["by_status"]
    badges: list[str] = []
    for key, label in STATUS_LABELS:
        count = statuses.get(key, 0)
        if not isinstance(count, int) or count < 0:
            raise GenerationError(f"health/latest.json: by_status.{key} must be a non-negative integer")
        if count:
            badges.append(f"[{count} {label}](badges/status-{label}.svg)")
    if sum(statuses.get(key, 0) for key, _ in STATUS_LABELS) != total:
        raise GenerationError("health/latest.json: status counts do not equal datasets_total")
    return "Current distribution (`_trust_summary`): " + " · ".join(badges)


def _render_browser_dependent(root: Path, dataset_count: int) -> str:
    summary = _health_summary(root, dataset_count)
    statuses = summary["by_status"]
    count = statuses.get("browser_dependent", 0)
    if not isinstance(count, int) or count < 0:
        raise GenerationError("health/latest.json: by_status.browser_dependent must be a non-negative integer")
    percentage = count / dataset_count * 100 if dataset_count else 0
    return (
        f"The current health summary identifies **{count} browser-dependent sources "
        f"({percentage:.1f}% of the catalogue)** that require a real browser to probe "
        "because their source pages render client-side JavaScript."
    )


def _render_licences(datasets: list[dict[str, Any]]) -> str:
    counts = Counter(_licence_name(row) for row in datasets)
    return "; ".join(f"{name} ({counts[name]})" for name in sorted(counts, key=str.casefold)) + "."


def _render_inventory(datasets: list[dict[str, Any]]) -> str:
    custodians = {
        _string(row.get("custodian"), field=f"dataset {row.get('id')!r} custodian")
        for row in datasets
    }
    gtfs = sum(1 for row in datasets if _string(row.get("id"), field="dataset id").startswith("gtfs_"))
    dataset_label = "dataset" if len(datasets) == 1 else "datasets"
    publisher_label = "publisher" if len(custodians) == 1 else "publishers"
    return (
        f"**{len(datasets)} official {dataset_label} across {len(custodians)} {publisher_label}**, including **{gtfs} GTFS transit feeds**. "
        "Browse the [published reports](data/) for plain-language health assessments, or use "
        "[`datapulse.json`](datapulse.json) as the machine-readable index of every source, licence, "
        "health-report path, and declared refresh cadence."
    )


def _render_cadence(datasets: list[dict[str, Any]]) -> str:
    counts = Counter(
        _string(row.get("refresh_frequency"), field=f"dataset {row.get('id')!r} refresh_frequency")
        for row in datasets
    )
    summary = "; ".join(
        f"{cadence} ({count})"
        for cadence, count in sorted(counts.items(), key=lambda item: (-item[1], item[0].casefold()))
    )
    return (
        "Declared refresh cadences: "
        f"{summary}. Per-dataset cadence remains available in [`datapulse.json`](datapulse.json) "
        "and each published health report."
    )


def generate(root: Path, *, check: bool = False, validate_only: bool = False) -> bool:
    """Render README.md deterministically while retaining externally owned blocks."""
    datasets = _datasets(root)
    template_path = root / "scripts/templates/README.md.tmpl"
    readme_path = root / "README.md"
    try:
        template = template_path.read_text(encoding="utf-8")
        current = readme_path.read_text(encoding="utf-8") if readme_path.exists() else template
    except (OSError, UnicodeError) as error:
        raise GenerationError(f"cannot read README input: {error}") from error
    rendered = template.replace(
        "{{BROWSER_DEPENDENT_SUMMARY}}", _render_browser_dependent(root, len(datasets))
    )
    for marker in EXTERNAL_MARKERS:
        rendered = _replace(rendered, marker, _external_body(current, marker))
    blocks = {
        "readme-hero": _render_hero(datasets),
        "readme-cover": f"**{len(datasets)} official datasets**",
        "readme-health": _render_health(root, len(datasets)),
        "readme-licences": _render_licences(datasets),
        "readme-inventory": _render_inventory(datasets),
        "readme-cadence": _render_cadence(datasets),
    }
    for marker in OWNED_MARKERS:
        rendered = _replace(rendered, marker, blocks[marker])
    return publish_text_outputs({readme_path: rendered}, check=check or validate_only)


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
        print(f"gen_readme.py: {error}", file=sys.stderr)
        return 1
    if (args.check or args.validate_only) and changed:
        print("gen_readme.py: README.md is stale", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
