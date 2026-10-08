from __future__ import annotations

import base64
import hashlib
import json
import shutil
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from scripts import attestation_sets, gen_attestations as ga
from scripts.attestation_sets import discovery, selected_directory
from scripts.tests.test_attestations import fixture_root, fixture_root_with_rekor, write
from scripts.verify_attestation_binding import (
    ContractError,
    _verify_merkle_proof,
    verify_rekor_evidence,
    verify_contract,
    verify_unbound_legacy_plane,
)
from scripts.verify_attestation_append import accepted_day_directory, verify_append


NOW = datetime(2026, 8, 15, 1, tzinfo=timezone.utc)
REAL_BUNDLE = (
    Path(__file__).parent
    / "fixtures/sigstore_rekor_migration/real_cosign_dsse_bundle.json"
)
REAL_BUNDLE_SHA256 = "595f6cb71d21af1fb0be64ec1e3156b3471c2025c60ab6f535e23d63db5a9fda"


def generated_root(tmp_path: Path) -> Path:
    root, key = fixture_root(tmp_path)
    ga.generate(root, key, NOW)
    return root


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def dump(path: Path, value: object) -> None:
    path.write_text(json.dumps(value) + "\n", encoding="utf-8")


def test_latest_pipeline_scores_can_advance_but_chain_head_cannot_diverge(tmp_path: Path) -> None:
    root = generated_root(tmp_path)
    directory = selected_directory(root)
    score_path = root / "attestations/latest/scores.json"
    scores = load(score_path)
    scores["generated_at"] = "2026-08-15T02:00:00Z"
    dump(score_path, scores)
    assert score_path.read_bytes() != (root / directory / "scores.json").read_bytes()
    assert selected_directory(root) == directory

    scores["generated_at"] = "2026-08-15T00:00:00Z"
    dump(score_path, scores)
    with pytest.raises(ContractError, match="latest projection is stale or mixed"):
        selected_directory(root)

    scores["generated_at"] = "2026-08-15T02:00:00Z"
    dump(score_path, scores)
    head_path = root / "attestations/latest/chain_head.json"
    head_path.write_bytes(head_path.read_bytes() + b" ")
    with pytest.raises(ContractError, match="latest projection is stale or mixed"):
        selected_directory(root)


@pytest.mark.parametrize("append_count", (1, 2))
def test_append_head_extends_accepted_base_without_byte_identity(
    tmp_path: Path, append_count: int,
) -> None:
    root, key = fixture_root(tmp_path)
    ga.generate(root, key, NOW)
    base_head = discovery(root)["current_head"]
    base_bytes = (root / ".attestations/chain_head.json").read_bytes()
    for arguments in (
        ("init", "-b", "main"),
        ("add", "attestations", ".attestations", "docs"),
        ("-c", "user.name=Test", "-c", "user.email=test@example.test", "commit",
         "-m", "accepted attestation fixture"),
    ):
        subprocess.run(["git", *arguments], cwd=root, check=True, capture_output=True)

    for offset in range(1, append_count + 1):
        previous_head = discovery(root)["current_head"]
        ga.generate(root, key, NOW + timedelta(days=offset))
    candidate = discovery(root)
    directory = selected_directory(root)
    head = load(root / directory / "chain_head.json")
    assert head["chain_head"] != base_head
    assert head["payload"]["previous_chain_head"] == previous_head
    assert (root / ".attestations/chain_head.json").read_bytes() != base_bytes
    assert (root / ".attestations/chain_head.json").read_bytes() == (
        root / directory / "chain_head.json"
    ).read_bytes()
    assert attestation_sets.assert_head_extends_base(candidate, base_head) == set(candidate["heads"]) - {base_head}
    verify_append(root, "HEAD")


@pytest.mark.parametrize("candidate_kind", ("stale", "non-linear"))
def test_head_that_does_not_extend_accepted_base_is_refused(
    tmp_path: Path, candidate_kind: str,
) -> None:
    root, key = fixture_root(tmp_path / "accepted")
    ga.generate(root, key, NOW)
    fork = tmp_path / "candidate"
    shutil.copytree(root, fork)
    ga.generate(root, key, NOW + timedelta(days=1))
    base_head = discovery(root)["current_head"]
    if candidate_kind == "non-linear":
        # A correctly signed later head forks from the predecessor of the
        # accepted base. Its own mirror and discovery are internally coherent.
        ga.generate(fork, fork / key.name, NOW + timedelta(days=2))
    candidate = discovery(fork)
    directory = selected_directory(fork)
    assert (fork / ".attestations/chain_head.json").read_bytes() == (
        fork / directory / "chain_head.json"
    ).read_bytes()
    with pytest.raises(ContractError, match="forward lineage parent missing or date moved backwards"):
        attestation_sets.assert_head_extends_base(candidate, base_head)


def test_append_with_stale_legacy_mirror_is_still_refused(tmp_path: Path) -> None:
    root, key = fixture_root(tmp_path)
    ga.generate(root, key, NOW)
    base_head = discovery(root)["current_head"]
    base_bytes = (root / ".attestations/chain_head.json").read_bytes()
    ga.generate(root, key, NOW + timedelta(days=1))
    candidate = discovery(root)
    assert attestation_sets.assert_head_extends_base(candidate, base_head) == {candidate["current_head"]}
    mirror = root / ".attestations/chain_head.json"
    directory = accepted_day_directory(root, candidate)
    expected = root / directory / "chain_head.json"
    expected_bytes = expected.read_bytes()
    mirror.write_bytes(base_bytes)
    with pytest.raises(ContractError, match="legacy mirror disagrees with current head") as error:
        selected_directory(root)
    message = str(error.value)
    assert message.startswith("legacy mirror disagrees with current head\n")
    assert f"mirror={mirror.resolve()} sha256={hashlib.sha256(base_bytes).hexdigest()} bytes={len(base_bytes)}" in message
    assert f"expected={expected.resolve()} sha256={hashlib.sha256(expected_bytes).hexdigest()} bytes={len(expected_bytes)}" in message
    assert f"day={directory} schema=datapulse/v2/chain-index" in message


def test_legacy_mirror_success_logs_absolute_operands(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture,
) -> None:
    root = generated_root(tmp_path)
    document = discovery(root)
    directory = accepted_day_directory(root, document)
    mirror = root / ".attestations/chain_head.json"
    expected = root / directory / "chain_head.json"
    digest = hashlib.sha256(expected.read_bytes()).hexdigest()
    monkeypatch.chdir(root)
    caplog.clear()

    attestation_sets.verify_legacy_mirror(Path("."), document, directory)

    assert len(caplog.records) == 1
    assert caplog.records[0].levelname == "WARNING"
    line = caplog.records[0].getMessage()
    assert f"mirror={mirror.resolve()} sha256={digest}" in line
    assert f"expected={expected.resolve()} sha256={digest}" in line
    assert "\n" not in line


def test_v1_index_keeps_legacy_mirror_guard_dormant_after_discovery_upgrade(
    tmp_path: Path,
) -> None:
    root = generated_root(tmp_path)
    index_path = root / "attestations/chain-index.json"
    index = load(index_path)
    index["schema"] = "datapulse/v1/chain-index"
    dump(index_path, index)
    mirror_path = root / ".attestations/chain_head.json"
    mirror_path.write_bytes(mirror_path.read_bytes() + b" ")

    assert discovery(root)["schema"] == "datapulse/v2/chain-index"
    assert selected_directory(root).startswith("attestations/")


def test_append_day_comes_from_candidate_index_even_when_later_day_exists(tmp_path: Path) -> None:
    root = generated_root(tmp_path)
    document = discovery(root)
    accepted_day = document["heads"][document["current_head"]].split("/")[1]
    other_day = "2026-08-16" if accepted_day != "2026-08-16" else "2026-08-17"
    (root / "attestations" / other_day).mkdir()

    assert accepted_day_directory(root, document) == f"attestations/{accepted_day}"


def test_append_verifier_rejects_stale_legacy_mirror(tmp_path: Path) -> None:
    root, key = fixture_root(tmp_path)
    ga.generate(root, key, NOW)
    old_mirror = (root / ".attestations/chain_head.json").read_bytes()
    for arguments in (
        ("init", "-b", "main"),
        ("add", "attestations", ".attestations", "docs"),
        ("-c", "user.name=Test", "-c", "user.email=test@example.test", "commit",
         "-m", "accepted attestation fixture"),
    ):
        subprocess.run(["git", *arguments], cwd=root, check=True, capture_output=True)
    ga.generate(root, key, NOW + timedelta(days=1))
    (root / ".attestations/chain_head.json").write_bytes(old_mirror)

    with pytest.raises(ContractError, match="legacy mirror disagrees with current head"):
        verify_append(root, "HEAD")


def real_bundle_reference(root: Path) -> tuple[dict, str]:
    """Build the reference exactly as the daily workflow's inline Python does."""
    assert hashlib.sha256(REAL_BUNDLE.read_bytes()).hexdigest() == REAL_BUNDLE_SHA256
    bundle = load(REAL_BUNDLE)
    entry = bundle["verificationMaterial"]["tlogEntries"][0]
    statement = json.loads(base64.b64decode(bundle["dsseEnvelope"]["payload"]))
    subject_digest = statement["subject"][0]["digest"]["sha256"]
    log_id = base64.b64decode(entry["logId"]["keyId"], validate=True).hex()
    directory = root / "attestations/real-rekor"
    directory.mkdir(parents=True)
    bundle_path = directory / REAL_BUNDLE.name
    shutil.copy2(REAL_BUNDLE, bundle_path)
    reference = {
        "schema": "datapulse/v1/sigstore-rekor-reference",
        "artifact": "health/latest.json",
        "artifact_sha256": subject_digest,
        "bundle": bundle_path.name,
        "run_id": f"health-{subject_digest}",
        "rekor": {
            "log_id": log_id,
            "log_index": entry["logIndex"],
            "uuid": hashlib.sha256(
                base64.b64decode(entry["canonicalizedBody"], validate=True)
            ).hexdigest(),
            "inclusion_proof": True,
            "signed_entry_timestamp": True,
        },
    }
    reference_path = directory / "reference.json"
    dump(reference_path, reference)
    return {
        "reference_ref": "attestations/real-rekor/reference.json",
        "bundle_ref": f"attestations/real-rekor/{bundle_path.name}",
    }, subject_digest


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
        "artifact_signed": False,
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


def test_same_day_changed_health_with_invalid_key_refuses_reuse(tmp_path: Path) -> None:
    root, key = fixture_root(tmp_path)
    ga.generate(root, key, NOW)
    dated = root / "attestations/2026-08-15"
    committed = {path.name: path.read_bytes() for path in dated.glob("*.json")}
    health = load(root / "health/latest.json")
    health["datasets"][0]["status"] = "stale"
    write(root / "health/latest.json", health)
    other_key = tmp_path / "different-private-key.json"
    write(other_key, {"key_id": "not-the-committed-key"})
    (root / "attestations/latest/binding.json").write_text("{}\n")

    before_latest = (root / "attestations/latest/binding.json").read_bytes()
    with pytest.raises(ValueError):
        ga.generate(root, other_key, NOW + timedelta(hours=1))

    assert committed == {path.name: path.read_bytes() for path in dated.glob("*.json")}
    assert (root / "attestations/latest/binding.json").read_bytes() == before_latest


def test_same_day_corrupt_dated_set_fails_closed_without_mutating_latest(tmp_path: Path) -> None:
    root, key = fixture_root(tmp_path)
    ga.generate(root, key, NOW)
    latest_before = (root / "attestations/latest/binding.json").read_bytes()
    binding = load(root / "attestations/2026-08-15/binding.json")
    binding["payload"]["health"]["artifact_sha256"] = "0" * 64
    write(root / "attestations/2026-08-15/binding.json", binding)

    with pytest.raises(ValueError, match="corrupt or inconsistent"):
        ga.generate(root, key, NOW + timedelta(hours=1))

    assert (root / "attestations/latest/binding.json").read_bytes() == latest_before


def test_same_day_invalid_scores_fail_closed_without_mutating_latest(tmp_path: Path) -> None:
    root, key = fixture_root(tmp_path)
    ga.generate(root, key, NOW)
    latest_before = (root / "attestations/latest/scores.json").read_bytes()
    (root / "attestations/2026-08-15/scores.json").write_text("[]\n", encoding="utf-8")

    with pytest.raises(ValueError, match="corrupt or inconsistent"):
        ga.generate(root, key, NOW + timedelta(hours=1))

    assert (root / "attestations/latest/scores.json").read_bytes() == latest_before


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


def test_non_attestation_key_purpose_is_rejected(tmp_path: Path) -> None:
    root = generated_root(tmp_path)
    registry_path = root / "docs/.well-known/datapulse-probe-keys.json"
    registry = load(registry_path)
    registry["keys"][0]["purpose"] = "observation-receipt-signing"
    dump(registry_path, registry)

    with pytest.raises(ContractError, match="wrong purpose"):
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
    with pytest.raises(ContractError, match="projection"):
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

    with pytest.raises(ContractError, match="unresolved head"):
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
    statement = {
        "_type": "https://in-toto.io/Statement/v1",
        "subject": [{"name": "health/latest.json", "digest": {"sha256": digest}}],
        "predicateType": "https://www.data-pulse.my/predicates/health-snapshot/v1",
        "predicate": {},
    }
    bundle = {
        "mediaType": "application/vnd.dev.sigstore.bundle.v0.3+json",
        "dsseEnvelope": {
            "payloadType": "application/vnd.in-toto+json",
            "payload": base64.b64encode(
                json.dumps(statement, sort_keys=True, separators=(",", ":")).encode("utf-8")
            ).decode("ascii"),
            "signatures": [{"sig": base64.b64encode(b"fixture signature").decode("ascii")}],
        },
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
    root, key, rekor_reference = fixture_root_with_rekor(tmp_path)
    ga.generate(root, key, NOW, rekor_reference)
    result = verify_contract(root, now=NOW + timedelta(hours=1), require_rekor=True)
    assert result["claims"] == {
        "artifact_signed": True,
        "rekor_witnessed": True,
        "source_truth_verified": False,
    }
    assert result["rekor"]["log_id"] == "a" * 64
    assert result["rekor"]["log_index"] == 0
    assert len(result["rekor"]["uuid"]) == 64


def test_same_day_rekor_reference_does_not_mutate_committed_binding(tmp_path: Path) -> None:
    root, key = fixture_root(tmp_path)
    ga.generate(root, key, NOW)
    legacy_before = (root / "attestations/2026-08-15/sample.json").read_bytes()
    reference = install_rekor_fixture(root, attach=False)

    dated_binding = (root / "attestations/2026-08-15/binding.json").read_bytes()
    ga.generate(root, key, NOW + timedelta(hours=1), reference)
    ga.generate(root, key, NOW + timedelta(hours=2), reference)

    assert (root / "attestations/2026-08-15/sample.json").read_bytes() == legacy_before
    assert (root / "attestations/2026-08-15/binding.json").read_bytes() == dated_binding
    assert (root / "attestations/latest/binding.json").read_bytes() != dated_binding
    assert verify_contract(root, now=NOW + timedelta(hours=2))["claims"]["rekor_witnessed"] is True
    assert len(load(root / "attestations/chain-index.json")["days"]["2026-08-15"]) == 2


def test_missing_rekor_proof_reference_is_rejected(tmp_path: Path) -> None:
    root = generated_root(tmp_path)
    install_rekor_fixture(root, missing_proof=True)
    with pytest.raises(ContractError, match="inclusion proof"):
        verify_contract(root, now=NOW + timedelta(hours=1), require_rekor=True)


def test_real_cosign_dsse_bundle_accepts_protobuf_integer_proof(tmp_path: Path) -> None:
    root, _key = fixture_root(tmp_path)
    metadata, subject_digest = real_bundle_reference(root)

    # The fixture health bytes are deliberately small and do not hash to the
    # published bundle's immutable DSSE subject. This focused test therefore
    # supplies that subject digest, which is the binding verified by this path.
    result = verify_rekor_evidence(root, metadata, subject_digest)

    assert result["log_index"] == "2819296084"


def test_real_cosign_dsse_bundle_rejects_a_tampered_root_hash(tmp_path: Path) -> None:
    root, _key = fixture_root(tmp_path)
    metadata, subject_digest = real_bundle_reference(root)
    bundle_path = root / metadata["bundle_ref"]
    bundle = load(bundle_path)
    proof = bundle["verificationMaterial"]["tlogEntries"][0]["inclusionProof"]
    proof["rootHash"] = base64.b64encode(bytes(32)).decode("ascii")
    dump(bundle_path, bundle)

    with pytest.raises(ContractError, match="root does not verify"):
        verify_rekor_evidence(root, metadata, subject_digest)


def test_merkle_proof_prefers_proof_level_index_over_entry_index() -> None:
    bundle = load(REAL_BUNDLE)
    entry = bundle["verificationMaterial"]["tlogEntries"][0]
    entry["logIndex"] = "0"

    _verify_merkle_proof(entry)


def test_same_day_invalid_rekor_proof_is_rejected_without_publication(tmp_path: Path) -> None:
    root, key = fixture_root(tmp_path)
    ga.generate(root, key, NOW)
    reference = install_rekor_fixture(root, missing_proof=True, attach=False)

    with pytest.raises(ContractError, match="inclusion proof"):
        ga.generate(root, key, NOW + timedelta(hours=1), reference)

    binding = load(root / "attestations/latest/binding.json")
    assert binding["claims"]["rekor_witnessed"] is False
    assert binding["rekor"] is None
