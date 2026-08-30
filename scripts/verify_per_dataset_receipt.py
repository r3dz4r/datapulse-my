#!/usr/bin/env python3
"""Verify per-dataset DSSE evidence receipts against canonical public inputs."""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import logging
import subprocess
from pathlib import Path
from typing import Any

if __package__:
    from scripts.gen_per_dataset_receipt import (
        PREDICATE_TYPE, QUICK_TEST_IDS, StatementError, _validated_inputs,
        canonical_evidence_row, generate_statement, statement_bytes,
    )
else:
    from gen_per_dataset_receipt import (  # type: ignore[no-redef]
        PREDICATE_TYPE, QUICK_TEST_IDS, StatementError, _validated_inputs,
        canonical_evidence_row, generate_statement, statement_bytes,
    )


LOGGER = logging.getLogger(__name__)
ROOT = Path(__file__).resolve().parents[1]
BUNDLE_MEDIA_TYPE = "application/vnd.dev.sigstore.bundle.v0.3+json"
DSSE_PAYLOAD_TYPE = "application/vnd.in-toto+json"


class BundleError(ValueError):
    """Raised when a receipt cannot prove its expected per-dataset claim."""


def _load_json(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise BundleError(f"{label} is not readable JSON: {path}") from exc
    if not isinstance(value, dict):
        raise BundleError(f"{label} must be a JSON object: {path}")
    return value


def _decode_payload(bundle: dict[str, Any]) -> bytes:
    if bundle.get("mediaType") != BUNDLE_MEDIA_TYPE:
        raise BundleError(f"bundle mediaType must be {BUNDLE_MEDIA_TYPE}")
    envelope = bundle.get("dsseEnvelope")
    if not isinstance(envelope, dict) or envelope.get("payloadType") != DSSE_PAYLOAD_TYPE:
        raise BundleError(f"bundle DSSE payloadType must be {DSSE_PAYLOAD_TYPE}")
    signatures = envelope.get("signatures")
    if not isinstance(signatures, list) or len(signatures) != 1 or not isinstance(signatures[0], dict):
        raise BundleError("bundle DSSE envelope must contain exactly one signature")
    payload = envelope.get("payload")
    if not isinstance(payload, str) or not isinstance(signatures[0].get("sig"), str):
        raise BundleError("bundle DSSE payload or signature is missing")
    try:
        base64.b64decode(signatures[0]["sig"], validate=True)
        return base64.b64decode(payload, validate=True)
    except (ValueError, TypeError) as exc:
        raise BundleError("bundle DSSE payload or signature is not valid base64") from exc


def verify_receipt(*, dataset_id: str, health: Path, manifest: Path, data_dir: Path, identity: str, issuer: str, cosign: Path | None = None) -> str:
    """Verify one receipt's deterministic DSSE payload and optional Sigstore proof."""
    if not identity.startswith("https://") or not issuer.startswith("https://"):
        raise BundleError("certificate identity and OIDC issuer must be explicit HTTPS values")
    rows, manifest_by_id = _validated_inputs(health, manifest)
    health_row = next((row for row in rows if row["dataset_id"] == dataset_id), None)
    if health_row is None:
        raise BundleError(f"dataset is absent from health snapshot: {dataset_id}")
    expected_evidence = canonical_evidence_row(health_row, manifest_by_id[dataset_id])
    evidence_path = data_dir / f"{dataset_id}.receipt.evidence.json"
    statement_path = data_dir / f"{dataset_id}.receipt.statement.json"
    bundle_path = data_dir / f"{dataset_id}.receipt.sigstore.json"
    expected_statement = generate_statement(dataset_id, expected_evidence)
    if evidence_path.is_file() and evidence_path.read_bytes() != statement_bytes(expected_evidence):
        raise BundleError("persisted evidence row differs from canonical health evidence")
    if statement_path.is_file() and statement_path.read_bytes() != statement_bytes(expected_statement):
        raise BundleError("persisted statement differs from canonical per-dataset statement")
    payload = _decode_payload(_load_json(bundle_path, "bundle"))
    if payload != statement_bytes(expected_statement):
        raise BundleError("bundle DSSE payload differs from canonical per-dataset statement")
    subject = expected_statement["subject"][0]
    if subject["digest"]["sha256"] != hashlib.sha256(statement_bytes(expected_evidence)).hexdigest():
        raise BundleError("statement subject digest does not match canonical evidence row")
    if cosign is not None:
        completed = subprocess.run([
            str(cosign), "verify-blob-attestation", "--bundle", str(bundle_path),
            "--certificate-identity", identity, "--certificate-oidc-issuer", issuer,
            "--type", PREDICATE_TYPE, str(evidence_path),
        ], check=False, capture_output=True, text=True)
        if completed.returncode != 0:
            raise BundleError("cosign verification failed for the expected identity and issuer")
    return subject["digest"]["sha256"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--health", type=Path, default=ROOT / "health/latest.json")
    parser.add_argument("--manifest", type=Path, default=ROOT / "datapulse.json")
    parser.add_argument("--data-dir", type=Path, default=ROOT / "data")
    parser.add_argument("--dataset-id", action="append")
    parser.add_argument("--quick-test", action="store_true")
    parser.add_argument("--certificate-identity", required=True)
    parser.add_argument("--certificate-oidc-issuer", required=True)
    parser.add_argument("--cosign", type=Path)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    try:
        rows, _ = _validated_inputs(args.health, args.manifest)
        identifiers = args.dataset_id or [row["dataset_id"] for row in rows]
        if args.quick_test:
            identifiers = sorted(QUICK_TEST_IDS)
        for identifier in identifiers:
            verify_receipt(dataset_id=identifier, health=args.health, manifest=args.manifest, data_dir=args.data_dir, identity=args.certificate_identity, issuer=args.certificate_oidc_issuer, cosign=args.cosign)
    except (OSError, StatementError, BundleError, ValueError) as exc:
        raise SystemExit(f"Per-dataset receipt verification failed: {exc}") from exc
    LOGGER.info("Verified %d per-dataset receipt(s)", len(identifiers))


if __name__ == "__main__":
    main()
