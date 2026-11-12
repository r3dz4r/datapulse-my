#!/usr/bin/env python3
"""Keep generated proof storage consistent with the immutable digest boundary."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import gzip
from pathlib import Path
import shutil

import pytest

from scripts import gen_attestations as ga
from scripts.attestation_sets import selected_directory, verify_set
from scripts.bind_candidate_witness import bind_candidate
from scripts.tests.test_attestations import fixture_rekor_reference, fixture_root, write
from scripts.verify_attestation_binding import ContractError, verify_contract

NOW = datetime(2026, 8, 15, 1, tzinfo=timezone.utc)
DAY = "2026-08-15"


@pytest.mark.parametrize("force_append", [False, True])
@pytest.mark.parametrize("after_correction", [False, True])
def test_stale_health_input_is_refused_before_signing_without_writes(
    tmp_path: Path, force_append: bool, after_correction: bool,
) -> None:
    root, key = fixture_root(tmp_path)
    ga.generate(root, key, NOW)
    health_path = root / "health/latest.json"
    health = ga.load(health_path)
    if after_correction:
        health["checked_at"] = "2026-08-15T00:40:00Z"
        health["datasets"][0]["last_checked"] = health["checked_at"]
        write(health_path, health)
        ga.generate(root, key, NOW + timedelta(minutes=1))
    document = ga.discovery(root)
    reference = ga.set_directory(document["heads"][document["current_head"]]) + "/binding.json"
    bound = ga.load(root / reference)["payload"]["health"]["observed_at"]
    # The correction case is newer than the original daily alias but older
    # than the latest immutable revision; mutable projections are no authority.
    health["checked_at"] = "2026-08-15T00:20:00Z" if after_correction else "2026-08-14T23:59:59Z"
    health["datasets"][0]["last_checked"] = health["checked_at"]
    write(health_path, health)
    (root / "attestations/latest/binding.json").write_bytes(b"{}\n")
    key.unlink()
    before = {path.relative_to(root): path.read_bytes() for path in root.rglob("*") if path.is_file()}

    with pytest.raises(ValueError, match="stale_health_input:") as error:
        ga.generate(root, key, NOW + timedelta(minutes=2), force_append=force_append)

    assert health["checked_at"] in str(error.value)
    assert bound in str(error.value)
    assert reference in str(error.value)
    assert {path.relative_to(root): path.read_bytes() for path in root.rglob("*") if path.is_file()} == before


@pytest.mark.parametrize("force_append", [False, True])
@pytest.mark.parametrize("change", ["equal", "equal_correction", "newer"])
def test_equal_or_newer_health_keeps_reuse_and_append_behaviour(
    tmp_path: Path, force_append: bool, change: str,
) -> None:
    root, key = fixture_root(tmp_path)
    ga.generate(root, key, NOW)
    directory = selected_directory(root)
    accepted = {path: path.read_bytes() for path in (root / "attestations" / DAY).rglob("*")
                if path.is_file()}
    health = ga.load(root / "health/latest.json")
    if change == "equal_correction":
        health["datasets"][0]["status"] = "aging"
    elif change == "newer":
        health["checked_at"] = "2026-08-15T00:40:00Z"
        health["datasets"][0]["last_checked"] = health["checked_at"]
    write(root / "health/latest.json", health)

    ga.generate(root, key, NOW + timedelta(minutes=1), force_append=force_append)

    selected = selected_directory(root)
    assert (selected == directory) is (change == "equal" and not force_append)
    assert all(path.read_bytes() == content for path, content in accepted.items())
    verify_set(root, selected + "/chain_head.json")
    assert verify_contract(root, now=NOW + timedelta(minutes=1))["health"]["observed_at"] == health["checked_at"]
    if selected != directory:
        binding = ga.load(root / selected / "binding.json")["payload"]
        prior_head = ga.load(root / directory / "chain_head.json")["chain_head"]
        assert binding["correction"]["supersedes_chain_head"] == prior_head


def test_already_appended_alias_legacy_snapshot_refreshes_chain_head(tmp_path: Path) -> None:
    root, key = fixture_root(tmp_path)
    ga.generate(root, key, NOW)
    daily = root / "attestations" / DAY
    compressed = daily / "health.json.gz"
    (daily / "health.json").write_bytes(gzip.decompress(compressed.read_bytes()))
    compressed.unlink()
    verify_set(root, f"attestations/{DAY}/chain_head.json")
    accepted_index = (root / "attestations/chain-index.json").read_bytes()
    expected_head = (root / selected_directory(root) / "chain_head.json").read_bytes()
    mirror = root / ".attestations/chain_head.json"
    mirror.write_bytes(b"{}\n")

    ga.generate(root, key, NOW)

    assert mirror.read_bytes() == expected_head
    assert (root / "attestations/latest/chain_head.json").read_bytes() == expected_head
    assert (root / "attestations/chain-index.json").read_bytes() == accepted_index
    assert not compressed.exists()
    verify_set(root, f"attestations/{DAY}/chain_head.json")


@pytest.mark.parametrize("name", [*ga.FILES, "health.json.gz", "sample.json",
                                  "rekor-reference.json", "rekor-bundle.json"])
def test_already_appended_alias_absent_from_staging_preserves_committed_bytes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture, name: str,
) -> None:
    root, key = fixture_root(tmp_path)
    reference = fixture_rekor_reference(root, "rekor-fixture")
    ga.generate(root, key, NOW, reference)
    accepted = {path: path.read_bytes() for path in (root / "attestations" / DAY).rglob("*")
                if path.is_file()}
    accepted_index = (root / "attestations/chain-index.json").read_bytes()
    expected_head = (root / selected_directory(root) / "chain_head.json").read_bytes()
    mirror = root / ".attestations/chain_head.json"
    mirror.write_bytes(b"{}\n")
    prepare = ga._generate

    def prepare_without_alias(staging: Path, *args: object) -> None:
        prepare(staging, *args)
        assert (staging / "attestations/chain-index.json").read_bytes() == accepted_index
        (staging / "attestations" / DAY / name).unlink()

    monkeypatch.setattr(ga, "_generate", prepare_without_alias)
    ga.generate(root, key, NOW, reference)

    assert mirror.read_bytes() == expected_head
    assert (root / "attestations/latest/chain_head.json").read_bytes() == expected_head
    assert (root / "attestations/chain-index.json").read_bytes() == accepted_index
    assert all(path.read_bytes() == data for path, data in accepted.items())
    assert f"Skipping absent staged daily alias: attestations/{DAY}/{name}" in caplog.text


@pytest.mark.parametrize("name, message", [
    ("scores.json", "original daily attestation cannot be overwritten"),
    ("sample.json", "legacy dataset attestation cannot be overwritten"),
])
def test_present_staged_alias_disagreement_still_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, name: str, message: str,
) -> None:
    root, key = fixture_root(tmp_path)
    ga.generate(root, key, NOW)
    alias = root / "attestations" / DAY / name
    accepted = alias.read_bytes()
    prepare = ga._generate

    def prepare_with_disagreement(staging: Path, *args: object) -> None:
        prepare(staging, *args)
        (staging / "attestations" / DAY / name).write_bytes(b"{}\n")

    monkeypatch.setattr(ga, "_generate", prepare_with_disagreement)
    with pytest.raises(ValueError, match=message):
        ga.generate(root, key, NOW)
    assert alias.read_bytes() == accepted


@pytest.mark.parametrize("external", [False, True])
def test_generated_witness_verifies_in_revision_and_daily_set(tmp_path: Path, external: bool) -> None:
    root, key = fixture_root(tmp_path)
    reference = fixture_rekor_reference(root, f"rekor/{DAY}" if external else "rekor-fixture")

    ga.generate(root, key, NOW, reference)

    revision = selected_directory(root)
    for directory in (revision, f"attestations/{DAY}"):
        verify_set(root, directory + "/chain_head.json")
        for filename in ("rekor-reference.json", "rekor-bundle.json"):
            assert (root / directory / filename).is_file() is not external
    assert verify_contract(root, now=NOW, require_rekor=True)["claims"]["rekor_witnessed"] is True


def test_external_witness_timing_does_not_change_set_identity(tmp_path: Path) -> None:
    early, key = fixture_root(tmp_path / "early")
    late = tmp_path / "late"
    shutil.copytree(early, late)
    early_reference = fixture_rekor_reference(early, f"rekor/{DAY}")
    late_reference = fixture_rekor_reference(late, f"rekor/{DAY}")

    ga.generate(early, key, NOW, early_reference)
    ga.generate(late, late / key.name, NOW)
    bind_candidate(late, late / key.name, late_reference)

    assert selected_directory(early) == selected_directory(late)
    for root in (early, late):
        assert verify_contract(root, now=NOW, require_rekor=True)["claims"]["rekor_witnessed"] is True


@pytest.mark.parametrize("external", [False, True])
def test_witness_tampering_is_rejected_on_both_sides_of_digest_boundary(tmp_path: Path, external: bool) -> None:
    root, key = fixture_root(tmp_path)
    reference = fixture_rekor_reference(root, f"rekor/{DAY}" if external else "rekor-fixture")
    ga.generate(root, key, NOW, reference)
    directory = selected_directory(root)
    path = reference if external else root / directory / "rekor-reference.json"
    document = ga.load(path)
    if external:
        document["artifact_sha256"] = "0" * 64
        message = "does not bind the health digest"
    else:
        # This extra field does not invalidate the proof contract, but changing
        # copied immutable bytes must still invalidate the set digest.
        document["extra"] = "tampered"
        message = "content digest"
    write(path, document)

    with pytest.raises(ContractError, match=message):
        verify_set(root, directory + "/chain_head.json")
