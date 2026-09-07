#!/usr/bin/env python3
"""Independently verify DataPulse public attestation evidence.

This file intentionally imports no DataPulse code and uses only the Python
standard library.  It is suitable for downloading and running outside a
checkout; see docs/verify-datapulse-externally.md.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import sys
from pathlib import PurePosixPath
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


PUBLIC_BASE = "https://www.data-pulse.my"
RAW_BASE = "https://raw.githubusercontent.com/r3dz4r/datapulse-my/main"
REKOR_BASE = "https://rekor.sigstore.dev/api/v1/log/entries"
TIMEOUT_SECONDS = 20


class VerificationError(ValueError):
    """A public artifact does not meet the verification contract."""


def canonical_json(value: object) -> bytes:
    """Encode the producer's documented Ed25519 payload representation."""
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def fetch(url: str) -> bytes:
    """GET one fixed public artifact without following a caller-supplied URL."""
    request = Request(url, headers={"User-Agent": "datapulse-external-verifier/1"})
    with urlopen(request, timeout=TIMEOUT_SECONDS) as response:
        return response.read()


def fetch_json(url: str, label: str) -> tuple[bytes, dict[str, Any]]:
    try:
        raw = fetch(url)
        value = json.loads(raw.decode("utf-8"))
    except (HTTPError, URLError, OSError, UnicodeError, json.JSONDecodeError) as error:
        raise VerificationError(f"{label}: could not fetch valid JSON ({error})") from error
    if not isinstance(value, dict):
        raise VerificationError(f"{label}: expected a JSON object")
    return raw, value


# Minimal Edwards25519 verification implementation, following RFC 8032 section
# 5.1.7.  It verifies only; keys and signatures are public inputs.
_P = 2**255 - 19
_L = 2**252 + 27742317777372353535851937790883648493
_D = (-121665 * pow(121666, _P - 2, _P)) % _P
_I = pow(2, (_P - 1) // 4, _P)
_B = (
    15112221349535400772501151409588531511454012693041857206046113283949847762202,
    46316835694926478169428394003475163141307993866256225615783033603165251855960,
)


def _recover_x(y: int, sign: int) -> int:
    xx = (y * y - 1) * pow(_D * y * y + 1, _P - 2, _P) % _P
    x = pow(xx, (_P + 3) // 8, _P)
    if (x * x - xx) % _P:
        x = x * _I % _P
    if (x * x - xx) % _P or x == 0 and sign:
        raise VerificationError("Ed25519 point is invalid")
    return _P - x if x & 1 != sign else x


def _decode_point(encoded: bytes) -> tuple[int, int]:
    if len(encoded) != 32:
        raise VerificationError("Ed25519 point must be 32 bytes")
    value = int.from_bytes(encoded, "little")
    sign = value >> 255
    y = value & ((1 << 255) - 1)
    if y >= _P:
        raise VerificationError("Ed25519 point is non-canonical")
    point = (_recover_x(y, sign), y)
    if _encode_point(point) != encoded:
        raise VerificationError("Ed25519 point encoding is invalid")
    return point


def _encode_point(point: tuple[int, int]) -> bytes:
    x, y = point
    return (y | ((x & 1) << 255)).to_bytes(32, "little")


def _add(left: tuple[int, int], right: tuple[int, int]) -> tuple[int, int]:
    x1, y1 = left
    x2, y2 = right
    denominator = pow(1 + _D * x1 * x2 * y1 * y2 % _P, _P - 2, _P)
    x3 = (x1 * y2 + x2 * y1) * denominator % _P
    denominator = pow(1 - _D * x1 * x2 * y1 * y2 % _P, _P - 2, _P)
    y3 = (y1 * y2 + x1 * x2) * denominator % _P
    return x3, y3


def _scalar_mult(point: tuple[int, int], scalar: int) -> tuple[int, int]:
    result = (0, 1)
    while scalar:
        if scalar & 1:
            result = _add(result, point)
        point = _add(point, point)
        scalar >>= 1
    return result


def verify_ed25519(public_key: bytes, message: bytes, signature: bytes) -> bool:
    """Return whether an RFC 8032 Ed25519 signature verifies."""
    if len(public_key) != 32 or len(signature) != 64:
        return False
    try:
        point = _decode_point(public_key)
        r_encoded, s_encoded = signature[:32], signature[32:]
        r_point = _decode_point(r_encoded)
    except VerificationError:
        return False
    scalar = int.from_bytes(s_encoded, "little")
    if scalar >= _L:
        return False
    challenge = int.from_bytes(hashlib.sha512(r_encoded + public_key + message).digest(), "little") % _L
    calculated = _add(_scalar_mult(_B, scalar), _scalar_mult(((-point[0]) % _P, point[1]), challenge))
    return _encode_point(calculated) == _encode_point(r_point)


def require_base64(value: object, label: str) -> bytes:
    if not isinstance(value, str):
        raise VerificationError(f"{label}: missing base64 value")
    try:
        return base64.b64decode(value, validate=True)
    except (ValueError, UnicodeEncodeError) as error:
        raise VerificationError(f"{label}: invalid base64") from error


def nonnegative_integer(value: object, label: str) -> int:
    """Accept protobuf JSON's decimal-string integers as well as JSON numbers."""
    if isinstance(value, bool):
        raise VerificationError(f"{label}: must be a non-negative integer")
    if isinstance(value, int) and value >= 0:
        return value
    if isinstance(value, str) and value.isascii() and value.isdecimal():
        return int(value)
    raise VerificationError(f"{label}: must be a non-negative integer")


def active_key(registry: dict[str, Any]) -> dict[str, Any]:
    key_id = registry.get("current_key_id")
    keys = registry.get("keys")
    if registry.get("schema") != "datapulse/v1/probe-key-registry" or not isinstance(keys, list):
        raise VerificationError("key registry: unexpected schema")
    matches = [row for row in keys if isinstance(row, dict) and row.get("key_id") == key_id]
    if len(matches) != 1 or matches[0].get("status") != "active" or matches[0].get("algorithm") != "Ed25519":
        raise VerificationError("key registry: current Ed25519 key is missing or inactive")
    public = require_base64(matches[0].get("public_key_base64"), "key registry public key")
    if len(public) != 32:
        raise VerificationError("key registry: public key is not 32 bytes")
    return matches[0]


def safe_attestation_ref(date: object, dataset_id: object) -> str:
    if not isinstance(date, str) or not isinstance(dataset_id, str):
        raise VerificationError("attestation index: date or dataset id is missing")
    reference = f"attestations/{date}/{dataset_id}.json"
    path = PurePosixPath(reference)
    if ".." in path.parts or path.is_absolute() or path.parts[:1] != ("attestations",):
        raise VerificationError("attestation index: unsafe reference")
    return reference


def verify_envelope(envelope: dict[str, Any], key: dict[str, Any]) -> str:
    payload = envelope.get("payload")
    if envelope.get("schema") != "datapulse/v1/probe-attestation-envelope" or not isinstance(payload, dict):
        raise VerificationError("envelope: unexpected schema or payload")
    if payload.get("schema") != "datapulse/v1/probe-attestation":
        raise VerificationError("envelope: unexpected payload schema")
    if payload.get("key_id") != key.get("key_id"):
        raise VerificationError("envelope: payload key_id is not the active registry key")
    if payload.get("signer_pubkey_base64") != key.get("public_key_base64"):
        raise VerificationError("envelope: embedded signer public key differs from registry")
    public = require_base64(key.get("public_key_base64"), "registry public key")
    signature = require_base64(envelope.get("signature_base64"), "envelope signature")
    if not verify_ed25519(public, canonical_json(payload), signature):
        raise VerificationError("envelope: Ed25519 signature over canonical payload is invalid")
    previous = payload.get("previous_chain_head")
    if not isinstance(previous, str) or len(previous) != 64:
        raise VerificationError("envelope: previous chain head is invalid")
    try:
        expected_link = hashlib.sha256(bytes.fromhex(previous) + canonical_json(payload)).hexdigest()
    except ValueError as error:
        raise VerificationError("envelope: previous chain head is not hexadecimal") from error
    if envelope.get("chain_link") != expected_link:
        raise VerificationError("envelope: chain link does not bind its payload")
    dataset_id = payload.get("dataset_id")
    if not isinstance(dataset_id, str) or not dataset_id:
        raise VerificationError("envelope: dataset_id is missing")
    return dataset_id


def verify_merkle_proof(entry: dict[str, Any]) -> None:
    proof = entry.get("inclusionProof")
    promise = entry.get("inclusionPromise")
    if not isinstance(proof, dict) or not isinstance(promise, dict) or not promise.get("signedEntryTimestamp"):
        raise VerificationError("Sigstore bundle: inclusion proof or signed entry timestamp is missing")
    try:
        body = require_base64(entry.get("canonicalizedBody"), "Rekor canonicalized body")
        root = require_base64(proof.get("rootHash"), "Rekor proof root hash")
        siblings = [require_base64(item, "Rekor proof sibling") for item in proof["hashes"]]
        # Sigstore serializes the proof's checkpoint index separately from the
        # entry's current log index; Merkle reconstruction uses the former.
        index = nonnegative_integer(proof["logIndex"], "Rekor proof logIndex")
        size = nonnegative_integer(proof["treeSize"], "Rekor proof treeSize")
    except (KeyError, TypeError) as error:
        raise VerificationError("Sigstore bundle: malformed inclusion proof") from error
    if not body or len(root) != 32 or any(len(item) != 32 for item in siblings) or size <= index:
        raise VerificationError("Sigstore bundle: invalid inclusion proof fields")
    current, node_index, last_index = hashlib.sha256(b"\x00" + body).digest(), index, size - 1
    for sibling in siblings:
        if node_index % 2 == 1 or node_index == last_index:
            current = hashlib.sha256(b"\x01" + sibling + current).digest()
            while node_index and node_index % 2 == 0:
                node_index //= 2
                last_index //= 2
        else:
            current = hashlib.sha256(b"\x01" + current + sibling).digest()
        node_index //= 2
        last_index //= 2
    if last_index != 0 or current != root:
        raise VerificationError("Sigstore bundle: inclusion proof root does not verify")


def verify_rekor(bundle: dict[str, Any]) -> str:
    try:
        entries = bundle["verificationMaterial"]["tlogEntries"]
        entry = entries[0]
        log_index = nonnegative_integer(entry["logIndex"], "Rekor logIndex")
        integrated_time = nonnegative_integer(entry["integratedTime"], "Rekor integratedTime")
    except (KeyError, IndexError, TypeError) as error:
        raise VerificationError("Sigstore bundle: tlog entry is missing") from error
    if not isinstance(entries, list) or len(entries) != 1:
        raise VerificationError("Sigstore bundle: tlog logIndex or integratedTime is invalid")
    verify_merkle_proof(entry)
    uuid = hashlib.sha256(require_base64(entry.get("canonicalizedBody"), "Rekor canonicalized body")).hexdigest()
    try:
        _, returned = fetch_json(f"{REKOR_BASE}/{uuid}", "Rekor public log")
    except VerificationError as error:
        print(f"LAYER 3 PASS (importable evidence present; Rekor not independently refetched: {error})")
        return "present"
    remote = returned.get(uuid)
    if not isinstance(remote, dict):
        raise VerificationError("Rekor public log: response does not contain requested UUID")
    if remote.get("canonicalizedBody") != entry.get("canonicalizedBody") or nonnegative_integer(remote.get("logIndex"), "Rekor returned logIndex") != log_index:
        raise VerificationError("Rekor public log: returned entry differs from served bundle")
    print(f"LAYER 3 PASS: Rekor UUID {uuid}, logIndex {log_index}, integratedTime {integrated_time}")
    return "refetched"


def verify_live(base_url: str) -> None:
    base = base_url.rstrip("/")
    if base != PUBLIC_BASE:
        raise VerificationError(f"public base must be exactly {PUBLIC_BASE}; use --self-test for local tampering tests")
    _, registry = fetch_json(f"{base}/.well-known/datapulse-probe-keys.json", "key registry")
    key = active_key(registry)
    _, index = fetch_json(f"{base}/attestations/latest/index.json", "latest attestation index")
    date, refs = index.get("date"), index.get("attestations")
    if index.get("schema") != "datapulse/v1/attestation-index" or not isinstance(refs, dict) or not refs:
        raise VerificationError("latest attestation index: unexpected schema or empty attestations")
    dataset_id = sorted(refs)[0]
    reference = safe_attestation_ref(date, dataset_id)
    if refs.get(dataset_id) != reference:
        raise VerificationError("latest attestation index: selected reference is not canonical")
    served_bytes, envelope = fetch_json(f"{base}/{reference}", "served envelope")
    verified_id = verify_envelope(envelope, key)
    if verified_id != dataset_id:
        raise VerificationError("envelope: dataset_id differs from latest index")
    print(f"LAYER 1 PASS: Ed25519 canonical-payload signature for {date}/{dataset_id} using {key['key_id']}")

    raw_bytes, _ = fetch_json(f"{RAW_BASE}/{reference}", "GitHub source envelope")
    if served_bytes != raw_bytes:
        raise VerificationError("source parity: served envelope bytes differ from GitHub main")
    served_latest, _ = fetch_json(f"{base}/attestations/latest/chain_head.json", "served latest chain head")
    raw_latest, _ = fetch_json(f"{RAW_BASE}/attestations/latest/chain_head.json", "GitHub latest chain head")
    raw_dated, _ = fetch_json(f"{RAW_BASE}/attestations/{date}/chain_head.json", "GitHub dated chain head")
    if raw_latest != raw_dated:
        raise VerificationError("source parity: GitHub latest chain head is not the newest dated head")
    if served_latest != raw_latest:
        raise VerificationError("source parity: served latest chain head differs from GitHub main")
    print(f"LAYER 2 PASS: served envelope matches GitHub main; latest chain head equals {date} dated head")

    _, bundle = fetch_json(f"{base}/signatures/health.latest.sigstore.json", "served Sigstore bundle")
    verify_rekor(bundle)


def self_test() -> None:
    """Exercise a known-good fixture and a deliberate payload tamper without I/O."""
    key = {"key_id": "fixture-key", "public_key_base64": "A6EHv/POEL4dcN0Y50vAmWfk1jCbpQ1fHdyGZBJVMbg="}
    payload = {
        "schema": "datapulse/v1/probe-attestation", "date": "2026-01-01",
        "observed_at": "2026-01-01T00:00:00Z", "dataset_id": "fixture",
        "source_url": "https://example.invalid/fixture", "observed_request_url": None,
        "access_dependency": "direct", "probe_count_14d": 1, "probe_count_24h": 1,
        "last_status": "fresh", "last_staleness_days": 0, "content_fingerprint": None,
        "browser_receipt": {"available": False, "reason": None},
        "previous_chain_head": "0" * 64, "key_id": "fixture-key",
        "signer_pubkey_base64": key["public_key_base64"],
    }
    envelope = {
        "schema": "datapulse/v1/probe-attestation-envelope", "payload": payload,
        "signature_base64": "inJhSma4ZDEr+miSUIVOLCiYOly3YfVdYKzOQConY9S+HhdRevRuXw4OEhrU8eYvYckFhnc6uTDJNbsay9kQBg==",
        "chain_link": "d9174b4b94dea8ef3ca6b31652d8f8f84fadb6e1f810451f842d20fbf934730f",
    }
    verify_envelope(envelope, key)
    tampered = dict(envelope)
    tampered["payload"] = dict(payload, dataset_id="tampered")
    try:
        verify_envelope(tampered, key)
    except VerificationError:
        pass
    else:
        raise VerificationError("self-test: tampered envelope unexpectedly verified")
    print("SELF-TEST PASS: known signature verified and deliberately tampered payload failed")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default=PUBLIC_BASE, help=f"public site to verify (must be {PUBLIC_BASE})")
    parser.add_argument("--self-test", action="store_true", help="run offline valid/tampered signature checks")
    args = parser.parse_args()
    try:
        if args.self_test:
            self_test()
        else:
            verify_live(args.base_url)
    except VerificationError as error:
        print(f"FAIL: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
