#!/usr/bin/env python3
"""Classify newline-separated changed paths for narrow CI profiles.

The default mode accepts health-cycle outputs only when ``health/latest.json``
is included. Mixed-ownership generated pages also require the snapshot pair.
``--ci-artifact-profile`` additionally accepts signed observation-receipt outputs
for CI only; publication must keep the default profile because receipts are site inputs.
``--append-only`` accepts the immutable append and its verified projections.
``--release-only`` accepts release-please's version markers and extra file.
Unknown paths deliberately select the source profile.
"""

from __future__ import annotations

import argparse
from collections.abc import Iterable
from datetime import date
import re
import sys


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
SNAPSHOT_PAIR = frozenset({"catalog-snapshot.json", "changelog.json"})
RELEASE_MARKERS = frozenset({".release-please-manifest.json", "CHANGELOG.md", "VERSION.txt"})
RELEASE_OUTPUTS = RELEASE_MARKERS | {"server.json"}


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


def is_mixed_ownership_health_output(path: str) -> bool:
    """Recognize files whose health-generated sections share a public page."""
    return path == "README.md" or re.fullmatch(r"data/[A-Za-z0-9_-]+\.md", path) is not None


def _is_observation_receipt_output(path: str) -> bool:
    if path == "observation-receipts/chain_head.json":
        return True
    match = re.fullmatch(r"observation-receipts/days/([0-9]{4}-[0-9]{2}-[0-9]{2})\.json", path)
    if match is None:
        return False
    try:
        date.fromisoformat(match.group(1))
    except ValueError:
        return False
    return True


def is_health_only_change(paths: Iterable[str], *, ci_artifact_profile: bool = False) -> bool:
    """Return whether paths are health outputs with a snapshot and required context."""
    normalized = tuple(path for path in paths if path)
    if not normalized or "health/latest.json" not in normalized:
        return False
    # These pages retain external sections; require the two outputs written
    # together by gen_catalog_snapshot.py before using the artifact profile.
    has_mixed_ownership_output = any(is_mixed_ownership_health_output(path) for path in normalized)
    if has_mixed_ownership_output and not SNAPSHOT_PAIR.issubset(normalized):
        return False
    return all(
        is_health_cycle_output(path) or is_mixed_ownership_health_output(path)
        or (ci_artifact_profile and _is_observation_receipt_output(path))
        for path in normalized
    )


def is_append_output(path: str) -> bool:
    """Return whether a path belongs to an immutable attestation append."""
    if not _has_safe_components(path):
        return False
    if path in APPEND_PROJECTIONS:
        return True
    if re.fullmatch(r"attestations/successors/[0-9a-f]{64}\.json", path):
        return True
    match = re.fullmatch(
        r"attestations/(\d{4}-\d{2}-\d{2})/(?:revisions/[0-9a-f]{64}/)?[A-Za-z0-9_-]+\.json(?:\.gz)?",
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


def is_release_only_change(paths: Iterable[str]) -> bool:
    """Return whether paths are exclusively a complete release-please change."""
    normalized = {path for path in paths if path}
    return RELEASE_MARKERS.issubset(normalized) and normalized.issubset(RELEASE_OUTPUTS)


def main() -> int:
    """Read newline-separated paths from standard input and return classifier status."""
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    profiles = parser.add_mutually_exclusive_group()
    profiles.add_argument("--append-only", action="store_true", help="classify attestation appends")
    profiles.add_argument("--release-only", action="store_true", help="classify release-please artifacts")
    profiles.add_argument(
        "--ci-artifact-profile",
        action="store_true",
        help="include observation-receipt outputs for CI, never for publication",
    )
    args = parser.parse_args()
    paths = sys.stdin.read().splitlines()
    if args.append_only:
        return 0 if is_append_only_change(paths) else 1
    if args.release_only:
        return 0 if is_release_only_change(paths) else 1
    return 0 if is_health_only_change(paths, ci_artifact_profile=args.ci_artifact_profile) else 1


if __name__ == "__main__":
    raise SystemExit(main())
