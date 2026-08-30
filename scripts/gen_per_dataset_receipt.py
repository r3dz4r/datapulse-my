#!/usr/bin/env python3
"""Generate deterministic per-dataset evidence blobs and in-toto statements."""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
from pathlib import Path
from typing import Any

if __package__:
    from scripts.gen_sigstore_bundle import STATEMENT_TYPE, StatementError, atomic_write, statement_bytes
else:
    from gen_sigstore_bundle import STATEMENT_TYPE, StatementError, atomic_write, statement_bytes  # type: ignore[no-redef]


LOGGER = logging.getLogger(__name__)
ROOT = Path(__file__).resolve().parents[1]
HEALTH_SCHEMA = "datapulse/v0.4/dataset-health"
PREDICATE_TYPE = "https://www.data-pulse.my/predicates/per-dataset-evidence/v1"
PREDICATE_SCHEMA = "datapulse/v1/per-dataset-evidence"
QUICK_TEST_IDS = frozenset({"fuelprice", "cpi_3d", "dosm_lfs_month"})  # cpi was split into cpi_3d/4d/5d/core/headline/state in the current manifest
EVIDENCE_FIELDS = (
    "dataset_id", "last_checked", "status", "message", "request_url", "access_method",
    "http_status", "content_length", "last_modified", "content_freshness_date",
    "first_record_timestamp", "record_count", "record_count_within_tolerance",
    "freshness_signal", "freshness_signal_source",
)


def _load_object(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise StatementError(f"{label} is not readable JSON: {path}") from exc
    if not isinstance(value, dict):
        raise StatementError(f"{label} must be a JSON object: {path}")
    return value


def _validated_inputs(health_path: Path, manifest_path: Path) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]]]:
    health = _load_object(health_path, "health snapshot")
    if health.get("schema") != HEALTH_SCHEMA:
        raise StatementError(f"health schema must be {HEALTH_SCHEMA}")
    rows = health.get("datasets")
    if not isinstance(rows, list) or not rows or not all(isinstance(row, dict) for row in rows):
        raise StatementError("health datasets must be a non-empty array of objects")
    manifest = _load_object(manifest_path, "manifest")
    entries = manifest.get("datasets")
    if not isinstance(entries, list) or not entries or not all(isinstance(entry, dict) for entry in entries):
        raise StatementError("manifest datasets must be a non-empty array of objects")
    by_id: dict[str, dict[str, Any]] = {}
    for entry in entries:
        identifier = entry.get("id")
        if not isinstance(identifier, str) or not identifier or identifier in by_id:
            raise StatementError("manifest datasets must have unique id strings")
        if not isinstance(entry.get("licence"), str) or not entry["licence"]:
            raise StatementError(f"manifest dataset {identifier} must have a licence")
        by_id[identifier] = entry
    identifiers: set[str] = set()
    for row in rows:
        identifier = row.get("dataset_id")
        if not isinstance(identifier, str) or not identifier or identifier in identifiers:
            raise StatementError("health datasets must have unique dataset_id strings")
        if identifier not in by_id:
            raise StatementError(f"health dataset {identifier} is absent from the manifest")
        identifiers.add(identifier)
        for field in EVIDENCE_FIELDS:
            if field not in row:
                raise StatementError(f"health dataset {identifier} is missing {field}")
    if identifiers != set(by_id):
        raise StatementError("manifest and health dataset identities must match")
    return rows, by_id


def canonical_evidence_row(row: dict[str, Any], manifest_entry: dict[str, Any]) -> dict[str, Any]:
    """Return the exact public trust-plane row bound by a dataset receipt."""
    return {**{field: row[field] for field in EVIDENCE_FIELDS}, "licence": manifest_entry["licence"]}


def generate_statement(dataset_id: str, evidence: dict[str, Any]) -> dict[str, Any]:
    """Build the statement whose subject is the canonical evidence row bytes."""
    digest = hashlib.sha256(statement_bytes(evidence)).hexdigest()
    return {
        "_type": STATEMENT_TYPE,
        "subject": [{
            "name": f"data/{dataset_id}.receipt.evidence.json",
            "digest": {"sha256": digest},
        }],
        "predicateType": PREDICATE_TYPE,
        "predicate": {"schema": PREDICATE_SCHEMA, "health": evidence},
    }


def generate_receipts(health_path: Path, manifest_path: Path, data_dir: Path, *, quick_test: bool = False) -> list[str]:
    """Write deterministic evidence blobs/statements and return generated identifiers."""
    rows, manifest_by_id = _validated_inputs(health_path, manifest_path)
    selected = [row for row in rows if not quick_test or row["dataset_id"] in QUICK_TEST_IDS]
    if quick_test and {row["dataset_id"] for row in selected} != QUICK_TEST_IDS:
        raise StatementError("quick-test requires fuelprice, cpi, and dosm_lfs_month")
    identifiers: list[str] = []
    for row in sorted(selected, key=lambda item: item["dataset_id"]):
        identifier = row["dataset_id"]
        evidence = canonical_evidence_row(row, manifest_by_id[identifier])
        atomic_write(data_dir / f"{identifier}.receipt.evidence.json", statement_bytes(evidence))
        atomic_write(data_dir / f"{identifier}.receipt.statement.json", statement_bytes(generate_statement(identifier, evidence)))
        identifiers.append(identifier)
    return identifiers


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--health", type=Path, default=ROOT / "health/latest.json")
    parser.add_argument("--manifest", type=Path, default=ROOT / "datapulse.json")
    parser.add_argument("--data-dir", type=Path, default=ROOT / "data")
    parser.add_argument("--quick-test", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    try:
        identifiers = generate_receipts(args.health, args.manifest, args.data_dir, quick_test=args.quick_test)
    except (OSError, StatementError, ValueError) as exc:
        raise SystemExit(f"Per-dataset receipt generation failed: {exc}") from exc
    print(f"Generated {len(identifiers)} per-dataset receipts ({identifiers[0]} … {identifiers[-1]}).")


if __name__ == "__main__":
    main()
