#!/usr/bin/env python3
"""Reject public files that expose repository-internal notes or analyses."""

from __future__ import annotations

import argparse
import re
import subprocess
from pathlib import Path


PUBLIC_ROOT_FILES = frozenset({"README.md", "llms.txt", "agent.json", "mcp.json", "server.json", "glama.json"})
INTERNAL_REFERENCE = re.compile(
    r"(?:^|(?<![A-Za-z0-9_~./-]))(?:\./)?(?:notes|analyses)/[^\s)\]}>\"']+?\.md(?=$|[\s)\]}>\"',;:!?#])"
)


def _is_public_path(relative_path: str) -> bool:
    """Return whether a tracked path is an explicitly public file."""
    if relative_path in PUBLIC_ROOT_FILES:
        return True
    return (
        relative_path.startswith("docs/")
        and relative_path.endswith((".md", ".html"))
        or relative_path.startswith("claims/")
        and relative_path.endswith(".json")
    )


def _tracked_public_paths(root: Path) -> list[Path]:
    """List tracked public files without traversing untracked content."""
    result = subprocess.run(
        ["git", "-C", str(root), "ls-files", "-z"],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(f"unable to list tracked files: {result.stderr.strip()}")
    return sorted(
        (root / relative_path for relative_path in result.stdout.split("\x00") if _is_public_path(relative_path)),
        key=lambda path: path.as_posix(),
    )


def verify_public_internal_refs(root: Path) -> list[str]:
    """Return diagnostics for prohibited internal references in public files."""
    try:
        paths = _tracked_public_paths(root)
    except RuntimeError as exc:
        return [str(exc)]

    errors: list[str] = []
    for path in paths:
        relative_path = path.relative_to(root).as_posix()
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except OSError as exc:
            errors.append(f"{relative_path}: cannot read public file: {exc}")
            continue
        for line_number, line in enumerate(lines, start=1):
            for _ in INTERNAL_REFERENCE.finditer(line):
                errors.append(f"{relative_path}:{line_number}: prohibited internal repository reference")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    errors = verify_public_internal_refs(args.root.resolve())
    if errors:
        print(f"Public internal-reference verification failed ({len(errors)} violation(s)):")
        for error in errors:
            print(f"- {error}")
        return 1
    print("Public internal-reference verification passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
