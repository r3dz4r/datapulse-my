#!/usr/bin/env python3
"""Stamp the canonical website origin into the datapulse.json $schema pointer."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.public_surface_generation import (
    GenerationError,
    atomic_write_text,
    load_public_surfaces,
)


SCHEMA_ARTIFACT = "datapulse.schema.json"

# The manifest is pretty-printed with two-space indentation, so a top-level
# "$schema" key is uniquely identifiable by its exact indent; nested keys would
# sit at four spaces or deeper. Matching the whole line keeps every other
# manifest byte untouched.
SCHEMA_POINTER_RE = re.compile(
    r'(?m)^(?P<indent>  )"\$schema": "(?P<value>[^"\n]*)"(?P<comma>,?)$'
)


def canonical_schema_url(config: dict) -> str:
    """Derive the canonical manifest schema URL from the public-surface origins."""
    return f"{config['origins']['website']}/{SCHEMA_ARTIFACT}"


def stamp(root: Path) -> str:
    """Set datapulse.json $schema to the canonical URL, preserving all other bytes."""
    config = load_public_surfaces(root)
    canonical = canonical_schema_url(config)
    path = root / "datapulse.json"
    try:
        original = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as error:
        raise GenerationError(f"cannot read {path}: {error}") from error
    try:
        document = json.loads(original)
    except json.JSONDecodeError as error:
        raise GenerationError(f"{path}: invalid JSON: {error}") from error
    if not isinstance(document, dict) or not isinstance(document.get("$schema"), str):
        raise GenerationError(f"{path}: expected an object with a string $schema")
    matches = list(SCHEMA_POINTER_RE.finditer(original))
    if len(matches) != 1:
        raise GenerationError(
            f"{path}: expected exactly one top-level $schema pointer line, found {len(matches)}"
        )
    updated = SCHEMA_POINTER_RE.sub(
        lambda match: f"{match.group('indent')}\"$schema\": \"{canonical}\"{match.group('comma')}",
        original,
        count=1,
    )
    if updated != original:
        atomic_write_text(path, updated)
    return canonical


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        canonical = stamp(args.root)
    except GenerationError as error:
        print(f"stamp_manifest_origin.py: {error}", file=sys.stderr)
        return 1
    print(f"stamp_manifest_origin.py: datapulse.json $schema = {canonical}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
