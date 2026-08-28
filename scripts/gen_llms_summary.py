#!/usr/bin/env python3
"""Render marker-owned LLM catalogue facts from canonical local inputs."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.public_surface_generation import GenerationError, load_json, load_public_surfaces, publish_text_outputs, replace_owned_block


PUBLIC_SURFACE_LINKS = {
    "/": ("Live dashboard", "Human-readable dataset status cards with embedded health and manifest data."),
    "/landing.html": ("Landing page", "Public DataPulse MY overview."),
    "/npra.html": ("NPRA page", "Public NPRA dataset surface."),
    "/health-methodology.html": ("Health methodology", "Published status and freshness methodology."),
    "/learn.html": ("Learn", "Practical verification-first guidance for building with Malaysian public data."),
    "/buyer-api-reference.md": ("Buyer API reference", "Read-only buyer API contract and examples."),
    "/llms.txt": ("LLM index", "Machine-readable discovery index for agents."),
    "/datapulse.json": ("Dataset manifest", "Full machine-readable dataset manifest."),
    "/datapulse.schema.json": ("Manifest JSON Schema", "Machine-readable schema for the dataset manifest."),
    "/health/latest.json": ("Latest health snapshot", "Current published dataset health evidence."),
    "/health/trends.json": ("Published trends", "Per-dataset freshness trend and reliability evidence."),
    "/health/drift.json": ("Published drift", "Published structural and record-count drift evidence."),
    "/health/reconciliation.json": ("Published reconciliation", "Cross-source publication differences for human review."),
    "/feed.xml": ("RSS feed", "Dataset health changes with status-tagged entries."),
    "/changelog.json": ("Changelog", "Machine-readable release-by-release summary."),
    "/agent.json": ("Agent manifest", "Machine-readable agent capability manifest."),
    "/mcp.json": ("MCP advertisement", "Machine-readable MCP server advertisement."),
    "/data/jsonld/catalog.json": ("JSON-LD catalog", "Schema.org JSON-LD dataset catalog."),
    "/badges/": ("Status badges", "Per-dataset SVG health badges."),
}


def generate(root: Path, *, check: bool = False, validate_only: bool = False) -> bool:
    """Render catalogue summary and curated datasets without broad substitutions."""
    config = load_public_surfaces(root)
    datasets = load_json(root / "datapulse.json").get("datasets")
    if not isinstance(datasets, list) or not all(isinstance(row, dict) and isinstance(row.get("id"), str) for row in datasets):
        raise GenerationError("datapulse.json: datasets must be an array of objects with ids")
    by_id = {row["id"]: row for row in datasets}
    missing = [dataset_id for dataset_id in config["featured_dataset_ids"] if dataset_id not in by_id]
    if missing:
        raise GenerationError(f"featured dataset id(s) missing from manifest: {', '.join(missing)}")
    configured_paths = set(config["pages"]) | set(config["artifacts"])
    missing_paths = set(PUBLIC_SURFACE_LINKS) - configured_paths
    if missing_paths:
        raise GenerationError(
            "required llms public surface path(s) absent from public-surfaces.json: "
            + ", ".join(sorted(missing_paths))
        )
    unknown_paths = configured_paths - set(PUBLIC_SURFACE_LINKS)
    if unknown_paths:
        raise GenerationError(
            "public-surfaces.json path(s) have no llms.txt rendering: "
            + ", ".join(sorted(unknown_paths))
        )
    path = root / "llms.txt"
    try:
        original = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as error:
        raise GenerationError(f"cannot read {path}: {error}") from error
    count = len(datasets)
    summary = (
        f"> DataPulse MY publishes a machine-readable manifest of {count} official datasets.\n\n"
        "Each manifest entry retains its human-readable `steward` and stable `custodian` publisher ID. "
        "Health anomaly fields explain freshness-delta outliers without adding statuses."
    )
    website = config["origins"]["website"]
    featured = "\n".join(
        f"- [{by_id[dataset_id].get('name', dataset_id)}]({website}/data/{dataset_id}.md): "
        f"{by_id[dataset_id].get('licence', 'Licence not stated')}; {by_id[dataset_id].get('refresh_frequency', 'cadence not stated')}."
        for dataset_id in config["featured_dataset_ids"]
    )
    public_artifacts = "\n".join(
        f"- [{PUBLIC_SURFACE_LINKS[path][0]}]({website}{path}): {PUBLIC_SURFACE_LINKS[path][1]}"
        for path in [*config["pages"], *config["artifacts"]]
    )
    updated = replace_owned_block(original, "catalog-summary", summary)
    updated = replace_owned_block(updated, "featured-datasets", featured)
    updated = replace_owned_block(updated, "public-artifacts", public_artifacts)
    if validate_only:
        return False
    return publish_text_outputs({path: updated}, check=check)


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
        print(f"gen_llms_summary.py: {error}", file=sys.stderr)
        return 1
    if args.check and changed:
        print("gen_llms_summary.py: outputs are stale", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
