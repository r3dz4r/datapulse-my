#!/usr/bin/env python3
"""Exercise classification and deletion gates using local-only git remotes."""

from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys
from typing import Any

import pytest

from scripts import reap_landed_branches as reaper

SCRIPT = Path(__file__).resolve().parents[1] / "reap_landed_branches.py"


def git(root: Path, *args: str) -> str:
    """Run fixture git, propagating failures."""
    return subprocess.run(["git", "-C", str(root), *args], check=True,
                          text=True, capture_output=True).stdout.strip()


def commit_file(root: Path, name: str, text: str) -> str:
    """Create a real commit in the disposable fixture."""
    (root / name).write_text(text, encoding="utf-8")
    git(root, "add", name)
    git(root, "commit", "-m", name)
    return git(root, "rev-parse", "HEAD")


@pytest.fixture
def repository(tmp_path: Path) -> dict[str, Any]:
    root = tmp_path / "checkout"
    remote = tmp_path / "remote.git"
    root.mkdir()
    git(root, "init", "-b", "main")
    git(root, "config", "user.name", "Fixture")
    git(root, "config", "user.email", "fixture@example.invalid")
    git(root, "config", "commit.gpgsign", "false")
    initial = commit_file(root, "initial.txt", "base\n")
    git(root, "switch", "-c", "b-patch")
    patch_sha = commit_file(root, "patch.txt", "equivalent patch\n")
    git(root, "switch", "-c", "c-squashed", initial)
    commit_file(root, "first.txt", "first\n")
    commit_file(root, "second.txt", "second\n")
    git(root, "switch", "main")
    commit_file(root, "main-only.txt", "different parent\n")
    git(root, "cherry-pick", patch_sha)
    assert git(root, "rev-parse", "HEAD") != patch_sha
    git(root, "merge", "--squash", "c-squashed")
    git(root, "commit", "-m", "squash two commits")
    for name in ("a-equal", "health-automation", "open-pr", "release-please--fixture"):
        git(root, "branch", name)
    git(root, "switch", "-c", "d-unmerged")
    commit_file(root, "unique.txt", "unshipped\n")
    git(root, "switch", "main")
    git(root, "init", "--bare", str(remote))
    git(root, "remote", "add", "origin", str(remote))
    git(root, "push", "origin", "--all")
    return {"root": root, "remote": remote, "heads": reaper.remote_heads(root, "origin")}


@pytest.fixture
def cli_environment(repository: dict[str, Any], tmp_path: Path) -> dict[str, str]:
    """Replace gh with a local-only API emulator, never the installed gh binary."""
    directory = tmp_path / "bin"
    directory.mkdir()
    real_git = shutil.which("git")
    assert real_git
    # Only get-url is overridden: all actual remote operations use the bare fixture.
    (directory / "git").write_text(
        f"#!{sys.executable}\n"
        "import os, sys\n"
        "if sys.argv[1:] == ['remote', 'get-url', 'origin']:\n"
        "    sys.stdout.write('git@github-fixture:fixture/repository.git\\n')\n"
        "else:\n"
        "    os.execv(os.environ['FIXTURE_GIT'], ['git', *sys.argv[1:]])\n",
        encoding="utf-8",
    )
    (directory / "gh").write_text(
        f"#!{sys.executable}\n" + r'''import json, os, subprocess, sys
from pathlib import Path
from urllib.parse import unquote
args = sys.argv[1:]
log = Path(os.environ['FIXTURE_LOG'])
with log.open('a') as stream:
    stream.write(json.dumps(args) + '\n')
if args[:2] == ['pr', 'list']:
    assert args == ['pr', 'list', '--repo', 'fixture/repository', '--state', 'open',
                    '--limit', '1000', '--json', 'headRefName', '--jq', '.[].headRefName']
    if os.environ.get('FAIL_QUERY'):
        sys.exit(8)
    queries = sum(json.loads(line)[:2] == ['pr', 'list'] for line in log.read_text().splitlines())
    if queries > 1 and os.environ.get('MOVE_BRANCH'):
        subprocess.run([os.environ['FIXTURE_GIT'], '--git-dir', os.environ['FIXTURE_REMOTE'],
                        'update-ref', 'refs/heads/a-equal', os.environ['MOVE_BRANCH']], check=True)
    branches = os.environ.get('FIXTURE_PRS', '')
    if queries > 1:
        branches = os.environ.get('LATER_PRS', branches)
    sys.stdout.write(branches)
elif args[:3] == ['api', '--method', 'DELETE']:
    prefix = 'repos/fixture/repository/git/refs/heads/'
    assert len(args) == 4 and args[3].startswith(prefix)
    branch = unquote(args[3][len(prefix):])
    manifest = json.loads(Path(os.environ['FIXTURE_MANIFEST']).read_text())
    assert manifest['mode'] == 'apply'
    assert any(item['branch'] == branch and item['sha'] for item in manifest['landed'])
    if branch == os.environ.get('FAIL_DELETE'):
        sys.exit(9)
    subprocess.run([os.environ['FIXTURE_GIT'], '--git-dir', os.environ['FIXTURE_REMOTE'],
                    'update-ref', '-d', 'refs/heads/' + branch], check=True)
else:
    sys.exit('Unexpected gh call; no network access is implemented')
''', encoding="utf-8",
    )
    for name in ("git", "gh"):
        (directory / name).chmod(0o755)
    env = dict(os.environ)
    # Keep unrelated operator environment out of the fixture emulator.
    for name in ("FAIL_QUERY", "FAIL_DELETE", "MOVE_BRANCH", "LATER_PRS"):
        env.pop(name, None)
    env.update(PATH=f"{directory}{os.pathsep}{env['PATH']}", FIXTURE_GIT=real_git,
               FIXTURE_REMOTE=str(repository["remote"]), FIXTURE_PRS="open-pr\n",
               FIXTURE_LOG=str(tmp_path / "gh-calls.jsonl"),
               FIXTURE_MANIFEST=str(tmp_path / "report.json"))
    return env


def run_cli(repository: dict[str, Any], env: dict[str, str], *args: str) -> subprocess.CompletedProcess[str]:
    """Run the actual CLI against the disposable remote, with stubbed gh only."""
    return subprocess.run([sys.executable, str(SCRIPT), "--repo-root", str(repository["root"]),
                           "--no-fetch", *args], env=env, text=True, capture_output=True)


def calls(env: dict[str, str]) -> list[list[str]]:
    """Read every attempted gh operation."""
    path = Path(env["FIXTURE_LOG"])
    return [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []


def assert_no_deletions(repository: dict[str, Any], env: dict[str, str]) -> None:
    """Verify both the emulator log and all remote head SHAs."""
    assert not any(call[0] == "api" for call in calls(env))
    assert reaper.remote_heads(repository["root"], "origin") == repository["heads"]


def test_classifier_all_named_cases(repository: dict[str, Any]) -> None:
    report = reaper.classify_branches(repository["root"], "origin", "main",
                                      repository["heads"], {"open-pr"})
    landed = {item["branch"]: item for item in report["landed"]}
    kept = {item["branch"]: item["reason"] for item in report["keep"]}
    unmerged = {item["branch"]: item["ahead"] for item in report["unmerged"]}
    assert kept["main"] == "base"
    assert "main" not in landed
    assert landed["a-equal"]["rule"] == "zero-ahead"
    assert landed["a-equal"]["sha"] == repository["heads"]["main"]
    assert landed["b-patch"]["rule"] == "patch-equivalent"
    # Patch-id cannot recognize a two-commit branch squash-merged as one commit.
    assert unmerged["c-squashed"] == 2
    assert "c-squashed" not in landed
    assert unmerged["d-unmerged"] == 1
    assert kept["health-automation"] == "builtin"
    assert "health-automation" not in landed
    assert kept["open-pr"] == "open-pr"
    assert "open-pr" not in landed
    assert kept["release-please--fixture"] == "builtin"
    assert report["total"] == len(repository["heads"])
    for key in ("landed", "keep", "unmerged"):
        assert report[key] == sorted(report[key], key=lambda item: item["branch"])


def test_cli_report_is_deterministic_and_never_deletes(
    repository: dict[str, Any], cli_environment: dict[str, str],
) -> None:
    first = run_cli(repository, cli_environment, "--mode", "report")
    second = run_cli(repository, cli_environment, "--mode", "report")
    assert first.returncode == second.returncode == 0, first.stderr + second.stderr
    assert first.stdout == second.stdout
    report = json.loads(first.stdout)
    direct = reaper.classify_branches(repository["root"], "origin", "main",
                                      repository["heads"], {"open-pr"})
    assert report == direct
    assert_no_deletions(repository, cli_environment)


def test_report_fetch_does_not_prune_tracking_refs(
    repository: dict[str, Any], cli_environment: dict[str, str],
) -> None:
    root = repository["root"]
    git(root, "update-ref", "refs/remotes/origin/retired", repository["heads"]["main"])
    result = subprocess.run([sys.executable, str(SCRIPT), "--repo-root", str(root),
                             "--mode", "report"], env=cli_environment, text=True,
                            capture_output=True)
    assert result.returncode == 0, result.stderr
    assert git(root, "rev-parse", "refs/remotes/origin/retired") == repository["heads"]["main"]
    assert_no_deletions(repository, cli_environment)


def test_manifest_fsyncs_file_and_directory(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    actual_fsync = os.fsync
    synced_modes: list[int] = []

    def record_fsync(fd: int) -> None:
        synced_modes.append(os.fstat(fd).st_mode)
        actual_fsync(fd)

    monkeypatch.setattr(reaper.os, "fsync", record_fsync)
    manifest = tmp_path / "report.json"
    reaper.write_report({"mode": "apply"}, manifest)
    assert json.loads(manifest.read_text()) == {"mode": "apply"}
    assert len(synced_modes) == 2
    assert stat.S_ISREG(synced_modes[0])
    assert stat.S_ISDIR(synced_modes[1])


def test_apply_refuses_empty_pr_result(repository: dict[str, Any], cli_environment: dict[str, str]) -> None:
    cli_environment["FIXTURE_PRS"] = ""
    result = run_cli(repository, cli_environment, "--mode", "apply", "--json",
                     cli_environment["FIXTURE_MANIFEST"])
    assert result.returncode == 1
    assert "empty open-PR" in result.stderr
    assert_no_deletions(repository, cli_environment)


@pytest.mark.parametrize("mode", ["report", "apply"])
def test_query_failure_refuses(repository: dict[str, Any], cli_environment: dict[str, str], mode: str) -> None:
    cli_environment["FAIL_QUERY"] = "1"
    result = run_cli(repository, cli_environment, "--mode", mode, "--json",
                     cli_environment["FIXTURE_MANIFEST"])
    assert result.returncode == 1
    assert "gh pr failed" in result.stderr
    assert_no_deletions(repository, cli_environment)


def test_missing_gh_refuses(repository: dict[str, Any], cli_environment: dict[str, str]) -> None:
    # Remove both the fake executable and access to the installed gh binary.
    bin_dir = Path(cli_environment["PATH"].split(os.pathsep)[0])
    (bin_dir / "gh").unlink()
    cli_environment["PATH"] = str(bin_dir)
    result = run_cli(repository, cli_environment, "--mode", "apply", "--json",
                     cli_environment["FIXTURE_MANIFEST"])
    assert result.returncode == 1
    assert "gh unavailable" in result.stderr
    assert_no_deletions(repository, cli_environment)


def test_apply_deletes_only_eligible_and_persists_manifest(
    repository: dict[str, Any], cli_environment: dict[str, str], tmp_path: Path,
) -> None:
    keep_file = tmp_path / "keep.txt"
    keep_file.write_text("b-patch\n", encoding="utf-8")
    result = run_cli(repository, cli_environment, "--mode", "apply", "--json",
                     cli_environment["FIXTURE_MANIFEST"], "--keep-file", str(keep_file))
    assert result.returncode == 0, result.stderr
    manifest = json.loads(Path(cli_environment["FIXTURE_MANIFEST"]).read_text())
    assert manifest["mode"] == "apply"
    assert manifest["deleted"] == [{"branch": "a-equal", "sha": repository["heads"]["a-equal"],
                                     "rule": "zero-ahead"}]
    assert manifest["not_deleted"] == []
    assert {item["branch"]: item["reason"] for item in manifest["keep"]}["b-patch"] == "keep-file"
    expected = dict(repository["heads"])
    del expected["a-equal"]
    assert reaper.remote_heads(repository["root"], "origin") == expected
    assert [call[3] for call in calls(cli_environment) if call[0] == "api"] == [
        "repos/fixture/repository/git/refs/heads/a-equal"]


def test_keep_file_in_report(repository: dict[str, Any], cli_environment: dict[str, str], tmp_path: Path) -> None:
    path = tmp_path / "keep.txt"
    path.write_text("a-equal\n", encoding="utf-8")
    result = run_cli(repository, cli_environment, "--keep-file", str(path))
    assert result.returncode == 0, result.stderr
    report = json.loads(result.stdout)
    assert {"branch": "a-equal", "reason": "keep-file"} in report["keep"]
    assert "a-equal" not in [item["branch"] for item in report["landed"]]
    assert_no_deletions(repository, cli_environment)


@pytest.mark.parametrize("current", [True, False])
def test_apply_skips_worktree_branches(
    repository: dict[str, Any], cli_environment: dict[str, str], tmp_path: Path, current: bool,
) -> None:
    if current:
        git(repository["root"], "switch", "a-equal")
    else:
        git(repository["root"], "worktree", "add", str(tmp_path / "other"), "a-equal")
    cli_environment["FIXTURE_PRS"] += "b-patch\n"
    result = run_cli(repository, cli_environment, "--mode", "apply", "--json",
                     cli_environment["FIXTURE_MANIFEST"])
    assert result.returncode == 0, result.stderr
    manifest = json.loads(Path(cli_environment["FIXTURE_MANIFEST"]).read_text())
    assert manifest["skipped"][0]["branch"] == "a-equal"
    assert manifest["skipped"][0]["reason"] == "checked-out"
    assert manifest["deleted"] == []
    assert_no_deletions(repository, cli_environment)


@pytest.mark.parametrize("fail_branch", ["a-equal", "b-patch"])
def test_deletion_failure_stops_and_records_exact_progress(
    repository: dict[str, Any], cli_environment: dict[str, str], fail_branch: str,
) -> None:
    cli_environment["FAIL_DELETE"] = fail_branch
    result = run_cli(repository, cli_environment, "--mode", "apply", "--json",
                     cli_environment["FIXTURE_MANIFEST"])
    assert result.returncode == 1
    assert "Apply stopped" in result.stderr
    manifest = json.loads(Path(cli_environment["FIXTURE_MANIFEST"]).read_text())
    deleted = [item["branch"] for item in manifest["deleted"]]
    assert deleted == (["a-equal"] if fail_branch == "b-patch" else [])
    assert [item["branch"] for item in manifest["not_deleted"]] == (
        ["b-patch"] if deleted else ["a-equal", "b-patch"])
    expected = dict(repository["heads"])
    for branch in deleted:
        del expected[branch]
    assert reaper.remote_heads(repository["root"], "origin") == expected
    assert [call[3].rsplit("/", 1)[1] for call in calls(cli_environment) if call[0] == "api"] == (
        ["a-equal", "b-patch"] if deleted else ["a-equal"])


def test_manifest_failure_deletes_nothing(repository: dict[str, Any], cli_environment: dict[str, str], tmp_path: Path) -> None:
    result = run_cli(repository, cli_environment, "--mode", "apply", "--json",
                     str(tmp_path / "missing-parent" / "manifest.json"))
    assert result.returncode == 1
    assert "Manifest write failed" in result.stderr
    assert_no_deletions(repository, cli_environment)


def test_apply_requires_manifest_path(repository: dict[str, Any], cli_environment: dict[str, str]) -> None:
    result = run_cli(repository, cli_environment, "--mode", "apply")
    assert result.returncode == 1
    assert "requires --json" in result.stderr
    assert_no_deletions(repository, cli_environment)


def test_moved_branch_aborts_apply(repository: dict[str, Any], cli_environment: dict[str, str]) -> None:
    cli_environment["MOVE_BRANCH"] = repository["heads"]["d-unmerged"]
    result = run_cli(repository, cli_environment, "--mode", "apply", "--json",
                     cli_environment["FIXTURE_MANIFEST"])
    assert result.returncode == 1
    assert "Remote changed before deletion of a-equal" in result.stderr
    assert not any(call[0] == "api" for call in calls(cli_environment))


def test_new_open_pr_is_skipped(repository: dict[str, Any], cli_environment: dict[str, str]) -> None:
    cli_environment["LATER_PRS"] = "open-pr\na-equal\nb-patch\n"
    result = run_cli(repository, cli_environment, "--mode", "apply", "--json",
                     cli_environment["FIXTURE_MANIFEST"])
    assert result.returncode == 0, result.stderr
    manifest = json.loads(Path(cli_environment["FIXTURE_MANIFEST"]).read_text())
    assert [item["branch"] for item in manifest["skipped"]] == ["a-equal", "b-patch"]
    assert_no_deletions(repository, cli_environment)


def test_empty_recheck_aborts(repository: dict[str, Any], cli_environment: dict[str, str]) -> None:
    cli_environment["LATER_PRS"] = ""
    result = run_cli(repository, cli_environment, "--mode", "apply", "--json",
                     cli_environment["FIXTURE_MANIFEST"])
    assert result.returncode == 1
    assert_no_deletions(repository, cli_environment)


def test_stale_base_ref_refuses(repository: dict[str, Any]) -> None:
    git(repository["root"], "update-ref", "refs/remotes/origin/main", repository["heads"]["b-patch"])
    with pytest.raises(reaper.ReaperError, match="Remote base differs"):
        reaper.classify_branches(repository["root"], "origin", "main", repository["heads"], {"open-pr"})


def test_unique_merge_commit_is_never_patch_equivalent(repository: dict[str, Any]) -> None:
    root = repository["root"]
    git(root, "switch", "-c", "merge-only")
    git(root, "merge", "--no-ff", "b-patch", "-m", "unique merge")
    # b-patch's patch is landed, but its unique merge commit is omitted by git cherry.
    heads = dict(repository["heads"], **{"merge-only": git(root, "rev-parse", "HEAD")})
    report = reaper.classify_branches(root, "origin", "main", heads, {"open-pr"})
    assert "merge-only" in [item["branch"] for item in report["unmerged"]]
    assert "merge-only" not in [item["branch"] for item in report["landed"]]


def test_not_a_repository_refuses(tmp_path: Path) -> None:
    assert reaper.main(["--repo-root", str(tmp_path), "--no-fetch"]) == 1


def test_unreadable_remote_refuses(repository: dict[str, Any]) -> None:
    git(repository["root"], "remote", "set-url", "origin", str(repository["remote"] / "missing"))
    with pytest.raises(reaper.ReaperError, match="ls-remote failed"):
        reaper.remote_heads(repository["root"], "origin")


def test_pr_limit_refuses(repository: dict[str, Any], cli_environment: dict[str, str]) -> None:
    cli_environment["FIXTURE_PRS"] = "open-pr\n" * 1000
    result = run_cli(repository, cli_environment)
    assert result.returncode == 1
    assert "keep set may be incomplete" in result.stderr
    assert_no_deletions(repository, cli_environment)
