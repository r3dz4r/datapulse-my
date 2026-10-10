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
    """Dates cannot establish signed-parent incompatibility; retain all evidence."""
    return []


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
