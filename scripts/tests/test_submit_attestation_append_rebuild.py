"""A filed append is replaced from main when its Git parent is overtaken."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

from scripts import gen_attestations as ga
from scripts.tests.test_attestation_projections import accepted_root
from scripts.tests.test_attestations import fixture_root


ROOT = Path(__file__).resolve().parents[2]


def _git(root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=root, check=True, capture_output=True, text=True
    ).stdout.strip()


def test_nothing_to_append_writes_noop_result(tmp_path: Path) -> None:
    root, _ = accepted_root(tmp_path / "repo")
    scripts = root / "scripts"
    scripts.mkdir()
    for name in (
        "verify_attestation_append.py", "attestation_fetch_refs.py", "attestation_sets.py",
        "verify_attestation_binding.py", "attestation_commit_back.py", "gen_attestations.py",
    ):
        shutil.copyfile(ROOT / "scripts" / name, scripts / name)
    _git(root, "remote", "add", "origin", str(root))
    result_file = tmp_path / "submission-result"
    result = subprocess.run(
        ["bash", str(ROOT / "scripts/submit_attestation_append.sh")], cwd=root,
        env={**os.environ, "APPEND_SUBMISSION_RESULT": str(result_file)},
        capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert result_file.read_text().split() == ["noop", "-", "0"]


@pytest.mark.parametrize("advance_chain", [False, True])
def test_filed_append_is_rebuilt_from_moved_main_once(tmp_path: Path, advance_chain: bool) -> None:
    root, key = fixture_root(tmp_path / "repo")
    scripts = root / "scripts"
    scripts.mkdir()
    for name in (
        "verify_attestation_append.py", "attestation_fetch_refs.py", "attestation_sets.py",
        "verify_attestation_binding.py", "attestation_commit_back.py", "gen_attestations.py",
    ):
        shutil.copyfile(ROOT / "scripts" / name, scripts / name)
    ga.generate(root, key, datetime(2026, 8, 15, 1, tzinfo=timezone.utc))
    _git(root, "init", "-b", "main")
    _git(root, "config", "user.name", "Test")
    _git(root, "config", "user.email", "test@example.test")
    _git(root, "add", "attestations", ".attestations", "docs", "scripts", "datapulse.json", "health")
    _git(root, "commit", "-m", "accepted fixture")
    remote = tmp_path / "origin.git"
    _git(tmp_path, "clone", "--bare", str(root), str(remote))
    _git(root, "remote", "add", "origin", str(remote))
    ga.generate(root, key, datetime(2026, 8, 16, 1, tzinfo=timezone.utc))

    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    gh = bin_dir / "gh"
    gh.write_text(
        f"#!{sys.executable}\n"
        "import json, os, sys\n"
        "args = sys.argv[1:]\n"
        "with open(os.environ['GH_CALLS'], 'a') as log: log.write(' '.join(args) + '\\n')\n"
        "if args[:2] == ['pr', 'view']:\n"
        " print(json.dumps({'number': 7, 'headRefName': os.environ['OLD_BRANCH'],"
        " 'headRefOid': os.environ['OLD_SHA'], 'baseRefName': 'main', 'state': 'OPEN'}))\n"
    )
    gh.chmod(0o755)
    env = {**os.environ, "PATH": str(bin_dir) + os.pathsep + os.environ["PATH"],
           "GH_CALLS": str(tmp_path / "gh-calls"), "DATAPULSE_ALLOW_UNWITNESSED_PUBLICATION": "1"}
    first = subprocess.run(
        ["bash", str(ROOT / "scripts/submit_attestation_append.sh")], cwd=root,
        env=env, capture_output=True, text=True,
    )
    assert first.returncode == 0, first.stdout + first.stderr
    old_branch = _git(root, "branch", "--show-current")
    old_sha = _git(root, "rev-parse", "HEAD")

    advance = tmp_path / "advance"
    _git(tmp_path, "clone", str(remote), str(advance))
    _git(advance, "config", "user.name", "Test")
    _git(advance, "config", "user.email", "test@example.test")
    (advance / "advance.txt").write_text("main moved\n", encoding="utf-8")
    _git(advance, "add", "advance.txt")
    if advance_chain:
        ga.generate(advance, key, datetime(2026, 8, 15, 2, tzinfo=timezone.utc), force_append=True)
        _git(advance, "add", "attestations", ".attestations")
    _git(advance, "commit", "-m", "advance accepted base")
    accepted = _git(advance, "rev-parse", "HEAD")
    _git(advance, "push", "origin", "main")

    result_file = tmp_path / "submission-result"
    if advance_chain:
        missing_key = subprocess.run(
            ["bash", str(ROOT / "scripts/submit_attestation_append.sh"),
             "--rebuild", "7", old_branch, old_sha],
            cwd=root, env={**env, "OLD_BRANCH": old_branch, "OLD_SHA": old_sha},
            capture_output=True, text=True,
        )
        assert missing_key.returncode != 0
        assert "signing key unavailable" in missing_key.stderr
        assert accepted in missing_key.stderr and _git(root, "rev-parse", f"{old_sha}^") in missing_key.stderr
    env.update(OLD_BRANCH=old_branch, OLD_SHA=old_sha, APPEND_SUBMISSION_RESULT=str(result_file),
               DATAPULSE_ATTESTATION_PRIVATE_KEY_FILE=str(key))
    rebuilt = subprocess.run(
        ["bash", str(ROOT / "scripts/submit_attestation_append.sh"),
         "--rebuild", "7", old_branch, old_sha],
        cwd=root, env=env, capture_output=True, text=True,
    )
    assert rebuilt.returncode == 0, rebuilt.stdout + rebuilt.stderr
    assert "append rebased onto the accepted head" in rebuilt.stdout
    branch, sha, marker = result_file.read_text().split()
    assert marker == "1"
    assert branch.startswith("attestation/append-") and branch != old_branch
    assert _git(remote, "rev-parse", f"{branch}^") == accepted
    assert _git(remote, "rev-parse", branch) == sha
    assert "pr close 7" in (tmp_path / "gh-calls").read_text()

    again = subprocess.run(
        ["bash", str(ROOT / "scripts/submit_attestation_append.sh"),
         "--rebuild", "8", branch, sha],
        cwd=root, env=env, capture_output=True, text=True,
    )
    assert again.returncode != 0
    assert "second append rebuild" in again.stderr
