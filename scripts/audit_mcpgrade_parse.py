#!/usr/bin/env python3
"""Parse mcpgrade JSON output into a structured summary dict.

Hermetic helper so tests can exercise the extraction logic without npx.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any


def parse_mcpgrade_output(data: dict[str, Any]) -> dict[str, Any] | None:
    """Extract grade, total_score, and tool count from mcpgrade JSON.

    Returns None if required fields are missing or null.
    """
    grade = data.get("grade")
    total_score = data.get("totalScore")
    snapshot = data.get("snapshot", {})
    tools = snapshot.get("toolCount") if isinstance(snapshot, dict) else None

    if grade is None or total_score is None or tools is None:
        return None

    return {
        "grade": str(grade),
        "total_score": int(total_score),
        "tools": int(tools),
    }


def parse_file(path: Path) -> dict[str, Any] | None:
    """Load JSON from *path* and return parsed summary, or None on failure."""
    try:
        with open(path) as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError):
        return None
    return parse_mcpgrade_output(data)


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Parse mcpgrade JSON output")
    parser.add_argument("file", type=Path, help="Path to mcpgrade JSON")
    parser.add_argument(
        "--format",
        choices=["json", "summary"],
        default="summary",
        help="Output format (default: summary)",
    )
    args = parser.parse_args()

    result = parse_file(args.file)
    if result is None:
        print(f"UNKNOWN: could not parse mcpgrade output — inspect {args.file}", file=sys.stderr)
        sys.exit(3)

    if args.format == "json":
        print(json.dumps(result))
    else:
        print(
            f"OK: mcpgrade grade={result['grade']} score={result['total_score']} tools={result['tools']}"
        )


if __name__ == "__main__":
    main()
