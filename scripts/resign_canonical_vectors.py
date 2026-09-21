#!/usr/bin/env python3
"""Re-sign canonical-form vectors through the isolated vectors signer.

The operator performs the real fixture update as the signer identity with:
``sudo -u datapulse-signer python3 scripts/resign_canonical_vectors.py``.
The client never reads, writes, or logs private key material.  It sends each
logical vector payload to the socket and accepts a result only after verifying
the returned signature using the published vector-key registry.
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import socket
import sys
from pathlib import Path
from typing import Any

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOCKET = Path("/run/datapulse-vectors/sign.sock")
DEFAULT_FIXTURE = ROOT / "scripts/tests/fixtures/canonical_vectors.json"
DEFAULT_KEYS = ROOT / "docs/.well-known/datapulse-vector-keys.json"
PURPOSE = "canonical-form-v1"
RESPONSE_LIMIT = 1 << 20


class ResignError(Exception):
    """Raised when a fixture cannot be safely re-signed."""


def canonical(value: Any) -> bytes:
    """Return the normative canonical-form bytes for a JSON value."""
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def load_active_key(path: Path) -> dict[str, Any]:
    """Load the one active canonical-vector-only key from the published registry."""
    try:
        registry = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ResignError(f"cannot load vector key registry: {error}") from error
    if registry.get("schema") != "datapulse/v1/vector-key-registry":
        raise ResignError("vector key registry has an unexpected schema")
    keys = registry.get("keys")
    if not isinstance(keys, list):
        raise ResignError("vector key registry has no keys array")
    active = [
        key
        for key in keys
        if isinstance(key, dict)
        and key.get("status") == "active"
        and isinstance(key.get("purpose"), str)
        and "canonical-form test vectors" in key["purpose"].lower()
        and "never observation receipts" in key["purpose"].lower()
    ]
    if len(active) != 1:
        raise ResignError("vector key registry must contain exactly one active vector-only key")
    key = active[0]
    if key.get("algorithm") != "Ed25519" or not isinstance(key.get("key_id"), str):
        raise ResignError("active vector key is incomplete")
    try:
        public = base64.b64decode(key["public_key_base64"], validate=True)
        Ed25519PublicKey.from_public_bytes(public)
    except (KeyError, TypeError, ValueError) as error:
        raise ResignError("active vector key has an invalid public_key_base64") from error
    return key


def request_signature(socket_path: Path, payload: Any, key: dict[str, Any]) -> str:
    """Request and verify one signature, rejecting malformed or refused responses."""
    request = {"purpose": PURPOSE, "payload": payload}
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as connection:
            connection.settimeout(10)
            connection.connect(os.fspath(socket_path))
            connection.sendall(canonical(request) + b"\n")
            response_bytes = bytearray()
            while b"\n" not in response_bytes:
                chunk = connection.recv(65536)
                if not chunk:
                    break
                response_bytes.extend(chunk)
                if len(response_bytes) > RESPONSE_LIMIT:
                    raise ResignError("signer response exceeded the size limit")
    except ResignError:
        raise
    except (OSError, ValueError) as error:
        raise ResignError(f"signer unavailable: {socket_path}: {error}") from error

    try:
        response = json.loads(bytes(response_bytes).split(b"\n", 1)[0].decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ResignError("signer response is not valid JSON") from error
    if not isinstance(response, dict):
        raise ResignError("signer response must be a JSON object")
    if response.get("status") == "error":
        reason = response.get("reason")
        raise ResignError(f"signer refused: {reason if isinstance(reason, str) else 'unspecified'}")
    if response.get("status") != "signed":
        raise ResignError("signer response has an unexpected status")
    if response.get("key_id") != key["key_id"] or response.get("algorithm") != "Ed25519":
        raise ResignError("signer response does not identify the active vector key")
    signature_b64 = response.get("signature_base64")
    if not isinstance(signature_b64, str):
        raise ResignError("signer response is missing signature_base64")
    try:
        signature = base64.b64decode(signature_b64, validate=True)
        public = Ed25519PublicKey.from_public_bytes(base64.b64decode(key["public_key_base64"], validate=True))
        public.verify(signature, canonical(payload))
    except (InvalidSignature, ValueError) as error:
        raise ResignError("signer returned a signature that does not verify") from error
    return signature_b64


def signed_payload(vector: dict[str, Any]) -> Any:
    """Return the payload signed by a positive or canonical-form vector."""
    if "payload" in vector:
        return vector["payload"]
    if "payload_a" in vector:
        return vector["payload_a"]
    raise ResignError(f"signed vector {vector.get('name')!r} has no payload")


def resign_fixture(fixture_path: Path, keys_path: Path, socket_path: Path) -> None:
    """Atomically replace every signed-vector signature after all checks succeed."""
    try:
        fixture = json.loads(fixture_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ResignError(f"cannot load fixture: {error}") from error
    if fixture.get("schema") != "datapulse/v1/canonical-form-vectors":
        raise ResignError("fixture has an unexpected schema")
    key = load_active_key(keys_path)
    groups = (fixture.get("positive"), fixture.get("canonical_form"))
    if not all(isinstance(group, list) for group in groups):
        raise ResignError("fixture is missing signed vector groups")

    # Do all socket calls before changing the in-memory fixture, then replace
    # the file once. A partial signer outage therefore cannot publish a mix.
    replacements: list[tuple[dict[str, Any], str]] = []
    for group in groups:
        assert isinstance(group, list)
        for vector in group:
            if not isinstance(vector, dict):
                raise ResignError("signed vector is not an object")
            replacements.append((vector, request_signature(socket_path, signed_payload(vector), key)))
    for vector, signature_b64 in replacements:
        vector["signature"] = {
            "algorithm": "Ed25519",
            "key_id": key["key_id"],
            "signature_base64": signature_b64,
        }
    fixture["keys"] = [key]

    temporary = fixture_path.with_name(f".{fixture_path.name}.tmp")
    try:
        temporary.write_text(json.dumps(fixture, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        os.replace(temporary, fixture_path)
    except OSError as error:
        try:
            temporary.unlink()
        except OSError:
            pass
        raise ResignError(f"cannot replace fixture: {error}") from error


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line paths for the re-signing operation."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--socket", type=Path, default=DEFAULT_SOCKET)
    parser.add_argument("--fixture", type=Path, default=DEFAULT_FIXTURE)
    parser.add_argument("--keys", type=Path, default=DEFAULT_KEYS)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Run the fail-closed re-sign operation."""
    args = parse_args(argv)
    try:
        resign_fixture(args.fixture, args.keys, args.socket)
    except ResignError as error:
        print(f"resign failed: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
