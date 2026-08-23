"""Fixture-only contract for the deferred self-hosted Rekor migration.

These tests intentionally validate transport-neutral metadata only.  They do
not invoke Cosign, Rekor, OpenBao, sockets, or cryptographic key generation.
"""
from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

import pytest


FIXTURES = Path(__file__).parent / "fixtures" / "sigstore_rekor_migration"


def fixture_directory(tmp_path: Path) -> Path:
    """Copy checked-in examples to an isolated, deterministic test location."""
    destination = tmp_path / "sigstore-rekor-migration-fixtures"
    shutil.copytree(FIXTURES, destination)
    return destination


def load_fixture(directory: Path, name: str) -> dict:
    return json.loads((directory / name).read_text(encoding="utf-8"))


def assert_legacy_envelope(envelope: dict) -> None:
    payload = envelope["payload"]
    assert envelope["schema"] == "datapulse/v1/probe-attestation-envelope"
    assert payload["schema"] == "datapulse/v1/probe-attestation"
    assert envelope["signature_base64"].startswith("fixture-only-")
    assert len(envelope["chain_link"]) == 64
    assert envelope["verification_level"] == "L1-capable"
    assert envelope["git_tag_anchor"]["tag"].startswith("v")
    assert len(envelope["git_tag_anchor"]["commit"]) == 40


def assert_cosign_bundle(bundle: dict, expected_digest: str) -> None:
    assert bundle["media_type"] == "application/vnd.dev.cosign.bundle.v0+json"
    assert bundle["artifact_digest"] == expected_digest
    assert bundle["signing_identity"]["kms_uri"].startswith("openbao://")
    inclusion = bundle["rekor_inclusion"]
    assert inclusion["log_id"]
    assert inclusion["log_index"] >= 0
    assert inclusion["inclusion_proof"]
    assert inclusion["signed_entry_timestamp"]


def canonical_daily_digest(artifact: dict) -> str:
    """Hash only deterministic fixture bytes; this is not signature verification."""
    return "sha256:" + hashlib.sha256(artifact["canonical_json"].encode("utf-8")).hexdigest()


def test_current_ed25519_fixture_preserves_chain_and_git_tag_compatibility(tmp_path: Path) -> None:
    fixture = load_fixture(fixture_directory(tmp_path), "current_ed25519_envelope.json")
    assert_legacy_envelope(fixture)


def test_cosign_bundle_fixture_refers_to_the_canonical_daily_artifact_digest(tmp_path: Path) -> None:
    fixture = load_fixture(fixture_directory(tmp_path), "cosign_bundle.json")
    assert canonical_daily_digest(fixture["canonical_daily_artifact"]) == fixture["canonical_daily_artifact"]["sha256"]
    assert_cosign_bundle(fixture, fixture["canonical_daily_artifact"]["sha256"])


def test_dual_published_fixture_requires_both_backends_to_name_the_same_digest(tmp_path: Path) -> None:
    fixture = load_fixture(fixture_directory(tmp_path), "dual_published.json")
    assert canonical_daily_digest(fixture["canonical_daily_artifact"]) == fixture["canonical_daily_artifact"]["sha256"]
    assert_legacy_envelope(fixture["ed25519_envelope"])
    assert_cosign_bundle(fixture["cosign_bundle"], fixture["canonical_daily_artifact"]["sha256"])
    assert fixture["ed25519_envelope"]["payload_digest"] == fixture["cosign_bundle"]["artifact_digest"]


def test_digest_mismatch_fixture_is_rejected_before_either_backend_is_accepted(tmp_path: Path) -> None:
    fixture = load_fixture(fixture_directory(tmp_path), "digest_mismatch.json")
    with pytest.raises(AssertionError):
        assert_cosign_bundle(fixture["cosign_bundle"], fixture["ed25519_envelope"]["payload_digest"])


@pytest.mark.parametrize("name", ["malformed_bundle.json", "missing_rekor_inclusion.json"])
def test_incomplete_cosign_metadata_is_not_accepted_as_transparency_evidence(tmp_path: Path, name: str) -> None:
    fixture = load_fixture(fixture_directory(tmp_path), name)
    with pytest.raises((AssertionError, KeyError, TypeError)):
        assert_cosign_bundle(fixture["cosign_bundle"], fixture["canonical_daily_artifact"]["sha256"])


def test_unavailable_sigstore_backend_fails_closed_without_invalidating_ed25519_result(tmp_path: Path) -> None:
    fixture = load_fixture(fixture_directory(tmp_path), "verifier_unavailable.json")
    assert_legacy_envelope(fixture["ed25519_envelope"])
    assert fixture["sigstore_verification"] == {
        "attempted": True,
        "satisfied": False,
        "reason": "verifier backend unavailable; fail closed",
    }
    assert fixture["ed25519_verification"]["satisfied"] is True
