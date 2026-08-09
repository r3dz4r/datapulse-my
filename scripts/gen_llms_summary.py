#!/usr/bin/env python3
"""Derive the dataset-count references in llms.txt from datapulse.json."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path


MANIFEST_PATTERN = r"a machine-readable manifest of \d+ official datasets"
CATALOGUE_PATTERN = r"the \d+-dataset catalogue"


class GenerationError(Exception):
    """Raised when inputs do not satisfy the generator contract."""


def generate(root: Path) -> None:
    manifest_path = root / "datapulse.json"
    llms_path = root / "llms.txt"

    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise GenerationError(f"cannot read {manifest_path}: {error}") from error

    datasets = manifest.get("datasets") if isinstance(manifest, dict) else None
    if not isinstance(datasets, list):
        raise GenerationError(f"{manifest_path}: 'datasets' must be an array")
    count = len(datasets)

    try:
        original = llms_path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as error:
        raise GenerationError(f"cannot read {llms_path}: {error}") from error

    updated, manifest_matches = re.subn(
        MANIFEST_PATTERN,
        f"a machine-readable manifest of {count} official datasets",
        original,
    )
    updated, catalogue_matches = re.subn(
        CATALOGUE_PATTERN,
        f"the {count}-dataset catalogue",
        updated,
    )

    missing = []
    if manifest_matches < 1:
        missing.append(f"{MANIFEST_PATTERN!r} (expected 1, found 0)")
    if catalogue_matches < 2:
        missing.append(
            f"{CATALOGUE_PATTERN!r} (expected 2, found {catalogue_matches})"
        )
    if missing:
        raise GenerationError("missing llms.txt count pattern(s): " + ", ".join(missing))

    if updated != original:
        llms_path.write_text(updated, encoding="utf-8")


def parse_args() -> argparse.Namespace:
    default_root = Path(__file__).resolve().parent.parent
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=default_root)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        generate(args.root)
    except GenerationError as error:
        print(f"gen_llms_summary.py: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
