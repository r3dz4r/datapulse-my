#!/usr/bin/env python3
"""Prove staged-byte isolation independently of any particular filename list."""
from __future__ import annotations

import shutil
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from scripts import gen_attestations as ga
from scripts.attestation_sets import discovery, selected_directory, verify_set
from scripts.tests.test_attestations import fixture_root, write
from scripts.verify_attestation_append import append_paths, verify_append
from scripts.verify_attestation_binding import ContractError
from scripts.verify_chain_linearity import verify_chain_linearity

NOW = datetime(2026, 8, 15, 1, tzinfo=timezone.utc)


def git(root: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=root, check=True,
                          capture_output=True, text=True).stdout.strip()


def accept(root: Path) -> str:
    if not (root / ".git").exists():
        git(root, "init", "-b", "main")
        git(root, "config", "user.name", "Test")
        git(root, "config", "user.email", "test@example.test")
    # Signing keys are intentionally excluded from the fixture Git tree.
    git(root, "add", "attestations", ".attestations", "docs", "health", "datapulse.json")
    git(root, "commit", "-m", "accept fixture")
    return git(root, "rev-parse", "HEAD")


def staged_bytes(root: Path, base: str) -> dict[str, bytes]:
    paths = append_paths(root, base)
    assert paths, "fixture must contain a real append"
    return {path: (root / path).read_bytes() for path in paths}


def assert_isolated(left: dict[str, bytes], right: dict[str, bytes]) -> None:
    differing = [path for path in left.keys() & right.keys() if left[path] != right[path]]
    assert not differing, f"shared staged paths differ: {sorted(differing)}"


@pytest.mark.parametrize("same_day", [True, False])
def test_candidates_from_different_heads_have_no_differing_staged_path(
    tmp_path: Path, same_day: bool,
) -> None:
    left, key = fixture_root(tmp_path / "left")
    ga.generate(left, key, NOW)
    right = tmp_path / "right"
    shutil.copytree(left, right)
    left_base = accept(left)
    health = ga.load(right / "health/latest.json")
    health["datasets"][0]["status"] = "aging"
    write(right / "health/latest.json", health)
    ga.generate(right, right / key.name, NOW + timedelta(hours=1))
    right_base = accept(right)
    parents = [discovery(root)["current_head"] for root in (left, right)]
    assert parents[0] != parents[1]
    target = NOW + (timedelta(hours=2) if same_day else timedelta(days=1))
    ga.generate(left, key, target, force_append=True)
    ga.generate(right, right / key.name, target, force_append=True)
    assert_isolated(staged_bytes(left, left_base), staged_bytes(right, right_base))


def test_binding_publication_and_scores_are_part_of_directory_identity(tmp_path: Path) -> None:
    left, key = fixture_root(tmp_path / "left")
    right = tmp_path / "right"
    shutil.copytree(left, right)
    # The legacy daily digest excluded publication time and scores. Those
    # differences must now produce distinct paths even with identical probes.
    ga.generate(left, key, NOW)
    ga.generate(right, right / key.name, NOW + timedelta(hours=1))
    assert discovery(left)["current_head"] != discovery(right)["current_head"]
    l = {p.relative_to(left).as_posix(): p.read_bytes()
         for p in (left / selected_directory(left)).iterdir()}
    r = {p.relative_to(right).as_posix(): p.read_bytes()
         for p in (right / selected_directory(right)).iterdir()}
    assert_isolated(l, r)


def test_immutable_only_append_advances_discovery_without_projection_writes(tmp_path: Path) -> None:
    root, key = fixture_root(tmp_path)
    ga.generate(root, key, NOW)
    base = accept(root)
    old_head = discovery(root)["current_head"]
    ga.generate(root, key, NOW + timedelta(days=1))
    new_head = discovery(root)["current_head"]
    paths = append_paths(root, base)
    # Restore every tracked file, retaining only the independently staged set.
    git(root, "restore", ".")
    assert discovery(root)["current_head"] == new_head != old_head
    assert verify_chain_linearity(root).chain_head == new_head
    verify_append(root, base)
    with pytest.raises(ValueError, match="must be accepted"):
        verify_append(root, base, require_committed=True)
    git(root, "add", "--", *paths)
    git(root, "commit", "-m", "immutable-only append")
    verify_append(root, "HEAD")
    with pytest.raises(ContractError, match="stale or mixed"):
        verify_append(root, "HEAD", require_committed=True)
    assert set(git(root, "diff", "--name-only", base, "HEAD").splitlines()) == set(paths)
    # Publication still refuses the inherited stale view until it is derived.
    with pytest.raises(ContractError, match="stale or mixed"):
        selected_directory(root)
    directory = selected_directory(root, projections=False)
    ga.promote(root, directory)
    assert selected_directory(root) == directory
    verify_append(root, "HEAD", require_committed=True)


def test_structurally_mergeable_signed_fork_still_fails_accepted_parent(tmp_path: Path) -> None:
    root, key = fixture_root(tmp_path / "left")
    ga.generate(root, key, NOW)
    base = accept(root)
    fork = tmp_path / "fork"
    shutil.copytree(root, fork)
    ga.generate(root, key, NOW + timedelta(days=1))
    ga.generate(fork, fork / key.name, NOW + timedelta(days=2))
    left, right = staged_bytes(root, base), staged_bytes(fork, base)
    assert_isolated(left, right)
    git(root, "restore", ".")
    git(root, "switch", "-c", "left")
    git(root, "add", "--", *left)
    git(root, "commit", "-m", "left append")
    git(root, "switch", "-c", "right", base)
    for path, data in right.items():
        target = root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    git(root, "add", "--", *right)
    git(root, "commit", "-m", "right append")
    git(root, "merge", "--no-edit", "left")
    with pytest.raises(ContractError, match="accepted parent"):
        discovery(root)
    with pytest.raises(ContractError, match="accepted parent"):
        verify_append(root, base)


def test_content_digest_detects_unsigned_score_edit(tmp_path: Path) -> None:
    root, key = fixture_root(tmp_path)
    ga.generate(root, key, NOW)
    path = root / selected_directory(root) / "scores.json"
    scores = ga.load(path)
    scores["datasets"][0]["score"] = 0
    write(path, scores)
    with pytest.raises(ContractError, match="content digest"):
        discovery(root)


def test_compatible_append_union_has_one_head_in_either_file_merge_order(tmp_path: Path) -> None:
    root, key = fixture_root(tmp_path / "source")
    ga.generate(root, key, NOW)
    first_base = accept(root)
    historical = discovery(root)
    historical_ref = historical["heads"][historical["current_head"]]
    historical_bytes = (root / Path(historical_ref).parent / "binding.json").read_bytes()
    checkpoint = tmp_path / "checkpoint"
    shutil.copytree(root, checkpoint)
    ga.generate(root, key, NOW + timedelta(days=1))
    first = staged_bytes(root, first_base)
    second_base = accept(root)
    ga.generate(root, key, NOW + timedelta(days=1, hours=1), force_append=True)
    second = staged_bytes(root, second_base)
    terminal = discovery(root)["current_head"]
    assert_isolated(first, second)
    for number, order in enumerate(((first, second), (second, first))):
        merged = tmp_path / f"merged-{number}"
        shutil.copytree(checkpoint, merged)
        for files in order:
            for path, data in files.items():
                target = merged / path
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(data)
        assert discovery(merged)["current_head"] == terminal
        verify_append(merged, "HEAD")
        assert (merged / Path(historical_ref).parent / "binding.json").read_bytes() == historical_bytes
        assert verify_set(merged, historical_ref)["chain_head"] == historical["current_head"]


def test_accepted_binding_raw_bytes_cannot_be_rewritten(tmp_path: Path) -> None:
    root, key = fixture_root(tmp_path)
    ga.generate(root, key, NOW)
    base = accept(root)
    directory = selected_directory(root)
    ga.generate(root, key, NOW + timedelta(days=1))
    binding = root / directory / "binding.json"
    binding.write_bytes(binding.read_bytes() + b" ")
    with pytest.raises(ValueError, match="immutable evidence changed or deleted"):
        verify_append(root, base)
