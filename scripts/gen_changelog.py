#!/usr/bin/env python3
"""Generate changelog.json from the manifest and current health snapshot."""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
STATUSES = (
    "fresh",
    "aging",
    "stale",
    "degraded",
    "browser-dependent",
    "unreachable",
    "unknown",
    "unknown-freshness",
    "reference",
)


def read_json(name: str) -> dict:
    return json.loads((ROOT / name).read_text(encoding="utf-8"))


def sorted_counts(values: list[str]) -> dict[str, int]:
    return dict(sorted(Counter(values).items()))


def main() -> None:
    manifest = read_json("datapulse.json")
    health_path = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "health/latest.json"
    health = json.loads(health_path.read_text(encoding="utf-8"))
    entries = manifest["datasets"]
    health_rows = health["datasets"]
    health_by_id = {row["dataset_id"]: row for row in health_rows}

    status_counts = Counter(row.get("status", "unknown") for row in health_rows)
    document = {
        "version": "2.0.0",
        "generated_at": health["checked_at"],
        "site": {
            "url": "https://data-pulse.my/",
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
    (ROOT / "changelog.json").write_text(
        json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"Generated changelog.json for {len(entries)} datasets at {health['checked_at']}")


if __name__ == "__main__":
    main()
