#!/usr/bin/env python3
"""Derive manifest-scoped health totals offline, preserving every recorded probe.

Snapshot-only records remain as evidence but do not count towards the manifest.
Only missing IDs receive provisional rows; no measurement or clock is invented.
"""

from __future__ import annotations

import argparse
from collections import Counter
import logging
from pathlib import Path
import sys
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.gen_readme import STATUS_LABELS
from scripts.public_surface_generation import (
    GenerationError,
    atomic_write_json,
    load_json,
)
from scripts.validate_at_runtime import validate_health, validate_manifest

LOGGER = logging.getLogger(__name__)
STATUS_KEYS = {status: key for key, status in STATUS_LABELS}


def _index(document: dict[str, Any], field: str, source: str) -> dict[str, dict[str, Any]]:
    rows = document.get("datasets")
    if not isinstance(rows, list):
        raise GenerationError(f"{source}: datasets must be an array")
    indexed: dict[str, dict[str, Any]] = {}
    for row in rows:
        if not isinstance(row, dict):
            raise GenerationError(f"{source}: dataset must be an object")
        dataset_id = row.get(field)
        if not isinstance(dataset_id, str) or not dataset_id:
            raise GenerationError(f"{source}: {field} must be a non-empty string")
        if dataset_id in indexed:
            raise GenerationError(f"{source}: duplicate dataset id {dataset_id!r}")
        indexed[dataset_id] = row
    return indexed


def generate(root: Path) -> bool:
    """Reconcile catalogue membership; refuse aggregates unsupported by records."""
    inputs = (
        (validate_manifest, root / "datapulse.json"),
        (validate_health, root / "health/latest.json"),
    )
    for validator, path in inputs:
        valid, errors = validator(path)
        if not valid:
            raise GenerationError("; ".join(errors))
    manifest = _index(load_json(root / "datapulse.json"), "id", "datapulse.json")
    path = root / "health/latest.json"
    snapshot = load_json(path)
    records = _index(snapshot, "dataset_id", "health/latest.json")
    summary = snapshot.get("_trust_summary")
    if not isinstance(summary, dict):
        raise GenerationError("health/latest.json: _trust_summary must be an object")
    total = summary.get("datasets_total")
    counts = summary.get("by_status")
    if type(total) is not int or total < 0 or not isinstance(counts, dict):
        raise GenerationError("health/latest.json: invalid _trust_summary")
    if any(
        key not in STATUS_KEYS.values() or type(count) is not int or count < 0
        for key, count in counts.items()
    ):
        raise GenerationError("health/latest.json: invalid by_status count or status")
    all_counts: Counter[str] = Counter()
    manifest_counts: Counter[str] = Counter()
    for dataset_id, row in records.items():
        status = row.get("status")
        if not isinstance(status, str) or status not in STATUS_KEYS:
            raise GenerationError(f"health/latest.json: invalid status for {dataset_id!r}")
        key = STATUS_KEYS[status]
        all_counts[key] += 1
        if dataset_id in manifest:
            manifest_counts[key] += 1

    # Accept the original probe-wide summary or a previously derived catalogue
    # summary. Any other mismatch is corruption, not an onboarding adjustment.
    if not any(
        total == sum(expected.values()) and Counter(counts) == expected
        for expected in (all_counts, manifest_counts)
    ):
        raise GenerationError("health/latest.json: _trust_summary does not match recorded statuses")

    missing = sorted(manifest.keys() - records.keys())
    manifest_counts["unknown_freshness"] += len(missing)
    derived_counts = {key: manifest_counts[key] for key, _ in STATUS_LABELS}
    if not missing and total == len(manifest) and counts == derived_counts:
        return False
    # Appending leaves existing rows, their order, and all nested evidence intact.
    snapshot["datasets"].extend(
        {
            "dataset_id": dataset_id,
            "url": manifest[dataset_id]["url"],
            "last_checked": None,
            "status": "unknown-freshness",
            "message": "Not probed; provisional onboarding status.",
        }
        for dataset_id in missing
    )
    summary["datasets_total"] = len(manifest)
    summary["by_status"] = derived_counts
    atomic_write_json(path, snapshot)
    return True


def main() -> int:
    """Run the local derivation with a fail-closed exit status."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    try:
        generate(args.root)
    except GenerationError as error:
        LOGGER.error("gen_health_trust_summary.py: %s", error)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
