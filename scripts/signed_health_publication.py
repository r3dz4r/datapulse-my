#!/usr/bin/env python3
"""Fixture-staged exact health snapshot signing, offline verification and publication.

No credential discovery, network transport, production namespace or key loading.
A future operator adapter must inject a signer and an immutable-create transport.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import re
import subprocess
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import Any, Protocol

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

try:
    from scripts.verify_attestation_binding import ATTESTATION_KEY_PURPOSE, canonical
except ImportError:
    from verify_attestation_binding import ATTESTATION_KEY_PURPOSE, canonical

PACKAGE_SCHEMA = "datapulse/v1/signed-health-package"
BINDING_SCHEMA = "datapulse/v1/signed-health-binding"
RESPONSE_SCHEMA = "datapulse/v1/signed-health-response"
POINTER_SCHEMA = "datapulse/v1/signed-health-pointer"
DOMAIN = b"datapulse/v1/signed-health-binding\x00"
POLICY = "health-observation-36h-v1"
MAX_AGE_SECONDS = 129600
FUTURE_SKEW_SECONDS = 300
MAX_PACKAGE_BYTES = 8 * 1024 * 1024
MAX_HEALTH_BYTES = 5 * 1024 * 1024
MAX_BINDING_BYTES = 4096
MAX_REGISTRY_BYTES = 256 * 1024
PREFIX = "signed-health/v1/"
LATEST_KEY = PREFIX + "latest.json"
DIGEST = re.compile(r"[0-9a-f]{64}")
COMMIT = re.compile(r"[0-9a-f]{40}")
KEY_ID = re.compile(r"ed25519-[0-9a-f]{16}")
TIME = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}(?:\.[0-9]{1,6})?(?:Z|\+00:00)")
PACKAGE_FIELDS = {"schema", "version", "health_base64", "binding_base64", "signature_base64"}
BINDING_FIELDS = {"schema", "version", "subject", "health_sha256", "health_bytes", "observed_at", "assembled_at", "signed_at", "source_commit", "key_id", "signer_public_key_sha256", "algorithm", "key_purpose", "policy", "claim_scope", "source_truth_verified"}


class PublicationError(ValueError):
    """A bounded reason token safe for operator or consumer reporting."""


def _require(condition: bool, reason: str) -> None:
    if not condition:
        raise PublicationError(reason)


def digest(raw: bytes) -> str:
    """Return the content identity of exact bytes."""
    return hashlib.sha256(raw).hexdigest()


def b64(raw: bytes) -> str:
    """Encode bytes in canonical standard padded base64."""
    return base64.b64encode(raw).decode("ascii")


def unb64(value: object, limit: int) -> bytes:
    """Reject noncanonical, malformed and oversized byte representations."""
    _require(isinstance(value, str) and len(value) <= 4 * ((limit + 2) // 3), "invalid_base64")
    try:
        raw = base64.b64decode(value, validate=True)
    except (ValueError, UnicodeError) as error:
        raise PublicationError("invalid_base64") from error
    _require(len(raw) <= limit and b64(raw) == value, "invalid_base64")
    return raw


def strict_json(raw: bytes, limit: int) -> dict[str, Any]:
    """Parse bounded UTF-8 JSON, rejecting duplicates and nonfinite numbers."""
    _require(type(raw) is bytes and 0 < len(raw) <= limit, "invalid_json_size")

    def pairs(items: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in items:
            _require(key not in result, "duplicate_json_key")
            result[key] = value
        return result

    def number(text: str) -> float:
        result = float(text)
        _require(result not in (float("inf"), float("-inf")), "invalid_json_number")
        return result

    def integer(text: str) -> int:
        try:
            result = int(text)
            _require(float(result) not in (float("inf"), float("-inf")), "invalid_json_number")
            return result
        except OverflowError as error:
            raise PublicationError("invalid_json_number") from error

    def invalid_constant(_: str) -> None:
        raise PublicationError("invalid_json_number")

    try:
        value = json.loads(raw.decode("utf-8"), object_pairs_hook=pairs, parse_int=integer, parse_float=number, parse_constant=invalid_constant)
    except (UnicodeError, ValueError, RecursionError) as error:
        if isinstance(error, PublicationError):
            raise
        raise PublicationError("invalid_json") from error
    _require(isinstance(value, dict), "invalid_json_object")

    def depth(item: Any, level: int) -> None:
        _require(level <= 64, "invalid_json_depth")
        if isinstance(item, dict):
            for child in item.values():
                depth(child, level + 1)
        elif isinstance(item, list):
            for child in item:
                depth(child, level + 1)

    depth(value, 0)
    return value


def timestamp(value: object) -> float:
    """Strict UTC RFC3339 instant (up to six fractional digits), in seconds."""
    _require(isinstance(value, str) and TIME.fullmatch(value) is not None, "invalid_timestamp")
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()
    except ValueError as error:
        raise PublicationError("invalid_timestamp") from error


def _token(value: object, pattern: re.Pattern[str], reason: str) -> str:
    _require(isinstance(value, str) and pattern.fullmatch(value) is not None, reason)
    return value


def trusted_key(registry: dict[str, Any], key_id: str, signed_at: str, now: str) -> bytes:
    """Use the separately trusted probe registry, with stricter ambiguity checks."""
    _require(isinstance(registry, dict) and registry.get("schema") == "datapulse/v2/probe-key-registry" and type(registry.get("version")) is int and registry["version"] == 2, "invalid_registry")
    rows = registry.get("keys")
    _require(isinstance(rows, list) and bool(rows) and all(isinstance(row, dict) for row in rows), "invalid_registry")
    ids = [_token(row.get("key_id"), KEY_ID, "invalid_key_identity") for row in rows]
    _require(len(set(ids)) == len(ids), "ambiguous_key")
    active = [row for row in rows if row.get("purpose") == ATTESTATION_KEY_PURPOSE and row.get("status") == "active"]
    _require(len(active) == 1 and active[0]["key_id"] == key_id and registry.get("current_key_id") == key_id, "inactive_or_ambiguous_key")
    row = active[0]
    _require(row.get("algorithm") == "Ed25519", "wrong_algorithm")
    _require(row.get("compromised_at") is None and row.get("revoked_at") is None, "revoked_or_compromised_key")
    start, end = timestamp(row.get("not_before")), timestamp(row.get("not_after"))
    _require(start <= timestamp(signed_at) <= end and start <= timestamp(now) <= end, "key_outside_window")
    public = unb64(row.get("public_key_base64"), 32)
    _require(len(public) == 32 and "ed25519-" + digest(public)[:16] == key_id, "key_identity_mismatch")
    return public


def _health(raw: bytes) -> dict[str, Any]:
    health = strict_json(raw, MAX_HEALTH_BYTES)
    timestamp(health.get("checked_at"))
    _require(health.get("schema") == "datapulse/v0.4/dataset-health" and isinstance(health.get("_trust_summary"), dict), "invalid_health")
    rows = health.get("datasets")
    _require(isinstance(rows, list) and bool(rows), "invalid_health")
    ids: set[str] = set()
    for row in rows:
        _require(isinstance(row, dict), "invalid_health")
        identifier = row.get("dataset_id")
        _require(isinstance(identifier, str) and bool(identifier) and identifier not in ids and isinstance(row.get("status"), str) and bool(row["status"]), "invalid_health")
        ids.add(identifier)
    return health


def build_package(health_bytes: bytes, *, registry: dict[str, Any], key_id: str, signer: Callable[[bytes], bytes], assembled_at: str, signed_at: str, source_commit: str) -> bytes:
    """Freeze once, bind every byte, sign with an injected authority and self-verify."""
    _require(type(health_bytes) is bytes, "health_not_frozen")
    health = _health(health_bytes)
    public = trusted_key(registry, key_id, signed_at, signed_at)
    binding = {
        "schema": BINDING_SCHEMA, "version": 1, "subject": "health/latest.json",
        "health_sha256": digest(health_bytes), "health_bytes": len(health_bytes),
        "observed_at": health["checked_at"], "assembled_at": assembled_at, "signed_at": signed_at,
        "source_commit": source_commit, "key_id": key_id, "signer_public_key_sha256": digest(public),
        "algorithm": "Ed25519", "key_purpose": ATTESTATION_KEY_PURPOSE, "policy": POLICY,
        "claim_scope": "exact-health-snapshot", "source_truth_verified": False,
    }
    binding_bytes = canonical(binding)
    try:
        signature = signer(DOMAIN + binding_bytes)
    except Exception:
        # Injected signers may include secrets in their error messages.
        raise PublicationError("signer_unavailable") from None
    _require(type(signature) is bytes and len(signature) == 64, "invalid_signature")
    package = canonical({"schema": PACKAGE_SCHEMA, "version": 1, "health_base64": b64(health_bytes), "binding_base64": b64(binding_bytes), "signature_base64": b64(signature)})
    verify_package(package, registry=registry, now=signed_at)
    return package


def verify_package(package: bytes, *, registry: dict[str, Any], now: str, expected_publication: str | None = None, minimum_observed_at: str | None = None) -> dict[str, Any]:
    """Offline verification with caller clock and optional retained anti-replay floor."""
    identity = digest(package)
    if expected_publication is not None:
        _token(expected_publication, DIGEST, "invalid_publication")
        _require(identity == expected_publication, "publication_mismatch")
    obj = strict_json(package, MAX_PACKAGE_BYTES)
    _require(set(obj) == PACKAGE_FIELDS and obj["schema"] == PACKAGE_SCHEMA and type(obj["version"]) is int and obj["version"] == 1, "invalid_package")
    health_bytes = unb64(obj["health_base64"], MAX_HEALTH_BYTES)
    binding_bytes = unb64(obj["binding_base64"], MAX_BINDING_BYTES)
    signature = unb64(obj["signature_base64"], 64)
    binding = strict_json(binding_bytes, MAX_BINDING_BYTES)
    _require(set(binding) == BINDING_FIELDS and binding["schema"] == BINDING_SCHEMA and type(binding["version"]) is int and binding["version"] == 1, "invalid_binding")
    _require(binding["subject"] == "health/latest.json" and binding["claim_scope"] == "exact-health-snapshot" and binding["source_truth_verified"] is False, "invalid_claim_scope")
    _require(binding["policy"] == POLICY, "unsupported_policy")
    _require(binding["algorithm"] == "Ed25519" and binding["key_purpose"] == ATTESTATION_KEY_PURPOSE, "wrong_signing_purpose")
    _token(binding["source_commit"], COMMIT, "invalid_source_commit")
    _token(binding["health_sha256"], DIGEST, "invalid_health_digest")
    _token(binding["signer_public_key_sha256"], DIGEST, "invalid_signer_digest")
    _token(binding["key_id"], KEY_ID, "invalid_key_identity")
    _require(type(binding["health_bytes"]) is int and binding["health_bytes"] == len(health_bytes), "health_size_mismatch")
    _require(digest(health_bytes) == binding["health_sha256"], "health_digest_mismatch")
    health = _health(health_bytes)
    _require(health["checked_at"] == binding["observed_at"], "observation_mismatch")
    observed, assembled, signed, current = [timestamp(value) for value in (binding["observed_at"], binding["assembled_at"], binding["signed_at"], now)]
    _require(observed <= assembled <= signed and signed <= current + FUTURE_SKEW_SECONDS, "invalid_time_order")
    _require(-FUTURE_SKEW_SECONDS <= current - observed <= MAX_AGE_SECONDS, "outside_freshness_policy")
    if minimum_observed_at is not None:
        _require(observed >= timestamp(minimum_observed_at), "replay_below_floor")
    public = trusted_key(registry, binding["key_id"], binding["signed_at"], now)
    _require(digest(public) == binding["signer_public_key_sha256"], "signer_identity_mismatch")
    _require(len(signature) == 64, "invalid_signature")
    try:
        Ed25519PublicKey.from_public_bytes(public).verify(signature, DOMAIN + binding_bytes)
    except (InvalidSignature, ValueError) as error:
        raise PublicationError("invalid_signature") from error
    return {"verified": True, "publication_sha256": identity, "observed_at": binding["observed_at"], "age_seconds": current - observed, "age_authenticated": False, "policy": POLICY, "source_truth_verified": False}


class PublicationTransport(Protocol):
    """Injected destination-aware storage; create MUST reject different existing bytes.

    A real adapter needs immutable-create semantics or externally enforced writer
    serialization. A KV GET followed by blind PUT does not satisfy this contract.
    """

    def get(self, destination: str, key: str) -> bytes | None: ...
    def create(self, destination: str, key: str, value: bytes) -> None: ...
    def put_pointer(self, destination: str, key: str, value: bytes) -> None: ...


def object_key(identity: str) -> str:
    """Construct only a safe content-addressed key."""
    return PREFIX + "objects/" + _token(identity, DIGEST, "invalid_publication") + ".json"


def publish_package(package: bytes, *, destination: str, transport: PublicationTransport, registry: dict[str, Any], now: str) -> str:
    """Verify, immutable-create, exact read-back verify, then advance latest."""
    _require(isinstance(destination, str) and re.fullmatch(r"[A-Za-z0-9_-]{1,128}", destination) is not None, "explicit_destination_required")
    identity = verify_package(package, registry=registry, now=now)["publication_sha256"]
    key = object_key(identity)
    existing = transport.get(destination, key)
    _require(existing is None or existing == package, "immutable_collision")
    if existing is None:
        transport.create(destination, key, package)
    received = transport.get(destination, key)
    _require(received == package, "readback_mismatch")
    verify_package(received, registry=registry, now=now, expected_publication=identity)
    transport.put_pointer(destination, LATEST_KEY, canonical({"schema": POINTER_SCHEMA, "publication_sha256": identity}))
    return identity


def response_envelope(package: bytes) -> bytes:
    """Carry the complete immutable object verbatim for independent verification."""
    return canonical({"schema": RESPONSE_SCHEMA, "publication_sha256": digest(package), "package_base64": b64(package)})


def verify_response(raw: bytes, *, registry: dict[str, Any], now: str, expected_publication: str | None = None, minimum_observed_at: str | None = None) -> dict[str, Any]:
    """Independently check a served envelope; never trust the HTTP verdict."""
    value = strict_json(raw, 12 * 1024 * 1024)
    _require(set(value) == {"schema", "publication_sha256", "package_base64"} and value["schema"] == RESPONSE_SCHEMA, "invalid_response")
    identity = _token(value["publication_sha256"], DIGEST, "invalid_publication")
    if expected_publication is not None:
        _require(identity == expected_publication, "publication_mismatch")
    return verify_package(unb64(value["package_base64"], MAX_PACKAGE_BYTES), registry=registry, now=now, expected_publication=identity, minimum_observed_at=minimum_observed_at)


class FixtureStorage:
    """Disposable, in-memory transport; never contacts external storage."""

    def __init__(self) -> None:
        self.values: dict[tuple[str, str], bytes] = {}
        self.events: list[tuple[str, str]] = []

    def get(self, destination: str, key: str) -> bytes | None:
        """Read one isolated value."""
        self.events.append(("get", key))
        return self.values.get((destination, key))

    def create(self, destination: str, key: str, value: bytes) -> None:
        """Perform conditional immutable creation in this single-process fixture."""
        self.events.append(("create", key))
        _require((destination, key) not in self.values or self.values[destination, key] == value, "immutable_collision")
        self.values[destination, key] = value

    def put_pointer(self, destination: str, key: str, value: bytes) -> None:
        """Replace just the latest pointer."""
        self.events.append(("pointer", key))
        _require(key == LATEST_KEY, "invalid_pointer_key")
        self.values[destination, key] = value


def fixture() -> tuple[bytes, dict[str, Any], Ed25519PrivateKey, str]:
    """Generate disposable keys in memory with the existing key-id convention."""
    private = Ed25519PrivateKey.generate()
    public = private.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
    key_id = "ed25519-" + digest(public)[:16]
    registry = {"schema": "datapulse/v2/probe-key-registry", "version": 2, "current_key_id": key_id, "keys": [{"key_id": key_id, "algorithm": "Ed25519", "purpose": ATTESTATION_KEY_PURPOSE, "status": "active", "public_key_base64": b64(public), "not_before": "2026-01-01T00:00:00Z", "not_after": "2027-01-01T00:00:00Z", "compromised_at": None}]}
    raw = canonical({"schema": "datapulse/v0.4/dataset-health", "checked_at": "2026-10-01T00:00:00Z", "_trust_summary": {"pipeline_heartbeat_at": "2026-10-01T00:00:01Z"}, "datasets": [{"dataset_id": "fixture", "status": "fresh", "extra": ["preserved", 123]}]}) + b"\n"
    return raw, registry, private, key_id


def exercise_handler(values: dict[str, bytes], registry: dict[str, Any] | None, *, now: str, path: str = "/health/verified/latest.json", crypto_available: bool = True, assets_available: bool = True, ed25519_available: bool = True, method: str = "GET") -> tuple[int, bytes]:
    """Run the actual Pages handler offline with Node/WebCrypto and isolated mocks."""
    handler = Path(__file__).resolve().parents[1] / "functions/health/verified/[[path]].js"
    harness = r'''
import { webcrypto } from "node:crypto";
import { readFileSync } from "node:fs";
const input = JSON.parse(readFileSync(0, "utf8"));
Object.defineProperty(globalThis, "crypto", {value: input.crypto_available ? (input.ed25519_available ? webcrypto : {subtle:{digest:webcrypto.subtle.digest.bind(webcrypto.subtle), importKey:async () => {throw Error("unsupported Ed25519");}}}) : {}, configurable: true});
Date.now = () => Date.parse(input.now);
const { onRequest } = await import(input.handler);
const assets = {fetch: async request => {
  if (new URL(request.url).pathname !== "/.well-known/datapulse-probe-keys.json") throw Error("unexpected asset request");
  return input.registry === null ? new Response("missing", {status:404}) : new Response(input.registry);
}};
const kv = {get: async (key, type) => {
  if (type !== "arrayBuffer") throw Error("wrong KV type");
  if (!(key in input.values)) return null;
  const bytes = Buffer.from(input.values[key], "base64");
  return bytes.buffer.slice(bytes.byteOffset, bytes.byteOffset + bytes.byteLength);
}};
const response = await onRequest({request: new Request("https://fixture.invalid" + input.path, {method:input.method}), env: {DATAPULSE_HEALTH_INDEX:kv, ...(input.assets_available ? {ASSETS:assets} : {})}});
process.stdout.write(JSON.stringify({status:response.status, body:Buffer.from(await response.arrayBuffer()).toString("base64"), cache:response.headers.get("Cache-Control")}));
'''
    data = {"handler": handler.as_uri(), "values": {key: b64(value) for key, value in values.items()}, "registry": canonical(registry).decode() if registry is not None else None, "now": now, "path": path, "crypto_available": crypto_available, "ed25519_available": ed25519_available, "assets_available": assets_available, "method": method}
    result = subprocess.run(["node", "--experimental-default-type=module", "--input-type=module", "-e", harness], input=canonical(data), capture_output=True, timeout=20)
    _require(result.returncode == 0, "fixture_handler_failed")
    output = strict_json(result.stdout, 16 * 1024 * 1024)
    _require(output.get("cache") == "no-store", "fixture_cache_policy_failed")
    return output["status"], unb64(output["body"], 12 * 1024 * 1024)


def quick_test() -> dict[str, Any]:
    """Exercise freeze/sign/publish/actual handler/independent Python consumer."""
    raw, registry, private, key_id = fixture()
    now = "2026-10-01T00:01:00Z"
    package = build_package(raw, registry=registry, key_id=key_id, signer=private.sign, assembled_at=now, signed_at=now, source_commit="eaf56e5fc910ac380b270ff0f655adc9bd0d658e")
    storage = FixtureStorage()
    identity = publish_package(package, destination="fixture", transport=storage, registry=registry, now=now)
    status, body = exercise_handler({key: value for (destination, key), value in storage.values.items()}, registry, now=now)
    _require(status == 200, "fixture_handler_unavailable")
    result = verify_response(body, registry=registry, now=now, expected_publication=identity)
    return {"ok": True, "fixture_only": True, "publisher": "verified_readback_before_pointer", "handler_status": status, "consumer_verified": result["verified"], "age_seconds": result["age_seconds"], "writes": sum(event[0] in {"create", "pointer"} for event in storage.events), "source_truth_verified": False}


def main(argv: list[str] | None = None) -> int:
    """Fixture exercise or offline verification; never load a private key or publish."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--quick-test", action="store_true")
    parser.add_argument("--in", dest="input", type=Path, help="Explicit response envelope for offline verification")
    parser.add_argument("--registry", type=Path, help="Separately trusted public registry")
    parser.add_argument("--now", help="Explicit consumer clock, UTC RFC3339")
    parser.add_argument("--minimum-observed-at")
    parser.add_argument("--expected-publication")
    args = parser.parse_args(argv)
    try:
        if args.quick_test:
            _require(not any((args.input, args.registry, args.now, args.minimum_observed_at, args.expected_publication)), "ambiguous_cli_mode")
            result = quick_test()
        else:
            _require(bool(args.input and args.registry and args.now), "explicit_verifier_inputs_required")
            result = verify_response(args.input.read_bytes(), registry=strict_json(args.registry.read_bytes(), MAX_REGISTRY_BYTES), now=args.now, minimum_observed_at=args.minimum_observed_at, expected_publication=args.expected_publication)
        print(json.dumps(result, sort_keys=True, separators=(",", ":")))
        return 0
    except (PublicationError, OSError, subprocess.SubprocessError) as error:
        reason = str(error) if isinstance(error, PublicationError) else "local_io_failure"
        print(json.dumps({"ok": False, "error": reason}, separators=(",", ":")))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
