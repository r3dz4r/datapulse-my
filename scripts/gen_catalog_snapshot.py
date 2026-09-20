#!/usr/bin/env python3
"""Generate the canonical current snapshot and its one-release legacy alias.

``catalog-snapshot.json`` is the canonical current-state artifact.  The public
surface configuration still publishes ``changelog.json`` for compatibility, so
the alias remains byte-identical until that published URL can be retired.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

try:  # imported as scripts.gen_catalog_snapshot (tests)
    from scripts.artifact_modes import replace_file
except ImportError:  # executed directly: scripts/ is on sys.path
    from artifact_modes import replace_file
from public_surface_generation import load_public_surfaces

ROOT = Path(__file__).resolve().parents[1]
STATUSES = (
    "fresh",
    "aging",
    "stale",
    "discontinued",
    "degraded",
    "browser-dependent",
    "unreachable",
    "unknown",
    "unknown-freshness",
    "reference",
)


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict) or not isinstance(value.get("datasets"), list):
        raise ValueError(f"{path} must contain a datasets array")
    return value


def sorted_counts(values: list[str]) -> dict[str, int]:
    return dict(sorted(Counter(values).items()))


def atomic_write(path: Path, content: bytes) -> None:
    replace_file(path, content)


def build_snapshot(manifest: dict[str, Any], health: dict[str, Any], *, website: str) -> dict[str, Any]:
    entries = manifest["datasets"]
    health_rows = health["datasets"]
    health_by_id = {row["dataset_id"]: row for row in health_rows}
    status_counts = Counter(row.get("status", "unknown") for row in health_rows)
    return {
        "version": "2.0.0",
        "generated_at": health["checked_at"],
        "site": {
            "url": website + "/",
            "repository": "https://github.com/r3dz4r/datapulse-my",
        },
        "manifest": {
            "datasets_total": len(entries),
            "by_namespace": sorted_counts([row["namespace"] for row in entries]),
            "by_licence": sorted_counts([row["licence"] for row in entries]),
            "by_lifecycle": sorted_counts(
                [row.get("real_status", "unknown") for row in entries]
            ),
        },
        "health": {
            "checked_at": health["checked_at"],
            "datasets_total": len(health_rows),
            "by_status": {status: status_counts[status] for status in STATUSES},
            "signal_sources": health.get("_trust_summary", {}).get(
                "datasets_health_signal_source", {}
            ),
        },
        "datasets": [
            {
                "dataset_id": entry["id"],
                "name": entry["name"],
                "namespace": entry["namespace"],
                "licence": entry["licence"],
                "lifecycle": entry.get("real_status", "unknown"),
                "status": health_by_id.get(entry["id"], {}).get("status", "unknown"),
                "last_checked": health_by_id.get(entry["id"], {}).get("last_checked"),
            }
            for entry in entries
        ],
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=ROOT / "datapulse.json")
    parser.add_argument("--health", type=Path, default=ROOT / "health/latest.json")
    parser.add_argument("--output", type=Path, default=ROOT / "catalog-snapshot.json")
    parser.add_argument(
        "--legacy-alias",
        type=Path,
        default=ROOT / "changelog.json",
        help="one-release byte-identical compatibility alias",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    try:
        manifest = read_json(args.manifest)
        health = read_json(args.health)
        document = build_snapshot(
            manifest, health, website=load_public_surfaces(ROOT)["origins"]["website"]
        )
        content = (json.dumps(document, ensure_ascii=False, indent=2) + "\n").encode()
        atomic_write(args.output, content)
        atomic_write(args.legacy_alias, content)
    except (OSError, UnicodeError, json.JSONDecodeError, KeyError, ValueError) as exc:
        raise SystemExit(f"catalog snapshot generation failed: {exc}") from exc
    print(
        f"Generated {args.output.name} for {len(manifest['datasets'])} datasets at "
        f"{health['checked_at']}; {args.legacy_alias.name} is a deprecated alias"
    )


if __name__ == "__main__":
    main()
