#!/usr/bin/env python3
"""Reject retired manual MCP source stamping."""

from __future__ import annotations

import sys


def main() -> int:
    print(
        "bump_mcp_source_version.py: refusing manual MCP source stamping; "
        "the published stamp is derived from default-branch mcp/ history. "
        "Hand-stamping caused the source-revision drift this generator now prevents.",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
