#!/usr/bin/env python3
"""Pin candidate and projection resolution in the append verifier."""
from __future__ import annotations

import json
import shutil
import subprocess
from collections import Counter
from datetime import timedelta
from pathlib import Path

import pytest

from scripts import attestation_sets, gen_attestations as ga
from scripts import verify_attestation_append as verifier
from scripts.attestation_sets import discovery
from scripts.classify_change import is_append_only_change
from scripts.tests.test_append_set_isolation import NOW, accept, git
from scripts.tests.test_attestations import fixture_root


ROOT = Path(__file__).resolve().parents[2]
SUBMITTER = ROOT / "scripts/submit_attestation_append.sh"


def write_successor(root: Path, parent: str, child: str) -> str:
    source = SUBMITTER.read_text(encoding="utf-8")
    start = source.index("write_successor_record() {")
    end = source.index("\n}", start) + 2
    result = subprocess.run(
        ["bash", "-c", source[start:end] + '\nwrite_successor_record "$1" "$2"',
         "bash", parent, child],
        cwd=root, check=True, capture_output=True, text=True,
    )
    return result.stdout.strip()


def test_same_parent_candidates_conflict_on_successor_record(tmp_path: Path) -> None:
    left, key = fixture_root(tmp_path / "left")
    ga.generate(left, key, NOW)
    base = accept(left)
    parent = discovery(left)["current_head"]
    right = tmp_path / "right"
    shutil.copytree(left, right)

    ga.generate(left, key, NOW + timedelta(days=1))
    ga.generate(right, right / key.name, NOW + timedelta(days=2))
    left_child = discovery(left)["current_head"]
    right_child = discovery(right)["current_head"]
    assert left_child != right_child
    left_path = write_successor(left, parent, left_child)
    right_path = write_successor(right, parent, right_child)
    assert left_path == right_path == f"attestations/successors/{parent}.json"
    assert is_append_only_change((left_path,))
    assert not is_append_only_change(("attestations/successors/not-a-head.json",))
    left_bytes = (left / left_path).read_bytes()
    assert json.loads(left_bytes) == {"parent": parent, "child": left_child}
    assert write_successor(left, parent, left_child) == left_path
    assert (left / left_path).read_bytes() == left_bytes
    right_bytes = (right / right_path).read_bytes()
    assert json.loads(right_bytes) == {"parent": parent, "child": right_child}
    assert left_bytes != right_bytes

    left_paths = verifier.append_paths(left, base)
    right_paths = verifier.append_paths(right, base)
    git(left, "restore", ".")
    verifier.verify_append(left, base)
    git(left, "switch", "-c", "left")
    git(left, "add", "--", *left_paths, left_path)
    git(left, "commit", "-m", "left append")
    git(left, "switch", "-c", "right", base)
    for path in right_paths:
        target = left / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((right / path).read_bytes())
    target = left / right_path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(right_bytes)
    git(left, "add", "--", *right_paths, right_path)
    git(left, "commit", "-m", "right append")
    merge = subprocess.run(
        ["git", "merge", "--no-edit", "left"], cwd=left,
        capture_output=True, text=True,
    )
    assert merge.returncode != 0
    assert f"CONFLICT (add/add): Merge conflict in {left_path}" in merge.stdout
    assert left_path in git(left, "ls-files", "-u")


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
