"""Offline coverage for binding a new day's health snapshot to Rekor evidence."""

from __future__ import annotations

import json
import hashlib
from datetime import datetime, timezone
from pathlib import Path

import pytest

from scripts import gen_attestations as ga
from scripts.tests.test_attestations import fixture_rekor_reference, fixture_root
from scripts.verify_attestation_binding import ContractError
from scripts.verify_sigstore_bundle import verify_bundle


ROOT = Path(__file__).resolve().parents[2]


def test_daily_rekor_evidence_is_committable_and_staged_with_its_binding() -> None:
    """A witnessed binding must commit the evidence paths it references."""
    gitignore = (ROOT / ".gitignore").read_text(encoding="utf-8")
    daily = (ROOT / ".github/workflows/datapulse-attest-daily.yml").read_text(encoding="utf-8")

    assert "attestations/rekor/" not in gitignore
    commit_step = daily.split("      - name: Commit dated envelopes and open or update their pull request\n", 1)[1]
    assert 'git add -- "attestations/rekor/$day"' in commit_step


def test_matching_rekor_reference_marks_new_binding_as_witnessed(tmp_path: Path) -> None:
    root, key = fixture_root(tmp_path)
    reference = fixture_rekor_reference(root, "rekor-fixture")

    ga.generate(root, key, datetime(2026, 8, 15, 1, tzinfo=timezone.utc), reference)

    binding = json.loads((root / "attestations/2026-08-15/binding.json").read_text())
    assert binding["claims"]["rekor_witnessed"] is True
    assert binding["rekor"] == {
        "reference_ref": "attestations/rekor-fixture/reference.json",
        "bundle_ref": "attestations/rekor-fixture/bundle.json",
    }


def test_rekor_dsse_fixture_is_accepted_by_sigstore_and_binding_verifiers(tmp_path: Path) -> None:
    root, _key = fixture_root(tmp_path)
    reference = fixture_rekor_reference(root, "rekor-fixture")
    bundle = reference.parent / "bundle.json"
    digest = hashlib.sha256((root / "health/latest.json").read_bytes()).hexdigest()

    assert verify_bundle(
        health=root / "health/latest.json",
        manifest=root / "datapulse.json",
        chain_head=root / ".attestations/chain_head.json",
        source_commit="c" * 40,
        bundle=bundle,
        identity="https://example.test/identity",
        issuer="https://example.test/issuer",
    )["subject_sha256"] == digest
    ga.generate(root, _key, datetime(2026, 8, 15, 1, tzinfo=timezone.utc), reference)


def test_mismatched_rekor_reference_is_rejected_before_binding(tmp_path: Path) -> None:
    root, key = fixture_root(tmp_path)
    reference = fixture_rekor_reference(root, "rekor-fixture")
    document = json.loads(reference.read_text())
    document["artifact_sha256"] = "f" * 64
    reference.write_text(json.dumps(document) + "\n")

    with pytest.raises(ContractError, match="does not bind the health digest"):
        ga.generate(root, key, datetime(2026, 8, 15, 1, tzinfo=timezone.utc), reference)

    assert not (root / "attestations/2026-08-15/binding.json").exists()
