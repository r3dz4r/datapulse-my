#!/usr/bin/env python3
"""Offline behavioral tests, including the actual Pages onRequest with WebCrypto."""
from __future__ import annotations

import copy
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from scripts import signed_health_publication as shp

NOW = "2026-10-01T00:01:00Z"
COMMIT = "eaf56e5fc910ac380b270ff0f655adc9bd0d658e"
ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def material() -> dict[str, Any]:
    raw, registry, private, key_id = shp.fixture()
    package = shp.build_package(raw, registry=registry, key_id=key_id, signer=private.sign, assembled_at=NOW, signed_at=NOW, source_commit=COMMIT)
    return {"raw": raw, "registry": registry, "private": private, "key_id": key_id, "package": package}


def package_fields(material: dict[str, Any]) -> dict[str, Any]:
    return json.loads(material["package"])


def binding_fields(material: dict[str, Any]) -> dict[str, Any]:
    return json.loads(shp.unb64(package_fields(material)["binding_base64"], shp.MAX_BINDING_BYTES))


def changed_binding(material: dict[str, Any], changes: dict[str, Any], *, resign: bool = False) -> bytes:
    obj = package_fields(material)
    binding = binding_fields(material)
    binding.update(changes)
    raw = shp.canonical(binding)
    obj["binding_base64"] = shp.b64(raw)
    if resign:
        obj["signature_base64"] = shp.b64(material["private"].sign(shp.DOMAIN + raw))
    return shp.canonical(obj)


def values(package: bytes) -> dict[str, bytes]:
    identity = shp.digest(package)
    return {shp.LATEST_KEY: shp.canonical({"schema": shp.POINTER_SCHEMA, "publication_sha256": identity}), shp.object_key(identity): package}


def verify(material: dict[str, Any], package: bytes | None = None, **kwargs: Any) -> dict[str, Any]:
    return shp.verify_package(material["package"] if package is None else package, registry=material["registry"], now=kwargs.pop("now", NOW), **kwargs)


def assert_rejected(material: dict[str, Any], package: bytes, *, registry: dict[str, Any] | None = None, now: str = NOW) -> None:
    trust = material["registry"] if registry is None else registry
    with pytest.raises(shp.PublicationError):
        shp.verify_package(package, registry=trust, now=now)
    # Recompute the package's storage hash to ensure inner checks, rather than
    # only the outer hash, must discriminate these adversarial cases.
    status, body = shp.exercise_handler(values(package), trust, now=now)
    assert status == 503
    assert json.loads(body) == {"error": "verified_health_unavailable"}


def test_deterministic_construction_preserves_exact_payload(material: dict[str, Any]) -> None:
    again = shp.build_package(material["raw"], registry=material["registry"], key_id=material["key_id"], signer=material["private"].sign, assembled_at=NOW, signed_at=NOW, source_commit=COMMIT)
    assert again == material["package"]
    assert shp.unb64(package_fields(material)["health_base64"], shp.MAX_HEALTH_BYTES) == material["raw"]
    assert b"pipeline_heartbeat_at" in material["raw"]
    assert verify(material)["verified"] is True
    assert binding_fields(material)["source_truth_verified"] is False


def test_payload_mutation_rejected(material: dict[str, Any]) -> None:
    obj = package_fields(material)
    obj["health_base64"] = shp.b64(material["raw"].replace(b'"fresh"', b'"stale"'))
    assert_rejected(material, shp.canonical(obj))


def test_signature_mutation_rejected(material: dict[str, Any]) -> None:
    obj = package_fields(material)
    signature = bytearray(shp.unb64(obj["signature_base64"], 64))
    signature[0] ^= 1
    obj["signature_base64"] = shp.b64(bytes(signature))
    assert_rejected(material, shp.canonical(obj))


@pytest.mark.parametrize("field,value", [("source_commit", "a" * 40), ("assembled_at", "2026-10-01T00:00:30Z"), ("signer_public_key_sha256", "0" * 64)])
def test_altered_claims_with_unchanged_health_digest_rejected(material: dict[str, Any], field: str, value: str) -> None:
    assert_rejected(material, changed_binding(material, {field: value}))


@pytest.mark.parametrize("changes", [
    {"version": 2}, {"version": True}, {"version": 1.0}, {"policy": "unlimited"},
    {"subject": "health/trends.json"}, {"claim_scope": "dashboard"}, {"source_truth_verified": True},
    {"key_purpose": "observation-receipt-signing"}, {"algorithm": "RSA"},
    {"source_commit": "abc"}, {"source_commit": "A" * 40}, {"source_commit": "a" * 40 + "\n"},
    {"health_sha256": "0" * 64}, {"health_sha256": "0" * 64 + "\n"},
    {"health_bytes": True}, {"health_bytes": 1.0}, {"health_bytes": "123"},
    {"observed_at": "2026-09-30T00:00:00Z"}, {"unexpected": "claim"},
])
def test_signed_but_unsupported_or_mismatched_claims_rejected(material: dict[str, Any], changes: dict[str, Any]) -> None:
    assert_rejected(material, changed_binding(material, changes, resign=True))


@pytest.mark.parametrize("field,value", [
    ("signed_at", True), ("signed_at", 0), ("signed_at", None), ("signed_at", "2026-10-01"),
    ("signed_at", "2026-10-01T00:01:00"), ("signed_at", "2026-10-01T00:01:00z"),
    ("signed_at", "2026-02-30T00:01:00Z"), ("signed_at", "2026-10-01T24:01:00Z"),
    ("signed_at", "2026-10-01T00:01:60Z"), ("signed_at", "2026-10-01T00:01:00Z\n"),
    ("signed_at", "2026-10-01T00:01:00+08:00"), ("signed_at", "0000-10-01T00:01:00Z"),
    ("assembled_at", "2026-10-01T00:02:00Z"), ("assembled_at", "2026-09-30T23:59:59Z"),
])
def test_adversarial_timestamp_and_order_rejected(material: dict[str, Any], field: str, value: Any) -> None:
    assert_rejected(material, changed_binding(material, {field: value}, resign=True))


@pytest.mark.parametrize("change", [
    {"status": "revoked"}, {"status": "compromised"}, {"status": "superseded"},
    {"purpose": "observation-receipt-signing"}, {"algorithm": "RSA"},
    {"compromised_at": "2026-10-01T00:00:00Z"}, {"compromised_at": False},
    {"revoked_at": "2026-10-01T00:00:00Z"},
    {"not_after": "2026-09-30T23:59:59Z"}, {"not_before": "2026-10-01T00:02:00Z"},
    {"not_after": "2026-02-30T00:00:00Z"}, {"public_key_base64": shp.b64(bytes(32))},
])
def test_registry_key_rules_rejected(material: dict[str, Any], change: dict[str, Any]) -> None:
    trust = copy.deepcopy(material["registry"])
    trust["keys"][0].update(change)
    assert_rejected(material, material["package"], registry=trust)


@pytest.mark.parametrize("case", ["untrusted", "current", "duplicate", "two_active", "schema", "version"])
def test_registry_identity_and_ambiguity_rejected(material: dict[str, Any], case: str) -> None:
    trust = copy.deepcopy(material["registry"])
    if case == "untrusted":
        _, trust, _, _ = shp.fixture()
    elif case == "current":
        trust["current_key_id"] = "ed25519-" + "0" * 16
    elif case == "duplicate":
        trust["keys"].append(copy.deepcopy(trust["keys"][0]))
    elif case == "two_active":
        _, other, _, _ = shp.fixture()
        trust["keys"].append(other["keys"][0])
    elif case == "schema":
        trust["schema"] = "datapulse/v1/probe-key-registry"
    else:
        trust["version"] = 2.0
    assert_rejected(material, material["package"], registry=trust)


def test_consumer_window_is_required_even_when_signing_window_was_valid(material: dict[str, Any]) -> None:
    trust = copy.deepcopy(material["registry"])
    trust["keys"][0]["not_after"] = NOW
    assert_rejected(material, material["package"], registry=trust, now="2026-10-01T00:01:01Z")


@pytest.mark.parametrize("now", ["2026-10-02T12:00:01Z", "2026-09-30T23:54:59Z"])
def test_valid_stale_or_future_snapshot_rejected(material: dict[str, Any], now: str) -> None:
    assert_rejected(material, material["package"], now=now)


def test_replay_floor_and_identity_floor(material: dict[str, Any]) -> None:
    floor = "2026-10-01T00:00:01Z"
    with pytest.raises(shp.PublicationError, match="replay_below_floor"):
        verify(material, minimum_observed_at=floor)
    status, _ = shp.exercise_handler(values(material["package"]), material["registry"], now=NOW, path="/health/verified/latest.json?minimum_observed_at=" + floor)
    assert status == 503
    with pytest.raises(shp.PublicationError, match="publication_mismatch"):
        verify(material, expected_publication="0" * 64)
    assert verify(material, minimum_observed_at="2026-10-01T00:00:00Z")["verified"]


@pytest.mark.parametrize("raw", [b'{}{}', b'{"schema":NaN}', b'{"schema":Infinity}', b'{"schema":1e999}', b'{"schema":"x","schema":"y"}', b'{"schema":"x","\\u0073chema":"y"}', b'[]', b'\xff', b'{"x":' + b'[' * 65 + b'0' + b']' * 65 + b'}'])
def test_malformed_or_duplicate_json_rejected_by_both_verifiers(material: dict[str, Any], raw: bytes) -> None:
    assert_rejected(material, raw)


@pytest.mark.parametrize("layer", ["binding", "health"])
def test_duplicate_inner_json_even_with_valid_signature_rejected(material: dict[str, Any], layer: str) -> None:
    obj = package_fields(material)
    binding = binding_fields(material)
    if layer == "health":
        raw = material["raw"].strip()[:-1] + b',"checked_at":"2026-10-01T00:00:00Z"}'
        obj["health_base64"] = shp.b64(raw)
        binding.update(health_sha256=shp.digest(raw), health_bytes=len(raw))
        binding_raw = shp.canonical(binding)
    else:
        binding_raw = shp.canonical(binding)[:-1] + b',"policy":"health-observation-36h-v1"}'
    obj["binding_base64"] = shp.b64(binding_raw)
    obj["signature_base64"] = shp.b64(material["private"].sign(shp.DOMAIN + binding_raw))
    assert_rejected(material, shp.canonical(obj))


@pytest.mark.parametrize("change", [{"version": True}, {"version": 1.0}, {"version": 2}, {"signature_base64": ""}, {"signature_base64": "@@@"}, {"health_base64": " "}, {"binding_base64": "YQ==\n"}, {"key": "embedded-untrusted-key"}])
def test_package_shape_and_proof_rejected(material: dict[str, Any], change: dict[str, Any]) -> None:
    obj = package_fields(material)
    obj.update(change)
    assert_rejected(material, shp.canonical(obj))


def test_snapshot_signature_cannot_be_borrowed(material: dict[str, Any]) -> None:
    newer = material["raw"].replace(b'00:00:00Z', b'00:00:30Z')
    package = shp.build_package(newer, registry=material["registry"], key_id=material["key_id"], signer=material["private"].sign, assembled_at=NOW, signed_at=NOW, source_commit=COMMIT)
    obj = json.loads(package)
    obj["signature_base64"] = package_fields(material)["signature_base64"]
    assert_rejected(material, shp.canonical(obj))
    with pytest.raises(shp.PublicationError, match="publication_mismatch"):
        verify(material, package, expected_publication=shp.digest(material["package"]))


def test_publisher_exact_order_and_idempotent_immutable_object(material: dict[str, Any]) -> None:
    storage = shp.FixtureStorage()
    identity = shp.publish_package(material["package"], destination="fixture", transport=storage, registry=material["registry"], now=NOW)
    key = shp.object_key(identity)
    assert storage.events == [("get", key), ("create", key), ("get", key), ("pointer", shp.LATEST_KEY)]
    assert storage.values["fixture", key] == material["package"]
    storage.events.clear()
    shp.publish_package(material["package"], destination="fixture", transport=storage, registry=material["registry"], now=NOW)
    assert storage.events == [("get", key), ("get", key), ("pointer", shp.LATEST_KEY)]


@pytest.mark.parametrize("mode", ["interrupted", "partial", "mismatch", "collision", "race_collision", "pointer_failure"])
def test_publish_failures_do_not_advance_pointer(material: dict[str, Any], mode: str) -> None:
    class FailingStorage(shp.FixtureStorage):
        def create(self, destination: str, key: str, value: bytes) -> None:
            if mode == "interrupted":
                self.events.append(("create", key))
                raise shp.PublicationError("interrupted")
            if mode == "race_collision":
                self.values[destination, key] = b"racing bad bytes"
            super().create(destination, key, value[:50] if mode == "partial" else value)
            if mode == "mismatch":
                self.values[destination, key] = b"readback mismatch"

        def put_pointer(self, destination: str, key: str, value: bytes) -> None:
            if mode == "pointer_failure":
                self.events.append(("pointer", key))
                raise shp.PublicationError("pointer unavailable")
            super().put_pointer(destination, key, value)

    storage = FailingStorage()
    old = b"old pointer"
    storage.values["fixture", shp.LATEST_KEY] = old
    key = shp.object_key(shp.digest(material["package"]))
    if mode == "collision":
        storage.values["fixture", key] = b"collision"
    with pytest.raises(shp.PublicationError):
        shp.publish_package(material["package"], destination="fixture", transport=storage, registry=material["registry"], now=NOW)
    assert storage.values["fixture", shp.LATEST_KEY] == old
    if mode != "pointer_failure":
        assert all(event[0] != "pointer" for event in storage.events)


def test_bad_signature_never_writes_and_destination_is_explicit(material: dict[str, Any]) -> None:
    storage = shp.FixtureStorage()
    bad = changed_binding(material, {"source_commit": "a" * 40})
    with pytest.raises(shp.PublicationError):
        shp.publish_package(bad, destination="fixture", transport=storage, registry=material["registry"], now=NOW)
    assert storage.events == []
    for destination in ("", "../production", "https://example.invalid", None):
        with pytest.raises(shp.PublicationError, match="explicit_destination_required"):
            shp.publish_package(material["package"], destination=destination, transport=storage, registry=material["registry"], now=NOW)
    assert storage.events == []


def test_actual_handler_response_independently_verified_by_python(material: dict[str, Any]) -> None:
    storage = shp.FixtureStorage()
    identity = shp.publish_package(material["package"], destination="fixture", transport=storage, registry=material["registry"], now=NOW)
    kv = {key: value for (_, key), value in storage.values.items()}
    for path in ("/health/verified/latest.json", f"/health/verified/{identity}.json"):
        status, body = shp.exercise_handler(kv, material["registry"], now=NOW, path=path)
        assert status == 200
        result = shp.verify_response(body, registry=material["registry"], now=NOW, expected_publication=identity)
        assert result["verified"] and result["age_seconds"] == 60
        assert result["age_authenticated"] is False
        response = json.loads(body)
        assert shp.unb64(response["package_base64"], shp.MAX_PACKAGE_BYTES) == material["package"]
        assert set(response) == {"schema", "publication_sha256", "package_base64"}


def test_pointer_before_object_and_payload_proof_substitution_fail_closed(material: dict[str, Any]) -> None:
    kv = values(material["package"])
    identity = shp.digest(material["package"])
    kv.pop(shp.object_key(identity))
    assert shp.exercise_handler(kv, material["registry"], now=NOW)[0] == 503
    kv[shp.object_key(identity)] = changed_binding(material, {"source_commit": "a" * 40}, resign=True)
    assert shp.exercise_handler(kv, material["registry"], now=NOW)[0] == 503


def test_signer_outage_old_pointer_new_unsigned_data_and_staleness(material: dict[str, Any]) -> None:
    storage = shp.FixtureStorage()
    shp.publish_package(material["package"], destination="fixture", transport=storage, registry=material["registry"], now=NOW)
    before = dict(storage.values)

    def outage(_: bytes) -> bytes:
        raise RuntimeError("never echo injected signer detail")

    with pytest.raises(shp.PublicationError, match="^signer_unavailable$"):
        package = shp.build_package(material["raw"], registry=material["registry"], key_id=material["key_id"], signer=outage, assembled_at=NOW, signed_at=NOW, source_commit=COMMIT)
        shp.publish_package(package, destination="fixture", transport=storage, registry=material["registry"], now=NOW)
    assert storage.values == before
    kv = {key: value for (_, key), value in storage.values.items()}
    kv["health/latest.json"] = material["raw"].replace(b'"fresh"', b'"stale"')
    status, body = shp.exercise_handler(kv, material["registry"], now="2026-10-01T01:00:00Z")
    assert status == 200
    result = shp.verify_response(body, registry=material["registry"], now="2026-10-01T01:00:00Z")
    assert result["age_seconds"] == 3600 and result["publication_sha256"] == shp.digest(material["package"])
    assert shp.exercise_handler(kv, material["registry"], now="2026-10-03T00:00:00Z")[0] == 503


def test_reordered_pointer_can_be_complete_but_consumer_floor_rejects(material: dict[str, Any]) -> None:
    newer = material["raw"].replace(b'00:00:00Z', b'00:00:30Z')
    package = shp.build_package(newer, registry=material["registry"], key_id=material["key_id"], signer=material["private"].sign, assembled_at=NOW, signed_at=NOW, source_commit=COMMIT)
    kv = {**values(package), **values(material["package"])}  # older pointer arrives last
    status, body = shp.exercise_handler(kv, material["registry"], now=NOW)
    assert status == 200
    assert shp.verify_response(body, registry=material["registry"], now=NOW)["publication_sha256"] == shp.digest(material["package"])
    with pytest.raises(shp.PublicationError, match="replay_below_floor"):
        shp.verify_response(body, registry=material["registry"], now=NOW, minimum_observed_at="2026-10-01T00:00:30Z")


@pytest.mark.parametrize("options", [{"crypto_available": False}, {"ed25519_available": False}, {"assets_available": False}])
def test_missing_runtime_crypto_or_trusted_assets_fails_closed(material: dict[str, Any], options: dict[str, Any]) -> None:
    assert shp.exercise_handler(values(material["package"]), material["registry"], now=NOW, **options)[0] == 503


def test_missing_registry_and_package_no_static_fallback(material: dict[str, Any]) -> None:
    assert shp.exercise_handler(values(material["package"]), None, now=NOW)[0] == 503
    assert shp.exercise_handler({"health/latest.json": material["raw"]}, material["registry"], now=NOW)[0] == 503


@pytest.mark.parametrize("pointer", [b'{}', b'{"schema":"datapulse/v1/signed-health-pointer","publication_sha256":"../health/latest.json"}', b'{"schema":"datapulse/v1/signed-health-pointer","publication_sha256":true}', b'{"schema":"x","schema":"y"}'])
def test_unsafe_or_malformed_pointer_rejected(material: dict[str, Any], pointer: bytes) -> None:
    kv = values(material["package"])
    kv[shp.LATEST_KEY] = pointer
    assert shp.exercise_handler(kv, material["registry"], now=NOW)[0] == 503


def test_oversized_package_rejected(material: dict[str, Any]) -> None:
    oversized = b" " * (shp.MAX_PACKAGE_BYTES + 1)
    assert_rejected(material, oversized)


@pytest.mark.parametrize("path,expected", [("/health/verified/nope.json", 404), ("/health/verified/../latest.json", 404), ("/health/latest.json", 404), ("/health/verified/%2e%2e.json", 404), ("/health/verified/latest.json?registry=https://evil.invalid", 400), ("/health/verified/latest.json?minimum_observed_at=x&minimum_observed_at=y", 400), ("/health/verified/latest.json?minimum_observed_at=invalid", 503)])
def test_unknown_or_unsafe_request_rejected(material: dict[str, Any], path: str, expected: int) -> None:
    assert shp.exercise_handler(values(material["package"]), material["registry"], now=NOW, path=path)[0] == expected


def test_non_get_method_rejected(material: dict[str, Any]) -> None:
    assert shp.exercise_handler(values(material["package"]), material["registry"], now=NOW, method="POST")[0] == 405


def test_response_envelope_mutation_and_identity_substitution_rejected(material: dict[str, Any]) -> None:
    response = json.loads(shp.response_envelope(material["package"]))
    response["publication_sha256"] = "0" * 64
    with pytest.raises(shp.PublicationError, match="publication_mismatch"):
        shp.verify_response(shp.canonical(response), registry=material["registry"], now=NOW)
    with pytest.raises(shp.PublicationError, match="publication_mismatch"):
        shp.verify_response(shp.response_envelope(material["package"]), registry=material["registry"], now=NOW, expected_publication="0" * 64)


def test_cli_quick_test_is_real_bounded_and_offline() -> None:
    result = subprocess.run([sys.executable, str(ROOT / "scripts/signed_health_publication.py"), "--quick-test"], capture_output=True, text=True, timeout=20)
    assert result.returncode == 0, result.stderr
    assert len(result.stdout) < 512
    summary = json.loads(result.stdout)
    assert summary == {"age_seconds": 60.0, "consumer_verified": True, "fixture_only": True, "handler_status": 200, "ok": True, "publisher": "verified_readback_before_pointer", "source_truth_verified": False, "writes": 2}
    assert all(term not in result.stdout for term in ("base64", "private", "signature", "datasets"))


def test_cli_offline_verifier_and_missing_inputs(material: dict[str, Any], tmp_path: Path) -> None:
    response = tmp_path / "response.fixture.json"
    registry = tmp_path / "registry.fixture.json"
    response.write_bytes(shp.response_envelope(material["package"]))
    registry.write_bytes(shp.canonical(material["registry"]))
    command = [sys.executable, str(ROOT / "scripts/signed_health_publication.py")]
    result = subprocess.run(command + ["--in", str(response), "--registry", str(registry), "--now", NOW], capture_output=True, text=True)
    assert result.returncode == 0
    assert json.loads(result.stdout)["verified"] is True
    result = subprocess.run(command, capture_output=True, text=True)
    assert result.returncode == 1
    assert json.loads(result.stdout) == {"ok": False, "error": "explicit_verifier_inputs_required"}
    result = subprocess.run(command + ["--quick-test", "--registry", str(registry)], capture_output=True, text=True)
    assert result.returncode == 1
    assert json.loads(result.stdout)["error"] == "ambiguous_cli_mode"


def test_existing_unsigned_publisher_cannot_target_verified_layout() -> None:
    from scripts.publish_health_index import HEALTH_ARTIFACTS, KEY
    assert not KEY.startswith(shp.PREFIX)
    assert all(not ("health/" + name).startswith(shp.PREFIX) for name in HEALTH_ARTIFACTS)


def test_freshness_boundaries_and_fractional_timestamps(material: dict[str, Any]) -> None:
    assert verify(material, now="2026-10-02T12:00:00Z")["age_seconds"] == shp.MAX_AGE_SECONDS
    assert_rejected(material, material["package"], now="2026-10-02T12:00:00.001Z")
    assert shp.exercise_handler(values(material["package"]), material["registry"], now="2026-10-02T12:00:00Z")[0] == 200
    raw = material["raw"].replace(b'00:00:00Z', b'00:00:00.123456+00:00')
    package = shp.build_package(raw, registry=material["registry"], key_id=material["key_id"], signer=material["private"].sign, assembled_at=NOW, signed_at=NOW, source_commit=COMMIT)
    status, body = shp.exercise_handler(values(package), material["registry"], now=NOW)
    assert status == 200
    assert shp.verify_response(body, registry=material["registry"], now=NOW)["observed_at"] == "2026-10-01T00:00:00.123456+00:00"


def test_float_size_matching_actual_bytes_still_rejected(material: dict[str, Any]) -> None:
    assert_rejected(material, changed_binding(material, {"health_bytes": float(len(material["raw"]))}, resign=True))


def test_handler_rechecks_registry_and_clock_in_same_runtime(material: dict[str, Any]) -> None:
    # Keep one imported module alive across requests; changing trusted assets and
    # the consumer clock must invalidate a previously successful verification.
    harness = r'''
import {webcrypto} from "node:crypto";
import {readFileSync} from "node:fs";
Object.defineProperty(globalThis, "crypto", {value:webcrypto});
const input = JSON.parse(readFileSync(0,"utf8"));
const {onRequest} = await import(input.handler);
let registry = input.registry, now = Date.parse(input.now), assetReads = 0, advanceDuringRead = false;
Date.now = () => now;
const context = {request:new Request("https://fixture.invalid/health/verified/latest.json"), env:{
  ASSETS:{fetch:async () => {assetReads++; return new Response(JSON.stringify(registry));}},
  DATAPULSE_HEALTH_INDEX:{get:async key => {
    const data = Buffer.from(input.values[key], "base64");
    if (advanceDuringRead && key.includes("/objects/")) now = Date.parse("2026-10-03T00:00:00Z");
    return data.buffer.slice(data.byteOffset,data.byteOffset+data.byteLength);
  }}
}};
const statuses = [(await onRequest(context)).status];
registry = structuredClone(registry); registry.keys[0].status = "revoked";
statuses.push((await onRequest(context)).status);
registry = input.registry; now = Date.parse("2026-10-03T00:00:00Z");
statuses.push((await onRequest(context)).status);
now = Date.parse(input.now); advanceDuringRead = true;
statuses.push((await onRequest(context)).status);
process.stdout.write(JSON.stringify({statuses,assetReads}));
'''
    data = {"handler": (ROOT / "functions/health/verified/[[path]].js").as_uri(), "registry": material["registry"], "now": NOW, "values": {key: shp.b64(raw) for key, raw in values(material["package"]).items()}}
    result = subprocess.run(["node", "--experimental-default-type=module", "--input-type=module", "-e", harness], input=shp.canonical(data), capture_output=True, timeout=20)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == {"statuses": [200, 503, 503, 503], "assetReads": 4}


def test_local_quick_test_failure_is_machine_readable_and_not_stubbed(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.setattr(shp, "exercise_handler", lambda *args, **kwargs: (503, b'{}'))
    assert shp.main(["--quick-test"]) == 1
    assert json.loads(capsys.readouterr().out) == {"ok": False, "error": "fixture_handler_unavailable"}


@pytest.mark.parametrize("layer", ["package", "binding", "health"])
def test_utf8_bom_not_silently_stripped(material: dict[str, Any], layer: str) -> None:
    obj = package_fields(material)
    if layer == "package":
        package = b"\xef\xbb\xbf" + material["package"]
    else:
        binding = binding_fields(material)
        if layer == "health":
            raw = b"\xef\xbb\xbf" + material["raw"]
            obj["health_base64"] = shp.b64(raw)
            binding.update(health_sha256=shp.digest(raw), health_bytes=len(raw))
            binding_raw = shp.canonical(binding)
        else:
            binding_raw = b"\xef\xbb\xbf" + shp.canonical(binding)
        obj["binding_base64"] = shp.b64(binding_raw)
        obj["signature_base64"] = shp.b64(material["private"].sign(shp.DOMAIN + binding_raw))
        package = shp.canonical(obj)
    assert_rejected(material, package)
