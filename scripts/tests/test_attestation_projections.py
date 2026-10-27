#!/usr/bin/env python3
"""Exercise accepted attestation projection refresh in small Git trees."""
from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
from datetime import timedelta
from pathlib import Path

import pytest

from scripts import gen_attestations as ga
from scripts.attestation_sets import verify_legacy_mirror
from scripts.tests.test_append_set_isolation import NOW
from scripts.tests.test_attestations import fixture_root
from scripts.verify_attestation_append import accepted_discovery, append_paths

SCRIPT = Path(__file__).resolve().parents[1] / "gen_attestation_projections.py"
PROJECTIONS = (
    "attestations/latest/index.json",
    "attestations/latest/chain_head.json",
    "attestations/chain-index.json",
    ".attestations/chain_head.json",
    "attestations/latest/binding.json",
    "attestations/latest/scores.json",
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


def test_daily_alias_materialization_with_one_accepted_revision(tmp_path: Path) -> None:
    producer, key = accepted_root(tmp_path / "producer")
    base = git(producer, "rev-parse", "HEAD")
    now = NOW + timedelta(days=1)
    day = now.date().isoformat()
    ga.generate(producer, key, now)
    head = index(producer)["current_head"]
    directory = Path("attestations") / day / "revisions" / head
    candidate = {path.name: path.read_bytes() for path in (producer / directory).iterdir()}
    paths = append_paths(producer, base)
    assert paths and all(Path(path).parent == directory for path in paths)
    git(producer, "restore", "--", "attestations/latest", "attestations/chain-index.json",
        ".attestations/chain_head.json", "datapulse.json")
    git(producer, "add", "--", *paths)
    git(producer, "commit", "-m", "accept immutable revision only")
    root = tmp_path / "accepted"
    git(producer, "clone", "--no-local", str(producer), str(root))
    result = run(root)
    assert result.returncode == 0, result.stdout + result.stderr
    assert index(root)["days"][day] == [head]
    assert index(root)["heads"][head] == (directory / "chain_head.json").as_posix()
    assert not any(path.is_file() for path in (root / "attestations" / day).iterdir())

    ga.generate(root, key, now)

    for name in ga.FILES:
        assert (root / "attestations/latest" / name).read_bytes() == candidate[name]
    assert (root / ".attestations/chain_head.json").read_bytes() == candidate["chain_head.json"]
    assert {path.name: path.read_bytes() for path in (root / directory).iterdir()} == candidate
    assert not any(path.is_file() for path in (root / "attestations" / day).iterdir())


def test_daily_alias_materialization_matches_staged_bytes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    root, key = accepted_root(tmp_path)
    now = NOW + timedelta(days=1)
    day = Path("attestations") / now.date().isoformat()
    candidate: dict[str, bytes] = {}
    generate_candidate = ga._generate

    def capture(staging: Path, *args, **kwargs) -> None:
        generate_candidate(staging, *args, **kwargs)
        candidate.update({path.name: path.read_bytes() for path in (staging / day).iterdir()
                          if path.is_file()})

    monkeypatch.setattr(ga, "_generate", capture)
    ga.generate(root, key, now)

    assert set(candidate) == {*ga.FILES, "health.json.gz", "sample.json"}
    assert {path.name: path.read_bytes() for path in (root / day).iterdir()
            if path.is_file()} == candidate


@pytest.mark.parametrize("target, message", [
    ("chain_head.json", "original daily attestation cannot be overwritten"),
    ("sample.json", "legacy dataset attestation cannot be overwritten"),
    ("revision", "immutable destination cannot be overwritten"),
])
def test_daily_alias_materialization_preserves_overwrite_guards(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, target: str, message: str,
) -> None:
    root, key = accepted_root(tmp_path)
    day = Path("attestations") / NOW.date().isoformat()
    before = {path.relative_to(root): path.read_bytes() for path in (root / day).rglob("*")
              if path.is_file()}
    generate_candidate = ga._generate

    def conflict(staging: Path, *args, **kwargs) -> None:
        generate_candidate(staging, *args, **kwargs)
        path = (next((staging / day / "revisions").glob("*/chain_head.json"))
                if target == "revision" else staging / day / target)
        path.write_bytes(path.read_bytes() + b" ")

    monkeypatch.setattr(ga, "_generate", conflict)
    with pytest.raises(ValueError, match=message):
        ga.generate(root, key, NOW)
    assert {path: (root / path).read_bytes() for path in before} == before


def test_second_revision_advances_head_and_day_count(tmp_path: Path) -> None:
    root, key = accepted_root(tmp_path)
    previous = index(root)
    accept_next_day(root, key)
    latest_scores = root / "attestations/latest/scores.json"
    latest_scores.write_bytes(b'{"generated_at":"2000-01-01T00:00:00Z"}\n')
    result = run(root)
    current = index(root)
    latest_head = json.loads((root / PROJECTIONS[1]).read_text(encoding="utf-8"))
    latest_index = json.loads((root / PROJECTIONS[0]).read_text(encoding="utf-8"))
    check(result.returncode == 0 and current["current_head"] != previous["current_head"]
          and current["current_head"] == accepted_discovery(root, "HEAD")["current_head"]
          and len(current["days"]) == len(previous["days"]) + 1
          and latest_head["chain_head"] == current["current_head"]
          and latest_index["date"] == "2026-08-16",
          f"accepted revision advances head and day count: {result.stderr}")
    binding = root / "attestations/latest/binding.json"
    assert binding.read_bytes() == (root / latest_index["binding_ref"]).read_bytes()
    assert json.loads(binding.read_bytes())["payload"]["ed25519"]["chain_head"] == current["current_head"]
    assert latest_scores.read_bytes() == (root / Path(latest_index["binding_ref"]).with_name("scores.json")).read_bytes()


def test_older_dated_first_merged_child_is_selected(tmp_path: Path) -> None:
    root, key = accepted_root(tmp_path / "accepted")
    base = git(root, "rev-parse", "HEAD")
    sibling = tmp_path / "sibling"
    shutil.copytree(root, sibling)
    ga.generate(root, key, NOW + timedelta(days=1))
    older = next((root / "attestations/2026-08-16/revisions").glob("*/chain_head.json"))
    older_head = json.loads(older.read_text(encoding="utf-8"))["chain_head"]
    git(root, "restore", ".")
    git(root, "switch", "-c", "older")
    git(root, "add", "--", "attestations/2026-08-16")
    git(root, "commit", "-m", "older signed child")

    ga.generate(sibling, sibling / key.name, NOW + timedelta(days=2))
    newer = next((sibling / "attestations/2026-08-17/revisions").glob("*/chain_head.json"))
    newer_head = json.loads(newer.read_text(encoding="utf-8"))["chain_head"]
    git(root, "switch", "-c", "newer", base)
    shutil.copytree(newer.parent, root / newer.parent.relative_to(sibling))
    git(root, "add", "--", "attestations/2026-08-17")
    git(root, "commit", "-m", "newer signed sibling")
    git(root, "switch", "main")
    git(root, "merge", "--no-ff", "-m", "accept older child", "older")
    git(root, "merge", "--no-ff", "-m", "retain newer sibling", "newer")

    result = run(root)
    current = index(root)
    check(result.returncode == 0 and current["current_head"] == older_head
          and current["current_head"] == accepted_discovery(root, "HEAD")["current_head"]
          and newer_head in current["rejected_heads"]
          and json.loads((root / PROJECTIONS[1]).read_text(encoding="utf-8"))["chain_head"] == older_head,
          f"first merged older-dated child wins over newer sibling: {result.stdout} {result.stderr}")


def test_dirty_projection_does_not_override_accepted_git_head(tmp_path: Path) -> None:
    root, key = accepted_root(tmp_path)
    accept_next_day(root, key)
    accepted = accepted_discovery(root, "HEAD")["current_head"]
    checkpoint = root / PROJECTIONS[2]
    document = index(root)
    document["current_head"] = "f" * 64
    checkpoint.write_text(json.dumps(document) + "\n", encoding="utf-8")
    result = run(root)
    check(result.returncode == 0 and index(root)["current_head"] == accepted,
          f"accepted Git head overrides dirty projection: {result.stdout} {result.stderr}")


def test_stale_legacy_mirror_is_refreshed_from_accepted_head(tmp_path: Path) -> None:
    root, key = accepted_root(tmp_path)
    accept_next_day(root, key)
    mirror = root / PROJECTIONS[3]
    mirror.write_bytes(b"stale mirror\\n")
    result = run(root)
    current = index(root)
    reference = current["heads"][current["current_head"]]
    directory = reference.rsplit("/", 1)[0]
    revision = root / directory / "revisions" / current["current_head"]
    if (revision / "chain_head.json").is_file():
        directory = revision.relative_to(root).as_posix()
    expected = (root / directory / "chain_head.json").read_bytes()
    check(result.returncode == 0 and mirror.read_bytes() == expected,
          f"stale mirror refreshes from accepted head: {result.stdout} {result.stderr}")
    verify_legacy_mirror(root, current, directory)


def test_correct_legacy_mirror_is_not_written_and_check_passes(tmp_path: Path) -> None:
    root, _ = accepted_root(tmp_path)
    mirror = root / PROJECTIONS[3]
    before = mirror.stat().st_mtime_ns
    result = run(root, "--check")
    check(result.returncode == 0 and mirror.stat().st_mtime_ns == before
          and "OK: accepted attestation projections match evidence" in result.stdout,
          f"correct mirror is unchanged and check succeeds: {result.stdout} {result.stderr}")


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
          f"conflicting siblings exit={result.returncode} identify accepted and candidate heads: {output}")


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
    check(result.returncode == 1 and len(stale) == 6
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


@pytest.mark.parametrize("damage", ["previous", "missing", "whitespace"])
def test_binding_only_drift_is_checked_and_repaired(tmp_path: Path, damage: str) -> None:
    root, key = accepted_root(tmp_path)
    binding = root / "attestations/latest/binding.json"
    previous = binding.read_bytes()
    accept_next_day(root, key)
    result = run(root)
    assert result.returncode == 0, result.stdout + result.stderr
    latest_index = json.loads((root / PROJECTIONS[0]).read_bytes())
    expected = (root / latest_index["binding_ref"]).read_bytes()
    assert binding.read_bytes() == expected
    untouched = {path: (root / path).read_bytes() for path in PROJECTIONS if path != PROJECTIONS[4]}
    if damage == "missing":
        binding.unlink()
    else:
        binding.write_bytes(previous if damage == "previous" else expected + b" ")
    before = binding.read_bytes() if binding.is_file() else None
    result = run(root, "--check")
    assert result.returncode == 1, result.stdout + result.stderr
    stale = [line for line in result.stdout.splitlines() if line.startswith("STALE ")]
    assert len(stale) == 1 and "attestations/latest/binding.json" in stale[0]
    assert "committed=" in stale[0] and "derived=chain_head=" in stale[0]
    assert (binding.read_bytes() if binding.is_file() else None) == before
    assert {path: (root / path).read_bytes() for path in untouched} == untouched
    result = run(root)
    assert result.returncode == 0, result.stdout + result.stderr
    assert binding.read_bytes() == expected
    assert {path: (root / path).read_bytes() for path in untouched} == untouched
    result = run(root, "--check")
    assert result.returncode == 0, result.stdout + result.stderr


def test_write_refuses_untracked_binding_projection(tmp_path: Path) -> None:
    root, _ = accepted_root(tmp_path)
    git(root, "rm", "--cached", "--", "attestations/latest/binding.json")
    result = run(root)
    assert result.returncode == 2
    assert "projection file is not tracked at HEAD: attestations/latest/binding.json" in result.stdout


def test_write_refuses_dirty_immutable_binding(tmp_path: Path) -> None:
    root, _ = accepted_root(tmp_path)
    latest_index = json.loads((root / PROJECTIONS[0]).read_bytes())
    frozen = root / latest_index["binding_ref"]
    frozen.write_bytes(frozen.read_bytes() + b" ")
    before = {path: (root / path).read_bytes() for path in PROJECTIONS}
    result = run(root)
    assert result.returncode == 2 and "working tree must be clean:" in result.stdout
    assert latest_index["binding_ref"] in result.stdout
    assert {path: (root / path).read_bytes() for path in PROJECTIONS} == before
