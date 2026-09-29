#!/usr/bin/env python3
"""Exclude Cloudflare Pages assets larger than the configured per-file limit."""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import NoReturn


DEFAULT_LIMIT_BYTES = 25 * 1024 * 1024
MANIFEST_NAME = "excluded-assets.json"


class GuardError(Exception):
    """The staged site could not be checked or its manifest could not be written."""


def positive_int(value: str) -> int:
    """Parse a positive byte limit for argparse."""
    try:
        parsed = int(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError("must be an integer number of bytes") from error
    if parsed <= 0:
        raise argparse.ArgumentTypeError("must be greater than zero")
    return parsed


def timestamp() -> str:
    """Return a UTC timestamp suitable for the published manifest."""
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def site_files(site_dir: Path) -> list[Path]:
    """Return every file in the staged site, failing closed on traversal errors."""
    files: list[Path] = []

    def on_error(error: OSError) -> NoReturn:
        raise GuardError(f"cannot read staged site directory {site_dir}: {error}") from error

    try:
        for root, directories, filenames in os.walk(site_dir, onerror=on_error):
            directories.sort()
            filenames.sort()
            files.extend(Path(root) / filename for filename in filenames)
    except OSError as error:
        raise GuardError(f"cannot read staged site directory {site_dir}: {error}") from error
    return files


def write_manifest(site_dir: Path, limit_bytes: int, excluded_assets: list[dict[str, object]]) -> None:
    """Atomically write the exclusion record into the staged site."""
    manifest_path = site_dir / MANIFEST_NAME
    temporary_path = manifest_path.with_name(f".{MANIFEST_NAME}.tmp")
    manifest = {
        "generated_at": timestamp(),
        "size_limit_bytes": limit_bytes,
        "excluded_assets": excluded_assets,
    }
    try:
        temporary_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
        temporary_path.replace(manifest_path)
    except OSError as error:
        try:
            temporary_path.unlink(missing_ok=True)
        except OSError:
            pass
        raise GuardError(f"cannot write exclusion manifest {manifest_path}: {error}") from error


def check_site(site_dir: Path, limit_bytes: int) -> list[dict[str, object]]:
    """Remove oversized staged assets and return their public manifest entries."""
    if not site_dir.is_dir():
        raise GuardError(f"staged site directory is missing or unreadable: {site_dir}")

    excluded_assets: list[dict[str, object]] = []
    for asset_path in site_files(site_dir):
        try:
            size_bytes = asset_path.stat().st_size
        except OSError as error:
            raise GuardError(f"cannot measure staged asset {asset_path}: {error}") from error
        if size_bytes <= limit_bytes:
            continue

        relative_path = asset_path.relative_to(site_dir).as_posix()
        try:
            asset_path.unlink()
        except OSError as error:
            raise GuardError(f"cannot remove oversized staged asset {asset_path}: {error}") from error

        excluded_at = timestamp()
        print(f"excluded oversized Pages asset: {relative_path} ({size_bytes / 1024 / 1024:.1f} MiB)")
        excluded_assets.append(
            {
                "path": relative_path,
                "size_bytes": size_bytes,
                "limit_bytes": limit_bytes,
                "timestamp": excluded_at,
            }
        )

    write_manifest(site_dir, limit_bytes, excluded_assets)
    return excluded_assets


def parse_args() -> argparse.Namespace:
    """Parse the staged site directory and its maximum asset size."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("site_dir", type=Path, help="assembled Pages directory to check")
    parser.add_argument(
        "--limit-bytes",
        type=positive_int,
        default=DEFAULT_LIMIT_BYTES,
        help="maximum permitted asset size in bytes (default: 25 MiB)",
    )
    return parser.parse_args()


def main() -> int:
    """Run the guard and return a process status."""
    args = parse_args()
    try:
        check_site(args.site_dir, args.limit_bytes)
    except GuardError as error:
        print(f"Pages asset-size guard failed: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
