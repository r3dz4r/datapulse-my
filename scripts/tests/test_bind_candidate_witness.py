"""Exercise the candidate witness write against the immutable set verifier."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from scripts import gen_attestations as ga
from scripts.attestation_sets import selected_directory, verify_set
from scripts.bind_candidate_witness import bind_candidate
from scripts.tests.test_attestations import fixture_rekor_reference, fixture_root, write
from scripts.verify_attestation_binding import ContractError


NOW = datetime(2026, 8, 15, 1, tzinfo=timezone.utc)


def test_late_witness_bind_leaves_candidate_set_verifiable(tmp_path: Path) -> None:
    root, key = fixture_root(tmp_path)
    ga.generate(root, key, NOW)
    directory = selected_directory(root)
    head_ref = directory + "/chain_head.json"
    original_digest = ga.load(root / head_ref)["payload"]["append_content_sha256"]
    reference = fixture_rekor_reference(root, "rekor/2026-08-15")

    bind_candidate(root, key, reference)

    binding = ga.load(root / directory / "binding.json")
    assert binding["rekor"]["reference_ref"] == reference.relative_to(root).as_posix()
    assert binding["claims"]["rekor_witnessed"] is True
    assert ga.load(root / head_ref)["payload"]["append_content_sha256"] == original_digest
    assert ga.load(root / "attestations/latest/binding.json") == binding
    verify_set(root, head_ref)


def test_corrupted_bound_witness_is_refused(tmp_path: Path) -> None:
    root, key = fixture_root(tmp_path)
    ga.generate(root, key, NOW)
    reference = fixture_rekor_reference(root, "rekor/2026-08-15")
    bind_candidate(root, key, reference)
    directory = selected_directory(root)
    binding_path = root / directory / "binding.json"
    binding = ga.load(binding_path)
    binding["rekor"]["bundle_ref"] = "attestations/rekor/2026-08-15/missing.json"
    write(binding_path, binding)

    with pytest.raises(ContractError):
        verify_set(root, directory + "/chain_head.json")
