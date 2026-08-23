from __future__ import annotations

import base64
import hashlib
import json
import shutil
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from scripts import gen_attestations as ga
from scripts.tests.test_attestations import fixture_root, write
from scripts.verify_attestation_binding import (
    ContractError,
    verify_contract,
    verify_unbound_legacy_plane,
)


NOW = datetime(2026, 8, 15, 1, tzinfo=timezone.utc)


def generated_root(tmp_path: Path) -> Path:
    root, key = fixture_root(tmp_path)
    ga.generate(root, key, NOW)
    return root


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def dump(path: Path, value: object) -> None:
    path.write_text(json.dumps(value) + "\n", encoding="utf-8")


def test_clean_fixture_binds_health_chain_dataset_set_time_and_active_key(tmp_path: Path) -> None:
    root = generated_root(tmp_path)
    binding = load(root / "attestations/latest/binding.json")
    payload = binding["payload"]
    health_bytes = (root / "health/latest.json").read_bytes()

    assert binding["schema"] == "datapulse/v1/attestation-binding-envelope"
    assert payload["schema"] == "datapulse/v1/attestation-binding"
    assert payload["health"] == {
        "artifact_ref": "health/latest.json",
        "artifact_sha256": hashlib.sha256(health_bytes).hexdigest(),
        "dataset_count": 1,
        "dataset_ids_sha256": ga.sha(ga.canonical(["sample"])),
        "observed_at": "2026-08-15T00:00:00Z",
    }
    assert payload["published_at"] == "2026-08-15T01:00:00Z"
    assert payload["ed25519"]["key_id"] == "ed25519-test"
    assert payload["ed25519"]["key_status"] == "active"
    assert payload["ed25519"]["chain_head"] == load(root / "attestations/latest/chain_head.json")["chain_head"]
    assert binding["claims"] == {
        "artifact_signed": True,
        "rekor_witnessed": False,
        "source_truth_verified": False,
    }
    assert binding["rekor"] is None

    result = verify_contract(root, now=NOW + timedelta(hours=1))
    assert result["claims"] == binding["claims"]
    assert result["freshness"]["status"] == "current"


def test_additive_binding_does_not_change_legacy_signed_payload_shapes(tmp_path: Path) -> None:
    root = generated_root(tmp_path)
    dataset_payload = load(root / "attestations/2026-08-15/sample.json")["payload"]
    head_payload = load(root / "attestations/2026-08-15/chain_head.json")["payload"]

    assert set(dataset_payload) == {
        "schema", "date", "observed_at", "dataset_id", "source_url",
        "observed_request_url", "access_dependency", "probe_count_14d",
        "probe_count_24h", "last_status", "last_staleness_days",
        "content_fingerprint", "browser_receipt", "previous_chain_head",
        "key_id", "signer_pubkey_base64",
    }
    assert set(head_payload) == {
        "schema", "date", "previous_chain_head", "dataset_count",
        "dataset_links_sha256", "key_id",
    }
    assert ga.canonical(dataset_payload) == json.dumps(
        dataset_payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def test_same_day_generation_is_byte_idempotent(tmp_path: Path) -> None:
    root, key = fixture_root(tmp_path)
    ga.generate(root, key, NOW)
    before = {
        path.relative_to(root): path.read_bytes()
        for path in (root / "attestations/2026-08-15").glob("*.json")
    }

    ga.generate(root, key, NOW + timedelta(hours=1))

    assert before == {
        path.relative_to(root): path.read_bytes()
        for path in (root / "attestations/2026-08-15").glob("*.json")
    }


def test_same_day_different_health_is_rejected_as_ambiguous(tmp_path: Path) -> None:
    root, key = fixture_root(tmp_path)
    ga.generate(root, key, NOW)
    health = load(root / "health/latest.json")
    health["datasets"][0]["status"] = "stale"
    write(root / "health/latest.json", health)

    with pytest.raises(ValueError, match="same-day attestation already exists"):
        ga.generate(root, key, NOW + timedelta(hours=1))


def test_older_dated_attestation_cannot_supersede_latest(tmp_path: Path) -> None:
    root, key = fixture_root(tmp_path)
    ga.generate(root, key, NOW)
    ga.generate(root, key, NOW + timedelta(days=1))

    with pytest.raises(ValueError, match="supersede latest"):
        ga.generate(root, key, NOW + timedelta(hours=1))

    assert load(root / "attestations/latest/index.json")["date"] == "2026-08-16"


@pytest.mark.parametrize("field", ["artifact_sha256", "dataset_count", "dataset_ids_sha256", "observed_at"])
def test_health_binding_mismatch_is_rejected(tmp_path: Path, field: str) -> None:
    root = generated_root(tmp_path)
    binding_path = root / "attestations/latest/binding.json"
    binding = load(binding_path)
    replacements = {
        "artifact_sha256": "0" * 64,
        "dataset_count": 2,
        "dataset_ids_sha256": "0" * 64,
        "observed_at": "2026-08-14T00:00:00Z",
    }
    binding["payload"]["health"][field] = replacements[field]
    dump(binding_path, binding)

    with pytest.raises(ContractError, match="binding"):
        verify_contract(root, now=NOW + timedelta(hours=1))


def test_stale_binding_is_rejected(tmp_path: Path) -> None:
    root = generated_root(tmp_path)
    with pytest.raises(ContractError, match="stale"):
        verify_contract(root, now=NOW + timedelta(days=2))


def test_superseded_key_is_rejected(tmp_path: Path) -> None:
    root = generated_root(tmp_path)
    registry_path = root / "docs/.well-known/datapulse-probe-keys.json"
    registry = load(registry_path)
    registry["keys"][0]["status"] = "superseded"
    dump(registry_path, registry)

    with pytest.raises(ContractError, match="active"):
        verify_contract(root, now=NOW + timedelta(hours=1))


def test_non_current_active_key_is_rejected(tmp_path: Path) -> None:
    root = generated_root(tmp_path)
    registry_path = root / "docs/.well-known/datapulse-probe-keys.json"
    registry = load(registry_path)
    registry["current_key_id"] = "ed25519-newer"
    dump(registry_path, registry)

    with pytest.raises(ContractError, match="not active"):
        verify_contract(root, now=NOW + timedelta(hours=1))


def test_unattested_health_policy_still_requires_an_active_legacy_plane(tmp_path: Path) -> None:
    root = generated_root(tmp_path)
    (root / "attestations/latest/binding.json").unlink()
    verify_unbound_legacy_plane(root, now=NOW + timedelta(hours=1))

    registry_path = root / "docs/.well-known/datapulse-probe-keys.json"
    registry = load(registry_path)
    registry["keys"][0]["status"] = "superseded"
    dump(registry_path, registry)
    with pytest.raises(ContractError, match="not active"):
        verify_unbound_legacy_plane(root, now=NOW + timedelta(hours=1))


def test_duplicate_date_chain_index_is_rejected(tmp_path: Path) -> None:
    root = generated_root(tmp_path)
    index_path = root / "attestations/chain-index.json"
    index = load(index_path)
    index["heads"]["f" * 64] = "attestations/2026-08-15/other-chain-head.json"
    dump(index_path, index)

    with pytest.raises(ContractError, match="duplicate-date"):
        verify_contract(root, now=NOW + timedelta(hours=1))


def install_rekor_fixture(root: Path, *, missing_proof: bool = False, attach: bool = True) -> Path:
    binding_path = root / "attestations/latest/binding.json"
    binding = load(binding_path)
    digest = binding["payload"]["health"]["artifact_sha256"]
    bundle_path = root / "attestations/2026-08-15/health.sigstore.bundle.json"
    canonicalized_body = base64.b64encode(b"fixture Rekor body").decode("ascii")
    leaf_hash = hashlib.sha256(b"\x00" + base64.b64decode(canonicalized_body)).digest()
    entry = {
        "logId": {"keyId": base64.b64encode(bytes.fromhex("a" * 64)).decode("ascii")},
        "logIndex": 0,
        "integratedTime": 1786755600,
        "canonicalizedBody": canonicalized_body,
        "inclusionProof": {"rootHash": base64.b64encode(leaf_hash).decode("ascii"), "hashes": [], "treeSize": 1},
        "inclusionPromise": {"signedEntryTimestamp": "fixture-set"},
    }
    if missing_proof:
        entry.pop("inclusionProof")
    bundle = {
        "mediaType": "application/vnd.dev.sigstore.bundle.v0.3+json",
        "messageSignature": {"messageDigest": {"algorithm": "SHA2_256", "digest": digest}},
        "verificationMaterial": {"tlogEntries": [entry]},
    }
    dump(bundle_path, bundle)
    reference_path = root / "attestations/2026-08-15/health.sigstore.json"
    dump(reference_path, {
        "schema": "datapulse/v1/sigstore-rekor-reference",
        "artifact": "health/latest.json",
        "artifact_sha256": digest,
        "bundle": "health.sigstore.bundle.json",
        "run_id": f"health-{digest}",
        "rekor": {
            "log_id": "a" * 64,
            "log_index": 0,
            "uuid": hashlib.sha256(base64.b64decode(canonicalized_body)).hexdigest(),
            "inclusion_proof": True,
            "signed_entry_timestamp": True,
        },
    })
    if attach:
        binding["rekor"] = {
            "reference_ref": "attestations/2026-08-15/health.sigstore.json",
            "bundle_ref": "attestations/2026-08-15/health.sigstore.bundle.json",
        }
        binding["claims"]["rekor_witnessed"] = True
        # Rekor metadata is additive evidence, not part of the legacy Ed25519 payload.
        dump(binding_path, binding)
        dump(root / "attestations/2026-08-15/binding.json", binding)
        shutil.copy2(reference_path, root / "attestations/latest/health.sigstore.json")
        shutil.copy2(bundle_path, root / "attestations/latest/health.sigstore.bundle.json")
    return reference_path


def test_complete_rekor_reference_binds_the_same_health_digest(tmp_path: Path) -> None:
    root = generated_root(tmp_path)
    install_rekor_fixture(root)
    result = verify_contract(root, now=NOW + timedelta(hours=1), require_rekor=True)
    assert result["claims"] == {
        "artifact_signed": True,
        "rekor_witnessed": True,
        "source_truth_verified": False,
    }
    assert result["rekor"]["log_id"] == "a" * 64
    assert result["rekor"]["log_index"] == 0
    assert len(result["rekor"]["uuid"]) == 64


def test_same_day_rekor_enrichment_is_additive_and_idempotent(tmp_path: Path) -> None:
    root, key = fixture_root(tmp_path)
    ga.generate(root, key, NOW)
    legacy_before = (root / "attestations/2026-08-15/sample.json").read_bytes()
    reference = install_rekor_fixture(root, attach=False)

    ga.generate(root, key, NOW + timedelta(hours=1), reference)
    first_binding = (root / "attestations/latest/binding.json").read_bytes()
    ga.generate(root, key, NOW + timedelta(hours=2), reference)

    assert (root / "attestations/2026-08-15/sample.json").read_bytes() == legacy_before
    assert (root / "attestations/latest/binding.json").read_bytes() == first_binding
    assert verify_contract(root, now=NOW + timedelta(hours=2), require_rekor=True)["claims"]["rekor_witnessed"] is True


def test_missing_rekor_proof_reference_is_rejected(tmp_path: Path) -> None:
    root = generated_root(tmp_path)
    install_rekor_fixture(root, missing_proof=True)
    with pytest.raises(ContractError, match="inclusion proof"):
        verify_contract(root, now=NOW + timedelta(hours=1), require_rekor=True)


def test_generator_rejects_missing_rekor_proof_before_updating_latest(tmp_path: Path) -> None:
    root, key = fixture_root(tmp_path)
    ga.generate(root, key, NOW)
    reference = install_rekor_fixture(root, missing_proof=True, attach=False)

    with pytest.raises(ContractError, match="inclusion proof"):
        ga.generate(root, key, NOW + timedelta(hours=1), reference)

    binding = load(root / "attestations/latest/binding.json")
    assert binding["claims"]["rekor_witnessed"] is False
    assert binding["rekor"] is None
