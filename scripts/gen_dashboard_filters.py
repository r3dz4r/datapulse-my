#!/usr/bin/env python3
"""Generate deterministic dashboard namespace filter counts."""

import argparse
import json
from collections import Counter
from pathlib import Path


CANONICAL_NAMESPACES = (
    "economy",
    "environment",
    "government_open_data",
    "healthcare",
    "other",
    "transport",
    "weather",
)


def build_dashboard_filters(manifest: dict) -> dict:
    datasets = manifest.get("datasets", [])
    counts = Counter(row.get("namespace") for row in datasets)
    namespaces = [{"key": "all", "count": len(datasets)}]
    namespaces.extend(
        {"key": key, "count": counts.get(key, 0)}
        for key in CANONICAL_NAMESPACES
    )
    return {"namespaces": namespaces}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=Path("datapulse.json"))
    parser.add_argument(
        "--output", type=Path, default=Path("docs/.dashboard_filters.json")
    )
    args = parser.parse_args()

    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    filters = build_dashboard_filters(manifest)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(filters, indent=2) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
