#!/usr/bin/env python3
"""Verify the additive health/Ed25519/Rekor attestation binding contract."""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey


DEFAULT_MAX_AGE_SECONDS = 36 * 60 * 60
DIGEST = re.compile(r"[0-9a-f]{64}")


class ContractError(ValueError):
    """Published attestation metadata violates the binding contract."""


def canonical(value: object) -> bytes:
    """Retain the canonical JSON form used by legacy Ed25519 verifiers."""
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def _load(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ContractError(f"{label} is missing or invalid") from error
    if not isinstance(value, dict):
        raise ContractError(f"{label} must be an object")
    return value


def _parse_time(value: object, label: str) -> datetime:
    if not isinstance(value, str):
        raise ContractError(f"{label} must be an ISO-8601 timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise ContractError(f"{label} must be an ISO-8601 timestamp") from error
    if parsed.tzinfo is None:
        raise ContractError(f"{label} must include a UTC offset")
    return parsed.astimezone(timezone.utc)


def _digest_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _normalise_digest(value: object, label: str) -> str:
    if isinstance(value, str) and DIGEST.fullmatch(value):
        return value
    if isinstance(value, str):
        try:
            decoded = base64.b64decode(value, validate=True)
        except (ValueError, UnicodeEncodeError):
            decoded = b""
        if len(decoded) == hashlib.sha256().digest_size:
            return decoded.hex()
    raise ContractError(f"{label} is not a SHA-256 digest")


def _safe_ref(value: object, prefix: str, suffix: str = ".json") -> str:
    if not isinstance(value, str):
        raise ContractError("attestation proof reference is missing")
    path = PurePosixPath(value)
    if (
        path.is_absolute()
        or ".." in path.parts
        or not value.startswith(prefix)
        or not value.endswith(suffix)
    ):
        raise ContractError("attestation proof reference is unsafe")
    return value


def _registry_key(
    registry: dict[str, Any], key_id: object, published_at: datetime, now: datetime
) -> tuple[dict[str, Any], Ed25519PublicKey]:
    rows = registry.get("keys")
    if registry.get("schema") != "datapulse/v1/probe-key-registry" or not isinstance(rows, list):
        raise ContractError("key registry is invalid")
    matches = [row for row in rows if isinstance(row, dict) and row.get("key_id") == key_id]
    if len(matches) != 1:
        raise ContractError("attestation key is missing or ambiguous")
    row = matches[0]
    if registry.get("current_key_id") != key_id or row.get("status") != "active":
        raise ContractError("attestation key is not active")
    not_before = _parse_time(row.get("not_before"), "key not_before")
    not_after = _parse_time(row.get("not_after"), "key not_after")
    if not (not_before <= published_at <= not_after and not_before <= now <= not_after):
        raise ContractError("attestation key is outside its active window")
    try:
        raw = base64.b64decode(row["public_key_base64"], validate=True)
        public = Ed25519PublicKey.from_public_bytes(raw)
    except (KeyError, ValueError, TypeError) as error:
        raise ContractError("attestation public key is invalid") from error
    return row, public


def _verify_signature(
    public: Ed25519PublicKey, payload: object, signature: object, label: str
) -> None:
    if not isinstance(signature, str):
        raise ContractError(f"{label} signature is missing")
    try:
        public.verify(base64.b64decode(signature, validate=True), canonical(payload))
    except (ValueError, InvalidSignature) as error:
        raise ContractError(f"{label} signature is invalid") from error


def _verify_legacy_plane(
    root: Path,
    index: dict[str, Any],
    head: dict[str, Any],
    public: Ed25519PublicKey,
    registry_row: dict[str, Any],
    *,
    verify_datasets: bool = True,
) -> None:
    payload = head.get("payload")
    links = head.get("dataset_links")
    if (
        head.get("schema") != "datapulse/v1/daily-chain-head-envelope"
        or not isinstance(payload, dict)
        or payload.get("schema") != "datapulse/v1/daily-chain-head"
        or not isinstance(links, list)
    ):
        raise ContractError("legacy daily chain head is invalid")
    previous = payload.get("previous_chain_head")
    if not isinstance(previous, str) or not DIGEST.fullmatch(previous):
        raise ContractError("legacy previous chain head is invalid")
    _verify_signature(public, payload, head.get("signature_base64"), "daily chain head")
    if _digest_bytes(bytes.fromhex(previous) + canonical(payload)) != head.get("chain_head"):
        raise ContractError("daily chain head digest is invalid")
    if payload.get("dataset_count") != len(links):
        raise ContractError("daily chain dataset count is invalid")
    if payload.get("dataset_links_sha256") != _digest_bytes(canonical(links)):
        raise ContractError("daily chain dataset hash is invalid")
    if payload.get("key_id") != registry_row.get("key_id"):
        raise ContractError("daily chain key does not match active key")

    refs = index.get("attestations")
    if (
        index.get("schema") != "datapulse/v1/attestation-index"
        or not isinstance(refs, dict)
        or index.get("date") != payload.get("date")
        or index.get("chain_head_ref") != f"attestations/{payload.get('date')}/chain_head.json"
    ):
        raise ContractError("latest attestation index is invalid")
    link_by_id = {
        row.get("dataset_id"): row.get("chain_link")
        for row in links
        if isinstance(row, dict)
    }
    if len(link_by_id) != len(links) or set(refs) != set(link_by_id):
        raise ContractError("attestation index and daily links disagree")
    if not verify_datasets:
        return
    for dataset_id, reference in refs.items():
        expected_ref = f"attestations/{payload['date']}/{dataset_id}.json"
        if reference != expected_ref:
            raise ContractError("dataset attestation reference is invalid")
        envelope = _load(root / reference, f"dataset attestation {dataset_id}")
        dataset_payload = envelope.get("payload")
        if (
            envelope.get("schema") != "datapulse/v1/probe-attestation-envelope"
            or not isinstance(dataset_payload, dict)
            or dataset_payload.get("schema") != "datapulse/v1/probe-attestation"
            or dataset_payload.get("dataset_id") != dataset_id
            or dataset_payload.get("previous_chain_head") != previous
            or dataset_payload.get("key_id") != registry_row.get("key_id")
            or dataset_payload.get("signer_pubkey_base64")
            != registry_row.get("public_key_base64")
        ):
            raise ContractError("dataset attestation does not match daily chain")
        _verify_signature(
            public, dataset_payload, envelope.get("signature_base64"), "dataset attestation"
        )
        expected_link = _digest_bytes(bytes.fromhex(previous) + canonical(dataset_payload))
        if envelope.get("chain_link") != expected_link or link_by_id[dataset_id] != expected_link:
            raise ContractError("dataset attestation chain link is invalid")


def _verify_merkle_proof(entry: dict[str, Any]) -> None:
    proof = entry.get("inclusionProof")
    promise = entry.get("inclusionPromise")
    body = entry.get("canonicalizedBody")
    if not isinstance(proof, dict) or not isinstance(promise, dict):
        raise ContractError("Rekor inclusion proof reference is missing")
    if not isinstance(promise.get("signedEntryTimestamp"), str) or not promise["signedEntryTimestamp"]:
        raise ContractError("Rekor signed entry timestamp is missing")
    try:
        leaf_body = base64.b64decode(body, validate=True)
        root_hash = base64.b64decode(proof["rootHash"], validate=True)
        hashes = [base64.b64decode(item, validate=True) for item in proof["hashes"]]
        index = entry["logIndex"]
        tree_size = proof["treeSize"]
    except (KeyError, TypeError, ValueError) as error:
        raise ContractError("Rekor inclusion proof is invalid") from error
    if (
        not leaf_body
        or len(root_hash) != 32
        or any(len(item) != 32 for item in hashes)
        or isinstance(index, bool)
        or not isinstance(index, int)
        or isinstance(tree_size, bool)
        or not isinstance(tree_size, int)
        or index < 0
        or tree_size <= index
    ):
        raise ContractError("Rekor inclusion proof is invalid")
    current = hashlib.sha256(b"\x00" + leaf_body).digest()
    node_index = index
    last_index = tree_size - 1
    for sibling in hashes:
        if node_index % 2 == 1 or node_index == last_index:
            current = hashlib.sha256(b"\x01" + sibling + current).digest()
            while node_index != 0 and node_index % 2 == 0:
                node_index //= 2
                last_index //= 2
        else:
            current = hashlib.sha256(b"\x01" + current + sibling).digest()
        node_index //= 2
        last_index //= 2
    if last_index != 0 or current != root_hash:
        raise ContractError("Rekor inclusion proof root does not verify")


def _verify_rekor(
    root: Path, metadata: object, expected_digest: str
) -> dict[str, Any] | None:
    if metadata is None:
        return None
    if not isinstance(metadata, dict):
        raise ContractError("Rekor binding metadata is invalid")
    reference_ref = _safe_ref(metadata.get("reference_ref"), "attestations/")
    bundle_ref = _safe_ref(metadata.get("bundle_ref"), "attestations/")
    reference = _load(root / reference_ref, "Rekor reference")
    reference_bundle = reference.get("bundle")
    resolved_reference_bundle = (
        (PurePosixPath(reference_ref).parent / reference_bundle).as_posix()
        if isinstance(reference_bundle, str)
        else None
    )
    if (
        reference.get("schema") != "datapulse/v1/sigstore-rekor-reference"
        or reference.get("artifact") != "health/latest.json"
        or reference.get("artifact_sha256") != expected_digest
        or resolved_reference_bundle != bundle_ref
        or reference.get("run_id") != f"health-{expected_digest}"
    ):
        raise ContractError("Rekor reference does not bind the health digest")
    bundle = _load(root / bundle_ref, "Sigstore bundle")
    try:
        digest = bundle["messageSignature"]["messageDigest"]
        entries = bundle["verificationMaterial"]["tlogEntries"]
        entry = entries[0]
        log_id = _normalise_digest(entry["logId"]["keyId"], "Rekor LogID")
    except (KeyError, IndexError, TypeError) as error:
        raise ContractError("Sigstore bundle is incomplete") from error
    if (
        digest.get("algorithm") != "SHA2_256"
        or _normalise_digest(digest.get("digest"), "Sigstore artifact digest")
        != expected_digest
        or not isinstance(entries, list)
        or len(entries) != 1
    ):
        raise ContractError("Sigstore bundle does not bind the health digest")
    _verify_merkle_proof(entry)
    canonicalized_body = base64.b64decode(entry["canonicalizedBody"], validate=True)
    uuid = hashlib.sha256(canonicalized_body).hexdigest()
    summary = reference.get("rekor")
    if not isinstance(summary, dict) or summary != {
        "log_id": log_id,
        "log_index": entry["logIndex"],
        "uuid": uuid,
        "inclusion_proof": True,
        "signed_entry_timestamp": True,
    }:
        raise ContractError("Rekor proof summary does not match the bundle")
    return summary


def verify_rekor_evidence(
    root: Path, metadata: dict[str, Any], expected_digest: str
) -> dict[str, Any]:
    """Validate proposed Rekor evidence before a generator publishes its references."""
    result = _verify_rekor(root, metadata, expected_digest)
    if result is None:
        raise ContractError("required Rekor proof reference is missing")
    return result


def verify_unbound_legacy_plane(
    root: Path, *, now: datetime | None = None, verify_datasets: bool = True
) -> None:
    """Validate legacy L1 evidence before allowing an honestly unattested snapshot."""
    current = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    index = _load(root / "attestations/latest/index.json", "latest attestation index")
    head = _load(root / "attestations/latest/chain_head.json", "latest chain head")
    payload = head.get("payload")
    if not isinstance(payload, dict):
        raise ContractError("legacy daily chain head is invalid")
    registry = _load(
        root / "docs/.well-known/datapulse-probe-keys.json", "probe key registry"
    )
    registry_row, public = _registry_key(
        registry, payload.get("key_id"), current, current
    )
    _verify_legacy_plane(
        root, index, head, public, registry_row, verify_datasets=verify_datasets
    )
    chain_index = _load(root / "attestations/chain-index.json", "chain index")
    date = payload.get("date")
    refs = [
        ref
        for ref in chain_index.get("heads", {}).values()
        if isinstance(ref, str) and ref.startswith(f"attestations/{date}/")
    ]
    if refs != [f"attestations/{date}/chain_head.json"]:
        raise ContractError("duplicate-date attestation ambiguity detected")


def verify_contract(
    root: Path,
    *,
    now: datetime | None = None,
    require_rekor: bool = False,
    verify_datasets: bool = True,
) -> dict[str, Any]:
    """Verify all served attestation planes against the current health bytes."""
    current = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    health_path = root / "health/latest.json"
    health = _load(health_path, "health snapshot")
    index = _load(root / "attestations/latest/index.json", "latest attestation index")
    head = _load(root / "attestations/latest/chain_head.json", "latest chain head")
    binding = _load(root / "attestations/latest/binding.json", "latest binding")
    payload = binding.get("payload")
    if (
        binding.get("schema") != "datapulse/v1/attestation-binding-envelope"
        or not isinstance(payload, dict)
        or payload.get("schema") != "datapulse/v1/attestation-binding"
    ):
        raise ContractError("attestation binding schema is invalid")
    published_at = _parse_time(payload.get("published_at"), "binding publication time")
    health_binding = payload.get("health")
    ed25519 = payload.get("ed25519")
    freshness = payload.get("freshness")
    if not isinstance(health_binding, dict) or not isinstance(ed25519, dict) or not isinstance(freshness, dict):
        raise ContractError("attestation binding payload is incomplete")
    max_age = freshness.get("max_age_seconds")
    if isinstance(max_age, bool) or not isinstance(max_age, int) or max_age <= 0:
        raise ContractError("served freshness contract is invalid")
    registry = _load(
        root / "docs/.well-known/datapulse-probe-keys.json", "probe key registry"
    )
    registry_row, public = _registry_key(
        registry, ed25519.get("key_id"), published_at, current
    )
    _verify_signature(public, payload, binding.get("signature_base64"), "binding")
    if (
        ed25519.get("key_status") != "active"
        or ed25519.get("chain_head") != head.get("chain_head")
        or ed25519.get("chain_head_ref")
        != f"attestations/{payload.get('date')}/chain_head.json"
        or payload.get("date") != index.get("date")
    ):
        raise ContractError("Ed25519 binding does not match the latest daily head")
    _verify_legacy_plane(
        root, index, head, public, registry_row, verify_datasets=verify_datasets
    )

    chain_index = _load(root / "attestations/chain-index.json", "chain index")
    dated_refs = [
        ref
        for ref in chain_index.get("heads", {}).values()
        if isinstance(ref, str) and ref.startswith(f"attestations/{payload['date']}/")
    ]
    if dated_refs != [f"attestations/{payload['date']}/chain_head.json"]:
        raise ContractError("duplicate-date attestation ambiguity detected")
    dated_binding = root / f"attestations/{payload['date']}/binding.json"
    if not dated_binding.is_file() or dated_binding.read_bytes() != (root / "attestations/latest/binding.json").read_bytes():
        raise ContractError("latest binding is stale or not the dated binding")

    observed_at = _parse_time(health_binding.get("observed_at"), "health observation time")
    if current < published_at or current < observed_at:
        raise ContractError("attestation timestamps are in the future")
    age_seconds = max(
        (current - published_at).total_seconds(),
        (current - observed_at).total_seconds(),
    )
    if age_seconds > max_age:
        raise ContractError("served attestation is stale")

    datasets = health.get("datasets")
    if not isinstance(datasets, list) or not datasets:
        raise ContractError("health dataset array is invalid")
    dataset_ids = [row.get("dataset_id") for row in datasets if isinstance(row, dict)]
    if len(dataset_ids) != len(datasets) or any(not isinstance(item, str) or not item for item in dataset_ids):
        raise ContractError("health dataset identifiers are invalid")
    if len(dataset_ids) != len(set(dataset_ids)):
        raise ContractError("health dataset identifiers are ambiguous")
    expected_health = {
        "artifact_ref": "health/latest.json",
        "artifact_sha256": _digest_bytes(health_path.read_bytes()),
        "dataset_count": len(dataset_ids),
        "dataset_ids_sha256": _digest_bytes(canonical(sorted(dataset_ids))),
        "observed_at": health.get("checked_at"),
    }
    if health_binding != expected_health:
        raise ContractError("health digest/count/time binding does not match served health")

    rekor = _verify_rekor(root, binding.get("rekor"), expected_health["artifact_sha256"])
    if require_rekor and rekor is None:
        raise ContractError("required Rekor proof reference is missing")
    claims = {
        "artifact_signed": True,
        "rekor_witnessed": rekor is not None,
        "source_truth_verified": False,
    }
    if binding.get("claims") != claims:
        raise ContractError("published trust claims do not match verified evidence")
    return {
        "schema": "datapulse/v1/attestation-verification-result",
        "claims": claims,
        "freshness": {
            "status": "current",
            "age_seconds": int(age_seconds),
            "max_age_seconds": max_age,
        },
        "health": expected_health,
        "ed25519": ed25519,
        "rekor": rekor,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parent.parent)
    parser.add_argument("--now")
    parser.add_argument("--require-rekor", action="store_true")
    parser.add_argument("--allow-unattested-health", action="store_true")
    parser.add_argument("--head-only", action="store_true")
    args = parser.parse_args()
    now = _parse_time(args.now, "verification time") if args.now else None
    try:
        result = verify_contract(
            args.root,
            now=now,
            require_rekor=args.require_rekor,
            verify_datasets=not args.head_only,
        )
    except ContractError as error:
        allowed_reasons = {
            "latest binding is missing or invalid",
            "served attestation is stale",
            "health digest/count/time binding does not match served health",
        }
        if args.allow_unattested_health and str(error) in allowed_reasons:
            if str(error) == "latest binding is missing or invalid":
                try:
                    verify_unbound_legacy_plane(
                        args.root, now=now, verify_datasets=not args.head_only
                    )
                except ContractError as legacy_error:
                    print(f"verify_attestation_binding.py: {legacy_error}")
                    return 1
            result = {
                "schema": "datapulse/v1/attestation-verification-result",
                "claims": {
                    "artifact_signed": False,
                    "rekor_witnessed": False,
                    "source_truth_verified": False,
                },
                "freshness": {"status": "unattested"},
                "reason": str(error),
            }
            print(json.dumps(result, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
            return 0
        print(f"verify_attestation_binding.py: {error}")
        return 1
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
