#!/usr/bin/env python3
"""Generate a deterministic in-toto statement for the canonical health snapshot."""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import re
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any

LOGGER = logging.getLogger(__name__)
ROOT = Path(__file__).resolve().parents[1]
STATEMENT_TYPE = "https://in-toto.io/Statement/v1"
PREDICATE_TYPE = "https://www.data-pulse.my/predicates/health-snapshot/v1"
PREDICATE_SCHEMA = "datapulse/v1/health-snapshot-attestation"
HEALTH_SCHEMA = "datapulse/v0.4/dataset-health"
LEGACY_CHAIN_SCHEMA = "datapulse/v1/daily-chain-head-envelope"
SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
COMMIT_PATTERN = re.compile(r"^[0-9a-f]{40}(?:[0-9a-f]{24})?$")


class StatementError(ValueError):
    """Raised when statement inputs cannot form an honest deterministic claim."""


def _decode_object(content: bytes, path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(content.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise StatementError(f"{label} is not readable JSON: {path}") from exc
    if not isinstance(value, dict):
        raise StatementError(f"{label} must be a JSON object: {path}")
    return value


def _load_object(path: Path, label: str) -> dict[str, Any]:
    try:
        content = path.read_bytes()
    except OSError as exc:
        raise StatementError(f"{label} is not readable JSON: {path}") from exc
    return _decode_object(content, path, label)


def _checked_at(value: object) -> str:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise StatementError("health checked_at must be a UTC timestamp ending in Z")
    try:
        datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as exc:
        raise StatementError("health checked_at must be an ISO 8601 UTC timestamp") from exc
    return value


def _health_rows(health: dict[str, Any]) -> list[dict[str, Any]]:
    if health.get("schema") != HEALTH_SCHEMA:
        raise StatementError(f"health schema must be {HEALTH_SCHEMA}")
    _checked_at(health.get("checked_at"))
    if not isinstance(health.get("_trust_summary"), dict):
        raise StatementError("health _trust_summary must be an object")
    rows = health.get("datasets")
    if not isinstance(rows, list) or not rows:
        raise StatementError("health datasets must be a non-empty array")
    if not all(isinstance(row, dict) for row in rows):
        raise StatementError("health datasets entries must be objects")
    identifiers = [row.get("dataset_id") for row in rows]
    if not all(isinstance(identifier, str) and identifier for identifier in identifiers):
        raise StatementError("health datasets entries must have dataset_id strings")
    if len(set(identifiers)) != len(identifiers):
        raise StatementError("health datasets must have unique dataset_id values")
    return rows


def _methodology_version(
    manifest: dict[str, Any], health_rows: list[dict[str, Any]]
) -> int:
    entries = manifest.get("datasets")
    if not isinstance(entries, list) or not entries:
        raise StatementError("manifest datasets must be a non-empty array")
    if not all(isinstance(entry, dict) for entry in entries):
        raise StatementError("manifest datasets entries must be objects")
    identifiers = [entry.get("id") for entry in entries]
    if not all(isinstance(identifier, str) and identifier for identifier in identifiers):
        raise StatementError("manifest datasets entries must have id strings")
    health_identifiers = {row["dataset_id"] for row in health_rows}
    if set(identifiers) != health_identifiers or len(identifiers) != len(health_rows):
        raise StatementError("manifest and health dataset identities must match")
    versions = [entry.get("methodology_version") for entry in entries]
    if not all(
        isinstance(version, int) and not isinstance(version, bool) and version > 0
        for version in versions
    ) or len(set(versions)) != 1:
        raise StatementError("manifest methodology_version must be one shared positive integer")
    return int(versions[0])


def _legacy_chain_head(chain: dict[str, Any], dataset_count: int) -> str:
    if chain.get("schema") != LEGACY_CHAIN_SCHEMA:
        raise StatementError(f"legacy chain schema must be {LEGACY_CHAIN_SCHEMA}")
    digest = chain.get("chain_head")
    if not isinstance(digest, str) or SHA256_PATTERN.fullmatch(digest) is None:
        raise StatementError("legacy chain_head must be a lowercase SHA-256 digest")
    payload = chain.get("payload")
    if not isinstance(payload, dict) or payload.get("dataset_count") != dataset_count:
        raise StatementError("legacy chain dataset_count must match canonical health")
    return digest


def generate_statement(
    health_path: Path,
    manifest_path: Path,
    chain_head_path: Path,
    source_commit: str,
) -> dict[str, Any]:
    """Build an in-toto Statement whose subject is the exact health file bytes."""
    if COMMIT_PATTERN.fullmatch(source_commit) is None:
        raise StatementError("source commit must be a lowercase 40- or 64-character hex digest")
    try:
        health_bytes = health_path.read_bytes()
    except OSError as exc:
        raise StatementError(f"health snapshot is not readable: {health_path}") from exc
    health = _decode_object(health_bytes, health_path, "health snapshot")
    manifest = _load_object(manifest_path, "manifest")
    chain = _load_object(chain_head_path, "legacy chain head")
    rows = _health_rows(health)
    methodology_version = _methodology_version(manifest, rows)
    chain_digest = _legacy_chain_head(chain, len(rows))
    return {
        "_type": STATEMENT_TYPE,
        "subject": [
            {
                "name": "health/latest.json",
                "digest": {"sha256": hashlib.sha256(health_bytes).hexdigest()},
            }
        ],
        "predicateType": PREDICATE_TYPE,
        "predicate": {
            "schema": PREDICATE_SCHEMA,
            "datasetCount": len(rows),
            "healthCheckedAt": health["checked_at"],
            "sourceCommit": source_commit,
            "methodologyVersion": methodology_version,
            "legacyEd25519": {
                "chainHeadRef": ".attestations/chain_head.json",
                "chainHead": chain_digest,
            },
        },
    }


def statement_bytes(statement: dict[str, Any]) -> bytes:
    """Serialize a statement canonically for stable DSSE payload bytes."""
    return (
        json.dumps(statement, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + "\n"
    ).encode("utf-8")


def atomic_write(path: Path, content: bytes) -> None:
    """Atomically replace a generated statement."""
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(descriptor, "wb") as temporary:
            temporary.write(content)
            temporary.flush()
            os.fsync(temporary.fileno())
        os.replace(temporary_name, path)
    except BaseException:
        try:
            os.unlink(temporary_name)
        except FileNotFoundError:
            pass
        raise


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--health", type=Path, default=ROOT / "health/latest.json")
    parser.add_argument("--manifest", type=Path, default=ROOT / "datapulse.json")
    parser.add_argument(
        "--legacy-chain-head",
        type=Path,
        default=ROOT / ".attestations/chain_head.json",
    )
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--out", type=Path, required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    try:
        rendered = statement_bytes(
            generate_statement(
                args.health,
                args.manifest,
                args.legacy_chain_head,
                args.source_commit,
            )
        )
        atomic_write(args.out, rendered)
    except (OSError, StatementError) as exc:
        raise SystemExit(f"Sigstore statement generation failed: {exc}") from exc
    LOGGER.info("Generated deterministic health attestation statement at %s", args.out)


if __name__ == "__main__":
    main()
