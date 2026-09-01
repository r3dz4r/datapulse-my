#!/usr/bin/env python3
"""Verify deterministic, untampered family as-of health snapshots."""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import shutil
import tempfile
from datetime import date
from pathlib import Path
from typing import Any

from gen_as_of import FAMILIES, _canonical_date, generate


ROOT = Path(__file__).resolve().parents[1]
LOGGER = logging.getLogger(__name__)


class VerificationError(Exception):
    """Raised when an as-of directory fails an integrity invariant."""


def _sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise VerificationError(f"invalid JSON file {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise VerificationError(f"{path} must contain a JSON object")
    return value


def _dataset_files(directory: Path) -> list[Path]:
    return sorted(path for path in directory.glob("*.json") if path.name != "_manifest.json")


def _expected_ids(root: Path, family: str) -> list[str]:
    manifest = _read_json(root / "datapulse.json")
    datasets = manifest.get("datasets")
    if not isinstance(datasets, list):
        raise VerificationError("datapulse.json must contain a datasets array")
    matcher = FAMILIES[family]["match"]
    return sorted(row["id"] for row in datasets if isinstance(row, dict) and isinstance(row.get("id"), str) and matcher(row))


def _first_difference(actual: Path, regenerated: Path) -> str | None:
    actual_files = {path.name: path for path in actual.glob("*.json")}
    regenerated_files = {path.name: path for path in regenerated.glob("*.json")}
    for name in sorted(set(actual_files) | set(regenerated_files), key=lambda item: (item == "_manifest.json", item)):
        if name not in actual_files:
            return f"regenerated file missing on disk: {name}"
        if name not in regenerated_files:
            return f"unexpected on-disk file: {name}"
        left, right = actual_files[name].read_bytes(), regenerated_files[name].read_bytes()
        if left != right:
            index = min(len(left), len(right))
            for index, (a, b) in enumerate(zip(left, right)):
                if a != b:
                    break
            return f"{name} differs at byte {index} (on-disk sha256 {_sha256(left)}, regenerated sha256 {_sha256(right)})"
    return None


def verify_directory(root: Path, directory: Path, family: str, date_text: str) -> None:
    manifest_path = directory / "_manifest.json"
    manifest = _read_json(manifest_path)
    files = _dataset_files(directory)
    actual_ids = [path.stem for path in files]
    expected_ids = _expected_ids(root, family)
    missing = sorted(set(expected_ids) - set(actual_ids))
    if missing:
        raise VerificationError(f"missing dataset file for expected dataset ID: {missing[0]}")
    if manifest.get("actual_dataset_count") != len(files):
        raise VerificationError(f"actual_dataset_count mismatch: manifest {manifest.get('actual_dataset_count')}, files {len(files)}")
    if len(files) != len(expected_ids):
        raise VerificationError(f"dataset file count mismatch: expected {len(expected_ids)}, found {len(files)}")
    digest = _sha256("".join(_sha256(path.read_bytes()) for path in files).encode("ascii"))
    digest_mismatch = manifest.get("manifest_sha256") != digest
    temporary_root = Path(tempfile.mkdtemp(prefix="as-of-verify-"))
    try:
        regenerated = generate(root, family, date_text, temporary_root)
        difference = _first_difference(directory, regenerated)
        if difference is not None:
            prefix = ""
            if digest_mismatch:
                prefix = f"manifest_sha256 mismatch in {manifest_path}: expected {manifest.get('manifest_sha256')}, actual {digest}; "
            raise VerificationError(prefix + f"regenerated view differs: {difference}")
        if digest_mismatch:
            raise VerificationError(f"manifest_sha256 mismatch in {manifest_path}: expected {manifest.get('manifest_sha256')}, actual {digest}")
    finally:
        shutil.rmtree(temporary_root)


def _directories(root: Path, family: str | None, date_text: str | None) -> list[tuple[Path, str, str]]:
    base = root / "health/as_of"
    families = [family] if family else sorted(path.name for path in base.iterdir() if path.is_dir()) if base.exists() else []
    selected: list[tuple[Path, str, str]] = []
    for name in families:
        if name not in FAMILIES:
            raise ValueError(f"unknown family: {name}")
        dates = [date_text] if date_text else sorted(path.name for path in (base / name).iterdir() if path.is_dir()) if (base / name).exists() else []
        for value in dates:
            if value is None:
                continue
            _canonical_date(value)
            selected.append((base / name / value, name, value))
    if not selected:
        raise ValueError("no as-of directories selected")
    return selected


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--family")
    parser.add_argument("--date")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        if args.family is not None and args.family not in FAMILIES:
            raise ValueError(f"unknown family: {args.family}")
        if args.date is not None:
            _canonical_date(args.date)
        directories = _directories(args.root.resolve(), args.family, args.date)
    except ValueError as exc:
        LOGGER.error("operator error: %s", exc)
        return 2
    for directory, family, date_text in directories:
        try:
            verify_directory(args.root.resolve(), directory, family, date_text)
        except (OSError, UnicodeError, ValueError, VerificationError) as exc:
            LOGGER.error("as-of verification failed for %s: %s", directory, exc)
            return 1
    LOGGER.info("verified %d deterministic as-of director%s", len(directories), "y" if len(directories) == 1 else "ies")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
