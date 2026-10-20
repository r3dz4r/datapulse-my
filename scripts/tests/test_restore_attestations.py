"""Hermetic tests for the delta-only attestation restore helper."""

from __future__ import annotations

import os
import shlex
import shutil
import subprocess
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/restore_attestations.sh"
DEFAULT_PATHSPECS = ("attestations", ".attestations/chain_head.json")

BASE_FILES = {
    "attestations/modified.json": '{"state": "source"}\n',
    "attestations/deleted.json": '{"state": "source"}\n',
    "attestations/same.json": '{"state": "same"}\n',
    ".attestations/chain_head.json": '{"head": "source"}\n',
}


def _git(repo: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        ["git", *args],
        cwd=repo,
        capture_output=True,
        text=True,
        env={**os.environ, "GIT_TERMINAL_PROMPT": "0"},
    )
    if check and result.returncode != 0:
        raise AssertionError(f"git {' '.join(args)} failed: {result.stdout}{result.stderr}")
    return result


def _build_repo(repo: Path, files: dict[str, str] | None = None) -> str:
    repo.mkdir()
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "restore-test@example.invalid")
    _git(repo, "config", "user.name", "Restore Test")
    for name, content in (files or BASE_FILES).items():
        path = repo / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-qm", "source")
    return _git(repo, "rev-parse", "HEAD").stdout.strip()


def _install_git_wrapper(tmp_path: Path) -> tuple[dict[str, str], Path]:
    """Put an instrumented git first on PATH and record restore argv paths."""
    real_git = shutil.which("git")
    assert real_git is not None
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    log = tmp_path / "restore.log"
    wrapper = bin_dir / "git"
    wrapper.write_text(
        textwrap.dedent(
            f'''\
            #!/usr/bin/env bash
            set -Eeuo pipefail
            if [[ "${{1:-}}" == restore ]]; then
              printf 'INVOCATION\\n' >> "$RESTORE_LOG"
              args=("$@")
              i=1
              while ((i < ${{#args[@]}})); do
                case "${{args[i]}}" in
                  --source) ((i += 2)) ;;
                  --worktree|--staged|--overlay|--no-overlay) ((i += 1)) ;;
                  --)
                    ((i += 1))
                    while ((i < ${{#args[@]}})); do
                      printf '%s\\n' "${{args[i]}}" >> "$RESTORE_LOG"
                      ((i += 1))
                    done
                    ;;
                  *)
                    printf '%s\\n' "${{args[i]}}" >> "$RESTORE_LOG"
                    ((i += 1))
                    ;;
                esac
              done
            fi
            exec {shlex.quote(real_git)} "$@"
            '''
        ),
        encoding="utf-8",
    )
    wrapper.chmod(0o755)
    env = {
        **os.environ,
        "PATH": f"{bin_dir}:{os.environ['PATH']}",
        "REAL_GIT": real_git,
        "RESTORE_LOG": str(log),
    }
    return env, log


def _restore_log(log: Path) -> tuple[int, list[str]]:
    if not log.exists():
        return 0, []
    lines = log.read_text(encoding="utf-8").splitlines()
    return lines.count("INVOCATION"), [line for line in lines if line != "INVOCATION"]


def _run_script(
    repo: Path, *args: str, env: dict[str, str] | None = None
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", str(SCRIPT), *args],
        cwd=repo,
        capture_output=True,
        text=True,
        env={**os.environ, **(env or {})},
    )


def _snapshot(repo: Path) -> dict[str, bytes]:
    snapshot: dict[str, bytes] = {}
    for name in DEFAULT_PATHSPECS:
        base = repo / name
        paths = [base] if base.is_file() else sorted(base.rglob("*"))
        for path in paths:
            if path.is_file():
                snapshot[path.relative_to(repo).as_posix()] = path.read_bytes()
    return snapshot


def _mutate_worktree(repo: Path) -> None:
    (repo / "attestations/modified.json").write_text('{"state": "worktree"}\n', encoding="utf-8")
    (repo / "attestations/deleted.json").unlink()
    (repo / "attestations/untracked.json").write_text('{"state": "untracked"}\n', encoding="utf-8")
    (repo / ".attestations/chain_head.json").write_text('{"head": "worktree"}\n', encoding="utf-8")


def test_restores_modified_and_deleted_but_never_untracked(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    revision = _build_repo(repo)
    _mutate_worktree(repo)
    env, log = _install_git_wrapper(tmp_path)

    result = _run_script(repo, "--source", revision, env=env)

    assert result.returncode == 0, result.stdout + result.stderr
    assert (repo / "attestations/modified.json").read_text() == '{"state": "source"}\n'
    assert (repo / "attestations/deleted.json").read_text() == '{"state": "source"}\n'
    assert (repo / ".attestations/chain_head.json").read_text() == '{"head": "source"}\n'
    assert (repo / "attestations/untracked.json").read_text() == '{"state": "untracked"}\n'
    assert _git(repo, "status", "--porcelain", "--", "attestations/untracked.json").stdout == (
        "?? attestations/untracked.json\n"
    )
    assert sorted(_restore_log(log)[1]) == [
        ".attestations/chain_head.json",
        "attestations/deleted.json",
        "attestations/modified.json",
    ]


def test_no_differences_is_a_single_informational_noop(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    revision = _build_repo(repo)
    env, log = _install_git_wrapper(tmp_path)

    result = _run_script(repo, "--source", revision, env=env)

    assert result.returncode == 0, result.stdout + result.stderr
    assert result.stderr == ""
    assert len(result.stdout.strip().splitlines()) == 1
    assert "No differences to restore" in result.stdout
    assert not log.exists(), log.read_text() if log.exists() else ""
    assert _git(repo, "status", "--porcelain").stdout == ""


def test_matching_path_is_never_passed_to_restore(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    revision = _build_repo(repo)
    _mutate_worktree(repo)
    before = (repo / "attestations/same.json").read_bytes()
    env, log = _install_git_wrapper(tmp_path)

    result = _run_script(repo, "--source", revision, env=env)

    assert result.returncode == 0, result.stdout + result.stderr
    _, restored = _restore_log(log)
    assert "attestations/same.json" not in restored
    assert sorted(restored) == [
        ".attestations/chain_head.json",
        "attestations/deleted.json",
        "attestations/modified.json",
    ]
    assert (repo / "attestations/same.json").read_bytes() == before


def test_script_matches_the_old_whole_tree_restore_exactly(tmp_path: Path) -> None:
    old_repo = tmp_path / "old"
    new_repo = tmp_path / "new"
    old_revision = _build_repo(old_repo)
    new_revision = _build_repo(new_repo)

    for repo in (old_repo, new_repo):
        _mutate_worktree(repo)
        # A tracked path the source lacks and a staged rename both exercise
        # paths the old whole-tree restore removes or recreates.
        (repo / "attestations/staged-new.json").write_text('{"state": "staged"}\n', encoding="utf-8")
        _git(repo, "add", "attestations/staged-new.json")
        _git(repo, "mv", "attestations/same.json", "attestations/renamed.json")
        (repo / "attestations/renamed.json").write_text('{"state": "renamed"}\n', encoding="utf-8")

    old = subprocess.run(
        ["git", "restore", "--source", old_revision, "--worktree", "--", *DEFAULT_PATHSPECS],
        cwd=old_repo,
        capture_output=True,
        text=True,
    )
    new = _run_script(new_repo, "--source", new_revision)

    assert old.returncode == 0, old.stdout + old.stderr
    assert new.returncode == 0, new.stdout + new.stderr
    assert _git(new_repo, "status", "--porcelain").stdout == _git(
        old_repo, "status", "--porcelain"
    ).stdout
    assert _snapshot(new_repo) == _snapshot(old_repo)


def test_scaling_restores_only_the_three_differing_paths(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    files = {f"attestations/bulk/{index:04d}.json": f'{{"index": {index}}}\n' for index in range(400)}
    files.update(BASE_FILES)
    revision = _build_repo(repo, files)
    differing = [
        "attestations/bulk/0007.json",
        "attestations/bulk/0199.json",
        "attestations/bulk/0399.json",
    ]
    for name in differing:
        (repo / name).write_text('{"index": "changed"}\n', encoding="utf-8")
    env, log = _install_git_wrapper(tmp_path)

    result = _run_script(repo, "--source", revision, env=env)

    assert result.returncode == 0, result.stdout + result.stderr
    _, restored = _restore_log(log)
    assert sorted(restored) == differing
    assert len(restored) == 3
    assert "Restored 3 path(s)" in result.stderr
    for name, _ in files.items():
        if name not in differing:
            assert name not in restored


def test_large_delta_is_restored_in_bounded_batches(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    files = {f"attestations/bulk/{index:02d}.json": f'{{"index": {index}}}\n' for index in range(5)}
    revision = _build_repo(repo, files)
    for name in files:
        (repo / name).write_text('{"index": "changed"}\n', encoding="utf-8")
    env, log = _install_git_wrapper(tmp_path)

    result = _run_script(
        repo,
        "--source",
        revision,
        env={**env, "RESTORE_ATTESTATIONS_BATCH_SIZE": "2"},
    )

    assert result.returncode == 0, result.stdout + result.stderr
    invocations, restored = _restore_log(log)
    assert invocations == 3
    assert sorted(restored) == sorted(files)
