#!/usr/bin/env python3
"""Pin candidate and projection resolution in the append verifier."""
from __future__ import annotations

from collections import Counter
from datetime import timedelta
from pathlib import Path

import pytest

from scripts import attestation_sets, gen_attestations as ga
from scripts import verify_attestation_append as verifier
from scripts.attestation_sets import discovery
from scripts.tests.test_append_set_isolation import NOW, accept, git
from scripts.tests.test_attestations import fixture_root


ROOT = Path(__file__).resolve().parents[2]


def test_new_append_set_is_verified_once_per_discovery(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    root, key = fixture_root(tmp_path)
    ga.generate(root, key, NOW)
    accept(root)
    ga.generate(root, key, NOW + timedelta(days=1))
    git(root, "restore", ".")
    candidate = next((root / "attestations/2026-08-16/revisions").glob("*/chain_head.json"))
    reference = candidate.relative_to(root).as_posix()
    calls: Counter[str] = Counter()
    original = attestation_sets.verify_set

    def count(candidate_root: Path, candidate_ref: str, *, verify_datasets: bool = True) -> dict:
        calls[candidate_ref] += 1
        return original(candidate_root, candidate_ref, verify_datasets=verify_datasets)

    monkeypatch.setattr(attestation_sets, "verify_set", count)
    document = discovery(root)
    assert document["heads"][document["current_head"]] == reference
    assert calls[reference] == 1


def test_mirror_directory_follows_aligned_projection(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    root, key = fixture_root(tmp_path / "candidate")
    ga.generate(root, key, NOW)
    base = accept(root)
    base_head = discovery(root)["current_head"]
    ga.generate(root, key, NOW + timedelta(days=1))
    candidate_head = discovery(root)["current_head"]
    assert candidate_head != base_head
    # Keep immutable append evidence, while restoring inherited projections.
    git(root, "restore", ".")
    assert discovery(root)["current_head"] == candidate_head
    resolved: list[str] = []
    original = verifier.accepted_day_directory

    def record(candidate_root: Path, document: dict) -> str:
        resolved.append(document["current_head"])
        return original(candidate_root, document)

    monkeypatch.setattr(verifier, "accepted_day_directory", record)
    verifier.verify_append(root, base)
    assert resolved == [base_head]


def test_committed_candidate_checks_mirror_once_in_private_fixture(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    root, key = fixture_root(tmp_path / "candidate")
    checkout_mirror = ROOT / ".attestations/chain_head.json"
    checkout_bytes = checkout_mirror.read_bytes()
    assert root.resolve() != ROOT.resolve()
    assert (root / ".attestations/chain_head.json").resolve().is_relative_to(tmp_path.resolve())
    ga.generate(root, key, NOW)
    accept(root)
    ga.generate(root, key, NOW + timedelta(days=1))
    accept(root)
    calls: list[tuple[str, str]] = []
    original = verifier.verify_legacy_mirror

    def record(candidate_root: Path, document: dict, directory: str) -> None:
        calls.append((document["current_head"], directory))
        original(candidate_root, document, directory)

    monkeypatch.setattr(verifier, "verify_legacy_mirror", record)
    monkeypatch.setattr(attestation_sets, "verify_legacy_mirror", record)
    verifier.verify_append(root, "HEAD", require_committed=True)
    assert len(calls) == 1
    assert calls[0][0] == discovery(root)["current_head"]
    assert checkout_mirror.read_bytes() == checkout_bytes
