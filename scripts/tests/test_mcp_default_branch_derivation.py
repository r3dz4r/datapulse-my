"""Origin HEAD resolution for detached checkouts and refusal boundaries."""

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


def make_origin(tmp_path: Path) -> tuple[Path, str]:
    origin = tmp_path / "origin"
    origin.mkdir()
    git(origin, "init", "-q", "-b", "main")
    git(origin, "config", "user.email", "test@example.invalid")
    git(origin, "config", "user.name", "Test")
    mcp_sha = commit(origin, "mcp/server.py", "deployed\n")
    commit(origin, "README.md", "non-runtime tip\n")
    git(origin, "checkout", "-q", "--detach", "main")
    return origin, mcp_sha


def detached_ci_checkout(tmp_path: Path, origin: Path) -> Path:
    checkout = tmp_path / "ci-checkout"
    checkout.mkdir()
    git(checkout, "init", "-q")
    git(checkout, "remote", "add", "origin", str(origin))
    tip = git(origin, "rev-parse", "HEAD")
    git(checkout, "fetch", "-q", "origin", f"+{tip}:refs/remotes/pull/1/merge")
    git(checkout, "checkout", "-q", "--detach", "refs/remotes/pull/1/merge")
    return checkout


def test_detached_origin_head_commit_is_used_as_search_tip(tmp_path: Path) -> None:
    origin, mcp_sha = make_origin(tmp_path)
    clone = tmp_path / "clone"
    subprocess.run(["git", "clone", "-q", str(detached_ci_checkout(tmp_path, origin)), str(clone)],
                   check=True, capture_output=True)
    advertised = git(clone, "ls-remote", "--symref", "origin", "HEAD").splitlines()
    assert not any(line.startswith("ref: ") for line in advertised)
    assert [line.split("\t")[1] for line in advertised] == ["HEAD"]
    assert newest_mcp_sha(clone) == mcp_sha


def test_shallow_checkout_still_refuses_before_searching(tmp_path: Path) -> None:
    origin, _ = make_origin(tmp_path)
    clone = tmp_path / "shallow"
    subprocess.run(
        ["git", "clone", "-q", "--depth", "1", Path(origin).as_uri(), str(clone)],
        check=True, capture_output=True,
    )
    assert git(clone, "rev-parse", "--is-shallow-repository") == "true"
    with pytest.raises(RepositoryHistoryError, match="history is shallow"):
        newest_mcp_sha(clone)


def test_unreadable_origin_is_unresolved_not_mismatch(tmp_path: Path) -> None:
    origin, _ = make_origin(tmp_path)
    clone = tmp_path / "clone"
    subprocess.run(["git", "clone", "-q", str(origin), str(clone)], check=True,
                   capture_output=True)
    git(clone, "remote", "set-url", "origin", str(tmp_path / "missing-origin"))
    git(clone, "update-ref", "--no-deref", "-d", "refs/remotes/origin/HEAD")

    with pytest.raises(RepositoryHistoryError):
        newest_mcp_sha(clone)
    result = subprocess.run(
        [sys.executable, str(VERIFY_SCRIPT), "--repo-path", str(clone),
         "--endpoint", "http://127.0.0.1:9/mcp"],
        capture_output=True, text=True, check=False, timeout=30,
    )
    assert result.returncode == EXIT_UNRESOLVED
    assert result.stdout.startswith("UNRESOLVED:")
