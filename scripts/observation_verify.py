#!/usr/bin/env python3
"""Offline verifier for host-side observation receipts.

Verification is deliberately local: the payload hash, the Ed25519 signature,
the registry validity window, and the receipt identity are all recomputed from
files on disk. No network call is made and no private key is needed or read.

A third party holds only the receipt and the trust anchor (the public key
registry), so the registry is mandatory and no path inside this repository is
assumed. Chain linkage is opportunistic: a chain head supplied with
``--chain-head`` or found next to the receipt (its directory or its parent) is
enforced, otherwise the run reports linkage as ``unchecked`` and still exits 0
when the primary checks pass. Every failure names its exact reason; the CLI
exits 0 on success and 1 on failure with each reason on stderr.
"""

from __future__ import annotations

import argparse
import base64
import json
import logging
import sys
from pathlib import Path
from typing import Any

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

if __package__:
    from scripts.observation_receipt import (
        RECEIPT_SCHEMA,
        ObservationReceiptError,
        canonical_bytes,
        parse_time,
        sha256_hex,
    )
else:
    from observation_receipt import (  # type: ignore[no-redef]
        RECEIPT_SCHEMA,
        ObservationReceiptError,
        canonical_bytes,
        parse_time,
        sha256_hex,
    )

LOGGER = logging.getLogger(__name__)

CHAIN_HEAD_FILENAME: str = "chain_head.json"

REQUIRED_PAYLOAD_FIELDS: tuple[str, ...] = (
    "schema",
    "observed_at",
    "cycle_date",
    "health_artifact_sha256",
    "dataset_count",
    "freshness_status_counts",
    "verification_profile_version",
    "policy_version",
    "key_id",
    "sequence_number",
    "previous_receipt_id",
    "valid_until",
    "limitations",
)


class ObservationVerificationError(Exception):
    """Raised when a verification input cannot be read at all."""


def load_json(path: Path, label: str) -> dict[str, Any]:
    """Read a JSON object for verification, naming unreadable inputs exactly."""
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except OSError as error:
        raise ObservationVerificationError(f"{label}_unreadable: {path}: {error}") from error
    except json.JSONDecodeError as error:
        raise ObservationVerificationError(f"{label}_malformed: {path} is not valid JSON: {error}") from error
    if not isinstance(document, dict):
        raise ObservationVerificationError(f"{label}_malformed: {path} must contain a JSON object")
    return document


def _is_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _structure_failures(receipt: dict[str, Any]) -> tuple[list[str], dict[str, Any] | None]:
    """Check the receipt envelope and required payload fields."""
    failures: list[str] = []
    payload = receipt.get("payload")
    if not isinstance(payload, dict):
        return ["receipt_malformed: receipt.payload must be a JSON object"], None
    if not isinstance(receipt.get("receipt_id"), str) or not receipt["receipt_id"]:
        failures.append("receipt_malformed: receipt.receipt_id must be a non-empty string")
    if not isinstance(receipt.get("signature_base64"), str) or not receipt["signature_base64"]:
        failures.append("receipt_malformed: receipt.signature_base64 must be a non-empty string")
    for name in REQUIRED_PAYLOAD_FIELDS:
        if name not in payload:
            failures.append(f"payload_missing_field: {name}")
    if payload.get("schema") != RECEIPT_SCHEMA:
        failures.append(f"payload_schema_mismatch: expected {RECEIPT_SCHEMA!r}, got {payload.get('schema')!r}")
    if not _is_int(payload.get("dataset_count")):
        failures.append("payload_field_type_invalid: dataset_count must be an integer")
    if not _is_int(payload.get("sequence_number")) or payload.get("sequence_number", 0) < 1:
        failures.append("payload_field_type_invalid: sequence_number must be a positive integer")
    if not isinstance(payload.get("freshness_status_counts"), dict):
        failures.append("payload_field_type_invalid: freshness_status_counts must be an object")
    if not isinstance(payload.get("limitations"), list):
        failures.append("payload_field_type_invalid: limitations must be an array")
    if payload.get("key_id") is not None and not isinstance(payload.get("key_id"), str):
        failures.append("payload_field_type_invalid: key_id must be a string")
    if payload.get("previous_receipt_id") is not None and not isinstance(payload.get("previous_receipt_id"), str):
        failures.append("payload_field_type_invalid: previous_receipt_id must be a string or null")
    return failures, payload


def _registry_failures(payload: dict[str, Any], registry: dict[str, Any]) -> tuple[list[str], dict[str, Any] | None]:
    """Find the key row and enforce status active plus the validity window."""
    failures: list[str] = []
    key_id = payload.get("key_id")
    rows = registry.get("keys")
    if not isinstance(rows, list):
        return ["registry_malformed: registry keys must be an array"], None
    matches = [row for row in rows if isinstance(row, dict) and row.get("key_id") == key_id]
    if len(matches) != 1:
        return [f"key_id_not_in_registry: expected exactly one row for {key_id!r}, found {len(matches)}"], None
    row = matches[0]
    if row.get("status") != "active":
        failures.append(f"key_not_active: registry status is {row.get('status')!r}")
    try:
        observed_at = parse_time(payload.get("observed_at"), label="observed_at")
        not_before = parse_time(row.get("not_before"), label="key_not_before")
        not_after = parse_time(row.get("not_after"), label="key_not_after")
    except ObservationReceiptError as error:
        failures.append(f"validity_window_unreadable: {error}")
        return failures, row
    if observed_at < not_before:
        failures.append(f"key_not_yet_valid: observed_at {payload.get('observed_at')} precedes not_before {row.get('not_before')}")
    if observed_at > not_after:
        failures.append(f"key_expired: observed_at {payload.get('observed_at')} follows not_after {row.get('not_after')}")
    return failures, row


def _signature_failures(receipt: dict[str, Any], payload: dict[str, Any], row: dict[str, Any]) -> list[str]:
    """Recompute the payload hash and verify the Ed25519 signature."""
    failures: list[str] = []
    canonical = canonical_bytes(payload)
    expected_receipt_id = sha256_hex(canonical)
    declared_receipt_id = receipt.get("receipt_id")
    if declared_receipt_id != expected_receipt_id:
        failures.append(
            f"receipt_id_mismatch: declared {declared_receipt_id!r} does not match canonical payload hash {expected_receipt_id}"
        )
    public_b64 = row.get("public_key_base64")
    signature_b64 = receipt.get("signature_base64")
    try:
        public_key = Ed25519PublicKey.from_public_bytes(base64.b64decode(public_b64 or "", validate=True))
        signature = base64.b64decode(signature_b64 or "", validate=True)
    except (ValueError, TypeError) as error:
        failures.append(f"signature_malformed: public key or signature is not valid base64 Ed25519: {error}")
        return failures
    try:
        public_key.verify(signature, canonical)
    except InvalidSignature:
        failures.append("signature_invalid: Ed25519 signature does not verify over the canonical payload")
    return failures


def _chain_failures(payload: dict[str, Any], chain_head: dict[str, Any]) -> list[str]:
    """Require the receipt's previous_receipt_id to match the chain head's prior receipt."""
    if "previous_receipt_id" not in chain_head:
        return ["chain_head_malformed: chain head is missing previous_receipt_id"]
    head_previous = chain_head.get("previous_receipt_id")
    if payload.get("previous_receipt_id") != head_previous:
        return [
            "previous_receipt_mismatch: receipt declares previous_receipt_id="
            f"{payload.get('previous_receipt_id')!r} but chain head records {head_previous!r}"
        ]
    return []


def find_adjacent_chain_head(receipt_path: Path) -> Path | None:
    """Return a chain head sitting next to the receipt, or ``None`` when absent.

    Resolution is relative to the receipt, never to this repository: the
    receipt's own directory first, then its parent. That finds a
    signer-produced tree (``<root>/receipts/<date>.json`` plus
    ``<root>/chain_head.json``) and still finds nothing when a third party
    holds only the receipt.
    """
    candidates = (receipt_path.parent / CHAIN_HEAD_FILENAME, receipt_path.parent.parent / CHAIN_HEAD_FILENAME)
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    return None


def checked_facts(
    receipt: dict[str, Any],
    registry: dict[str, Any],
    chain_head: dict[str, Any] | None,
) -> dict[str, Any]:
    """Return the public facts the verifier actually used, for its evidence report.

    Only public material appears here: the declared receipt id, the payload's
    key_id, the registry's public validity window, and whether linkage was
    checked. No key bytes are read or reported.
    """
    payload = receipt.get("payload")
    if not isinstance(payload, dict):
        payload = {}
    key_id = payload.get("key_id")
    row: dict[str, Any] | None = None
    rows = registry.get("keys")
    if isinstance(rows, list) and isinstance(key_id, str):
        matches = [candidate for candidate in rows if isinstance(candidate, dict) and candidate.get("key_id") == key_id]
        if len(matches) == 1:
            row = matches[0]
    return {
        "receipt_id": receipt.get("receipt_id"),
        "key_id": key_id,
        "key_status": row.get("status") if row is not None else None,
        "key_not_before": row.get("not_before") if row is not None else None,
        "key_not_after": row.get("not_after") if row is not None else None,
        "observed_at": payload.get("observed_at"),
        "linkage": "checked" if chain_head is not None else "unchecked",
    }


def print_checked_facts(facts: dict[str, Any]) -> None:
    """Print the verification evidence lines to stdout."""
    print(f"  receipt_id: {facts['receipt_id']}")
    print(f"  key_id: {facts['key_id']}")
    print(
        f"  key_window: status={facts['key_status']} "
        f"not_before={facts['key_not_before']} not_after={facts['key_not_after']}"
    )
    print(f"  observed_at: {facts['observed_at']}")
    print(f"  linkage: {facts['linkage']}")


def verify_receipt(
    receipt: dict[str, Any],
    *,
    registry: dict[str, Any],
    chain_head: dict[str, Any] | None = None,
) -> list[str]:
    """Return every verification failure; an empty list means the receipt is valid.

    The primary checks always run. Chain linkage runs only when a chain head is
    available; when ``chain_head`` is ``None`` linkage is deliberately left
    unchecked rather than reported as passing.
    """
    failures, payload = _structure_failures(receipt)
    if payload is None:
        return failures
    if failures:
        # The payload identity cannot be trusted, so stop before comparing it.
        return failures
    registry_problems, row = _registry_failures(payload, registry)
    failures.extend(registry_problems)
    if row is None:
        return failures
    failures.extend(_signature_failures(receipt, payload, row))
    if chain_head is not None:
        failures.extend(_chain_failures(payload, chain_head))
    return failures


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Verify a host-side observation receipt entirely offline.")
    parser.add_argument("--receipt", type=Path, required=True, help="Receipt JSON to verify.")
    parser.add_argument(
        "--registry",
        type=Path,
        required=True,
        help="Key registry with public keys and validity windows (the trust anchor; no default).",
    )
    parser.add_argument(
        "--chain-head",
        type=Path,
        default=None,
        help="Chain head that records the prior receipt. Defaults to a chain_head.json next to the receipt.",
    )
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    try:
        receipt = load_json(args.receipt, "receipt")
        registry = load_json(args.registry, "registry")
    except ObservationVerificationError as error:
        print(f"observation receipt verification failed: {error}", file=sys.stderr)
        return 1

    chain_head_path = args.chain_head if args.chain_head is not None else find_adjacent_chain_head(args.receipt)
    chain_head: dict[str, Any] | None = None
    if chain_head_path is not None:
        try:
            chain_head = load_json(chain_head_path, "chain_head")
        except ObservationVerificationError as error:
            print(f"observation receipt verification failed: {error}", file=sys.stderr)
            return 1

    failures = verify_receipt(receipt, registry=registry, chain_head=chain_head)
    facts = checked_facts(receipt, registry, chain_head)
    if failures:
        print_checked_facts(facts)
        for failure in failures:
            print(f"observation receipt verification failed: {failure}", file=sys.stderr)
        return 1
    print(f"observation receipt verification passed: {args.receipt}")
    print_checked_facts(facts)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
