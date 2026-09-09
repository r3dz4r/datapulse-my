"""Create and verify immutable inventories for Cloudflare Pages artifacts."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import sys
from typing import Any


SCHEMA = "datapulse/v1/release-artifact-manifest"
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_SOURCE_COMMIT = re.compile(r"^[0-9a-f]{40,64}$")


class ManifestError(ValueError):
    """Raised when an artifact inventory is malformed or does not match disk."""


def _validate_source_commit(source_commit: str) -> None:
    if _SOURCE_COMMIT.fullmatch(source_commit) is None:
        raise ManifestError("source commit must be a 40-64 character lowercase hexadecimal SHA")


def _validate_path(path: str, label: str) -> None:
    if (
        not path
        or path.startswith("/")
        or "\\" in path
        or any(part in {"", ".", ".."} for part in path.split("/"))
    ):
        raise ManifestError(f"unsafe {label} path: {path!r}")


def _site_root(site_root: Path) -> Path:
    try:
        metadata = site_root.lstat()
    except FileNotFoundError as error:
        raise ManifestError(f"site root is missing: {site_root}") from error
    if stat.S_ISLNK(metadata.st_mode):
        raise ManifestError(f"site root must not be a symlink: {site_root}")
    if not stat.S_ISDIR(metadata.st_mode):
        raise ManifestError(f"site root is not a directory: {site_root}")
    return site_root.resolve()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as artifact_file:
        for chunk in iter(lambda: artifact_file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def inventory(site_root: Path) -> list[dict[str, Any]]:
    """Return the sorted regular-file inventory, refusing all symlinks."""
    root = _site_root(site_root)
    files: list[dict[str, Any]] = []
    for directory, names, filenames in os.walk(root, topdown=True, followlinks=False):
        current = Path(directory)
        for name in names:
            candidate = current / name
            if stat.S_ISLNK(candidate.lstat().st_mode):
                raise ManifestError(f"symlink in site artifact: {candidate.relative_to(root)}")
        for name in filenames:
            candidate = current / name
            mode = candidate.lstat().st_mode
            relative = candidate.relative_to(root).as_posix()
            if stat.S_ISLNK(mode):
                raise ManifestError(f"symlink in site artifact: {relative}")
            if not stat.S_ISREG(mode):
                raise ManifestError(f"non-regular file in site artifact: {relative}")
            _validate_path(relative, "artifact")
            files.append({"path": relative, "sha256": _sha256(candidate), "size": candidate.stat().st_size})
    return sorted(files, key=lambda entry: entry["path"])


def aggregate_digest(files: list[dict[str, Any]]) -> str:
    """Hash sorted path, SHA-256, and byte-size records without filesystem metadata."""
    digest = hashlib.sha256()
    for entry in sorted(files, key=lambda item: item["path"]):
        digest.update(entry["path"].encode("utf-8"))
        digest.update(b"\0")
        digest.update(entry["sha256"].encode("ascii"))
        digest.update(b"\0")
        digest.update(str(entry["size"]).encode("ascii"))
        digest.update(b"\n")
    return digest.hexdigest()


def _manifest_for(files: list[dict[str, Any]], source_commit: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "source_commit": source_commit,
        "file_count": len(files),
        "files": files,
        "aggregate_sha256": aggregate_digest(files),
    }


def _validate_manifest(manifest: object) -> dict[str, Any]:
    if not isinstance(manifest, dict) or set(manifest) != {
        "schema", "source_commit", "file_count", "files", "aggregate_sha256"
    }:
        raise ManifestError("manifest schema is invalid")
    if manifest["schema"] != SCHEMA:
        raise ManifestError("manifest schema is invalid")
    source_commit = manifest["source_commit"]
    if not isinstance(source_commit, str):
        raise ManifestError("manifest source commit is invalid")
    _validate_source_commit(source_commit)
    files = manifest["files"]
    if not isinstance(files, list) or type(manifest["file_count"]) is not int:
        raise ManifestError("manifest file inventory is invalid")
    if manifest["file_count"] != len(files):
        raise ManifestError("manifest file count does not match inventory")
    paths: list[str] = []
    for entry in files:
        if not isinstance(entry, dict) or set(entry) != {"path", "sha256", "size"}:
            raise ManifestError("manifest file record is invalid")
        path, digest, size = entry["path"], entry["sha256"], entry["size"]
        if not isinstance(path, str):
            raise ManifestError("unsafe manifest path: non-string")
        _validate_path(path, "manifest")
        if not isinstance(digest, str) or _SHA256.fullmatch(digest) is None:
            raise ManifestError(f"manifest digest is invalid: {path}")
        if type(size) is not int or size < 0:
            raise ManifestError(f"manifest size is invalid: {path}")
        paths.append(path)
    if paths != sorted(paths) or len(paths) != len(set(paths)):
        raise ManifestError("manifest paths must be unique and sorted")
    aggregate = manifest["aggregate_sha256"]
    if not isinstance(aggregate, str) or _SHA256.fullmatch(aggregate) is None:
        raise ManifestError("manifest aggregate digest is invalid")
    if aggregate != aggregate_digest(files):
        raise ManifestError("manifest aggregate digest mismatch")
    return manifest


def load_manifest(manifest_path: Path) -> dict[str, Any]:
    """Load and validate a release-artifact manifest from JSON."""
    try:
        with manifest_path.open(encoding="utf-8") as manifest_file:
            return _validate_manifest(json.load(manifest_file))
    except FileNotFoundError as error:
        raise ManifestError(f"manifest is missing: {manifest_path}") from error
    except json.JSONDecodeError as error:
        raise ManifestError(f"manifest is not valid JSON: {manifest_path}") from error


def _atomic_write_json(output_path: Path, manifest: dict[str, Any]) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = output_path.with_name(f".{output_path.name}.{os.getpid()}.tmp")
    try:
        with temporary.open("x", encoding="utf-8") as output:
            json.dump(manifest, output, ensure_ascii=True, indent=2, sort_keys=True)
            output.write("\n")
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, output_path)
    finally:
        if temporary.exists():
            temporary.unlink()


def create_manifest(site_root: Path, output_path: Path, source_commit: str) -> dict[str, Any]:
    """Create an atomic, deterministic manifest outside the site artifact."""
    _validate_source_commit(source_commit)
    root = _site_root(site_root)
    output = output_path.resolve()
    if output.is_relative_to(root):
        raise ManifestError("manifest output must not be inside the site artifact")
    manifest = _manifest_for(inventory(root), source_commit)
    _atomic_write_json(output, manifest)
    return manifest


def verify_manifest(site_root: Path, manifest_path: Path, source_commit: str) -> dict[str, Any]:
    """Verify the source binding and exact byte inventory against a manifest."""
    _validate_source_commit(source_commit)
    manifest = load_manifest(manifest_path)
    if manifest["source_commit"] != source_commit:
        raise ManifestError("source commit mismatch")
    observed = inventory(site_root)
    expected = manifest["files"]
    if [entry["path"] for entry in observed] != [entry["path"] for entry in expected]:
        raise ManifestError("artifact inventory does not match manifest")
    for expected_entry, observed_entry in zip(expected, observed, strict=True):
        if expected_entry["size"] != observed_entry["size"]:
            raise ManifestError(f"size mismatch: {expected_entry['path']}")
        if expected_entry["sha256"] != observed_entry["sha256"]:
            raise ManifestError(f"digest mismatch: {expected_entry['path']}")
    if manifest["aggregate_sha256"] != aggregate_digest(observed):
        raise ManifestError("aggregate digest mismatch")
    return manifest


def _arguments(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("create", "verify"):
        command = commands.add_parser(name)
        command.add_argument("--site", required=True, type=Path)
        command.add_argument("--manifest", required=True, type=Path)
        command.add_argument("--source-commit", required=True)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Run the release-artifact manifest command-line interface."""
    args = _arguments(argv)
    try:
        if args.command == "create":
            manifest = create_manifest(args.site, args.manifest, args.source_commit)
            print(f"created release artifact manifest: {manifest['aggregate_sha256']}")
        else:
            manifest = verify_manifest(args.site, args.manifest, args.source_commit)
            print(f"verified release artifact manifest: {manifest['aggregate_sha256']}")
    except ManifestError as error:
        print(f"release artifact verification failed: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
