#!/usr/bin/env python3
"""Behavioral, REST-transport, coordination and local-runtime cases.

Every key here is generated in memory for the test only. No real key file,
credential, production endpoint or namespace is read or contacted; the only
network traffic is the loopback fixture server and the loopback Pages runtime.
"""
from __future__ import annotations

import copy
import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import pytest

from scripts import signed_health_integration as shi
from scripts import signed_health_publication as shp

NOW = "2026-10-01T00:01:00Z"
COMMIT = "eaf56e5fc910ac380b270ff0f655adc9bd0d658e"
ROOT = Path(__file__).resolve().parents[2]


# --------------------------------------------------------------------------- #
# Fixtures and helpers
# --------------------------------------------------------------------------- #


def make_material(
    *,
    observed: str = "2026-10-01T00:00:00Z",
    assembled: str = NOW,
    signed: str = NOW,
    marker: str = "signed",
    not_before: str = "2026-01-01T00:00:00Z",
    not_after: str = "2027-01-01T00:00:00Z",
) -> dict[str, Any]:
    private, key_id = shi.disposable_key()
    registry = shi.registry_fixture(private, key_id=key_id, not_before=not_before, not_after=not_after)
    health = shi.health_fixture(observed, marker=marker)
    package = shp.build_package(
        health,
        registry=registry,
        key_id=key_id,
        signer=private.sign,
        assembled_at=assembled,
        signed_at=signed,
        source_commit=COMMIT,
    )
    return {
        "private": private,
        "key_id": key_id,
        "registry": registry,
        "health": health,
        "package": package,
        "observed": observed,
        "assembled": assembled,
        "signed": signed,
        "now": NOW,
    }


def storage_values(package: bytes) -> dict[str, bytes]:
    identity = shp.digest(package)
    return {
        shp.LATEST_KEY: shp.canonical({"schema": shp.POINTER_SCHEMA, "publication_sha256": identity}),
        shp.object_key(identity): package,
    }


def make_transport(server: shi.MockKVRestServer, destination: str = "fixture", **kwargs: Any) -> shi.KVRestTransport:
    return shi.KVRestTransport(
        api_base=server.api_base,
        account_id="fixture-account",
        namespace_id="fixture-namespace",
        credential=server.credential,
        destination=destination,
        **kwargs,
    )


def publish(material: dict[str, Any], server: shi.MockKVRestServer, lock: shi.WriterLock, **overrides: Any) -> dict[str, Any]:
    transport = overrides.pop("transport", make_transport(server))
    kwargs: dict[str, Any] = {
        "registry": material["registry"],
        "key_id": material["key_id"],
        "signer": material["private"].sign,
        "assembled_at": material["assembled"],
        "signed_at": material["signed"],
        "source_commit": COMMIT,
        "destination": transport.destination,
        "transport": transport,
        "lock": lock,
        "now": material["now"],
    }
    kwargs.update(overrides)
    with lock:
        return shi.serialized_publish(material["health"], **kwargs)


@pytest.fixture
def material() -> dict[str, Any]:
    return make_material()


@pytest.fixture
def server() -> Any:
    fixture = shi.MockKVRestServer().start()
    yield fixture
    fixture.shutdown()


@pytest.fixture
def lock(tmp_path: Path) -> shi.WriterLock:
    return shi.WriterLock(shi.writer_lock_path(tmp_path, "fixture"), "fixture")


# --------------------------------------------------------------------------- #
# Cloudflare-KV-REST transport
# --------------------------------------------------------------------------- #


def test_transport_get_exact_encoded_path_and_binary_safe_bytes(server: shi.MockKVRestServer) -> None:
    transport = make_transport(server)
    key = "signed-health/v1/objects/with space.json"
    payload = bytes(range(256)) * 2
    server.storage[key] = payload
    assert transport.get("fixture", key) == payload
    call = server.calls[-1]
    assert call["method"] == "GET"
    assert call["path"] == "/accounts/fixture-account/storage/kv/namespaces/fixture-namespace/values/signed-health/v1/objects/with%20space.json"
    assert call["had_authorization"] is True
    assert call["status"] == 200


def test_transport_put_exact_paths_methods_and_body(material: dict[str, Any], server: shi.MockKVRestServer, lock: shi.WriterLock) -> None:
    result = publish(material, server, lock)
    assert result["ok"] is True
    identity = str(result["publication_sha256"])
    puts = [call for call in server.calls if call["method"] == "PUT"]
    assert [call["key"] for call in puts] == [shp.object_key(identity), shp.LATEST_KEY]
    assert [call["path"] for call in puts] == [
        "/accounts/fixture-account/storage/kv/namespaces/fixture-namespace/values/" + shp.object_key(identity),
        "/accounts/fixture-account/storage/kv/namespaces/fixture-namespace/values/" + shp.LATEST_KEY,
    ]
    assert puts[0]["body_sha256"] == shp.digest(material["package"])
    assert puts[0]["body_bytes"] == len(material["package"])
    assert server.storage[shp.LATEST_KEY] == shp.canonical({"schema": shp.POINTER_SCHEMA, "publication_sha256": identity})


def test_transport_missing_value_is_a_definite_absence(server: shi.MockKVRestServer) -> None:
    transport = make_transport(server)
    assert transport.get("fixture", shp.LATEST_KEY) is None
    assert server.calls[-1]["status"] == 404


def test_transport_rejects_api_error_envelope_as_stored_bytes(server: shi.MockKVRestServer) -> None:
    server.behaviour["error_envelope"] = True
    transport = make_transport(server)
    with pytest.raises(shi.TransportError, match="api_error_envelope") as excinfo:
        transport.get("fixture", shp.LATEST_KEY)
    assert excinfo.value.outcome == "failed"


def test_transport_bounds_oversized_responses(server: shi.MockKVRestServer) -> None:
    transport = make_transport(server, max_response_bytes=1024)
    server.storage[shp.LATEST_KEY] = b"x" * 5000
    with pytest.raises(shi.TransportError, match="response_too_large") as excinfo:
        transport.get("fixture", shp.LATEST_KEY)
    assert excinfo.value.outcome == "failed"
    assert transport.get("fixture", shp.object_key("0" * 64)) is None  # still responsive


def test_transport_read_timeout_failed_write_timeout_unknown_without_rollback_claim(server: shi.MockKVRestServer) -> None:
    transport = make_transport(server, timeout=0.3)
    server.behaviour["read_timeout"] = 1.2
    with pytest.raises(shi.TransportError) as read_error:
        transport.get("fixture", shp.LATEST_KEY)
    assert read_error.value.outcome == "failed"
    server.behaviour.pop("read_timeout")
    pointer = shp.canonical({"schema": shp.POINTER_SCHEMA, "publication_sha256": "0" * 64})
    server.behaviour["write_timeout"] = 1.2
    with pytest.raises(shi.TransportError) as write_error:
        transport.put_pointer("fixture", shp.LATEST_KEY, pointer)
    assert write_error.value.outcome == "unknown"
    assert write_error.value.phase == "put_pointer"
    # The write may have landed before the acknowledgement was lost; never claim otherwise.
    assert server.storage[shp.LATEST_KEY] == pointer
    assert "rollback" not in json.dumps(write_error.value.evidence).lower()
    # No automatic retry after an ambiguous acknowledgement.
    assert sum(1 for call in server.calls if call["method"] == "PUT") == 1


def test_transport_does_not_follow_redirect_or_forward_credential() -> None:
    origin = shi.MockKVRestServer().start()
    target = shi.MockKVRestServer().start()
    try:
        origin.behaviour["redirect"] = target.api_base + "/values/redirected"
        transport = make_transport(origin)
        with pytest.raises(shi.TransportError, match="redirect_not_followed") as excinfo:
            transport.get("fixture", shp.LATEST_KEY)
        assert excinfo.value.outcome == "failed"
        assert target.calls == []  # nothing was sent to the redirect host
        assert origin.calls[-1]["had_authorization"] is True
        assert origin.credential not in json.dumps(origin.calls)
    finally:
        origin.shutdown()
        target.shutdown()


@pytest.mark.parametrize(
    "api_base",
    [
        "http://10.0.0.1",
        "http://api.cloudflare.com/client/v4",
        "https://user:pass@api.cloudflare.com/client/v4",
        "ftp://127.0.0.1",
        "https://api.cloudflare.com/client/v4?account=1",
    ],
)
def test_transport_rejects_unsafe_or_ambiguous_api_base(api_base: str) -> None:
    with pytest.raises(shi.IntegrationError):
        shi.KVRestTransport(
            api_base=api_base,
            account_id="account",
            namespace_id="namespace",
            credential="fixture",
            destination="fixture",
        )


def test_transport_accepts_explicit_non_loopback_https_without_contacting_it() -> None:
    transport = shi.KVRestTransport(
        api_base="https://api.cloudflare.com/client/v4",
        account_id="account",
        namespace_id="namespace",
        credential="fixture",
        destination="fixture",
    )
    assert transport.path_prefix == "/client/v4"
    assert transport.calls == []


def test_transport_is_bound_to_one_destination(server: shi.MockKVRestServer) -> None:
    transport = make_transport(server)
    with pytest.raises(shi.IntegrationError, match="transport_destination_mismatch"):
        transport.get("other", shp.LATEST_KEY)
    assert server.calls == []


def test_transport_never_leaks_the_credential(server: shi.MockKVRestServer) -> None:
    secret = "SUPER-SECRET-fixture-token"
    server.credential = secret
    server.behaviour["error_envelope"] = True
    transport = make_transport(server)
    with pytest.raises(shi.TransportError) as excinfo:
        transport.get("fixture", shp.LATEST_KEY)
    blob = str(excinfo.value) + repr(excinfo.value.evidence) + json.dumps(transport.calls)
    assert secret not in blob
    assert server.calls[-1]["had_authorization"] is True


# --------------------------------------------------------------------------- #
# Destination-bound writer lock and serialized publication
# --------------------------------------------------------------------------- #


def test_writer_lock_rejects_overlapping_process(tmp_path: Path) -> None:
    path = tmp_path / "writer.lock"
    ready = tmp_path / "ready"
    child_code = (
        "import fcntl, os, time\n"
        f"fd = os.open({str(path)!r}, os.O_CREAT | os.O_RDWR, 0o600)\n"
        "fcntl.flock(fd, fcntl.LOCK_EX)\n"
        f"open({str(ready)!r}, 'w').write('ready')\n"
        "time.sleep(30)\n"
    )
    child = subprocess.Popen([sys.executable, "-c", child_code])
    try:
        deadline = time.monotonic() + 10
        while not ready.exists() and time.monotonic() < deadline:
            time.sleep(0.05)
        assert ready.exists()
        contender = shi.WriterLock(path, "fixture")
        with pytest.raises(shi.LockUnavailable, match="writer_lock_unavailable"):
            contender.acquire()
    finally:
        child.terminate()
        try:
            child.wait(timeout=5)
        except subprocess.TimeoutExpired:
            child.kill()
            child.wait(timeout=5)


def test_wrong_destination_lock_is_refused_before_any_write(material: dict[str, Any], server: shi.MockKVRestServer, tmp_path: Path) -> None:
    # This case cannot pass on a no-op: publishing must actually be gated.
    alpha = shi.WriterLock(shi.writer_lock_path(tmp_path, "alpha"), "alpha")
    transport = make_transport(server, destination="beta")
    with alpha:
        with pytest.raises(shi.IntegrationError, match="writer_lock_destination_mismatch"):
            shi.serialized_publish(
                material["health"],
                registry=material["registry"],
                key_id=material["key_id"],
                signer=material["private"].sign,
                assembled_at=material["assembled"],
                signed_at=material["signed"],
                source_commit=COMMIT,
                destination="beta",
                transport=transport,
                lock=alpha,
                now=material["now"],
            )
    assert server.calls == []


def test_publish_refuses_without_a_held_lock(material: dict[str, Any], server: shi.MockKVRestServer, tmp_path: Path) -> None:
    lock = shi.WriterLock(shi.writer_lock_path(tmp_path, "fixture"), "fixture")
    with pytest.raises(shi.IntegrationError, match="writer_lock_not_held"):
        shi.serialized_publish(
            material["health"],
            registry=material["registry"],
            key_id=material["key_id"],
            signer=material["private"].sign,
            assembled_at=material["assembled"],
            signed_at=material["signed"],
            source_commit=COMMIT,
            destination="fixture",
            transport=make_transport(server),
            lock=lock,
            now=material["now"],
        )
    assert server.calls == []


def test_serialized_publish_order_and_idempotent_object(material: dict[str, Any], server: shi.MockKVRestServer, lock: shi.WriterLock) -> None:
    result = publish(material, server, lock)
    assert result["ok"] is True
    assert [call["phase"] for call in server.calls] == ["get", "get", "create", "get", "put_pointer"]
    identity = str(result["publication_sha256"])
    before = dict(server.storage)
    second = publish(material, server, lock, transport=make_transport(server))
    assert second["ok"] is True
    assert second["publication_sha256"] == identity
    assert server.storage[shp.object_key(identity)] == material["package"]
    assert sum(1 for call in server.calls if call["phase"] == "create") == 1
    assert server.storage[shp.LATEST_KEY] == before[shp.LATEST_KEY]


def test_deterministic_package_bytes_for_fixed_inputs(material: dict[str, Any]) -> None:
    again = shp.build_package(
        material["health"],
        registry=material["registry"],
        key_id=material["key_id"],
        signer=material["private"].sign,
        assembled_at=material["assembled"],
        signed_at=material["signed"],
        source_commit=COMMIT,
    )
    assert again == material["package"]


def test_unavailable_authoritative_state_is_recorded_not_invented(material: dict[str, Any], server: shi.MockKVRestServer, lock: shi.WriterLock) -> None:
    # Pointer names a missing object: authoritative state is unavailable, so the
    # publisher records that honestly and repairs the pointer rather than claiming
    # it knows which version is globally newest.
    server.storage[shp.LATEST_KEY] = shp.canonical({"schema": shp.POINTER_SCHEMA, "publication_sha256": "0" * 64})
    result = publish(material, server, lock)
    assert result["ok"] is True
    assert result["pointer_regression"] == "authoritative_state_unavailable"


def test_existing_object_collision_does_not_advance_pointer(material: dict[str, Any], server: shi.MockKVRestServer, lock: shi.WriterLock) -> None:
    identity = shp.digest(material["package"])
    server.storage[shp.object_key(identity)] = b"different existing bytes"
    result = publish(material, server, lock)
    assert result["ok"] is False
    assert result["reason"] == "immutable_collision"
    assert result["pointer_outcome"] == "not_advanced"
    assert shp.LATEST_KEY not in server.storage
    assert all(call["method"] != "PUT" for call in server.calls)


def test_readback_mismatch_does_not_advance_pointer(material: dict[str, Any], server: shi.MockKVRestServer, lock: shi.WriterLock) -> None:
    server.behaviour["mutate_readback"] = True
    result = publish(material, server, lock)
    assert result["ok"] is False
    assert result["reason"] == "readback_mismatch"
    assert shp.LATEST_KEY not in server.storage
    assert all(call["phase"] != "put_pointer" for call in server.calls)


def test_malformed_stored_object_fails_closed(material: dict[str, Any], server: shi.MockKVRestServer, lock: shi.WriterLock) -> None:
    identity = shp.digest(material["package"])
    server.storage[shp.object_key(identity)] = b"not a signed package"
    result = publish(material, server, lock)
    assert result["ok"] is False
    assert result["reason"] == "immutable_collision"
    assert all(call["phase"] != "put_pointer" for call in server.calls)


def test_pointer_regression_is_rejected_and_pointer_is_unchanged(server: shi.MockKVRestServer, tmp_path: Path) -> None:
    later = make_material(observed="2026-10-01T01:00:00Z", assembled="2026-10-01T01:30:00Z", signed="2026-10-01T01:30:00Z", marker="later")
    earlier = make_material(observed="2026-10-01T00:00:00Z", assembled="2026-10-01T00:30:00Z", signed="2026-10-01T00:30:00Z", marker="earlier")
    # One signer/registry for both; later.registry is reused below.
    earlier["registry"] = later["registry"]
    earlier["key_id"] = later["key_id"]
    earlier["private"] = later["private"]
    lock = shi.WriterLock(shi.writer_lock_path(tmp_path, "fixture"), "fixture")
    later_now = "2026-10-01T02:00:00Z"
    with lock:
        first = shi.serialized_publish(
            later["health"],
            registry=later["registry"],
            key_id=later["key_id"],
            signer=later["private"].sign,
            assembled_at=later["assembled"],
            signed_at=later["signed"],
            source_commit=COMMIT,
            destination="fixture",
            transport=make_transport(server),
            lock=lock,
            now=later_now,
        )
    assert first["ok"] is True
    before = dict(server.storage)
    with lock:
        with pytest.raises(shi.IntegrationError, match="pointer_regression"):
            shi.serialized_publish(
                earlier["health"],
                registry=later["registry"],
                key_id=later["key_id"],
                signer=later["private"].sign,
                assembled_at=earlier["assembled"],
                signed_at=earlier["signed"],
                source_commit=COMMIT,
                destination="fixture",
                transport=make_transport(server),
                lock=lock,
                now=later_now,
            )
    assert server.storage == before


def test_equal_observation_times_have_no_total_order(server: shi.MockKVRestServer, tmp_path: Path) -> None:
    first = make_material(observed="2026-10-01T01:00:00Z", assembled="2026-10-01T01:30:00Z", signed="2026-10-01T01:30:00Z", marker="first")
    second = make_material(observed="2026-10-01T01:00:00Z", assembled="2026-10-01T01:30:00Z", signed="2026-10-01T01:30:00Z", marker="second")
    second["registry"] = first["registry"]
    second["key_id"] = first["key_id"]
    second["private"] = first["private"]
    lock = shi.WriterLock(shi.writer_lock_path(tmp_path, "fixture"), "fixture")
    now = "2026-10-01T02:00:00Z"
    with lock:
        assert shi.serialized_publish(first["health"], registry=first["registry"], key_id=first["key_id"], signer=first["private"].sign, assembled_at=first["assembled"], signed_at=first["signed"], source_commit=COMMIT, destination="fixture", transport=make_transport(server), lock=lock, now=now)["pointer_regression"] == "authoritative_state_unavailable"
        result = shi.serialized_publish(second["health"], registry=second["registry"], key_id=second["key_id"], signer=second["private"].sign, assembled_at=second["assembled"], signed_at=second["signed"], source_commit=COMMIT, destination="fixture", transport=make_transport(server), lock=lock, now=now)
    assert result["ok"] is True
    assert result["pointer_regression"] == "equal_observation_time_no_total_order"
    pointer = json.loads(server.storage[shp.LATEST_KEY])
    assert pointer["publication_sha256"] == result["publication_sha256"]


def test_lost_pointer_acknowledgement_is_reported_unknown_without_rollback_claim(material: dict[str, Any], server: shi.MockKVRestServer, lock: shi.WriterLock) -> None:
    server.behaviour["drop_pointer_ack"] = True
    result = publish(material, server, lock)
    assert result["ok"] is False
    assert result["pointer_outcome"] == "unknown"
    assert result["outcome"] == "unknown"
    assert result["claim"] == "no_rollback_claim"
    identity = shp.digest(material["package"])
    assert server.storage[shp.object_key(identity)] == material["package"]
    # The repository cannot prove a rollback; it only reports ambiguity honestly.
    assert server.storage.get(shp.LATEST_KEY) == shp.canonical({"schema": shp.POINTER_SCHEMA, "publication_sha256": identity})


# --------------------------------------------------------------------------- #
# Signer and registry input validation
# --------------------------------------------------------------------------- #


def test_signer_key_document_roundtrip_and_rejections() -> None:
    private, key_id = shi.disposable_key()
    public = private.public_key().public_bytes(shi.Encoding.Raw, shi.PublicFormat.Raw)
    document = shp.canonical({"key_id": key_id, "public_key_base64": shp.b64(public), "private_key_base64": shp.b64(private.private_bytes_raw())})
    parsed_id, signer = shi.signer_from_key_document(document)
    assert parsed_id == key_id
    signature = signer(b"domain")
    assert len(signature) == 64
    other_private, _ = shi.disposable_key()
    other_public = other_private.public_key().public_bytes(shi.Encoding.Raw, shi.PublicFormat.Raw)
    bad_public = shp.canonical({"key_id": key_id, "public_key_base64": shp.b64(other_public), "private_key_base64": shp.b64(private.private_bytes_raw())})
    with pytest.raises(shi.IntegrationError, match="key_identity_mismatch|key_material_mismatch"):
        shi.signer_from_key_document(bad_public)
    extra = dict(json.loads(document), extra=True)
    with pytest.raises(shi.IntegrationError, match="invalid_key_document"):
        shi.signer_from_key_document(shp.canonical(extra))
    with pytest.raises(shi.IntegrationError, match="invalid_key_document"):
        shi.signer_from_key_document(b"not json")


def test_registry_validation_rejects_bad_shapes() -> None:
    private, key_id = shi.disposable_key()
    base = shi.registry_fixture(private, key_id=key_id, not_before="2026-01-01T00:00:00Z", not_after="2027-01-01T00:00:00Z")
    cases: dict[str, dict[str, Any]] = {}
    cases["schema"] = {**base, "schema": "datapulse/v1/probe-key-registry"}
    cases["version"] = {**base, "version": 2.0}
    cases["current"] = {**base, "current_key_id": "ed25519-" + "0" * 16}
    duplicate = copy.deepcopy(base)
    duplicate["keys"].append(copy.deepcopy(duplicate["keys"][0]))
    cases["duplicate"] = duplicate
    revoked = copy.deepcopy(base)
    revoked["keys"][0]["status"] = "revoked"
    cases["revoked"] = revoked
    wrong_purpose = copy.deepcopy(base)
    wrong_purpose["keys"][0]["purpose"] = "observation-receipt-signing"
    cases["wrong_purpose"] = wrong_purpose
    expired = copy.deepcopy(base)
    expired["keys"][0]["not_after"] = "2025-01-01T00:00:00Z"
    cases["expired_window"] = expired
    wrong_id = copy.deepcopy(base)
    wrong_id["keys"][0]["key_id"] = "ed25519-" + "0" * 16
    cases["wrong_key_id"] = wrong_id
    wrong_public = copy.deepcopy(base)
    wrong_public["keys"][0]["public_key_base64"] = shp.b64(bytes(32))
    cases["wrong_public"] = wrong_public
    for name, value in cases.items():
        with pytest.raises(shi.IntegrationError):
            shi.validate_registry_bytes(shp.canonical(value))
    with pytest.raises(shi.IntegrationError, match="invalid_registry_size"):
        shi.validate_registry_bytes(b" " * (shp.MAX_REGISTRY_BYTES + 1))
    with pytest.raises(shi.IntegrationError, match="invalid_registry_json"):
        shi.validate_registry_bytes(b"not json")
    assert shi.validate_registry_bytes(shp.canonical(base))["schema"] == shi.REGISTRY_SCHEMA


def test_invalid_signer_output_never_reaches_the_pointer(server: shi.MockKVRestServer, lock: shi.WriterLock) -> None:
    material = make_material()
    forged = publish(material, server, lock, signer=lambda _data: bytes(64))
    assert forged["ok"] is False
    assert forged["phase"] == "freeze_sign"
    assert all(call["method"] != "PUT" for call in server.calls)

    def outage(_data: bytes) -> bytes:
        raise RuntimeError("injected signer detail must never surface")

    server.calls.clear()
    down = publish(material, server, lock, signer=outage)
    assert down["ok"] is False and down["reason"] == "signer_unavailable"
    assert all(call["method"] != "PUT" for call in server.calls)


# --------------------------------------------------------------------------- #
# Independent Pages artifact delivery
# --------------------------------------------------------------------------- #


def test_pages_artifact_is_reproducible_and_clearly_not_signature_authority(tmp_path: Path) -> None:
    private, key_id = shi.disposable_key()
    registry_bytes = shp.canonical(shi.registry_fixture(private, key_id=key_id, not_before="2026-01-01T00:00:00Z", not_after="2027-01-01T00:00:00Z"))
    first = shi.build_pages_artifact(registry_bytes, root=ROOT, out_dir=tmp_path / "first", source_commit=COMMIT)
    second = shi.build_pages_artifact(registry_bytes, root=ROOT, out_dir=tmp_path / "second", source_commit=COMMIT)
    assert (tmp_path / "first/manifest.json").read_bytes() == (tmp_path / "second/manifest.json").read_bytes()
    assert first["manifest"]["signature_authority"] is False
    assert first["manifest"]["registry_sha256"] == shp.digest(registry_bytes)
    assert first["manifest"]["source_commit"] == COMMIT
    asset = first["public"] / ".well-known" / "datapulse-probe-keys.json"
    assert asset.read_bytes() == registry_bytes
    # The manifest is delivery metadata outside the served directory, not an asset.
    assert not (first["public"] / "manifest.json").exists()
    assert (first["project"] / "functions/health/verified/[[path]].js").is_file()


def test_pages_artifact_rejects_invalid_registry_before_writing(tmp_path: Path) -> None:
    with pytest.raises(shi.IntegrationError):
        shi.build_pages_artifact(b"{}", root=ROOT, out_dir=tmp_path / "rejected", source_commit=COMMIT)
    assert not (tmp_path / "rejected").exists()


def test_pages_artifact_requires_explicit_source_commit(tmp_path: Path) -> None:
    private, key_id = shi.disposable_key()
    registry_bytes = shp.canonical(shi.registry_fixture(private, key_id=key_id, not_before="2026-01-01T00:00:00Z", not_after="2027-01-01T00:00:00Z"))
    with pytest.raises(shi.IntegrationError, match="invalid_source_commit"):
        shi.build_pages_artifact(registry_bytes, root=ROOT, out_dir=tmp_path / "commit", source_commit="not-a-commit")


# --------------------------------------------------------------------------- #
# Trust refresh, revocation, expiry and wrong purpose end to end
# --------------------------------------------------------------------------- #


def test_registry_refresh_revocation_expiry_and_wrong_purpose_fail_closed() -> None:
    material = make_material()
    kv = storage_values(material["package"])

    def status(registry: dict[str, Any]) -> int:
        return shp.exercise_handler(kv, registry, now=NOW)[0]

    assert status(material["registry"]) == 200
    revoked = copy.deepcopy(material["registry"])
    revoked["keys"][0]["status"] = "revoked"
    assert status(revoked) == 503
    expired = copy.deepcopy(material["registry"])
    expired["keys"][0]["not_after"] = "2026-09-30T00:00:00Z"
    assert status(expired) == 503
    wrong_purpose = copy.deepcopy(material["registry"])
    wrong_purpose["keys"][0]["purpose"] = "observation-receipt-signing"
    assert status(wrong_purpose) == 503
    # A refreshed, valid registry is delivery to the refreshed runtime again.
    assert status(material["registry"]) == 200
    # No unsigned fallback: with the signed object missing the route is unavailable.
    assert shp.exercise_handler({shp.LATEST_KEY: kv[shp.LATEST_KEY]}, material["registry"], now=NOW)[0] == 503


# --------------------------------------------------------------------------- #
# CLI safety and machine-readable modes
# --------------------------------------------------------------------------- #


def test_cli_no_arguments_performs_no_signing_and_no_network(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    def forbidden(*_args: Any, **_kwargs: Any) -> Any:
        raise AssertionError("must not be called without an explicit mode")

    monkeypatch.setattr(shi, "quick_test", forbidden)
    monkeypatch.setattr(shi, "runtime_rehearsal", forbidden)
    monkeypatch.setattr(shi, "KVRestTransport", forbidden)
    monkeypatch.setattr(shi.shp, "build_package", forbidden)
    assert shi.main([]) == 0
    output = json.loads(capsys.readouterr().out)
    assert output == {"ok": True, "mode": "noop", "signed": False, "network_writes": 0, "note": "opt_in_mode_required"}


def test_cli_subprocess_no_arguments_is_offline() -> None:
    result = subprocess.run([sys.executable, str(ROOT / "scripts/signed_health_integration.py")], capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr
    output = json.loads(result.stdout)
    assert output["mode"] == "noop" and output["signed"] is False and output["network_writes"] == 0


def test_cli_plan_mode_is_pure(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], tmp_path: Path) -> None:
    def forbidden(*_args: Any, **_kwargs: Any) -> Any:
        raise AssertionError("plan must not read or sign")

    monkeypatch.setattr(shi, "_load_signer", forbidden)
    monkeypatch.setattr(shi.shp, "build_package", forbidden)
    assert shi.main(["--plan", "--destination", "fixture", "--lock-dir", str(tmp_path)]) == 0
    output = json.loads(capsys.readouterr().out)
    assert output["mode"] == "plan" and output["signed"] is False and output["network_writes"] == 0
    assert output["writer_lock"].endswith("writer-fixture.lock")


def test_cli_write_modes_require_explicit_inputs(capsys: pytest.CaptureFixture[str]) -> None:
    assert shi.main(["--dry-run"]) == 1
    assert json.loads(capsys.readouterr().out)["error"] == "explicit_dry_run_inputs_required"
    assert shi.main(["--publish"]) == 1
    assert json.loads(capsys.readouterr().out)["error"] == "explicit_publish_inputs_required"
    assert shi.main(["--verify-response", "/nonexistent"]) == 1
    assert json.loads(capsys.readouterr().out)["error"] == "explicit_verifier_inputs_required"
    assert shi.main(["--quick-test", "--plan"]) == 1
    assert json.loads(capsys.readouterr().out)["error"] == "ambiguous_cli_mode"


def test_cli_dry_run_requires_an_explicit_signer(capsys: pytest.CaptureFixture[str]) -> None:
    result = shi.main(["--dry-run", "--health", "h", "--registry", "r", "--source-commit", COMMIT, "--assembled-at", NOW, "--signed-at", NOW])
    assert result == 1
    assert json.loads(capsys.readouterr().out)["error"] == "explicit_signer_key_required"


def test_cli_offline_verification_roundtrip(material: dict[str, Any], tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    response = tmp_path / "response.json"
    registry = tmp_path / "registry.json"
    response.write_bytes(shp.response_envelope(material["package"]))
    registry.write_bytes(shp.canonical(material["registry"]))
    assert shi.main(["--verify-response", str(response), "--registry", str(registry), "--now", NOW]) == 0
    output = json.loads(capsys.readouterr().out)
    assert output["verified"] is True and output["mode"] == "verify"
    assert shi.main(["--verify-response", str(response), "--registry", str(registry), "--now", NOW, "--expected-publication", "0" * 64]) == 1
    assert json.loads(capsys.readouterr().out)["ok"] is False


def test_quick_test_cli_is_real_bounded_and_redacted() -> None:
    result = subprocess.run([sys.executable, str(ROOT / "scripts/signed_health_integration.py"), "--quick-test"], capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stderr
    assert len(result.stdout) < 1024
    output = json.loads(result.stdout)
    assert output["ok"] is True and output["consumer_verified"] is True and output["fixture_only"] is True
    assert output["publisher"] == "serialized_kv_rest_verified_readback_before_pointer"
    assert output["source_truth_verified"] is False
    assert all(term not in result.stdout for term in ("base64", "private", "signature", "datasets", "SUPER-SECRET"))


def test_quick_test_failure_is_not_stubbed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(shi.shp, "exercise_handler", lambda *_args, **_kwargs: (503, b"{}"))
    with pytest.raises(shi.IntegrationError, match="fixture_handler_unavailable"):
        shi.quick_test()


# --------------------------------------------------------------------------- #
# Real local Wrangler/workerd Pages runtime
# --------------------------------------------------------------------------- #


def test_runtime_rehearsal_serves_real_pages_with_positive_and_negative_cases() -> None:
    # The real workerd run cannot pass on a Node-only or in-process substitute.
    result = shi.runtime_rehearsal(timeout=110)
    assert result["ok"] is True
    assert result["runtime"] == "local_wrangler_workerd_pages"
    assert result["deployed"] is False
    assert result["consumer_verified"] is True
    assert result["routes"]["latest"] == "200_verified"
    assert result["routes"]["digest"] == "200_verified"
    assert result["routes"]["missing_object"] == "503"
    assert result["routes"]["floor"] == "503"
    assert result["routes"]["unknown_path"] == "404"
    assert result["routes"]["non_get"] == "405"
    assert result["trust"]["revoked"] == "503"
    assert result["trust"]["wrong_purpose"] == "503"
    assert result["trust"]["refresh_forward"] == "200"
    assert result["unsigned_fallback"] == "not_served"
    assert result["source_truth_verified"] is False
