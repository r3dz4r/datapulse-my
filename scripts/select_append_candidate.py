#!/usr/bin/env python3
"""Select the newest open attestation append pull request."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path


def _append_day(pull_request: dict[str, object]) -> str | None:
    """Read the day encoded in the append PR title."""
    match = re.search(r"append signed evidence from source (\d{4}-\d{2}-\d{2})$", str(pull_request.get("title", "")))
    return match.group(1) if match else None


def select_superseded_siblings(
    pull_requests: list[dict[str, object]], merged_number: int
) -> list[int]:
    """Return open append PRs for the merged candidate's day, in number order."""
    merged = next((pr for pr in pull_requests if int(pr["number"]) == merged_number), None)
    if merged is None:
        return []
    day = _append_day(merged)
    if day is None:
        return []
    return sorted(
        int(pr["number"])
        for pr in pull_requests
        if int(pr["number"]) != merged_number
        and str(pr.get("state", "OPEN")).upper() == "OPEN"
        and str(pr["headRefName"]).startswith("attestation/append-")
        and _append_day(pr) == day
    )


def select_append_candidate(pull_requests: list[dict[str, object]]) -> int | None:
    """Return the newest append PR number, breaking timestamp ties by number."""
    candidates = [
        pull_request
        for pull_request in pull_requests
        if str(pull_request["headRefName"]).startswith("attestation/append-")
    ]
    if not candidates:
        return None

    # Same-day appends can be sibling revisions of one parent head. Accepting
    # both would make later candidates fail the chain's accepted-parent check.
    newest = max(
        candidates,
        key=lambda pull_request: (
            str(pull_request["createdAt"]),
            int(pull_request["number"]),
        ),
    )
    return int(newest["number"])


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
