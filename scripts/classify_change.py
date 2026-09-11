#!/usr/bin/env python3
"""Classify newline-separated changed paths for health-only pipeline work.

Exit zero only when every path is an exact health-cycle generated output and
``health/latest.json`` is included.  Unknown paths deliberately select the
source/release profile.
"""

from __future__ import annotations

import sys
from collections.abc import Iterable


ROOT_OUTPUTS = frozenset(
    {
        "catalog-graph.json",
        "catalog-snapshot.json",
        "changelog.json",
        "datapulse_summary.json",
        "feed.xml",
    }
)
HEALTH_OUTPUTS = frozenset(
    {
        "health/latest.json",
        "health/history.jsonl",
        "health/history_daily.json",
        "health/trends.json",
        "health/drift.json",
        "health/reconciliation.json",
        "health/evidence-coverage.json",
    }
)
LATEST_ATTESTATION_OUTPUTS = frozenset(
    {
        "attestations/latest/binding.json",
        "attestations/latest/chain_head.json",
        "attestations/latest/index.json",
        "attestations/latest/scores.json",
    }
)


def _has_safe_components(path: str) -> bool:
    """Reject empty, traversal, and non-repository-relative paths."""
    return bool(path) and all(component not in {"", ".", ".."} for component in path.split("/"))


def is_health_cycle_output(path: str) -> bool:
    """Return whether ``path`` is an exact output owned by a health cycle."""
    if not _has_safe_components(path):
        return False

    parts = path.split("/")
    if path in ROOT_OUTPUTS or path in HEALTH_OUTPUTS or path in LATEST_ATTESTATION_OUTPUTS:
        return True
    if path == ".attestations/chain_head.json":
        return True
    if len(parts) == 2 and parts[0] == "deltas":
        return bool(parts[1].removesuffix(".json")) and parts[1].endswith(".json")
    if len(parts) == 2 and parts[0] == "badges":
        return bool(parts[1].removesuffix(".svg")) and parts[1].endswith(".svg")
    if len(parts) == 3 and parts[:2] == ["data", "passports"]:
        return bool(parts[2].removesuffix(".json")) and parts[2].endswith(".json")
    if len(parts) == 3 and parts[0] == "record-evidence":
        return bool(parts[1]) and parts[2] == "latest.json"
    if len(parts) == 3 and parts[:2] == [".attestations", "latest"]:
        return bool(parts[2].removesuffix(".json")) and parts[2].endswith(".json")
    return False


def is_health_only_change(paths: Iterable[str]) -> bool:
    """Return whether paths are exclusively owned health outputs with a snapshot."""
    normalized = tuple(path for path in paths if path)
    return bool(normalized) and "health/latest.json" in normalized and all(
        is_health_cycle_output(path) for path in normalized
    )


def main() -> int:
    """Read newline-separated paths from standard input and return classifier status."""
    return 0 if is_health_only_change(sys.stdin.read().splitlines()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
