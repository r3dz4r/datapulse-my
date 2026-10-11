#!/usr/bin/env python3
"""Exercise acceptance waiting against real local Git authorities and signed sets."""
from __future__ import annotations

from datetime import timedelta
from pathlib import Path
import subprocess

import pytest

from scripts import gen_attestations as ga
from scripts import verify_attestation_append as verifier
from scripts.tests.test_append_set_isolation import NOW, accept, git
from scripts.tests.test_attestations import fixture_root


@pytest.fixture
def candidate(tmp_path: Path) -> tuple[Path, str, Path, Path, list[str]]:
    root, key = fixture_root(tmp_path / "candidate")
    ga.generate(root, key, NOW)
    source = accept(root)
    origin = tmp_path / "origin.git"
    git(root, "clone", "--bare", str(root), str(origin))
    git(root, "remote", "add", "origin", str(origin))
    authority = tmp_path / "authority"
    git(root, "clone", str(origin), str(authority))
    git(authority, "config", "user.name", "Test")
    git(authority, "config", "user.email", "test@example.test")
    ga.generate(root, key, NOW + timedelta(hours=1), force_append=True)
    paths = verifier.append_paths(root, source)
    for path in paths:
        target = authority / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((root / path).read_bytes())
    return root, source, authority, origin, paths


def merge_append(authority: Path, origin: Path) -> None:
    git(authority, "add", "attestations")
    git(authority, "commit", "-m", "accept immutable append")
    git(authority, "--git-dir=" + str(origin), "fetch", str(authority), "main:main")


def test_wait_observes_later_merge_without_mutating_candidate(
    candidate: tuple[Path, str, Path, Path, list[str]], monkeypatch: pytest.MonkeyPatch,
) -> None:
    root, source, authority, origin, paths = candidate
    frozen = {path: (root / path).read_bytes() for path in paths}
    health = (root / "health/latest.json").read_bytes()
    sleeps = []

    def accept_on_sleep(seconds: float) -> None:
        sleeps.append(seconds)
        assert git(root, "rev-parse", "origin/main") == source
        merge_append(authority, origin)

    monkeypatch.setattr(verifier.time, "sleep", accept_on_sleep)
    verifier.wait_for_acceptance(root, source, timeout=60, poll_seconds=1)
    assert sleeps == [1]
    assert git(root, "rev-parse", "HEAD") == source
    assert (root / "health/latest.json").read_bytes() == health
    assert {path: (root / path).read_bytes() for path in paths} == frozen
    verifier.verify_append(root, "origin/main", require_committed=True)


@pytest.mark.parametrize("changed_file", ["head", "binding", "health", "missing"])
def test_wait_rejects_inexact_authoritative_evidence(
    candidate: tuple[Path, str, Path, Path, list[str]], changed_file: str,
) -> None:
    root, source, authority, origin, paths = candidate
    name = {"head": "chain_head.json", "binding": "binding.json",
            "health": "health.json.gz", "missing": "binding.json"}[changed_file]
    path = authority / next(path for path in paths if path.endswith("/" + name))
    if changed_file == "missing":
        path.unlink()
    else:
        path.write_bytes(path.read_bytes() + b" ")
    merge_append(authority, origin)
    with pytest.raises(ValueError, match="bytes disagree|immutable evidence changed|missing"):
        verifier.wait_for_acceptance(root, source, timeout=0)


def test_wait_rejects_main_that_does_not_contain_source(
    candidate: tuple[Path, str, Path, Path, list[str]],
) -> None:
    root, source, authority, origin, _ = candidate
    git(authority, "checkout", "--orphan", "unrelated")
    git(authority, "add", "attestations", "docs", "health", "datapulse.json")
    git(authority, "commit", "-m", "unrelated evidence")
    git(authority, "--git-dir=" + str(origin), "fetch", str(authority), "unrelated:refs/heads/main", "--force")
    with pytest.raises(subprocess.CalledProcessError):
        verifier.wait_for_acceptance(root, source, timeout=0)


def test_wait_fails_closed_on_fetch_error(
    candidate: tuple[Path, str, Path, Path, list[str]],
) -> None:
    root, source, _, _, _ = candidate
    git(root, "remote", "set-url", "origin", str(root / "missing-origin"))
    with pytest.raises(subprocess.CalledProcessError):
        verifier.wait_for_acceptance(root, source, timeout=0)
