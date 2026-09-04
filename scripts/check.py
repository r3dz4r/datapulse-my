#!/usr/bin/env python3
"""Compatibility entry point for the repository contract check."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


def main() -> int:
    """Run the full contract check or the focused parquet/dashboard smoke tests."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
        help="repository root (defaults to the parent of scripts/)",
    )
    parser.add_argument(
        "--quick-test",
        action="store_true",
        help="run focused parquet freshness and dashboard smoke tests",
    )
    args = parser.parse_args()
    root = args.root.resolve()

    if args.quick_test:
        return subprocess.run(
            [
                sys.executable,
                "-m",
                "pytest",
                "scripts/tests/test_dashboard.py",
                "scripts/tests/test_extract_content_freshness.py",
                "scripts/tests/test_extract_parquet_freshness.py",
                "-q",
            ],
            cwd=root,
            check=False,
        ).returncode

    return subprocess.run(
        [sys.executable, str(root / "scripts/verify_repository_contract.py"), "--root", str(root)],
        check=False,
    ).returncode


if __name__ == "__main__":
    raise SystemExit(main())
