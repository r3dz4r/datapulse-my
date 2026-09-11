#!/usr/bin/env python3
"""Fail closed when version-bearing files disagree with the release-please manifest.

The newest v* tag is compared to the manifest as an ordered version: a tag
older than the manifest is a release in flight (release-please tags only after
the merge lands), while a tag newer than the manifest is real drift.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
MANIFEST_NAME = ".release-please-manifest.json"
VERSION_TXT_NAME = "VERSION.txt"
SERVER_JSON_NAME = "server.json"


class CannotDetermine(Exception):
    """A version-bearing value could not be read; absence is not agreement."""


@dataclass(frozen=True)
class ReleaseIdentity:
    """Versions collected from each source that exists."""

    manifest: str
    version_txt: str
    server_json: str
    tag: str | None


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse CLI flags. ``--check`` is the default when neither mode is given."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root",
        type=Path,
        default=REPO_ROOT,
        help="Repository root (default: parent of scripts/)",
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--check",
        action="store_true",
        help="Compare version-bearing files and exit 0 only when they agree (default)",
    )
    mode.add_argument(
        "--write",
        action="store_true",
        help="Write the manifest version into server.json, then compare",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit JSON instead of prose",
    )
    args = parser.parse_args(argv)
    if not args.write:
        args.check = True
    return args


def load_release_identity(root: Path) -> ReleaseIdentity:
    """Read every version-bearing source. Missing or unreadable sources raise."""
    return ReleaseIdentity(
        manifest=_read_manifest_version(root),
        version_txt=_read_version_txt(root),
        server_json=_read_server_json_version(root),
        tag=_read_newest_tag(root),
    )


def write_server_version(root: Path, version: str) -> None:
    """Set server.json version from the manifest without rewriting other fields."""
    path = root / SERVER_JSON_NAME
    data = _read_json_object(path)
    if "version" not in data or not isinstance(data["version"], str):
        raise CannotDetermine(f"{SERVER_JSON_NAME}: missing string version field")
    data["version"] = version
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def first_disagreement(identity: ReleaseIdentity) -> tuple[str, str, str, str] | None:
    """Return (left_source, left_value, right_source, right_value) vs the manifest.

    Files must match the manifest exactly. The tag is compared as an ordered
    version: equal or older agrees (older = release in flight), newer is drift,
    and a value that is not a dotted numeric version fails closed exactly like
    the old strict string comparison did.
    """
    baseline = identity.manifest
    for name, value in (
        ("version_txt", identity.version_txt),
        ("server_json", identity.server_json),
    ):
        if value != baseline:
            return ("manifest", baseline, name, value)
    if identity.tag is not None and not _tag_agrees_with_manifest(identity.tag, baseline):
        return ("manifest", baseline, "tag", identity.tag)
    return None


def main(argv: list[str] | None = None) -> int:
    """Compare (and optionally rewrite) release versions; 0 agree, 1 disagree, 2 unknown."""
    args = parse_args(argv)
    root = args.root.expanduser().resolve()
    try:
        if args.write:
            write_server_version(root, _read_manifest_version(root))
        identity = load_release_identity(root)
    except CannotDetermine as exc:
        print(f"cannot determine: {exc}", file=sys.stderr)
        return 2
    disagreement = first_disagreement(identity)
    agree = disagreement is None
    if args.json:
        payload = {
            "manifest": identity.manifest,
            "version_txt": identity.version_txt,
            "server_json": identity.server_json,
            "tag": identity.tag,
            "agree": agree,
        }
        print(json.dumps(payload))
    else:
        print(f"manifest: {identity.manifest}")
        print(f"version_txt: {identity.version_txt}")
        print(f"server_json: {identity.server_json}")
        if identity.tag is not None:
            print(f"tag: {identity.tag}")
        if disagreement is not None:
            left, left_value, right, right_value = disagreement
            print(f"disagree: {left}={left_value} {right}={right_value}")
        elif identity.tag is not None and _tag_is_behind(identity.tag, identity.manifest):
            print(
                f"note: tag {identity.tag} is behind the manifest "
                f"{identity.manifest} (release in flight)"
            )
    return 0 if agree else 1


def _parse_dotted_version(value: str) -> tuple[int, ...] | None:
    """Return the numeric components of a dotted version; None when not one."""
    if re.fullmatch(r"[0-9]+(?:\.[0-9]+)+", value) is None:
        return None
    return tuple(int(part) for part in value.split("."))


def _tag_is_behind(tag: str, manifest: str) -> bool:
    """True only when both parse and the tag is strictly older than the manifest."""
    tag_parts = _parse_dotted_version(tag)
    manifest_parts = _parse_dotted_version(manifest)
    return (
        tag_parts is not None
        and manifest_parts is not None
        and tag_parts < manifest_parts
    )


def _tag_agrees_with_manifest(tag: str, manifest: str) -> bool:
    """Equal or older tags agree (older = release in flight); anything else fails closed."""
    return tag == manifest or _tag_is_behind(tag, manifest)


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise CannotDetermine(f"missing {path.name}") from exc
    except OSError as exc:
        raise CannotDetermine(f"cannot read {path.name}: {exc}") from exc


def _read_json_object(path: Path) -> dict[str, object]:
    text = _read_text(path)
    try:
        value: object = json.loads(text)
    except json.JSONDecodeError as exc:
        raise CannotDetermine(f"unparseable JSON in {path.name}") from exc
    if not isinstance(value, dict):
        raise CannotDetermine(f"unparseable JSON in {path.name}: expected object")
    return value


def _read_manifest_version(root: Path) -> str:
    data = _read_json_object(root / MANIFEST_NAME)
    version = data.get(".")
    if not isinstance(version, str) or not version.strip():
        raise CannotDetermine(f"{MANIFEST_NAME}: missing '.' version")
    return version.strip()


def _read_version_txt(root: Path) -> str:
    return _read_text(root / VERSION_TXT_NAME).strip()


def _read_server_json_version(root: Path) -> str:
    data = _read_json_object(root / SERVER_JSON_NAME)
    version = data.get("version")
    if not isinstance(version, str):
        raise CannotDetermine(f"{SERVER_JSON_NAME}: missing string version field")
    return version


def _read_newest_tag(root: Path) -> str | None:
    """Read the newest v* tag at this root only; do not inherit a parent worktree."""
    git_dir = root / ".git"
    if not git_dir.exists():
        return None
    try:
        completed = subprocess.run(
            [
                "git",
                "--git-dir",
                str(git_dir),
                "--work-tree",
                str(root),
                "describe",
                "--tags",
                "--abbrev=0",
                "--match",
                "v*",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError as exc:
        raise CannotDetermine(f"git failure: {exc}") from exc
    if completed.returncode == 0:
        tag = completed.stdout.strip()
        return tag.removeprefix("v")
    stderr = (completed.stderr or "").strip()
    lowered = stderr.lower()
    # No matching tags is absence, not a determination failure.
    if "no names found" in lowered or "no tags" in lowered:
        return None
    raise CannotDetermine(f"git failure: {stderr or completed.returncode}")


if __name__ == "__main__":
    raise SystemExit(main())
