#!/usr/bin/env python3
"""Compare the published health status with the pure policy classifier."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

if __package__:
    from .health_policy import classify_status
else:
    from health_policy import classify_status


def _load_json(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def compare_health(snapshot: dict, manifest: dict) -> dict:
    """Return per-ID status and reason differences without mutating inputs."""
    checked_at = snapshot.get("checked_at")
    if not isinstance(checked_at, str):
        raise ValueError("health snapshot checked_at must be a string")
    now = datetime.fromisoformat(checked_at.replace("Z", "+00:00"))

    manifest_rows = manifest.get("datasets")
    health_rows = snapshot.get("datasets")
    if not isinstance(manifest_rows, list) or not isinstance(health_rows, list):
        raise ValueError("manifest and health snapshot must contain dataset arrays")

    manifest_metadata = {}
    for row in manifest_rows:
        if not isinstance(row, dict) or not isinstance(row.get("id"), str):
            raise ValueError("manifest dataset row has invalid id")
        dataset_id = row["id"]
        if dataset_id in manifest_metadata:
            raise ValueError(f"duplicate manifest dataset ID {dataset_id!r}")
        manifest_metadata[dataset_id] = {
            "refresh_frequency": row.get("refresh_frequency"),
            "data_type": row.get("data_type"),
        }

    differences = []
    seen_ids = set()
    for row in health_rows:
        if not isinstance(row, dict) or not isinstance(row.get("dataset_id"), str):
            raise ValueError("health dataset row has invalid dataset_id")
        dataset_id = row["dataset_id"]
        if dataset_id in seen_ids:
            raise ValueError(f"duplicate health dataset ID {dataset_id!r}")
        seen_ids.add(dataset_id)
        if dataset_id not in manifest_metadata:
            raise ValueError(f"health dataset ID {dataset_id!r} is absent from manifest")

        candidate = dict(row)
        candidate.update(manifest_metadata[dataset_id])
        if row.get("status") in {"degraded", "unreachable"}:
            candidate["probe_status"] = row["status"]
        new_status, new_reason = classify_status(candidate, now)
        old_status = row.get("status")
        old_reason = row.get("status_reason")
        differences.append(
            {
                "dataset_id": dataset_id,
                "fields": {
                    "status": {
                        "old": old_status,
                        "new": new_status,
                        "changed": old_status != new_status,
                    },
                    "status_reason": {
                        "old": old_reason,
                        "new": new_reason,
                        "changed": old_reason != new_reason,
                    },
                },
            }
        )

    missing_ids = set(manifest_metadata) - seen_ids
    if missing_ids:
        raise ValueError(f"health snapshot is missing dataset IDs {sorted(missing_ids)!r}")
    return {
        "schema": "datapulse/health-comparison/v1",
        "checked_at": checked_at,
        "datasets_compared": len(health_rows),
        "status_changes": sum(
            item["fields"]["status"]["changed"] for item in differences
        ),
        "differences": differences,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("snapshot", type=Path)
    parser.add_argument("manifest", type=Path)
    args = parser.parse_args()
    try:
        report = compare_health(_load_json(args.snapshot), _load_json(args.manifest))
    except Exception as exc:
        print(f"Health comparison failed: {exc}", file=sys.stderr)
        return 1
    json.dump(report, sys.stdout, indent=2, sort_keys=True)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
