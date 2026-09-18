#!/usr/bin/env python3
"""Offline verifier for host-side observation receipts.

Verification is deliberately local: the payload hash, the Ed25519 signature,
the registry validity window, and the receipt identity are all recomputed from
files on disk. No network call is made and no private key is needed or read.

A receipt lives either standalone or inside a dated day file. With
``--day-file`` (and ``--receipt-id`` when the file holds more than one entry)
the verifier selects the entry by ``receipt_id`` and additionally walks the
within-day chain: every entry's ``previous_receipt_id`` must equal the prior
entry's ``receipt_id``. A chain head supplied with ``--chain-head`` (or found
next to the input) anchors the walk: when the head belongs to the same day the
day's last receipt must equal its ``last_receipt_id``; when the head is an
earlier day's, the file's first entry must link to that head's last receipt.
Linkage is reported ``checked`` only when a walk actually happened, otherwise
``unchecked`` and primary checks still gate a 0 exit. The artifact binding is
reproduced only when ``--health`` supplies the served file; without it the
report says ``health_binding: unchecked`` rather than implying it was verified.
Every failure names its exact reason; the CLI exits 0 on success and 1 on
failure with each reason on stderr.
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
        DAY_SCHEMA,
        RECEIPT_SCHEMA,
        ObservationReceiptError,
        canonical_bytes,
        normalized_health_digest,
        parse_time,
        sha256_hex,
    )
else:
    from observation_receipt import (  # type: ignore[no-redef]
        DAY_SCHEMA,
        RECEIPT_SCHEMA,
        ObservationReceiptError,
        canonical_bytes,
        normalized_health_digest,
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


def _health_binding_failures(
    payload: dict[str, Any],
    health: dict[str, Any],
    health_path: Path | None,
) -> list[str]:
    """Recompute the normalized artifact digest and require it to match the payload.

    The digest is reproduced exactly as the signer computed it: the volatile
    ``_trust_summary.pipeline_heartbeat_at`` field is excluded first. A mismatch
    names both digests so a reader can see which artifact was supplied.
    """
    declared = payload.get("health_artifact_sha256")
    reproduced = normalized_health_digest(health)
    if declared != reproduced:
        source = health_path if health_path is not None else "<supplied artifact>"
        return [
            f"health_artifact_mismatch: artifact {source} yields {reproduced} "
            f"but payload declares health_artifact_sha256={declared}"
        ]
    return []


def _standalone_chain_failures(
    receipt: dict[str, Any],
    payload: dict[str, Any],
    chain_head: dict[str, Any],
) -> list[str]:
    """Anchor a standalone receipt to a chain head.

    A head that records ``last_receipt_id`` (the accumulated model) can only
    identify its newest receipt, so a standalone receipt is anchored by
    requiring it to *be* that receipt. A legacy head that records
    ``previous_receipt_id`` keeps the original prior-link comparison.
    """
    if "last_receipt_id" in chain_head:
        if receipt.get("receipt_id") != chain_head.get("last_receipt_id"):
            return [
                "chain_head_mismatch: receipt declares receipt_id="
                f"{receipt.get('receipt_id')!r} but chain head records last_receipt_id="
                f"{chain_head.get('last_receipt_id')!r}"
            ]
        return []
    if "previous_receipt_id" in chain_head:
        head_previous = chain_head.get("previous_receipt_id")
        if payload.get("previous_receipt_id") != head_previous:
            return [
                "previous_receipt_mismatch: receipt declares previous_receipt_id="
                f"{payload.get('previous_receipt_id')!r} but chain head records {head_previous!r}"
            ]
        return []
    return ["chain_head_malformed: chain head records neither last_receipt_id nor previous_receipt_id"]


def _day_receipts(document: dict[str, Any], label: str) -> list[dict[str, Any]]:
    """Return a day file's non-empty receipts array, or raise a named error."""
    receipts = document.get("receipts")
    if not isinstance(receipts, list) or not receipts:
        raise ObservationVerificationError(f"day_file_malformed: {label} receipts must be a non-empty array")
    for index, entry in enumerate(receipts):
        if not isinstance(entry, dict):
            raise ObservationVerificationError(f"day_file_malformed: {label} receipt {index} must be a JSON object")
    return receipts


def select_day_receipt(
    document: dict[str, Any],
    receipt_id: str | None,
    *,
    label: str = "day_file",
) -> tuple[list[dict[str, Any]], int]:
    """Locate one receipt inside a day file and return ``(receipts, index)``.

    ``receipt_id`` is required when the file holds more than one entry; a
    single-entry file needs no disambiguation.
    """
    schema = document.get("schema")
    if schema is not None and schema != DAY_SCHEMA:
        raise ObservationVerificationError(f"day_file_schema_mismatch: expected {DAY_SCHEMA!r}, got {schema!r}")
    receipts = _day_receipts(document, label)
    if receipt_id is None:
        if len(receipts) != 1:
            raise ObservationVerificationError(
                f"receipt_id_required: {label} holds {len(receipts)} receipts; pass --receipt-id to select one"
            )
        return receipts, 0
    matches = [index for index, entry in enumerate(receipts) if entry.get("receipt_id") == receipt_id]
    if not matches:
        raise ObservationVerificationError(f"receipt_id_not_in_day: no receipt with receipt_id {receipt_id!r} in {label}")
    if len(matches) > 1:
        raise ObservationVerificationError(
            f"receipt_id_ambiguous: {len(matches)} receipts in {label} share receipt_id {receipt_id!r}"
        )
    return receipts, matches[0]


def day_linkage_failures(receipts: list[dict[str, Any]], selected_index: int) -> list[str]:
    """Walk the within-day chain up to the selected entry.

    Every link is checked, so tampering with an entry reports a break for that
    entry and for each later entry whose chain passes through it.
    """
    failures: list[str] = []
    for index in range(1, selected_index + 1):
        previous = receipts[index - 1]
        current = receipts[index]
        payload = current.get("payload")
        declared = payload.get("previous_receipt_id") if isinstance(payload, dict) else None
        expected = previous.get("receipt_id")
        if declared != expected:
            failures.append(
                f"linkage_broken: entry {index} (receipt_id {current.get('receipt_id')!r}) declares "
                f"previous_receipt_id={declared!r} but entry {index - 1} has receipt_id {expected!r}"
            )
    return failures


def day_anchor_failures(
    receipts: list[dict[str, Any]],
    chain_head: dict[str, Any],
    day_file_path: Path | None,
) -> list[str]:
    """Anchor a day file to a chain head.

    Same-day head: the head's ``last_receipt_id`` must be the file's last
    receipt (and its count must agree). Earlier-day head: the file's first
    entry must link back to the head's last receipt.
    """
    head_day = chain_head.get("day_file")
    same_day = isinstance(head_day, str) and day_file_path is not None and Path(head_day).name == day_file_path.name
    if not same_day:
        same_day = chain_head.get("last_receipt_id") == receipts[-1].get("receipt_id")
    failures: list[str] = []
    if same_day:
        if chain_head.get("last_receipt_id") != receipts[-1].get("receipt_id"):
            failures.append(
                "chain_head_mismatch: chain head last_receipt_id="
                f"{chain_head.get('last_receipt_id')!r} but the day file's last receipt is "
                f"{receipts[-1].get('receipt_id')!r}"
            )
        head_count = chain_head.get("day_receipt_count")
        if isinstance(head_count, int) and not isinstance(head_count, bool) and head_count != len(receipts):
            failures.append(
                f"chain_head_count_mismatch: chain head records day_receipt_count={head_count} "
                f"but the day file holds {len(receipts)} receipts"
            )
        return failures
    first_payload = receipts[0].get("payload")
    declared = first_payload.get("previous_receipt_id") if isinstance(first_payload, dict) else None
    if declared != chain_head.get("last_receipt_id"):
        failures.append(
            "previous_receipt_mismatch: first entry declares previous_receipt_id="
            f"{declared!r} but chain head records last_receipt_id={chain_head.get('last_receipt_id')!r}"
        )
    return failures


def verify_day_receipt(
    document: dict[str, Any],
    *,
    registry: dict[str, Any],
    receipt_id: str | None = None,
    chain_head: dict[str, Any] | None = None,
    day_file_path: Path | None = None,
    health: dict[str, Any] | None = None,
    health_path: Path | None = None,
) -> tuple[list[str], dict[str, Any], bool]:
    """Verify one entry of a day file plus its within-day and head linkage.

    Returns ``(failures, selected_receipt, linkage_checked)``.
    """
    receipts, index = select_day_receipt(document, receipt_id, label=str(day_file_path or "day_file"))
    receipt = receipts[index]
    failures = verify_receipt(receipt, registry=registry, health=health, health_path=health_path)
    failures.extend(day_linkage_failures(receipts, index))
    linkage_checked = chain_head is not None or index > 0
    if chain_head is not None:
        failures.extend(day_anchor_failures(receipts, chain_head, day_file_path))
    return failures, receipt, linkage_checked


def find_adjacent_chain_head(receipt_path: Path) -> Path | None:
    """Return a chain head sitting next to the receipt, or ``None`` when absent.

    Resolution is relative to the input, never to this repository: the input's
    own directory first, then its parent. That finds a signer-produced tree
    (``<root>/days/<date>.json`` plus ``<root>/chain_head.json``) and still
    finds nothing when a third party holds only a standalone receipt.
    """
    candidates = (receipt_path.parent / CHAIN_HEAD_FILENAME, receipt_path.parent.parent / CHAIN_HEAD_FILENAME)
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    return None


def checked_facts(
    receipt: dict[str, Any],
    registry: dict[str, Any],
    linkage_checked: bool,
    binding_checked: bool = False,
) -> dict[str, Any]:
    """Return the public facts the verifier actually used, for its evidence report.

    Only public material appears here: the declared receipt id, the payload's
    key_id, the registry's public validity window, whether linkage was walked,
    and whether the artifact digest was reproduced against a supplied health
    file. No key bytes are read or reported.
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
        "linkage": "checked" if linkage_checked else "unchecked",
        "health_binding": "checked" if binding_checked else "unchecked",
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
    print(f"  health_binding: {facts.get('health_binding', 'unchecked')}")


def verify_receipt(
    receipt: dict[str, Any],
    *,
    registry: dict[str, Any],
    chain_head: dict[str, Any] | None = None,
    health: dict[str, Any] | None = None,
    health_path: Path | None = None,
) -> list[str]:
    """Return every verification failure; an empty list means the receipt is valid.

    The primary checks always run. Chain linkage runs only when a chain head is
    available; when ``chain_head`` is ``None`` linkage is deliberately left
    unchecked rather than reported as passing. The artifact digest is likewise
    reproduced only when a ``health`` artifact is supplied; otherwise the caller
    must report the binding as unchecked.
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
    if health is not None:
        failures.extend(_health_binding_failures(payload, health, health_path))
    if chain_head is not None:
        failures.extend(_standalone_chain_failures(receipt, payload, chain_head))
    return failures


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Verify a host-side observation receipt entirely offline.")
    parser.add_argument("--receipt", type=Path, default=None, help="Standalone receipt JSON to verify.")
    parser.add_argument(
        "--day-file",
        type=Path,
        default=None,
        help="Dated day file whose receipts array holds the receipt to verify.",
    )
    parser.add_argument("--receipt-id", default=None, help="receipt_id selecting an entry inside --day-file.")
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
        help="Chain head that anchors linkage. Defaults to a chain_head.json next to the input.",
    )
    parser.add_argument(
        "--health",
        type=Path,
        default=None,
        help="Health artifact whose normalized digest must reproduce the payload's health_artifact_sha256.",
    )
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    if (args.receipt is None) == (args.day_file is None):
        print(
            "observation receipt verification failed: input_required: pass exactly one of --receipt or --day-file",
            file=sys.stderr,
        )
        return 1

    input_path = args.day_file if args.day_file is not None else args.receipt
    assert input_path is not None
    try:
        registry = load_json(args.registry, "registry")
        if args.day_file is not None:
            day_document = load_json(args.day_file, "day_file")
        else:
            receipt = load_json(args.receipt, "receipt")
    except ObservationVerificationError as error:
        print(f"observation receipt verification failed: {error}", file=sys.stderr)
        return 1

    chain_head_path = args.chain_head if args.chain_head is not None else find_adjacent_chain_head(input_path)
    chain_head: dict[str, Any] | None = None
    if chain_head_path is not None:
        try:
            chain_head = load_json(chain_head_path, "chain_head")
        except ObservationVerificationError as error:
            print(f"observation receipt verification failed: {error}", file=sys.stderr)
            return 1

    health_artifact: dict[str, Any] | None = None
    if args.health is not None:
        try:
            health_artifact = load_json(args.health, "health_artifact")
        except ObservationVerificationError as error:
            print(f"observation receipt verification failed: {error}", file=sys.stderr)
            return 1

    try:
        if args.day_file is not None:
            failures, selected, linkage_checked = verify_day_receipt(
                day_document,
                registry=registry,
                receipt_id=args.receipt_id,
                chain_head=chain_head,
                day_file_path=args.day_file,
                health=health_artifact,
                health_path=args.health,
            )
        else:
            if args.receipt_id is not None and receipt.get("receipt_id") != args.receipt_id:
                print(
                    "observation receipt verification failed: receipt_id_mismatch: standalone receipt is "
                    f"{receipt.get('receipt_id')!r}, not {args.receipt_id!r}",
                    file=sys.stderr,
                )
                return 1
            failures = verify_receipt(
                receipt,
                registry=registry,
                chain_head=chain_head,
                health=health_artifact,
                health_path=args.health,
            )
            selected = receipt
            linkage_checked = chain_head is not None
    except ObservationVerificationError as error:
        print(f"observation receipt verification failed: {error}", file=sys.stderr)
        return 1

    facts = checked_facts(selected, registry, linkage_checked, binding_checked=health_artifact is not None)
    if failures:
        print_checked_facts(facts)
        for failure in failures:
            print(f"observation receipt verification failed: {failure}", file=sys.stderr)
        return 1
    print(f"observation receipt verification passed: {input_path}")
    print_checked_facts(facts)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
