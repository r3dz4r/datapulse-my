#!/usr/bin/env python3
"""Sign host-side observation receipts for the datapulse health artifact.

The observing process signs its own observation at the moment of execution: the
receipt is primary evidence produced next to the health artifact, not a CI
reconstruction. The signed payload binds the health artifact, the probe's
freshness summary, the signer's own bytes (``verification_profile_version``),
and a monotonic sequence number that links each receipt to the previous one.

Receipts accumulate one per observed state. Each cycle date gets an append-only
container, ``observation/days/<cycle_date>.json``, whose ``receipts`` array
grows by one entry every time the health artifact's content digest changes. A
re-run that observes the same digest is idempotent: the last entry already
carries that digest, so the signer writes nothing, reports ``already_signed``,
and exits 0. That makes the steady five-minute pipeline case cheap instead of an
error. ``observation/chain_head.json`` is a monotonic pointer across all days
and lets the next day link back to the previous day's last receipt. Private key
material is loaded only to produce a signature and is never logged, echoed, or
serialized into any output.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import logging
import os
import sys
import tempfile
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

LOGGER = logging.getLogger(__name__)

ROOT: Path = Path(__file__).resolve().parents[1]
SIGNER_PATH: Path = Path(__file__).resolve()

RECEIPT_SCHEMA: str = "datapulse/v1/observation-receipt"
DAY_SCHEMA: str = "datapulse/v1/observation-day"
CHAIN_HEAD_SCHEMA: str = "datapulse/v1/observation-chain-head"
VALIDITY_HOURS: int = 26

DEFAULT_OUTPUT_ROOT: Path = ROOT / "observation"
DEFAULT_HEALTH_PATH: Path = ROOT / "health" / "latest.json"
DEFAULT_METHODOLOGY_PATH: Path = ROOT / "health" / "methodology.json"
DEFAULT_KEY_PATH: Path = Path("/home/redza/.hermes/keys/datapulse-observation.ed25519.json")
DEFAULT_REGISTRY_PATH: Path = Path("/home/redza/.hermes/keys/datapulse-observation-registry.json")

# The three limits are fixed text so every receipt carries the same caveat.
LIMITATIONS: tuple[str, ...] = (
    "operator-produced evidence: the observing host signs its own observation at execution time",
    "timestamps rely on the host clock and are not independently witnessed",
    "upstream truth is not asserted; freshness statuses reflect this observation only",
)


class ObservationReceiptError(Exception):
    """Raised when a receipt cannot be built, validated, or placed safely."""


# ---------------------------------------------------------------------------
# Canonical form and time
# ---------------------------------------------------------------------------


def canonical_bytes(value: object) -> bytes:
    """Canonical JSON bytes used for every hash and signature in the receipt.

    Kept byte-for-byte identical to the repository convention (and to
    scripts/observation_store.py): sorted keys, UTF-8, compact separators.
    """
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def sha256_hex(data: bytes) -> str:
    """Lowercase hex sha256 digest, the identity form used for receipt ids."""
    return hashlib.sha256(data).hexdigest()


def parse_time(value: object, *, label: str = "timestamp") -> datetime:
    """Parse an ISO-8601 instant and normalize it to UTC.

    A naive timestamp is rejected: an ambiguous local time must never be
    silently treated as UTC inside evidence.
    """
    if not isinstance(value, str) or not value.strip():
        raise ObservationReceiptError(f"{label}_malformed: expected an ISO-8601 string, got {value!r}")
    text = value.strip()
    if text.endswith(("Z", "z")):
        text = text[:-1] + "+00:00"
    try:
        moment = datetime.fromisoformat(text)
    except ValueError as error:
        raise ObservationReceiptError(f"{label}_malformed: {value!r} is not an ISO-8601 instant") from error
    if moment.tzinfo is None:
        raise ObservationReceiptError(f"{label}_malformed: {value!r} has no timezone offset")
    return moment.astimezone(timezone.utc)


def format_time(value: datetime) -> str:
    """Render an instant as canonical UTC ISO-8601 with a trailing ``Z``."""
    return value.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


# ---------------------------------------------------------------------------
# Reading and writing
# ---------------------------------------------------------------------------


def load_json(path: Path, label: str) -> dict[str, Any]:
    """Read a JSON object, failing with a named reason rather than a traceback."""
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except OSError as error:
        raise ObservationReceiptError(f"{label}_unreadable: {path}: {error}") from error
    except json.JSONDecodeError as error:
        raise ObservationReceiptError(f"{label}_malformed: {path} is not valid JSON: {error}") from error
    if not isinstance(document, dict):
        raise ObservationReceiptError(f"{label}_malformed: {path} must contain a JSON object")
    return document


def _json_bytes(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def _atomic_write(path: Path, data: bytes) -> None:
    """Replace ``path`` atomically: sibling temp file, fsync, os.replace."""
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(descriptor, "wb") as temporary_file:
            temporary_file.write(data)
            temporary_file.flush()
            os.fsync(temporary_file.fileno())
        os.replace(temporary_name, path)
    except BaseException:
        try:
            os.unlink(temporary_name)
        except OSError:
            pass
        raise


def _relative_posix(path: Path, root: Path) -> str:
    """Render ``path`` relative to ``root`` when possible, else absolute."""
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()


# ---------------------------------------------------------------------------
# Health binding
# ---------------------------------------------------------------------------


def health_binding(health: dict[str, Any]) -> dict[str, Any]:
    """Derive the signed health fields: cycle date, count, statuses, and digest."""
    datasets = health.get("datasets")
    if not isinstance(datasets, list) or not datasets:
        raise ObservationReceiptError("health_datasets_invalid: health artifact datasets must be a non-empty array")
    statuses: Counter[str] = Counter()
    identifiers: list[str] = []
    for row in datasets:
        if not isinstance(row, dict):
            raise ObservationReceiptError("health_dataset_row_invalid: every health dataset row must be an object")
        dataset_id = row.get("dataset_id")
        if not isinstance(dataset_id, str) or not dataset_id:
            raise ObservationReceiptError("health_dataset_id_invalid: every health dataset row needs a non-empty dataset_id")
        status = row.get("status")
        if not isinstance(status, str) or not status:
            raise ObservationReceiptError(f"health_status_invalid: dataset {dataset_id!r} has no string status")
        identifiers.append(dataset_id)
        statuses[status] += 1
    if len(set(identifiers)) != len(identifiers):
        raise ObservationReceiptError("health_dataset_id_duplicate: health dataset ids must be unique")
    checked_at = health.get("checked_at")
    if not isinstance(checked_at, str):
        raise ObservationReceiptError("health_checked_at_invalid: health artifact checked_at must be an ISO-8601 string")
    cycle_date = parse_time(checked_at, label="health_checked_at").date().isoformat()
    return {
        "cycle_date": cycle_date,
        "dataset_count": len(datasets),
        "freshness_status_counts": dict(statuses),
        "health_artifact_sha256": sha256_hex(canonical_bytes(health)),
    }


def policy_version(methodology_path: Path) -> str | int | None:
    """Return methodology_version from the methodology artifact, or ``None``."""
    if not methodology_path.is_file():
        return None
    document = load_json(methodology_path, "methodology_artifact")
    value = document.get("methodology_version")
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (str, int)):
        raise ObservationReceiptError(
            f"methodology_version_invalid: {methodology_path} methodology_version must be a string, integer, or null"
        )
    return value


def verification_profile_version(signer_path: Path = SIGNER_PATH) -> str:
    """sha256 of the signer's own bytes; binds the proof to the producing code."""
    try:
        return sha256_hex(signer_path.read_bytes())
    except OSError as error:
        raise ObservationReceiptError(f"signer_unreadable: cannot hash {signer_path}: {error}") from error


# ---------------------------------------------------------------------------
# Payload and receipt construction
# ---------------------------------------------------------------------------


def build_payload(
    *,
    binding: dict[str, Any],
    observed_at: str,
    key_id: str,
    sequence_number: int,
    previous_receipt_id: str | None,
    policy: str | int | None,
    profile_version: str,
) -> dict[str, Any]:
    """Assemble the signed payload: exactly the fields in the receipt contract."""
    valid_until = format_time(parse_time(observed_at, label="observed_at") + timedelta(hours=VALIDITY_HOURS))
    return {
        "schema": RECEIPT_SCHEMA,
        "observed_at": observed_at,
        "cycle_date": binding["cycle_date"],
        "health_artifact_sha256": binding["health_artifact_sha256"],
        "dataset_count": binding["dataset_count"],
        "freshness_status_counts": binding["freshness_status_counts"],
        "verification_profile_version": profile_version,
        "policy_version": policy,
        "key_id": key_id,
        "sequence_number": sequence_number,
        "previous_receipt_id": previous_receipt_id,
        "valid_until": valid_until,
        "limitations": list(LIMITATIONS),
    }


def create_receipt(payload: dict[str, Any], private_key: Ed25519PrivateKey) -> dict[str, Any]:
    """Sign a payload and return the ``{payload, receipt_id, signature_base64}`` document."""
    canonical = canonical_bytes(payload)
    return {
        "payload": payload,
        "receipt_id": sha256_hex(canonical),
        "signature_base64": base64.b64encode(private_key.sign(canonical)).decode("ascii"),
    }


# ---------------------------------------------------------------------------
# Key and registry checks
# ---------------------------------------------------------------------------


def load_signing_key(key_path: Path) -> tuple[str, Ed25519PrivateKey, bytes]:
    """Load the Ed25519 key and prove the private key matches its public half.

    Returns ``(key_id, private_key, public_raw)``; the private key never leaves
    this process and is never included in any return value, log, or output.
    """
    document = load_json(key_path, "key_document")
    key_id = document.get("key_id")
    private_b64 = document.get("private_key_base64")
    public_b64 = document.get("public_key_base64")
    if not isinstance(key_id, str) or not key_id:
        raise ObservationReceiptError("key_document_malformed: key document is missing key_id")
    if not isinstance(private_b64, str) or not private_b64:
        raise ObservationReceiptError("key_document_malformed: key document is missing private_key_base64")
    if not isinstance(public_b64, str) or not public_b64:
        raise ObservationReceiptError("key_document_malformed: key document is missing public_key_base64")
    try:
        private_key = Ed25519PrivateKey.from_private_bytes(base64.b64decode(private_b64, validate=True))
        public_raw = base64.b64decode(public_b64, validate=True)
    except (ValueError, TypeError) as error:
        raise ObservationReceiptError("key_document_malformed: key material is not valid base64 Ed25519") from error
    derived = private_key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
    if derived != public_raw:
        raise ObservationReceiptError("key_pair_mismatch: private key does not match the documented public key")
    return key_id, private_key, public_raw


def registry_row(registry: dict[str, Any], key_id: str) -> dict[str, Any]:
    """Return the single registry row for ``key_id``; fail on missing or ambiguous."""
    rows = registry.get("keys")
    if not isinstance(rows, list):
        raise ObservationReceiptError("registry_malformed: registry keys must be an array")
    matches = [row for row in rows if isinstance(row, dict) and row.get("key_id") == key_id]
    if len(matches) != 1:
        raise ObservationReceiptError(f"key_id_not_in_registry: expected exactly one row for {key_id}, found {len(matches)}")
    return matches[0]


def require_active_window(row: dict[str, Any], observed_at: str) -> None:
    """Require status active and observed_at within [not_before, not_after]."""
    if row.get("status") != "active":
        raise ObservationReceiptError(f"key_not_active: registry status is {row.get('status')!r}")
    not_before = parse_time(row.get("not_before"), label="key_not_before")
    not_after = parse_time(row.get("not_after"), label="key_not_after")
    moment = parse_time(observed_at, label="observed_at")
    if moment < not_before:
        raise ObservationReceiptError(f"key_not_yet_valid: observed_at {observed_at} precedes not_before {row.get('not_before')}")
    if moment > not_after:
        raise ObservationReceiptError(f"key_expired: observed_at {observed_at} follows not_after {row.get('not_after')}")


# ---------------------------------------------------------------------------
# Day files and chain head
# ---------------------------------------------------------------------------


def chain_head_path(output_root: Path) -> Path:
    return output_root / "chain_head.json"


def day_file_path(output_root: Path, cycle_date: str) -> Path:
    """Path to the dated container that accumulates this cycle date's receipts."""
    return output_root / "days" / f"{cycle_date}.json"


def load_day_file(output_root: Path, cycle_date: str) -> dict[str, Any] | None:
    """Read the day container, or ``None`` when today has no receipts yet."""
    path = day_file_path(output_root, cycle_date)
    if not path.is_file():
        return None
    document = load_json(path, "day_file")
    receipts = document.get("receipts")
    if not isinstance(receipts, list):
        raise ObservationReceiptError(f"day_file_malformed: {path} receipts must be an array")
    declared_date = document.get("cycle_date")
    if declared_date is not None and declared_date != cycle_date:
        raise ObservationReceiptError(
            f"day_file_malformed: {path} declares cycle_date {declared_date!r}, expected {cycle_date!r}"
        )
    return {
        "schema": document.get("schema"),
        "cycle_date": cycle_date,
        "receipts": receipts,
        "updated_at": document.get("updated_at"),
    }


def load_chain_head(output_root: Path) -> dict[str, Any] | None:
    """Read the current chain head, or ``None`` for the first receipt.

    The canonical head carries ``last_receipt_id``/``last_observed_at``/
    ``day_file``/``day_receipt_count``. The legacy names are accepted when
    reading so an already-published head can be rolled forward without a
    migration step.
    """
    path = chain_head_path(output_root)
    if not path.is_file():
        return None
    head = load_json(path, "chain_head")
    sequence_number = head.get("sequence_number")
    if isinstance(sequence_number, bool) or not isinstance(sequence_number, int) or sequence_number < 1:
        raise ObservationReceiptError("chain_head_malformed: sequence_number must be a positive integer")
    last_receipt_id = head.get("last_receipt_id")
    if not isinstance(last_receipt_id, str) or not last_receipt_id:
        legacy_receipt_id = head.get("receipt_id")
        if isinstance(legacy_receipt_id, str) and legacy_receipt_id:
            last_receipt_id = legacy_receipt_id
        else:
            raise ObservationReceiptError("chain_head_malformed: last_receipt_id must be a non-empty string")
    return {
        "schema": head.get("schema", CHAIN_HEAD_SCHEMA),
        "sequence_number": sequence_number,
        "last_receipt_id": last_receipt_id,
        "last_observed_at": head.get("last_observed_at") or head.get("observed_at"),
        "day_file": head.get("day_file") or head.get("receipt_ref"),
        "day_receipt_count": head.get("day_receipt_count"),
        "updated_at": head.get("updated_at"),
    }


# ---------------------------------------------------------------------------
# Signing entry point
# ---------------------------------------------------------------------------


def sign_observation(
    *,
    output_root: Path,
    health_path: Path = DEFAULT_HEALTH_PATH,
    methodology_path: Path = DEFAULT_METHODOLOGY_PATH,
    key_path: Path = DEFAULT_KEY_PATH,
    registry_path: Path = DEFAULT_REGISTRY_PATH,
    now: datetime | None = None,
    expected_key_id: str | None = None,
) -> dict[str, Any]:
    """Sign the health artifact into ``output_root`` and advance the chain head.

    The signature is keyed by observed state, not by cycle date: a changed
    artifact appends an entry to today's day file and bumps the chain head,
    while re-observing the digest already carried by the last entry is an
    idempotent no-op that reports ``already_signed``. Returns a summary
    containing only public facts.
    """
    observed_at = format_time(now if now is not None else datetime.now(timezone.utc))
    health = load_json(health_path, "health_artifact")
    binding = health_binding(health)
    cycle_date = binding["cycle_date"]

    day_path = day_file_path(output_root, cycle_date)
    day_document = load_day_file(output_root, cycle_date)
    receipts: list[dict[str, Any]] = list(day_document["receipts"]) if day_document is not None else []

    if receipts:
        last_entry = receipts[-1]
        last_payload = last_entry.get("payload")
        if not isinstance(last_payload, dict):
            raise ObservationReceiptError(f"day_file_malformed: {day_path} last receipt has no payload object")
        if last_payload.get("health_artifact_sha256") == binding["health_artifact_sha256"]:
            # The normal five-minute case: the observed state has not changed.
            # Write nothing (not even updated_at) and never treat it as an error.
            return {
                "status": "already_signed",
                "receipt_id": last_entry.get("receipt_id"),
                "cycle_date": cycle_date,
                "sequence_number": last_payload.get("sequence_number"),
                "previous_receipt_id": last_payload.get("previous_receipt_id"),
                "observed_at": last_payload.get("observed_at"),
                "valid_until": last_payload.get("valid_until"),
                "policy_version": last_payload.get("policy_version"),
                "verification_profile_version": last_payload.get("verification_profile_version"),
                "day_file": _relative_posix(day_path, output_root),
                "day_receipt_count": len(receipts),
                "receipt_path": day_path.as_posix(),
                "chain_head_path": chain_head_path(output_root).as_posix(),
            }

    key_id, private_key, public_raw = load_signing_key(key_path)
    if expected_key_id is not None and key_id != expected_key_id:
        raise ObservationReceiptError(f"unexpected_key_id: key document declares {key_id}, expected {expected_key_id}")
    registry = load_json(registry_path, "registry")
    row = registry_row(registry, key_id)
    require_active_window(row, observed_at)
    try:
        registry_public = base64.b64decode(row.get("public_key_base64", ""), validate=True)
    except (ValueError, TypeError) as error:
        raise ObservationReceiptError("registry_malformed: public_key_base64 is not valid base64") from error
    if registry_public != public_raw:
        raise ObservationReceiptError("key_registry_mismatch: registry public key does not match the signing key")

    # Sequence continues across days: today's last entry when it exists,
    # otherwise the chain head's last receipt (the previous day's tail).
    if receipts:
        previous_payload = receipts[-1].get("payload")
        if not isinstance(previous_payload, dict) or not isinstance(previous_payload.get("sequence_number"), int):
            raise ObservationReceiptError(f"day_file_malformed: {day_path} last receipt has no integer sequence_number")
        sequence_number = int(previous_payload["sequence_number"]) + 1
        previous_receipt_id: str | None = receipts[-1].get("receipt_id")
    else:
        head = load_chain_head(output_root)
        if head is None:
            sequence_number = 1
            previous_receipt_id = None
        else:
            sequence_number = int(head["sequence_number"]) + 1
            previous_receipt_id = head["last_receipt_id"]

    payload = build_payload(
        binding=binding,
        observed_at=observed_at,
        key_id=key_id,
        sequence_number=sequence_number,
        previous_receipt_id=previous_receipt_id,
        policy=policy_version(methodology_path),
        profile_version=verification_profile_version(),
    )
    document = create_receipt(payload, private_key)

    # Self-verify before placing evidence: a receipt that cannot be verified
    # must never be written.
    Ed25519PublicKey.from_public_bytes(public_raw).verify(
        base64.b64decode(document["signature_base64"]), canonical_bytes(payload)
    )

    # Append-only: every loaded entry is carried forward untouched.
    updated_receipts = receipts + [document]
    day_file = {
        "schema": DAY_SCHEMA,
        "cycle_date": cycle_date,
        "receipts": updated_receipts,
        "updated_at": observed_at,
    }
    chain_head = {
        "schema": CHAIN_HEAD_SCHEMA,
        "sequence_number": sequence_number,
        "last_receipt_id": document["receipt_id"],
        "last_observed_at": observed_at,
        "day_file": _relative_posix(day_path, output_root),
        "day_receipt_count": len(updated_receipts),
        "updated_at": observed_at,
    }
    # Day file first, then the pointer: an interruption between the two leaves
    # a head that trails the day file, which the next run repairs. The reverse
    # order could advertise a receipt that was never durably written.
    _atomic_write(day_path, _json_bytes(day_file))
    _atomic_write(chain_head_path(output_root), _json_bytes(chain_head))
    return {
        "status": "signed",
        "receipt_id": document["receipt_id"],
        "cycle_date": cycle_date,
        "sequence_number": sequence_number,
        "previous_receipt_id": previous_receipt_id,
        "observed_at": observed_at,
        "valid_until": payload["valid_until"],
        "policy_version": payload["policy_version"],
        "verification_profile_version": payload["verification_profile_version"],
        "day_file": _relative_posix(day_path, output_root),
        "day_receipt_count": len(updated_receipts),
        "receipt_path": day_path.as_posix(),
        "chain_head_path": chain_head_path(output_root).as_posix(),
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Sign a host-side observation receipt for a health artifact.")
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT, help="Directory holding days/ and chain_head.json.")
    parser.add_argument("--health", type=Path, default=DEFAULT_HEALTH_PATH, help="Health artifact to bind.")
    parser.add_argument("--methodology", type=Path, default=DEFAULT_METHODOLOGY_PATH, help="Methodology artifact for policy_version.")
    parser.add_argument("--key", type=Path, default=DEFAULT_KEY_PATH, help="Ed25519 private key document (never printed).")
    parser.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY_PATH, help="Key registry with public keys and validity windows.")
    parser.add_argument("--expected-key-id", help="Fail unless the key document declares this key_id.")
    parser.add_argument("--now", help="ISO-8601 UTC override for observed_at (testing/reproducibility only).")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    try:
        now = parse_time(args.now, label="now") if args.now else datetime.now(timezone.utc)
        summary = sign_observation(
            output_root=args.output_root,
            health_path=args.health,
            methodology_path=args.methodology,
            key_path=args.key,
            registry_path=args.registry,
            now=now,
            expected_key_id=args.expected_key_id,
        )
    except ObservationReceiptError as error:
        print(f"observation receipt signing failed: {error}", file=sys.stderr)
        return 1
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
