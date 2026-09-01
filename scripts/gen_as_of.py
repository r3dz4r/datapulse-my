#!/usr/bin/env python3
"""Generate a deterministic per-family health view as known on a given date."""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import shutil
import subprocess
from datetime import date, datetime
from pathlib import Path
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[1]
LOGGER = logging.getLogger(__name__)
FamilyMatcher = Callable[[dict[str, Any]], bool]

FAMILIES: dict[str, dict[str, Any]] = {
    "bnm_open_api": {
        "display_name": "BNM Open API (apikijangportal.bnm.gov.my)",
        "match": lambda r: r.get("source") == "BNM Open API (apikijangportal.bnm.gov.my)",
        "expected_count": 8,
    },
    "gtfs_api": {
        "display_name": "data.gov.my (GTFS API)",
        "match": lambda r: r.get("source") == "data.gov.my (GTFS API)",
        "expected_count": 30,
    },
}


def _canonical_date(value: str) -> date:
    try:
        parsed = date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError("--date must be YYYY-MM-DD") from exc
    if parsed.isoformat() != value:
        raise ValueError("--date must be YYYY-MM-DD")
    return parsed


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must be a JSON object")
    return value


def _timestamp_date(value: object) -> date | None:
    if not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).date()
    except ValueError:
        return None


def _history_as_of(history_path: Path, as_of: date) -> dict[str, dict[str, Any]]:
    latest: dict[str, tuple[datetime, dict[str, Any]]] = {}
    for raw_line in history_path.read_text(encoding="utf-8").splitlines():
        try:
            row = json.loads(raw_line)
        except json.JSONDecodeError:
            continue
        if not isinstance(row, dict) or not isinstance(row.get("dataset_id"), str):
            continue
        observed_at = row.get("observed_at")
        if _timestamp_date(observed_at) is None or _timestamp_date(observed_at) > as_of:
            continue
        try:
            parsed = datetime.fromisoformat(observed_at.replace("Z", "+00:00"))
        except ValueError:
            continue
        prior = latest.get(row["dataset_id"])
        if prior is None or parsed > prior[0]:
            latest[row["dataset_id"]] = (parsed, row)
    return {dataset_id: row for dataset_id, (_, row) in latest.items()}


def _json_bytes(value: dict[str, Any]) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


def _sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _source_commit_sha(root: Path) -> str:
    result = subprocess.run(
        ["git", "-C", str(root), "rev-parse", "HEAD"], text=True, capture_output=True, check=False
    )
    if result.returncode != 0:
        raise ValueError(f"could not resolve source commit SHA for {root}")
    return result.stdout.strip()


def _replace_directory(temporary: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    backup: Path | None = None
    if target.exists():
        backup = target.with_name(f".{target.name}.previous")
        if backup.exists():
            shutil.rmtree(backup)
        os.rename(target, backup)
    try:
        os.rename(temporary, target)
    except BaseException:
        if backup is not None and backup.exists():
            os.rename(backup, target)
        raise
    if backup is not None:
        shutil.rmtree(backup)


def generate(root: Path, family: str, date_text: str, output_root: Path | None = None) -> Path:
    if family not in FAMILIES:
        raise ValueError(f"unknown family: {family}")
    as_of = _canonical_date(date_text)
    manifest = _read_json(root / "datapulse.json")
    latest = _read_json(root / "health/latest.json")
    checked_at = _timestamp_date(latest.get("checked_at"))
    if checked_at is None:
        raise ValueError("health/latest.json checked_at must be an ISO-8601 timestamp")
    if as_of > checked_at:
        raise ValueError(f"future as-of date {date_text} is later than health/latest.json checked_at")
    datasets = manifest.get("datasets")
    if not isinstance(datasets, list):
        raise ValueError("datapulse.json must contain a datasets array")
    config = FAMILIES[family]
    matcher: FamilyMatcher = config["match"]
    dataset_ids = sorted(row["id"] for row in datasets if isinstance(row, dict) and isinstance(row.get("id"), str) and matcher(row))
    if len(dataset_ids) != config["expected_count"]:
        raise ValueError(f"{family} expected {config['expected_count']} datasets, found {len(dataset_ids)}")
    history = _history_as_of(root / "health/history.jsonl", as_of)
    artifact_root = output_root if output_root is not None else root
    target = artifact_root / "health/as_of" / family / date_text
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(f"{target.name}.tmp")
    if temporary.exists():
        shutil.rmtree(temporary)
    temporary.mkdir()
    missing: list[str] = []
    file_hashes: list[str] = []
    try:
        for dataset_id in dataset_ids:
            row = history.get(dataset_id)
            if row is None:
                missing.append(dataset_id)
                row = {"_as_of_date": date_text, "dataset_id": dataset_id, "family": family, "observed_at": None, "reason": "no_observation_on_or_before_date", "source_published_at": None}
            else:
                row = dict(row)
                row["_as_of_date"] = date_text
            content = _json_bytes(row)
            (temporary / f"{dataset_id}.json").write_bytes(content)
            file_hashes.append(_sha256(content))
        view_manifest = {
            "family": family,
            "family_display_name": config["display_name"],
            "as_of_date": date_text,
            "expected_dataset_count": config["expected_count"],
            "actual_dataset_count": len(dataset_ids),
            "missing_history_dataset_ids": missing,
            "source_commit_sha": _source_commit_sha(root),
            "source_history_path": "health/history.jsonl",
            "manifest_sha256": _sha256("".join(file_hashes).encode("ascii")),
        }
        (temporary / "_manifest.json").write_bytes(_json_bytes(view_manifest))
        _replace_directory(temporary, target)
    except BaseException:
        if temporary.exists():
            shutil.rmtree(temporary)
        raise
    return target


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--family", required=True, choices=sorted(FAMILIES))
    parser.add_argument("--date", required=True)
    parser.add_argument("--root", type=Path, default=ROOT, help=argparse.SUPPRESS)
    parser.add_argument("--output-root", type=Path, help=argparse.SUPPRESS)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        target = generate(args.root.resolve(), args.family, args.date, args.output_root.resolve() if args.output_root else None)
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
        LOGGER.error("as-of generation failed: %s", exc)
        return 1
    LOGGER.info("generated deterministic as-of view at %s", target)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
