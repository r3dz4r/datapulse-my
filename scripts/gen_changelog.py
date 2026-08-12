#!/usr/bin/env python3
"""Deprecated shim for gen_catalog_snapshot.py."""

from __future__ import annotations

import sys

from gen_catalog_snapshot import main

if __name__ == "__main__":
    print(
        "DEPRECATED: gen_changelog.py now delegates to gen_catalog_snapshot.py",
        file=sys.stderr,
    )
    if len(sys.argv) == 2 and not sys.argv[1].startswith("-"):
        sys.argv[1:2] = ["--health", sys.argv[1]]
    main()
