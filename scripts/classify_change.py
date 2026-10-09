#!/usr/bin/env python3
"""Classify newline-separated changed paths for narrow CI profiles.

The default mode accepts exact health-cycle outputs only when ``health/latest.json``
is included. ``--append-only`` accepts the immutable append and its verified
projections. Unknown paths deliberately select the source/release profile.
"""

from __future__ import annotations

import re
import sys
from datetime import date
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
        "health/probe_counts.json",
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
APPEND_PROJECTIONS = LATEST_ATTESTATION_OUTPUTS | {
    ".attestations/chain_head.json",
    "attestations/chain-index.json",
}


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
    if len(parts) == 3 and parts[:2] == ["docs", "datasets"]:
        return re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]*\.html", parts[2]) is not None
    if len(parts) == 3 and parts[0] == "record-evidence":
        return parts[2] == "latest.json" or re.fullmatch(r"\d{4}-\d{2}-\d{2}\.json", parts[2]) is not None
    if len(parts) == 3 and parts[:2] == [".attestations", "latest"]:
        return bool(parts[2].removesuffix(".json")) and parts[2].endswith(".json")
    return False


def is_health_only_change(paths: Iterable[str]) -> bool:
    """Return whether paths are exclusively owned health outputs with a snapshot."""
    normalized = tuple(path for path in paths if path)
    return bool(normalized) and "health/latest.json" in normalized and all(
        is_health_cycle_output(path) for path in normalized
    )


def is_append_output(path: str) -> bool:
    """Return whether a path belongs to an immutable attestation append."""
    if not _has_safe_components(path):
        return False
    if path in APPEND_PROJECTIONS:
        return True
    match = re.fullmatch(
        r"attestations/(\d{4}-\d{2}-\d{2})/(?:revisions/[0-9a-f]{64}/)?[A-Za-z0-9_-]+\.json",
        path,
    )
    if match is None:
        match = re.fullmatch(
            r"attestations/rekor/(\d{4}-\d{2}-\d{2})/"
            r"(?:health\.[0-9a-f]{64}\.(?:statement|sigstore\.bundle)|reference\.[0-9a-f]{64})\.json",
            path,
        )
    if match is None:
        return False
    try:
        date.fromisoformat(match.group(1))
    except ValueError:
        return False
    return "/revisions/" in path or "/rekor/" in path or path.endswith("/chain_head.json")


def is_append_only_change(paths: Iterable[str]) -> bool:
    """Return whether every changed path is an attestation append output."""
    normalized = tuple(path for path in paths if path)
    return bool(normalized) and all(is_append_output(path) for path in normalized)


def main() -> int:
    """Read newline-separated paths from standard input and return classifier status."""
    paths = sys.stdin.read().splitlines()
    if sys.argv[1:] == ["--append-only"]:
        return 0 if is_append_only_change(paths) else 1
    if sys.argv[1:]:
        raise SystemExit("usage: classify_change.py [--append-only]")
    return 0 if is_health_only_change(paths) else 1


if __name__ == "__main__":
    raise SystemExit(main())
