#!/usr/bin/env python3
"""Exercise accepted attestation projection refresh in small Git trees."""
from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
from datetime import timedelta
from pathlib import Path

from scripts import gen_attestations as ga
from scripts.tests.test_append_set_isolation import NOW
from scripts.tests.test_attestations import fixture_root

SCRIPT = Path(__file__).resolve().parents[1] / "gen_attestation_projections.py"
PROJECTIONS = (
    "attestations/latest/index.json",
    "attestations/latest/chain_head.json",
    "attestations/chain-index.json",
)


def git(root: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=root, check=True, capture_output=True, text=True).stdout.strip()


def run(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["python3", str(SCRIPT), "--root", str(root), *args],
                          cwd=root, capture_output=True, text=True, check=False)


def check(condition: bool, label: str) -> None:
    print(f"{'PASS' if condition else 'FAIL'}: {label}")
    assert condition, label


def accepted_root(tmp_path: Path) -> tuple[Path, Path]:
    root, key = fixture_root(tmp_path)
    git(root, "init", "-b", "main")
    git(root, "config", "user.name", "Test")
    git(root, "config", "user.email", "test@example.test")
    (root / ".gitignore").write_text("private.json\n", encoding="utf-8")
    ga.generate(root, key, NOW)
    git(root, "add", "-A")
    git(root, "commit", "-m", "accepted first set")
    return root, key


def accept_next_day(root: Path, key: Path) -> None:
    ga.generate(root, key, NOW + timedelta(days=1))
    git(root, "restore", "--", "attestations/latest", "attestations/chain-index.json",
        ".attestations/chain_head.json", "datapulse.json")
    git(root, "add", "--", "attestations/2026-08-16")
    git(root, "commit", "-m", "accepted evidence only")


def index(root: Path) -> dict:
    return json.loads((root / "attestations/chain-index.json").read_text(encoding="utf-8"))


def test_one_accepted_chain_and_check(tmp_path: Path) -> None:
    root, _ = accepted_root(tmp_path)
    result = run(root)
    check(result.returncode == 0, f"one accepted chain refresh: {result.stderr}")
    result = run(root, "--check")
    check(result.returncode == 0, f"one accepted chain check: {result.stdout} {result.stderr}")


def test_second_revision_advances_head_and_day_count(tmp_path: Path) -> None:
    root, key = accepted_root(tmp_path)
    previous = index(root)
    accept_next_day(root, key)
    result = run(root)
    current = index(root)
    latest_head = json.loads((root / PROJECTIONS[1]).read_text(encoding="utf-8"))
    latest_index = json.loads((root / PROJECTIONS[0]).read_text(encoding="utf-8"))
    check(result.returncode == 0 and current["current_head"] != previous["current_head"]
          and len(current["days"]) == len(previous["days"]) + 1
          and latest_head["chain_head"] == current["current_head"]
          and latest_index["date"] == "2026-08-16",
          f"accepted revision advances head and day count: {result.stderr}")


def test_conflicting_sibling_refuses_with_both_heads(tmp_path: Path) -> None:
    root, key = accepted_root(tmp_path / "accepted")
    accepted = index(root)["current_head"]
    # Two signed siblings with no merge-order authority remain ambiguous.
    sibling = tmp_path / "sibling"
    shutil.copytree(root, sibling)
    ga.generate(root, key, NOW + timedelta(days=1))
    first = next((root / "attestations/2026-08-16/revisions").glob("*/chain_head.json"))
    first_head = json.loads(first.read_text(encoding="utf-8"))["chain_head"]
    git(root, "restore", ".")
    ga.generate(sibling, sibling / key.name, NOW + timedelta(days=1, hours=1))
    second = next((sibling / "attestations/2026-08-16/revisions").glob("*/chain_head.json"))
    shutil.copytree(second.parent, root / second.parent.relative_to(sibling))
    second_head = json.loads(second.read_text(encoding="utf-8"))["chain_head"]
    git(root, "restore", ".")
    git(root, "add", "--", "attestations/2026-08-16")
    git(root, "commit", "-m", "accepted conflicting siblings")
    result = run(root)
    output = result.stdout + result.stderr
    check(result.returncode == 2 and accepted in output and first_head in output
          and second_head in output,
          f"conflicting siblings identify accepted and candidate heads: {output}")


def test_idempotent_second_run(tmp_path: Path) -> None:
    root, _ = accepted_root(tmp_path)
    first = run(root)
    before = {path: hashlib.sha256((root / path).read_bytes()).hexdigest() for path in PROJECTIONS}
    second = run(root)
    after = {path: hashlib.sha256((root / path).read_bytes()).hexdigest() for path in PROJECTIONS}
    check(first.returncode == second.returncode == 0 and before == after and "UNCHANGED" in second.stdout,
          f"second run writes nothing: {second.stdout} {second.stderr}")


def test_check_names_stale_file_and_values(tmp_path: Path) -> None:
    root, key = accepted_root(tmp_path)
    old = index(root)["current_head"]
    accept_next_day(root, key)
    before = {path: (root / path).read_bytes() for path in PROJECTIONS}
    result = run(root, "--check")
    after = {path: (root / path).read_bytes() for path in PROJECTIONS}
    stale = [line for line in result.stdout.splitlines() if line.startswith("STALE ")]
    check(result.returncode == 1 and len(stale) == 3
          and all(path in result.stdout for path in PROJECTIONS)
          and old in result.stdout and "derived=" in result.stdout and before == after,
          f"stale check reports both values without writing: {result.stdout} {result.stderr}")


def test_write_refuses_non_main_branch(tmp_path: Path) -> None:
    root, _ = accepted_root(tmp_path)
    git(root, "switch", "-c", "candidate")
    result = run(root)
    check(result.returncode == 2 and "HEAD must be on branch main" in result.stdout,
          f"write refuses an unaccepted branch: {result.stdout} {result.stderr}")


def test_write_refuses_ignored_untracked_evidence(tmp_path: Path) -> None:
    root, _ = accepted_root(tmp_path)
    (root / ".git/info").mkdir(exist_ok=True)
    (root / ".git/info/exclude").write_text("attestations/ignored.json\n", encoding="utf-8")
    (root / "attestations/ignored.json").write_text("{}\n", encoding="utf-8")
    result = run(root)
    check(result.returncode == 2 and "evidence file is not tracked at HEAD" in result.stdout,
          f"write refuses ignored evidence outside HEAD: {result.stdout} {result.stderr}")
