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


def test_cli_is_offline_and_emits_one_line(repository: tuple[Path, str, str]) -> None:
    repo, main, _ = repository
    before_refs = git(repo, "show-ref")
    result = subprocess.run(
        [sys.executable, str(Path(publisher.__file__)), "--dry-run", "--repo", str(repo)],
        capture_output=True, text=True, check=True,
    )
    assert result.stdout.startswith("would-apply seq=1 tree=")
    assert len(result.stdout.splitlines()) == 1
    assert result.stderr == ""
    assert git(repo, "status", "--porcelain") == ""
    assert git(repo, "show-ref") == before_refs
    assert git(repo, "rev-parse", "HEAD") == main
