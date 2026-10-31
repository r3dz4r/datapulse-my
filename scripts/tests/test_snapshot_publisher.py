from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import pytest

from scripts import snapshot_publisher as publisher


def git(repo: Path, *args: str, input_text: str | None = None) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo), *args],
        input=input_text,
        text=True,
        capture_output=True,
        check=True,
    )
    return result.stdout.strip()


def commit(repo: Path, message: str) -> str:
    git(repo, "add", "-A")
    git(repo, "commit", "-m", message)
    return git(repo, "rev-parse", "HEAD")


def write(repo: Path, path: str, content: str) -> None:
    target = repo / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content)


@pytest.fixture
def repository(tmp_path: Path) -> tuple[Path, str, str]:
    repo = tmp_path / "fixture"
    repo.mkdir()
    git(repo, "init", "-q", "-b", "main")
    git(repo, "config", "user.name", "Fixture")
    git(repo, "config", "user.email", "fixture@example.test")
    write(repo, "config/keep.txt", "main only\n")
    write(repo, "health/latest.json", '{"old":true}\n')
    main = commit(repo, "initial main")

    git(repo, "checkout", "-q", "--orphan", "health-snapshots")
    git(repo, "rm", "-qr", "--cached", ".")
    (repo / "config/keep.txt").unlink()
    write(repo, "health/latest.json", '{"new":true}\n')
    write(repo, "docs/index.html", "new dashboard\n")
    source = main
    snapshot = commit(
        repo,
        f"snapshot\n\nSnapshot-Seq: 1\nSnapshot-Source: {source}\n",
    )
    git(repo, "checkout", "-q", "main")
    return repo, main, snapshot


def test_already_published_creates_no_object(repository: tuple[Path, str, str]) -> None:
    repo, _, snapshot = repository
    tree = git(repo, "rev-parse", f"{snapshot}^{{tree}}")
    write(repo, "health/snapshot.json", json.dumps({"seq": 1, "snapshot": snapshot, "tree": tree}))
    commit(repo, "chore(health): publish snapshot")
    before = set((repo / ".git/objects").rglob("*"))
    result = publisher.evaluate(repo)
    assert result.line == "would-skip already-published seq=1"
    assert set((repo / ".git/objects").rglob("*")) == before


def test_in_flight_is_injected(repository: tuple[Path, str, str]) -> None:
    repo, _, _ = repository
    assert publisher.evaluate(repo, in_flight_pr=42).line == "would-skip in-flight pr=42"


def test_matching_merged_tree_is_recorded(repository: tuple[Path, str, str]) -> None:
    repo, _, snapshot = repository
    write(repo, "health/latest.json", '{"new":true}\n')
    write(repo, "docs/index.html", "new dashboard\n")
    merged = commit(repo, "chore(health): update due dataset health")
    decision = publisher.evaluate(repo)
    tree = git(repo, "rev-parse", f"{snapshot}^{{tree}}")
    assert decision.comparison == f"matched-merged tree={tree} source={merged} note=cycle-already-reconciled"


def test_prior_merged_commit_is_not_current_cycle(repository: tuple[Path, str, str]) -> None:
    repo, _, _ = repository
    assert publisher.evaluate(repo).comparison == "no-merged-commit reason=merged-not-after-source"


def test_overlay_differs_from_merged_cycle(repository: tuple[Path, str, str]) -> None:
    repo, _, _ = repository
    write(repo, "health/latest.json", '{"lane":true}\n')
    merged = commit(repo, "chore(health): update due dataset health")

    decision = publisher.evaluate(repo)
    assert decision.line.startswith("would-apply seq=1 tree=")
    assert decision.comparison.startswith("differs-from-merged publisher=")
    assert " merged=" in decision.comparison
    assert " differing=2" in decision.comparison
    assert git(repo, "rev-parse", "main") == merged


def test_no_merged_commit_for_unmanaged_main(tmp_path: Path) -> None:
    repo = tmp_path / "fixture"
    repo.mkdir()
    git(repo, "init", "-q", "-b", "main")
    git(repo, "config", "user.name", "Fixture")
    git(repo, "config", "user.email", "fixture@example.test")
    write(repo, "config/keep.txt", "main only\n")
    source = commit(repo, "initial main")
    git(repo, "checkout", "-q", "--orphan", "health-snapshots")
    git(repo, "rm", "-qr", "--cached", ".")
    (repo / "config/keep.txt").unlink()
    write(repo, "health/latest.json", '{"new":true}\n')
    commit(repo, f"snapshot\n\nSnapshot-Seq: 1\nSnapshot-Source: {source}\n")
    git(repo, "checkout", "-q", "main")

    decision = publisher.evaluate(repo)
    assert decision.line.startswith("would-apply seq=1 tree=")
    assert decision.comparison == "no-merged-commit reason=no-managed-main-commit"


def test_foreign_write_supersedes_snapshot(repository: tuple[Path, str, str]) -> None:
    repo, _, snapshot = repository
    previous_tree = git(repo, "rev-parse", f"{snapshot}^{{tree}}")
    write(repo, "health/latest.json", '{"new":true}\n')
    write(repo, "docs/index.html", "new dashboard\n")
    write(repo, "health/snapshot.json", json.dumps({"seq": 0, "snapshot": snapshot, "tree": previous_tree}))
    commit(repo, "chore(health): publish snapshot")
    write(repo, "health/latest.json", '{"foreign":true}\n')
    foreign = commit(repo, "manual health correction")
    assert publisher.evaluate(repo).line == f"would-skip superseded-by {foreign}"


def test_overlay_is_deterministic_and_preserves_main(repository: tuple[Path, str, str]) -> None:
    repo, main, snapshot = repository
    before_refs = git(repo, "show-ref")
    before_objects = set((repo / ".git/objects").rglob("*"))
    before_index = (repo / ".git/index").read_bytes()
    scratch_root = Path(tempfile.gettempdir())
    before_scratch = set(scratch_root.glob("snapshot-publisher-*"))
    first = publisher.evaluate(repo)
    second = publisher.evaluate(repo)
    assert first == second
    assert first.line.startswith("would-apply seq=1 tree=")
    assert " changed=3" in first.line
    assert git(repo, "status", "--porcelain") == ""
    assert git(repo, "show-ref") == before_refs
    assert git(repo, "rev-parse", "HEAD") == main
    assert (repo / ".git/index").read_bytes() == before_index
    assert set((repo / ".git/objects").rglob("*")) == before_objects
    assert "GIT_INDEX_FILE" not in os.environ
    assert set(scratch_root.glob("snapshot-publisher-*")) == before_scratch

    # The returned tree is a content address; reconstructing the overlay in a
    # separate scratch object database lets us inspect it without retaining C.
    with publisher.overlay_objects(repo) as objects:
        overlay = publisher.build_overlay(repo, main, snapshot, 1, objects)
        assert overlay.tree == first.tree
        assert overlay.sha == first.sha
        assert publisher.git(repo, "show", f"{overlay.tree}:health/latest.json", env=objects.env) == b'{"new":true}\n'
        assert publisher.git(repo, "show", f"{overlay.tree}:docs/index.html", env=objects.env) == b"new dashboard\n"
        assert publisher.git(repo, "show", f"{overlay.tree}:config/keep.txt", env=objects.env) == publisher.git(repo, "show", f"{main}:config/keep.txt")
        watermark = json.loads(publisher.git(repo, "show", f"{overlay.tree}:health/snapshot.json", env=objects.env))
        assert watermark == {"seq": 1, "snapshot": snapshot, "tree": git(repo, "rev-parse", f"{snapshot}^{{tree}}")}


def test_large_snapshot_evaluates_within_ten_seconds(repository: tuple[Path, str, str]) -> None:
    repo, main, _ = repository
    git(repo, "checkout", "-q", "health-snapshots")
    for index in range(2_500):
        write(repo, f"badges/snapshot-{index:04d}.svg", "badge\n")
    write(repo, "badges/with\nnewline.svg", "badge\n")
    commit(repo, f"snapshot\n\nSnapshot-Seq: 2\nSnapshot-Source: {main}\n")
    git(repo, "checkout", "-q", "main")

    start = time.monotonic()
    result = publisher.evaluate(repo)
    elapsed = time.monotonic() - start
    # One index update per path exceeds this budget; a batched overlay leaves
    # ample room for Git startup and temporary file I/O on a slower CI host.
    assert elapsed < 10, f"snapshot evaluation took {elapsed:.2f}s"
    assert result.line.startswith("would-apply seq=2 tree=")


@pytest.mark.parametrize("message", ["snapshot", "snapshot\n\nSnapshot-Seq: x\nSnapshot-Source: abc"])
def test_invalid_trailers_fail(repository: tuple[Path, str, str], message: str) -> None:
    repo, _, _ = repository
    git(repo, "checkout", "-q", "health-snapshots")
    write(repo, "health/latest.json", "next\n")
    commit(repo, message)
    git(repo, "checkout", "-q", "main")
    with pytest.raises(publisher.PublisherError, match="Snapshot-"):
        publisher.evaluate(repo)


def test_unmanaged_snapshot_path_fails(repository: tuple[Path, str, str]) -> None:
    repo, main, _ = repository
    git(repo, "checkout", "-q", "health-snapshots")
    write(repo, "config/unmanaged.txt", "bad\n")
    commit(repo, f"snapshot\n\nSnapshot-Seq: 2\nSnapshot-Source: {main}")
    git(repo, "checkout", "-q", "main")
    with pytest.raises(publisher.PublisherError, match="unmanaged"):
        publisher.evaluate(repo)


def test_merge_snapshot_history_fails(repository: tuple[Path, str, str]) -> None:
    repo, main, snapshot = repository
    tree = git(repo, "rev-parse", f"{snapshot}^{{tree}}")
    merged = git(
        repo, "commit-tree", tree, "-p", snapshot, "-p", main,
        input_text=f"snapshot\n\nSnapshot-Seq: 2\nSnapshot-Source: {main}\n",
    )
    git(repo, "update-ref", "refs/heads/health-snapshots", merged)
    with pytest.raises(publisher.PublisherError, match="single-parent linear"):
        publisher.evaluate(repo)


def test_cli_is_offline_and_emits_two_lines(repository: tuple[Path, str, str]) -> None:
    repo, main, _ = repository
    before_refs = git(repo, "show-ref")
    result = subprocess.run(
        [sys.executable, str(Path(publisher.__file__)), "--dry-run", "--repo", str(repo)],
        capture_output=True, text=True, check=True,
    )
    assert result.stdout.startswith("would-apply seq=1 tree=")
    assert len(result.stdout.splitlines()) == 2
    assert result.stdout.splitlines()[1] == "no-merged-commit reason=merged-not-after-source"
    assert result.stderr == ""
    assert git(repo, "status", "--porcelain") == ""
    assert git(repo, "show-ref") == before_refs
    assert git(repo, "rev-parse", "HEAD") == main


RECORD_KEYS = {
    "decision", "reason", "state_left", "ceiling_seconds", "successor",
    "published_seq", "branch", "head",
}


@pytest.fixture
def remote(repository: tuple[Path, str, str], tmp_path: Path) -> Path:
    repo, _, _ = repository
    bare = tmp_path / "remote.git"
    git(tmp_path, "init", "-q", "--bare", str(bare))
    git(repo, "remote", "add", "origin", str(bare))
    git(repo, "push", "-q", "origin", "main", "health-snapshots")
    return bare


def run_apply(repo: Path, *extra: str) -> tuple[int, dict[str, object]]:
    result = subprocess.run(
        [sys.executable, str(Path(publisher.__file__)), "--apply", "--repo", str(repo), *extra],
        capture_output=True, text=True, check=False,
    )
    lines = result.stdout.splitlines()
    assert len(lines) == 1, result.stdout
    record = json.loads(lines[0])
    assert set(record) == RECORD_KEYS
    return result.returncode, record


def next_snapshot(repo: Path, parent: str, source: str, seq: int, content: str) -> str:
    """Write a descendant snapshot commit without moving any ref."""
    blob = git(repo, "hash-object", "-w", "--stdin", input_text=content)
    tree = git(repo, "mktree", input_text=f"100644 blob {blob}\tlatest.json\n")
    tree = git(repo, "mktree", input_text=f"040000 tree {tree}\thealth\n")
    return git(
        repo, "commit-tree", tree, "-p", parent,
        input_text=f"snapshot\n\nSnapshot-Seq: {seq}\nSnapshot-Source: {source}\n",
    )


@pytest.mark.parametrize("modes", [["--dry-run", "--apply"], []])
def test_apply_and_dry_run_are_mutually_exclusive(repository: tuple[Path, str, str], modes: list[str]) -> None:
    repo, _, _ = repository
    result = subprocess.run(
        [sys.executable, str(Path(publisher.__file__)), *modes, "--repo", str(repo)],
        capture_output=True, text=True, check=False,
    )
    assert result.returncode == 2
    assert result.stdout == ""


@pytest.mark.parametrize("branch", ["main", "refs/heads/main", "refs/heads/health-snapshots", "health-snapshots/x", ""])
def test_push_target_other_than_health_snapshots_refused_before_git(
    repository: tuple[Path, str, str], monkeypatch: pytest.MonkeyPatch, branch: str,
) -> None:
    repo, main, snapshot = repository
    calls: list[object] = []
    monkeypatch.setattr(publisher.subprocess, "run", lambda *a, **k: calls.append(a))
    with pytest.raises(publisher.PublisherError, match="refusing push target"):
        publisher.apply(repo, branch=branch)
    with pytest.raises(publisher.PublisherError, match="refusing push target"):
        publisher.push_with_lease(repo, branch, main, snapshot)
    assert calls == []
    assert publisher._push_target("health-snapshots") == "refs/heads/health-snapshots"


@pytest.mark.parametrize("case", ["already-published", "in-flight", "superseded"])
def test_apply_skips_match_dry_run_and_write_nothing(
    repository: tuple[Path, str, str], remote: Path, case: str,
) -> None:
    repo, _, snapshot = repository
    extra: list[str] = []
    tree = git(repo, "rev-parse", f"{snapshot}^{{tree}}")
    if case == "already-published":
        write(repo, "health/snapshot.json", json.dumps({"seq": 1, "snapshot": snapshot, "tree": tree}))
        commit(repo, "chore(health): publish snapshot")
    elif case == "in-flight":
        extra = ["--in-flight-pr", "42"]
    else:
        write(repo, "health/latest.json", '{"new":true}\n')
        write(repo, "docs/index.html", "new dashboard\n")
        write(repo, "health/snapshot.json", json.dumps({"seq": 0, "snapshot": snapshot, "tree": tree}))
        commit(repo, "chore(health): publish snapshot")
        write(repo, "health/latest.json", '{"foreign":true}\n')
        commit(repo, "manual health correction")
    dry = publisher.evaluate(repo, 42 if extra else None).line
    assert dry.startswith("would-skip ")
    before_local, before_remote = git(repo, "show-ref"), git(remote, "show-ref")
    code, record = run_apply(repo, *extra)
    assert code == 0
    assert record["decision"] == "skip"
    assert record["reason"] == dry
    assert record["branch"] == "health-snapshots"
    assert record["head"] == snapshot
    assert record["successor"] == {"already-published": "published", "in-flight": "pr_open", "superseded": "idle"}[case]
    assert git(repo, "show-ref") == before_local
    assert git(remote, "show-ref") == before_remote


def test_apply_refuses_to_rewrite_observation_chain_and_main_untouched(
    repository: tuple[Path, str, str], remote: Path,
) -> None:
    repo, main, snapshot = repository
    dry = publisher.evaluate(repo)
    assert dry.line.startswith("would-apply ")
    before = git(remote, "show-ref")
    code, record = run_apply(repo)
    assert code == 2
    assert record["decision"] == "refused"
    assert "non-fast-forward" in str(record["reason"])
    assert f"{dry.sha} does not descend from leased head {snapshot}" in str(record["reason"])
    assert git(remote, "show-ref") == before
    assert git(remote, "rev-parse", "refs/heads/main") == main


def test_lease_push_fast_forwards_health_snapshots_only(
    repository: tuple[Path, str, str], remote: Path,
) -> None:
    repo, main, snapshot = repository
    successor = next_snapshot(repo, snapshot, main, 2, '{"seq":2}\n')
    head, moved = publisher.push_with_lease(repo, "health-snapshots", successor, snapshot)
    assert (head, moved) == (successor, True)
    assert git(remote, "rev-parse", "refs/heads/health-snapshots") == successor
    assert git(remote, "rev-parse", "refs/heads/main") == main
    assert git(remote, "for-each-ref", "--format=%(refname)") == "refs/heads/health-snapshots\nrefs/heads/main"


def test_lease_push_is_idempotent(repository: tuple[Path, str, str], remote: Path) -> None:
    repo, main, snapshot = repository
    successor = next_snapshot(repo, snapshot, main, 2, '{"seq":2}\n')
    publisher.push_with_lease(repo, "health-snapshots", successor, snapshot)
    before = git(remote, "show-ref")
    before_log = git(remote, "rev-list", "--all")
    assert publisher.push_with_lease(repo, "health-snapshots", successor, snapshot) == (successor, False)
    assert git(remote, "show-ref") == before
    assert git(remote, "rev-list", "--all") == before_log


def test_moved_lease_refuses_naming_both_shas(
    repository: tuple[Path, str, str], remote: Path, tmp_path: Path,
) -> None:
    repo, main, snapshot = repository
    other = tmp_path / "other"
    git(tmp_path, "clone", "-q", str(remote), str(other))
    git(other, "config", "user.name", "Fixture")
    git(other, "config", "user.email", "fixture@example.test")
    moved = next_snapshot(other, snapshot, main, 2, '{"other":true}\n')
    git(other, "push", "-q", "origin", f"{moved}:refs/heads/health-snapshots")
    ours = next_snapshot(repo, snapshot, main, 2, '{"ours":true}\n')
    before = git(remote, "show-ref")

    with pytest.raises(publisher.PublisherError) as error:
        publisher.push_with_lease(repo, "health-snapshots", ours, snapshot)
    assert snapshot in str(error.value) and moved in str(error.value)
    assert "lease moved" in str(error.value)
    # The full apply path reads the same stale local head and refuses the same way.
    code, record = run_apply(repo)
    assert code == 2
    assert snapshot in str(record["reason"]) and moved in str(record["reason"])
    assert git(remote, "show-ref") == before


def test_workflow_schedule_stays_dry_run_without_write(repository: tuple[Path, str, str]) -> None:
    yaml = pytest.importorskip("yaml")
    path = Path(publisher.__file__).resolve().parents[1] / ".github/workflows/health-publish-snapshot.yml"
    workflow = yaml.safe_load(path.read_text())
    triggers = workflow[True]
    assert triggers["schedule"] == [{"cron": "7 * * * *"}]
    assert triggers["workflow_dispatch"]["inputs"]["apply"] == {
        "description": triggers["workflow_dispatch"]["inputs"]["apply"]["description"],
        "type": "boolean", "default": False, "required": False,
    }
    assert workflow["permissions"] == {"contents": "read"}
    dry, live = workflow["jobs"]["dry-run"], workflow["jobs"]["apply"]
    assert "permissions" not in dry
    assert "--dry-run" in dry["steps"][-1]["run"] and "--apply" not in dry["steps"][-1]["run"]
    assert live["if"] == "github.event_name == 'workflow_dispatch' && inputs.apply"
    assert live["permissions"] == {"contents": "write"}
    assert "--apply" in live["steps"][-1]["run"]
