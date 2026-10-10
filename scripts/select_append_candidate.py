#!/usr/bin/env python3
"""Select the oldest open attestation append pull request."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path


def _append_day(pull_request: dict[str, object]) -> str | None:
    """Read the day encoded in the append PR title."""
    match = re.search(r"(?:append signed set|append signed evidence from source) (\d{4}-\d{2}-\d{2})$", str(pull_request.get("title", "")))
    return match.group(1) if match else None


def select_superseded_siblings(
    pull_requests: list[dict[str, object]], merged_number: int
) -> list[int]:
    """Close only same-day PRs whose exact added blobs were in the merged PR.

    A matching date or signed parent alone does not make an independent append
    redundant. Missing or incomplete file metadata fails open: keep the PR.
    """
    merged = next((row for row in pull_requests if row.get("number") == merged_number), None)
    if merged is None or str(merged.get("state", "")).upper() != "MERGED":
        return []
    day = _append_day(merged)
    merged_files = _immutable_files(merged)
    if day is None or merged_files is None:
        return []
    result = []
    for row in pull_requests:
        if (row.get("number") == merged_number
                or str(row.get("state", "")).upper() != "OPEN"
                or not str(row.get("headRefName", "")).startswith("attestation/append-")
                or _append_day(row) != day):
            continue
        files = _immutable_files(row)
        if files is not None and files.items() <= merged_files.items():
            result.append(int(row["number"]))
    return sorted(result)


def _immutable_files(pull_request: dict[str, object]) -> dict[str, str] | None:
    """Require a complete, immutable append file list with Git blob identities."""
    rows = pull_request.get("files")
    if not isinstance(rows, list) or not rows:
        return None
    files: dict[str, str] = {}
    has_head = False
    for row in rows:
        if not isinstance(row, dict):
            return None
        path, digest = row.get("filename"), row.get("sha")
        if (row.get("status") != "added" or not isinstance(path, str)
                or not isinstance(digest, str) or re.fullmatch(r"[0-9a-f]{40}", digest) is None
                or re.fullmatch(r"attestations/\d{4}-\d{2}-\d{2}/revisions/[0-9a-f]{64}/[A-Za-z0-9_-]+\.json", path) is None
                or path in files):
            return None
        files[path] = digest
        has_head |= path.endswith("/chain_head.json")
    return files if has_head else None


def select_append_candidate(pull_requests: list[dict[str, object]]) -> int | None:
    """Return the oldest append PR number, breaking timestamp ties by number."""
    candidates = [
        pull_request
        for pull_request in pull_requests
        if str(pull_request["headRefName"]).startswith("attestation/append-")
        and str(pull_request.get("state", "OPEN")).upper() == "OPEN"
        and pull_request.get("mergeable") != "CONFLICTING"
        and not any(
            str(check.get("conclusion") or check.get("state")) in {
                "FAILURE", "ERROR", "CANCELLED", "TIMED_OUT", "ACTION_REQUIRED", "STARTUP_FAILURE"}
            for check in (pull_request.get("statusCheckRollup") or [])
        )
    ]
    if not candidates:
        return None

    # Preserve creation order; a later hash-addressed append does not supersede
    # an earlier one by sharing its day. Required CI checks signed-parent CAS.
    oldest = min(
        candidates,
        key=lambda pull_request: (
            str(pull_request["createdAt"]),
            int(pull_request["number"]),
        ),
    )
    return int(oldest["number"])


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", nargs="?", type=Path, help="JSON file; stdin by default")
    args = parser.parse_args()
    if args.path is None:
        pull_requests = json.load(sys.stdin)
    else:
        with args.path.open(encoding="utf-8") as stream:
            pull_requests = json.load(stream)
    number = select_append_candidate(pull_requests)
    if number is not None:
        sys.stdout.write(f"{number}\n")


if __name__ == "__main__":
    main()
