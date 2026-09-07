#!/usr/bin/env python3
"""Decide whether a daily attestation generation warrants a commit."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Iterable


def commit_message_for_changed_paths(changed_paths: Iterable[str], day: str) -> str | None:
    """Return the daily commit message only when that day's envelope changed."""
    dated_prefix = f"attestations/{day}/"
    if not any(path.startswith(dated_prefix) for path in changed_paths):
        return None
    return f"chore(attestations): commit signed envelopes for {day} [skip deploy]"


def main() -> int:
    """Print the commit message for newline-delimited changed paths, if any."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", required=True)
    args = parser.parse_args()

    message = commit_message_for_changed_paths(sys.stdin.read().splitlines(), args.date)
    if message is not None:
        print(message)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
