#!/usr/bin/env python3
"""Prove that a retained observation store survives backup and restore as verified evidence.

An archive nobody has ever restored is a belief, not a backup. This module
archives an observation store with exactly the flags the estate's backup
uses, restores the archive into a clean destination, deletes the original
tree, and only then verifies — so the verification cannot depend on the live
source bytes still being present.

Verification here reports, never repairs: a restore that silently "fixed" a
mismatch would convert corruption into confident, unusable evidence. Nothing
in this module writes inside any store it verifies, and every archive,
restore and verification root must be absolute so a proof can never depend
on the directory a timer happened to run in.
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Final

try:
    # Absolute form when the repo root is on sys.path (pipeline, pytest rootdir).
    from scripts.observation_gates import verify_store
except ModuleNotFoundError:  # bare form when scripts/ itself is on sys.path
    from observation_gates import verify_store

__all__ = [
    "RestoreError",
    "TAR_EXCLUDE_PATTERNS",
    "archive_store",
    "restore_store",
    "store_inventory",
    "verify_restored",
    "round_trip",
    "main",
]

# The estate backup's exclusion list, verbatim and in its order, so the proof
# exercises the real archive shape rather than an idealised one.
TAR_EXCLUDE_PATTERNS: Final[tuple[str, ...]] = (
    "*/.venv",
    "*/.git",
    "*/node_modules",
    "*/__pycache__",
    "*.pyc",
    "*/.mypy_cache",
    "*/.pytest_cache",
    "*/.ruff_cache",
)


class RestoreError(Exception):
    """Archive, restore or refusal failure; the message names the archive or path."""


def _require_absolute(path: Path, role: str) -> Path:
    """Reject relative paths: a cwd-dependent proof of independence proves nothing."""
    if not path.is_absolute():
        raise RestoreError(f"{role} must be an absolute path, got {path}")
    return path


def _run_tar(arguments: list[str], *, role: str) -> str:
    """Run tar, failing loudly on a non-zero exit or any diagnostic on stderr."""
    completed = subprocess.run(
        ["tar", *arguments],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if completed.returncode != 0:
        raise RestoreError(
            f"tar {role} failed with exit code {completed.returncode}: "
            f"{completed.stderr.strip() or completed.stdout.strip() or 'no output'}"
        )
    diagnostics = completed.stderr.strip()
    if diagnostics:
        raise RestoreError(
            f"tar {role} emitted diagnostics on stderr; treated as a failure: {diagnostics}"
        )
    return completed.stdout


def archive_store(source_root: Path, archive_path: Path) -> Path:
    """Archive the store at source_root into archive_path.

    Uses exactly the flags the estate's backup uses so the proof exercises the
    real shape:

        tar -cf <archive> --xattrs --acls --numeric-owner \\
            --exclude='*/.venv' --exclude='*/.git' --exclude='*/node_modules' \\
            --exclude='*/__pycache__' --exclude='*.pyc' --exclude='*/.mypy_cache' \\
            --exclude='*/.pytest_cache' --exclude='*/.ruff_cache' \\
            -C <parent of source_root> <name of source_root>

    Fails loudly on a non-zero tar exit, and treats diagnostics on stderr as a
    failure. Returns the archive path.
    """
    source = _require_absolute(Path(source_root), "source_root")
    archive = _require_absolute(Path(archive_path), "archive_path")
    if not source.is_dir():
        raise RestoreError(f"source store {source} is not a directory")
    archive.parent.mkdir(parents=True, exist_ok=True)
    _run_tar(
        [
            "-cf",
            str(archive),
            "--xattrs",
            "--acls",
            "--numeric-owner",
            *(f"--exclude={pattern}" for pattern in TAR_EXCLUDE_PATTERNS),
            "-C",
            str(source.parent),
            source.name,
        ],
        role=f"archive of {source}",
    )
    return archive


def _top_level_directory(archive: Path) -> str:
    """The single top-level directory member an archive of a store must carry."""
    listing = _run_tar(["-tf", str(archive)], role=f"listing of {archive}")
    names: set[str] = set()
    for member in listing.splitlines():
        cleaned = member.strip()
        while cleaned.startswith("./"):
            cleaned = cleaned[2:]
        if not cleaned:
            continue
        first = cleaned.split("/", 1)[0]
        if first:
            names.add(first)
    if not names:
        raise RestoreError(f"archive {archive} lists no members; there is nothing to restore")
    if len(names) > 1:
        raise RestoreError(
            f"archive {archive} has multiple top-level entries {sorted(names)}; "
            "a store archive must carry exactly one"
        )
    return next(iter(names))


def restore_store(archive_path: Path, destination_root: Path) -> Path:
    """Extract archive_path into a clean destination_root and return the restored store root.

    Refuses to extract into a non-empty destination rather than merging into it.
    Does not modify what was extracted: no chmod sweep, no rewrite, no repair.
    """
    archive = _require_absolute(Path(archive_path), "archive_path")
    destination = _require_absolute(Path(destination_root), "destination_root")
    if not archive.is_file():
        raise RestoreError(f"archive {archive} does not exist or is not a file")
    if destination.exists():
        if not destination.is_dir():
            raise RestoreError(f"destination {destination} exists and is not a directory")
        if any(destination.iterdir()):
            raise RestoreError(
                f"refusing to restore into non-empty destination {destination}; "
                "merging an archive into existing content is not a restore"
            )
    else:
        destination.mkdir(parents=True)
    top_level = _top_level_directory(archive)
    _run_tar(
        [
            "-xf",
            str(archive),
            "--xattrs",
            "--acls",
            "--numeric-owner",
            "--same-permissions",
            "-C",
            str(destination),
        ],
        role=f"restore of {archive}",
    )
    restored_root = destination / top_level
    if not restored_root.is_dir():
        raise RestoreError(
            f"archive {archive} did not produce directory {restored_root}; "
            "refusing to guess the store root"
        )
    return restored_root


def store_inventory(root: Path) -> set[Path]:
    """Every file under root as a set of root-relative paths.

    The inventory is the restore's completeness contract: what the archive
    carried is exactly what the restored tree must contain, file for file.
    """
    base = Path(root)
    if not base.is_dir():
        raise RestoreError(f"store root {base} is not a directory")
    return {path.relative_to(base) for path in base.rglob("*") if path.is_file()}


def verify_restored(
    restored_root: Path, *, expected_inventory: set[Path] | None = None
) -> dict[str, Any]:
    """Run verify_store from observation_gates over the restored root.

    Returns its counts plus:

      - "verified": True only when corrupt, unreadable and misnamed are all
        zero, no envelope is unreadable, and there are no dangling references.
        An envelope the verifier cannot parse is one whose references it
        cannot check, so a restored store that cannot be checked must not
        verify — an unreadable envelope is kept by cleanup AND fails the
        verdict;
      - "matches_source": the comparison against expected_inventory when one is
        supplied, naming any path present in one and absent from the other.

    A mismatch is a failure to report, never something to repair: nothing in
    this function writes, rewrites or removes stored bytes.
    """
    root = Path(restored_root)
    if not root.is_dir():
        raise RestoreError(f"restored store root {root} is not a directory")
    report = verify_store(root=root)
    counts = report["counts"]
    verified = (
        counts["corrupt"] == 0
        and counts["unreadable"] == 0
        and counts["misnamed"] == 0
        and counts["envelopes_unreadable"] == 0
        and counts["dangling_references"] == 0
    )
    result: dict[str, Any] = {
        "counts": counts,
        "failures": report["failures"],
        "dangling_references": report["dangling_references"],
        "verified": verified,
        "matches_source": None,
    }
    if expected_inventory is not None:
        restored_paths = {path.as_posix() for path in store_inventory(root)}
        expected_paths = {Path(path).as_posix() for path in expected_inventory}
        missing_from_restored = sorted(expected_paths - restored_paths)
        unexpected_in_restored = sorted(restored_paths - expected_paths)
        result["matches_source"] = {
            "matches": not missing_from_restored and not unexpected_in_restored,
            "missing_from_restored": missing_from_restored,
            "unexpected_in_restored": unexpected_in_restored,
        }
    return result


def round_trip(source_root: Path, *, workdir: Path) -> dict[str, Any]:
    """Archive, restore into a fresh directory under workdir, DELETE the source
    tree, and only then verify.

    The deletion before verification is the point of the exercise: verification
    must not depend on the original bytes still being present. Returns the report
    with the archive path, the restored root and the verification result.
    """
    source = _require_absolute(Path(source_root), "source_root")
    work = _require_absolute(Path(workdir), "workdir")
    if not source.is_dir():
        raise RestoreError(f"source store {source} is not a directory")
    work.mkdir(parents=True, exist_ok=True)
    expected_inventory = store_inventory(source)
    archive_path = archive_store(source, work / f"{source.name}.tar")
    restore_destination = Path(tempfile.mkdtemp(prefix=f"restore-{source.name}-", dir=work))
    restored_root = restore_store(archive_path, restore_destination)
    shutil.rmtree(source)
    verification = verify_restored(restored_root, expected_inventory=expected_inventory)
    return {
        "archive": str(archive_path),
        "restored_root": str(restored_root),
        "verification": verification,
        "source_deleted": not source.exists(),
    }


def _print_report(archive: Path, report: dict[str, Any]) -> None:
    """Human-readable operator output; details are dumped only when they name failures."""
    counts = report["counts"]
    print(f"archive: {archive}")
    print(
        f"objects: {counts['ok']} ok, {counts['corrupt']} corrupt, "
        f"{counts['unreadable']} unreadable, {counts['misnamed']} misnamed "
        f"(total {counts['total_objects']})"
    )
    print(
        f"envelopes: {counts['envelopes']} ({counts['envelopes_unreadable']} unreadable), "
        f"dangling references: {counts['dangling_references']}"
    )
    if report["verified"]:
        print("verified: True")
        return
    print("verified: False")
    print(
        json.dumps(
            {"failures": report["failures"], "dangling_references": report["dangling_references"]},
            indent=2,
            sort_keys=True,
        )
    )


def main(argv: list[str] | None = None) -> int:
    """CLI entry point.

    `python3 scripts/verify_observation_restore.py --archive <path>` restores an
    existing archive into a temporary directory and prints the verification
    report, exiting non-zero when verification fails. Exit codes: 0 verified,
    1 verification failed, 2 the archive could not be restored at all.
    """
    parser = argparse.ArgumentParser(
        description="Restore an observation-store archive into a temporary directory and verify it.",
    )
    parser.add_argument("--archive", required=True, type=Path, help="Path to the tar archive to restore.")
    args = parser.parse_args(argv)
    archive = args.archive
    if not archive.is_file():
        print(f"error: archive {archive} does not exist or is not a file", file=sys.stderr)
        return 2
    with tempfile.TemporaryDirectory(prefix="verify-observation-restore-") as temporary:
        try:
            restored_root = restore_store(archive, Path(temporary) / "restored")
        except RestoreError as error:
            print(f"error: {error}", file=sys.stderr)
            return 2
        report = verify_restored(restored_root)
    _print_report(archive, report)
    return 0 if report["verified"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
