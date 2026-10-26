#!/usr/bin/env python3
"""Exercise the acceptance shell with capped calls and terminal PR decisions."""
from __future__ import annotations

import json
import os
from pathlib import Path
import re
import subprocess

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github/workflows/deploy-cloudflare-pages.yml"


def _run() -> str:
    workflow = yaml.safe_load(WORKFLOW.read_text())
    return next(step["run"] for step in workflow["jobs"]["sign_health"]["steps"]
                if step.get("name") == "Require authoritative acceptance before signing publication")


def _exercise(
    tmp_path: Path, *, pr_number: int = 99, pr_branch: str = "attestation/append-candidate",
    **settings: str,
) -> tuple[subprocess.CompletedProcess[str], list[str]]:
    """Keep real shell/jq parsing; replace GitHub, Git, verifier and cap expiry."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    (scripts / "submit_attestation_append.sh").write_text(
        'echo submit >> "$CALL_LOG"\n'
        'if [[ "${1:-}" == --rebuild ]]; then exit 1; fi\n'
    )
    (scripts / "close_superseded_appends.sh").write_text('echo close >> "$CALL_LOG"\n')
    mocks = {
        "timeout": r'''#!/bin/bash
shift 2
cap=$1
shift
key=other
case "$*" in
  'python3 scripts/verify_attestation_append.py --base HEAD') key=preflight ;;
  *--require-committed*) key=committed ;;
  *--wait-for-acceptance*) key=decision ;;
  'bash scripts/submit_attestation_append.sh') key=submit ;;
  'gh pr list '*) key=list ;;
  'gh pr view attestation/'*) key=view ;;
  'gh pr view 99 '*) key=poll ;;
  'gh pr merge '*) key=arm ;;
  'git '*) key=git ;;
  'jq '*) key=jq ;;
esac
if [[ "$key" == "$CAP_TARGET" && ( ! -e "$CAP_MARKER" || "$CAP_ALWAYS" == 1 ) ]]; then
  touch "$CAP_MARKER"
  if [[ "$key" == jq ]]; then IFS= read -r -d '' consumed || :; fi
  printf 'cap %s %s\n' "$cap" "$key" >> "$CALL_LOG"
  printf 'partial output from interrupted call'
  exit "$CAP_STATUS"
fi
exec "$@"
''',
        "python3": r'''#!/bin/bash
printf 'verify %s\n' "$*" >> "$CALL_LOG"
if [[ "$*" == *--wait-for-acceptance* ]]; then exit "$PROOF_STATUS"; fi
if [[ "$*" == *--require-committed* ]]; then exit "$COMMITTED_STATUS"; fi
exit "$PREFLIGHT_STATUS"
''',
        "git": r'''#!/bin/bash
case "$*" in
  'branch --show-current') echo "$BRANCH" ;;
  'rev-parse HEAD') echo head-sha ;;
  *) exit 2 ;;
esac
''',
        "gh": r'''#!/bin/bash
printf 'gh %s\n' "$*" >> "$CALL_LOG"
case "$1 $2" in
  'pr list') echo "$OPEN_PRS" ;;
  'pr view')
    if [[ "$3" == attestation/* ]]; then
      [[ "$MISSING" != 1 ]] || exit 1
      echo "$INITIAL_PR"
    else
      echo "$POLLED_PR"
    fi ;;
  'pr merge') exit "$ARM_STATUS" ;;
  *) exit 2 ;;
esac
''',
    }
    for name, source in mocks.items():
        path = bin_dir / name
        path.write_text(source)
        path.chmod(0o755)
    initial = {
        "number": pr_number, "headRefName": pr_branch, "headRefOid": "head-sha",
        "baseRefName": "main", "isCrossRepository": False,
        "createdAt": "2026-10-15T00:00:00Z", "autoMergeRequest": None,
        "state": settings.pop("initial_state", "OPEN"),
        "statusCheckRollup": [{"name": "deterministic-safety-net", "status": "COMPLETED",
                               "conclusion": settings.pop("initial_check", "SUCCESS")}],
    }
    polled = {**initial, "state": settings.pop("poll_state", "MERGED")}
    polled["statusCheckRollup"] = [{"name": "deterministic-safety-net", "status": "COMPLETED",
                                  "conclusion": settings.pop("poll_check", "SUCCESS")}]
    log = tmp_path / "calls.log"
    env = {
        **os.environ, "PATH": f"{bin_dir}:{os.environ['PATH']}",
        "GITHUB_REPOSITORY": "test/repo", "PROMOTION_SOURCE_SHA": "source-sha",
        "GITHUB_OUTPUT": str(tmp_path / "outputs"),
        "GITHUB_STEP_SUMMARY": str(tmp_path / "summary"),
        "APPEND_ACCEPTANCE_PATIENCE_SECONDS": "30", "CALL_LOG": str(log),
        "APPEND_PREP_STATE": "ready", "APPEND_BRANCH": pr_branch,
        "APPEND_HEAD_SHA": "head-sha",
        "CAP_MARKER": str(tmp_path / "cap-fired"), "CAP_TARGET": "none", "CAP_ALWAYS": "0",
        "CAP_STATUS": "124", "PROOF_STATUS": "0", "COMMITTED_STATUS": "1",
        "PREFLIGHT_STATUS": "0", "ARM_STATUS": "0", "MISSING": "0", "OPEN_PRS": "[]",
        "BRANCH": "attestation/append-candidate", "INITIAL_PR": json.dumps(initial),
        "POLLED_PR": json.dumps(polled), **settings,
    }
    # Advance only the shell clock to exercise production deadline arithmetic.
    shell = re.sub(r'^\s*sleep .*$', 'SECONDS=$((SECONDS + 15))', _run(), flags=re.MULTILINE)
    result = subprocess.run(["bash", "-c", shell], cwd=tmp_path, env=env,
                            text=True, capture_output=True, timeout=10)
    return result, log.read_text().splitlines()


@pytest.mark.parametrize(("target", "cap"), [
    ("preflight", 240), ("committed", 240), ("list", 20), ("view", 20),
    ("poll", 20), ("git", 10), ("jq", 10), ("arm", 20),
])
def test_safe_cap_hit_is_named_and_retried(tmp_path: Path, target: str, cap: int) -> None:
    result, calls = _exercise(tmp_path, CAP_TARGET=target)
    assert result.returncode == 0, result.stdout + result.stderr
    assert f"exceeded {cap}s (exit 124)" in result.stderr
    assert "Retrying capped safe call" in result.stderr
    assert "partial output" not in result.stdout
    assert calls.count("submit") == 1
    assert any("--wait-for-acceptance 0" in call for call in calls)


def test_parser_retry_cannot_hide_an_existing_append_pr(tmp_path: Path) -> None:
    result, calls = _exercise(tmp_path, CAP_TARGET="jq", pr_number=77,
                              pr_branch="attestation/append-existing", OPEN_PRS=json.dumps([{
                                  "number": 77, "headRefName": "attestation/append-existing",
                                  "headRefOid": "head-sha", "baseRefName": "main",
                                  "createdAt": "2026-10-15T00:00:00Z",
                              }]))
    assert result.returncode == 0, result.stdout + result.stderr
    assert "Already-open append PR #77 (attestation/append-existing)" in result.stdout
    assert "Retrying capped safe call" in result.stderr
    assert "submit" not in calls
    assert any("--wait-for-acceptance 0" in call for call in calls)
    assert (tmp_path / "outputs").read_text() == "state=accepted\n"


@pytest.mark.parametrize(("target", "cap", "command"), [
    ("submit", 360, "bash scripts/submit_attestation_append.sh"),
    ("decision", 240, "python3 scripts/verify_attestation_append.py"),
])
def test_submission_and_decision_caps_defer_without_retry(
    tmp_path: Path, target: str, cap: int, command: str,
) -> None:
    result, calls = _exercise(tmp_path, CAP_TARGET=target)
    assert result.returncode == 0, result.stdout + result.stderr
    assert command in result.stderr
    assert f"exceeded {cap}s (exit 124)" in result.stderr
    assert "Retrying" not in result.stderr
    assert sum(call.startswith("cap ") for call in calls) == 1
    assert (tmp_path / "outputs").read_text() == "state=append-deferred\n"
    assert "append-deferred" in (tmp_path / "summary").read_text()
    if target == "submit":
        assert "Bounded append operation timed out" in result.stdout
        assert not any("--wait-for-acceptance" in call for call in calls)
    else:
        assert "PR #99 (attestation/append-candidate)" in result.stdout
        assert "deterministic-safety-net: COMPLETED/SUCCESS" in result.stdout
        assert "patience 30s" in result.stdout


@pytest.mark.parametrize("settings", [
    {"MISSING": "1"}, {"BRANCH": "main"}, {"initial_state": "CLOSED"},
    {"initial_check": "FAILURE"}, {"initial_check": "TIMED_OUT"},
    {"poll_state": "CLOSED"}, {"poll_check": "FAILURE"},
])
def test_decided_refusal_fails_immediately_with_context(tmp_path: Path, settings: dict[str, str]) -> None:
    result, calls = _exercise(tmp_path, **settings)
    assert result.returncode != 0
    assert "PR #" in result.stderr
    assert " is " in result.stderr
    assert "deterministic-safety-net:" in result.stderr
    elapsed = re.search(r"elapsed (\d+)s \(patience 30s\)", result.stderr)
    assert elapsed is not None and int(elapsed.group(1)) < 15
    assert not any("--wait-for-acceptance" in call for call in calls)
    if "initial_check" in settings:
        assert settings["initial_check"] in result.stderr
        assert "PR #99" in result.stderr
        assert not any("gh pr merge" in call for call in calls)
    if settings.get("initial_state") == "CLOSED":
        assert "PR #99" in result.stderr and "CLOSED" in result.stderr
        assert "COMPLETED/SUCCESS" in result.stderr


def test_permanent_read_cap_stops_at_existing_deadline(tmp_path: Path) -> None:
    result, calls = _exercise(tmp_path, CAP_TARGET="poll", CAP_ALWAYS="1")
    assert result.returncode == 0, result.stdout + result.stderr
    assert "exceeded 20s" in result.stderr
    assert "retry exhausted" in result.stderr
    assert "patience 30s" in result.stderr
    assert sum(call == "cap 20s poll" for call in calls) == 2
    assert not any("--wait-for-acceptance" in call for call in calls)
    assert (tmp_path / "outputs").read_text() == "state=append-deferred\n"
    assert "Bounded append operation timed out" in result.stdout


@pytest.mark.parametrize("state", ["OPEN", "MERGED"])
def test_successful_check_and_merge_never_replace_byte_proof(tmp_path: Path, state: str) -> None:
    result, calls = _exercise(tmp_path, poll_state=state, PROOF_STATUS="1")
    assert result.returncode == 1
    assert "Append acceptance proof failed" in result.stderr
    assert "deterministic-safety-net: COMPLETED/SUCCESS" in result.stderr
    assert any("--wait-for-acceptance 0" in call for call in calls)
    assert not (tmp_path / "outputs").exists()


def test_non_timeout_verification_failure_is_not_retried(tmp_path: Path) -> None:
    result, calls = _exercise(tmp_path, PREFLIGHT_STATUS="2")
    assert result.returncode == 2
    assert "Retrying" not in result.stderr
    assert calls == ["verify scripts/verify_attestation_append.py --base HEAD"]


def test_named_timeout_preserves_kill_status_and_closes_child_pipes(tmp_path: Path) -> None:
    helpers = _run().split("named_timeout()", 1)[1].split("retry_timeout()", 1)[0]
    wrapper = "named_timeout()" + helpers.replace('timeout -k 5s "${cap}s"',
                                                 'timeout -k 0.1s "${cap}s"')
    result = subprocess.run(
        ["bash", "-c", wrapper + '\nnamed_timeout 0.1 bash -c \'trap "" TERM; sleep 30 & wait\''],
        cwd=tmp_path, text=True, capture_output=True, timeout=5,
    )
    assert result.returncode == 137
    assert "exceeded 0.1s (exit 137)" in result.stderr
    assert "bash -c" in result.stderr


def test_production_bounds_and_newest_wins_deploy_concurrency() -> None:
    workflow = yaml.safe_load(WORKFLOW.read_text())
    assert workflow["env"]["APPEND_ACCEPTANCE_PATIENCE_SECONDS"] == 1485
    assert workflow["env"]["APPEND_REQUIRED_CHECK_WORST_OBSERVED_SECONDS"] == 1185
    assert workflow["jobs"]["sign_health"]["timeout-minutes"] == 132
    assert 'timeout -k 5s "${cap}s" "$@"' in _run()
    assert "timeout -k 5s 3000s bash -Eeuo pipefail" in _run()
    step = next(step for step in workflow["jobs"]["sign_health"]["steps"] if step.get("run") == _run())
    assert step["timeout-minutes"] == 51
    # Replace superseded pending deploys while preserving the active promotion.
    assert workflow["concurrency"] == {
        "group": "cloudflare-pages-deploy",
        "cancel-in-progress": False,
        "queue": "single",
    }
