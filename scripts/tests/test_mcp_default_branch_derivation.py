"""Default-branch derivation for an origin whose HEAD is not a symref.

A pull-request CI checkout leaves HEAD detached at the merge commit, so a clone
of it sees ``git ls-remote --symref origin HEAD`` reply with ``<sha>\\tHEAD``
alone: no ``ref:`` line. Each case builds throwaway repositories under tmp_path.
"""

from __future__ import annotations

from pathlib import Path
import subprocess
import sys

import pytest

from scripts.verify_mcp_deployment import (
    EXIT_UNRESOLVED,
    RepositoryHistoryError,
    newest_mcp_sha,
)


VERIFY_SCRIPT = Path(__file__).resolve().parents[2] / "scripts/verify_mcp_deployment.py"


def git(repo: Path, *args: str) -> str:
    return subprocess.check_output(
        ["git", "-C", str(repo), *args], text=True, stderr=subprocess.DEVNULL,
    ).strip()


def commit(repo: Path, path: str, text: str) -> str:
    target = repo / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")
    git(repo, "add", path)
    git(repo, "commit", "-qm", f"change {path}")
    return git(repo, "rev-parse", "HEAD")


def origin_with_detached_head(tmp_path: Path, *extra_branches: str) -> tuple[Path, str]:
    """Build an origin on ``main`` with HEAD detached at its tip; return the mcp commit."""
    origin = tmp_path / "origin"
    origin.mkdir()
    git(origin, "init", "-q", "-b", "main")
    git(origin, "config", "user.email", "test@example.invalid")
    git(origin, "config", "user.name", "Test")
    mcp_sha = commit(origin, "mcp/server.py", "deployed\n")
    commit(origin, "README.md", "non-runtime tip\n")
    for branch in extra_branches:
        git(origin, "branch", branch)
    git(origin, "checkout", "-q", "--detach", "main")
    return origin, mcp_sha


def clone_without_origin_head(tmp_path: Path, origin: Path) -> Path:
    """Clone, drop the local origin/HEAD, and move HEAD to unrelated mcp work."""
    clone = tmp_path / "clone"
    subprocess.run(["git", "clone", "-q", str(origin), str(clone)], check=True,
                   capture_output=True)
    subprocess.run(
        ["git", "-C", str(clone), "update-ref", "--no-deref", "-d", "refs/remotes/origin/HEAD"],
        check=False, capture_output=True,
    )
    git(clone, "config", "user.email", "test@example.invalid")
    git(clone, "config", "user.name", "Test")
    # A local, detached mcp commit: answering from HEAD would return this.
    git(clone, "checkout", "-q", "--detach")
    commit(clone, "mcp/server.py", "local health commit\n")
    assert subprocess.run(
        ["git", "-C", str(clone), "symbolic-ref", "--quiet", "refs/remotes/origin/HEAD"],
        check=False, capture_output=True,
    ).returncode != 0
    return clone


def assert_no_symref_line(clone: Path) -> None:
    advertised = git(clone, "ls-remote", "--symref", "origin", "HEAD").splitlines()
    assert not any(line.startswith("ref: ") for line in advertised)
    assert [line.split("\t")[1] for line in advertised] == ["HEAD"]


def test_sole_branch_at_head_names_the_default_branch(tmp_path: Path) -> None:
    origin, mcp_sha = origin_with_detached_head(tmp_path)
    clone = clone_without_origin_head(tmp_path, origin)
    assert_no_symref_line(clone)

    assert newest_mcp_sha(clone) == mcp_sha
    assert newest_mcp_sha(clone) != git(clone, "rev-parse", "HEAD")


def test_sole_branch_resolves_from_advertised_tip_when_local_ref_is_missing(
    tmp_path: Path,
) -> None:
    origin, mcp_sha = origin_with_detached_head(tmp_path)
    clone = clone_without_origin_head(tmp_path, origin)
    git(clone, "update-ref", "-d", "refs/remotes/origin/main")
    assert_no_symref_line(clone)

    assert newest_mcp_sha(clone) == mcp_sha


def test_two_branches_without_symref_are_refused(tmp_path: Path) -> None:
    # Both branches sit at HEAD, so neither the tip nor the name disambiguates.
    origin, _ = origin_with_detached_head(tmp_path, "release")
    clone = clone_without_origin_head(tmp_path, origin)
    assert_no_symref_line(clone)

    with pytest.raises(RepositoryHistoryError, match="2 branches are advertised"):
        newest_mcp_sha(clone)


def test_sole_branch_away_from_head_is_refused(tmp_path: Path) -> None:
    origin, _ = origin_with_detached_head(tmp_path)
    git(origin, "checkout", "-q", "--detach", "main~1")
    clone = clone_without_origin_head(tmp_path, origin)
    assert_no_symref_line(clone)

    with pytest.raises(RepositoryHistoryError, match="is not at HEAD"):
        newest_mcp_sha(clone)


def test_pull_request_checkout_with_no_branches_is_unresolved(tmp_path: Path) -> None:
    """The exact CI shape: origin is an actions/checkout of a PR merge commit."""
    upstream, _ = origin_with_detached_head(tmp_path)
    checkout = tmp_path / "pr-checkout"
    checkout.mkdir()
    git(checkout, "init", "-q")
    git(checkout, "remote", "add", "origin", str(upstream))
    git(checkout, "fetch", "-q", "origin",
        "+refs/heads/*:refs/remotes/origin/*",
        f"+{git(upstream, 'rev-parse', 'HEAD')}:refs/remotes/pull/1/merge")
    git(checkout, "checkout", "-q", "--force", "refs/remotes/pull/1/merge")
    clone = tmp_path / "clone"
    subprocess.run(["git", "clone", "-q", str(checkout), str(clone)], check=True,
                   capture_output=True)
    assert_no_symref_line(clone)
    assert git(clone, "ls-remote", "--heads", "origin") == ""

    with pytest.raises(RepositoryHistoryError, match="0 branches are advertised"):
        newest_mcp_sha(clone)
    # The CLI reports the refusal as unresolved before contacting any endpoint.
    result = subprocess.run(
        [sys.executable, str(VERIFY_SCRIPT), "--repo-path", str(clone),
         "--endpoint", "http://127.0.0.1:9/mcp"],
        capture_output=True, text=True, check=False, timeout=30,
    )
    assert result.returncode == EXIT_UNRESOLVED
    assert result.stdout.startswith("UNRESOLVED:")
