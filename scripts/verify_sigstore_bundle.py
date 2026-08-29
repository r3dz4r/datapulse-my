#!/usr/bin/env python3
"""Verify a DataPulse DSSE bundle against canonical health and repository inputs."""

from __future__ import annotations

import argparse
import base64
import json
import logging
import subprocess
from pathlib import Path
from typing import Any

from scripts.gen_sigstore_bundle import (
    PREDICATE_TYPE,
    generate_statement,
    statement_bytes,
)

LOGGER = logging.getLogger(__name__)
ROOT = Path(__file__).resolve().parents[1]
BUNDLE_MEDIA_TYPE = "application/vnd.dev.sigstore.bundle.v0.3+json"
DSSE_PAYLOAD_TYPE = "application/vnd.in-toto+json"


class BundleError(ValueError):
    """Raised when a Sigstore bundle does not prove the expected health claim."""


def _load_bundle(path: Path) -> dict[str, Any]:
    try:
        bundle = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise BundleError(f"bundle is not readable JSON: {path}") from exc
    if not isinstance(bundle, dict):
        raise BundleError("bundle must be a JSON object")
    return bundle


def _decode_payload(bundle: dict[str, Any]) -> bytes:
    if bundle.get("mediaType") != BUNDLE_MEDIA_TYPE:
        raise BundleError(f"bundle mediaType must be {BUNDLE_MEDIA_TYPE}")
    if "messageSignature" in bundle or "dsseEnvelope" not in bundle:
        raise BundleError("bundle must contain a DSSE attestation, not a message signature")
    verification = bundle.get("verificationMaterial")
    if not isinstance(verification, dict):
        raise BundleError("bundle verificationMaterial must be an object")
    tlog_entries = verification.get("tlogEntries")
    if not isinstance(tlog_entries, list) or not tlog_entries:
        raise BundleError("bundle must contain public transparency log evidence")
    envelope = bundle["dsseEnvelope"]
    if not isinstance(envelope, dict) or envelope.get("payloadType") != DSSE_PAYLOAD_TYPE:
        raise BundleError(f"bundle DSSE payloadType must be {DSSE_PAYLOAD_TYPE}")
    signatures = envelope.get("signatures")
    if not isinstance(signatures, list) or len(signatures) != 1:
        raise BundleError("bundle DSSE envelope must contain exactly one signature")
    signature = signatures[0]
    if not isinstance(signature, dict) or not isinstance(signature.get("sig"), str):
        raise BundleError("bundle DSSE signature is malformed")
    encoded = envelope.get("payload")
    if not isinstance(encoded, str):
        raise BundleError("bundle DSSE payload is missing")
    try:
        base64.b64decode(signature["sig"], validate=True)
        return base64.b64decode(encoded, validate=True)
    except (ValueError, TypeError) as exc:
        raise BundleError("bundle DSSE payload or signature is not valid base64") from exc


def _validate_verification_argument(value: str, label: str) -> None:
    if not value.startswith("https://") or any(character.isspace() for character in value):
        raise BundleError(f"{label} must be an explicit HTTPS identity")


def verify_bundle(
    *,
    health: Path,
    manifest: Path,
    chain_head: Path,
    source_commit: str,
    bundle: Path,
    identity: str,
    issuer: str,
    cosign: Path | None = None,
) -> dict[str, str]:
    """Verify deterministic payload parity and, when requested, its Sigstore proof."""
    _validate_verification_argument(identity, "certificate identity")
    _validate_verification_argument(issuer, "certificate OIDC issuer")
    expected_statement = generate_statement(health, manifest, chain_head, source_commit)
    expected_payload = statement_bytes(expected_statement)
    actual_payload = _decode_payload(_load_bundle(bundle))
    if actual_payload != expected_payload:
        raise BundleError("bundle DSSE payload differs from the deterministic health statement")
    if cosign is not None:
        completed = subprocess.run(
            [
                str(cosign),
                "verify-blob-attestation",
                "--bundle",
                str(bundle),
                "--certificate-identity",
                identity,
                "--certificate-oidc-issuer",
                issuer,
                "--type",
                PREDICATE_TYPE,
                str(health),
            ],
            check=False,
            capture_output=True,
            text=True,
        )
        if completed.returncode != 0:
            raise BundleError("cosign verification failed for the expected identity and issuer")
    return {
        "subject_sha256": expected_statement["subject"][0]["digest"]["sha256"],
        "identity": identity,
        "issuer": issuer,
    }


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
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--certificate-identity", required=True)
    parser.add_argument("--certificate-oidc-issuer", required=True)
    parser.add_argument("--cosign", type=Path, required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    try:
        result = verify_bundle(
            health=args.health,
            manifest=args.manifest,
            chain_head=args.legacy_chain_head,
            source_commit=args.source_commit,
            bundle=args.bundle,
            identity=args.certificate_identity,
            issuer=args.certificate_oidc_issuer,
            cosign=args.cosign,
        )
    except (OSError, BundleError, ValueError) as exc:
        raise SystemExit(f"Sigstore bundle verification failed: {exc}") from exc
    LOGGER.info("Verified health DSSE bundle for sha256:%s", result["subject_sha256"])


if __name__ == "__main__":
    main()
