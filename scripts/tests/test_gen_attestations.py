#!/usr/bin/env python3
"""Keep generated proof storage consistent with the immutable digest boundary."""
from __future__ import annotations

from datetime import datetime, timezone
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
