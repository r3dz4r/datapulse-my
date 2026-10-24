#!/usr/bin/env python3
"""Compare an arrival's source stamp with a previously fetched served proof.

The caller supplies the build's full head SHA and the canonical HTTPS release
proof. No network access, credentials, subprocesses or filesystem writes occur
here. Equality only deduplicates the same source; different commits are never
assumed equivalent. A missing or ambiguous identity always admits publication.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import sys


_SHA = re.compile(r"[0-9a-f]{40}")
_PROOF_MARKERS = (
    "# Release reproducibility verification",
    "<!-- generated: scripts/verify_release_reproducible.py; do not hand-edit -->",
    "- Status: `current generated release proof`",
    "- Protocol result: `byte-identical isolated release-build runs`",
)


def _served_identity(path: Path | None) -> str | None:
    if path is None:
        return None
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeError):
        return None
    if any(marker not in lines for marker in _PROOF_MARKERS):
        return None
    stamps = [line for line in lines if line.startswith("- Source SHA:")]
    if len(stamps) != 1:
        return None
    match = re.fullmatch(r"- Source SHA: `([0-9a-f]{40})`", stamps[0])
    return match[1] if match else None


def decide(promotion_source_sha: str | None, served_proof: Path | None) -> dict[str, str | None]:
    """Return one stable output shape, failing open to the existing deploy gates."""
    candidate = promotion_source_sha if promotion_source_sha and _SHA.fullmatch(promotion_source_sha) else None
    served = _served_identity(served_proof)
    decision = "publish"
    reason = "comparison_unavailable"
    if candidate is not None and served is not None:
        decision = "skip" if candidate == served else "publish"
        reason = "identities_equal" if candidate == served else "identities_differ"
    return {
        "decision": decision,
        "reason_code": reason,
        "reason": f"{reason}: candidate={candidate or 'unavailable'}; served={served or 'unavailable'}",
        "candidate_identity": candidate,
        "served_identity": served,
    }


class _Parser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        # Invalid invocations must not acquire a third, error-shaped decision.
        raise ValueError(message)


def main(argv: list[str] | None = None) -> int:
    """Emit JSON (default) or a human summary; both decisions exit zero."""
    parser = _Parser(description=__doc__)
    parser.add_argument("--promotion-source-sha", help="Full immutable build head SHA")
    parser.add_argument("--served-proof", type=Path, help="Fetched canonical release-verification.md")
    parser.add_argument("--mode", choices=("json", "human"), default="json")
    try:
        args = parser.parse_args(argv)
    except ValueError:
        result = decide(None, None)
        mode = "json"
    else:
        result = decide(args.promotion_source_sha, args.served_proof)
        mode = args.mode
    if mode == "json":
        sys.stdout.write(json.dumps(result, sort_keys=True) + "\n")
    else:
        sys.stdout.write(f"{result['decision']} {result['reason']}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
