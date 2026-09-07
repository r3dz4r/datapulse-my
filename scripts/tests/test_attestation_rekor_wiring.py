"""Offline coverage for binding a new day's health snapshot to Rekor evidence."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from scripts import gen_attestations as ga
from scripts.tests.test_attestations import fixture_rekor_reference, fixture_root
from scripts.verify_attestation_binding import ContractError


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


def test_mismatched_rekor_reference_is_rejected_before_binding(tmp_path: Path) -> None:
    root, key = fixture_root(tmp_path)
    reference = fixture_rekor_reference(root, "rekor-fixture")
    document = json.loads(reference.read_text())
    document["artifact_sha256"] = "f" * 64
    reference.write_text(json.dumps(document) + "\n")

    with pytest.raises(ContractError, match="does not bind the health digest"):
        ga.generate(root, key, datetime(2026, 8, 15, 1, tzinfo=timezone.utc), reference)

    assert not (root / "attestations/2026-08-15/binding.json").exists()
