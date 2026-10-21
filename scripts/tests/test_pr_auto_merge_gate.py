#!/usr/bin/env python3
"""Drive the read-only pre-merge gate through stubbed GitHub API responses."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
GATE = ROOT / "scripts/pr-auto-merge-gate.sh"
HEAD = "a" * 40


def _invoke(
    tmp_path: Path, instances: list[tuple[str, str | None, str]],
    *, args: tuple[str, ...] = ("2274",), tool_error: str = "", missing_gh: bool = False,
    context: str = "deterministic-safety-net", head: str = HEAD,
    missing_jq: bool = False, response: tuple[str, str] | None = None,
    paginate: bool = False,
) -> subprocess.CompletedProcess[str]:
    assert GATE.is_file(), "pre-merge gate script is missing"
    assert os.access(GATE, os.X_OK), "pre-merge gate must be executable"
    tools = tmp_path / "bin"
    tools.mkdir()
    if not missing_jq:
        tools.joinpath("jq").symlink_to(shutil.which("jq"))
    checks = [
        {"id": i, "name": context, "head_sha": head, "status": status,
         "conclusion": conclusion, "check_suite": {"id": i}}
        for i, (status, conclusion, _) in enumerate(instances, 1)
    ]
    runs = [
        {"id": 100 + i, "head_sha": head, "check_suite_id": i, "event": event}
        for i, (_, _, event) in enumerate(instances, 1)
    ]
    check_pages = [{"check_runs": [check]} for check in checks] if paginate else [{"check_runs": checks}]
    run_pages = [{"workflow_runs": [run]} for run in runs] if paginate else [{"workflow_runs": runs}]
    env = {
        **os.environ, "PATH": str(tools), "CHECKS": json.dumps(check_pages),
        "RUNS": json.dumps(run_pages), "HEAD_SHA": HEAD,
        "TOOL_ERROR": tool_error, "CALL_LOG": str(tmp_path / "calls"),
    }
    if response:
        env[response[0]] = response[1]
    if not missing_gh:
        stub = tools / "gh"
        stub.write_text(
            '#!/bin/bash\n'
            'printf "%s\\n" "$*" >> "$CALL_LOG"\n'
            '[[ "$*" != *merge* ]] || exit 97\n'
            'if [[ -n "$TOOL_ERROR" && ( "$TOOL_ERROR" == all || "$*" == *"$TOOL_ERROR"* ) ]]; then echo "API unavailable" >&2; exit 1; fi\n'
            'case "$*" in\n'
            '  *pulls/*) printf "%s\\n" "$HEAD_SHA" ;;\n'
            '  *check-runs*) printf "%s\\n" "$CHECKS" ;;\n'
            '  *actions/runs*) printf "%s\\n" "$RUNS" ;;\n'
            '  *) echo "unexpected gh invocation: $*" >&2; exit 98 ;;\n'
            'esac\n'
        )
        stub.chmod(0o755)
    result = subprocess.run(
        ["/bin/bash", str(GATE), *args], cwd=ROOT, env=env, text=True, capture_output=True,
    )
    if (tmp_path / "calls").exists():
        assert "pr merge" not in (tmp_path / "calls").read_text()
    return result


@pytest.mark.parametrize(
    ("instances", "code", "observed"),
    [
        ([("completed", "success", "pull_request")], 0, []),
        ([("completed", "neutral", "pull_request")], 0, []),
        ([("completed", "skipped", "pull_request")], 3, ["skipped"]),
        ([("in_progress", None, "pull_request")], 3, ["in_progress"]),
        ([("pending", None, "pull_request")], 3, ["pending"]),
        ([("queued", None, "pull_request")], 3, ["queued"]),
        ([("pending", None, "pull_request"), ("completed", "skipped", "push")],
         3, ["pending", "skipped", "pull_request", "push"]),
        ([], 3, ["absent"]),
        ([("completed", "success", "push")], 3, ["success", "push"]),
        ([("completed", "neutral", "workflow_dispatch")], 3, ["neutral", "workflow_dispatch"]),
        ([("completed", "failure", "pull_request")], 3, ["failure", "pull_request"]),
        ([("completed", "cancelled", "pull_request")], 3, ["cancelled"]),
        ([("pending", "success", "pull_request")], 3, ["pending", "success"]),
        ([("completed", "success", "push"), ("queued", None, "pull_request")],
         3, ["success", "push", "queued", "pull_request"]),
        ([("completed", "skipped", "push"), ("completed", "success", "pull_request")], 0, []),
    ],
)
def test_gate_observed_states(
    tmp_path: Path, instances: list[tuple[str, str | None, str]], code: int, observed: list[str],
) -> None:
    result = _invoke(tmp_path, instances)
    assert result.returncode == code, result.stdout + result.stderr
    for state in observed:
        assert state in result.stdout + result.stderr
    if code == 3:
        assert result.stderr.count("  check=") == len(instances)


@pytest.mark.parametrize("tool_error", ["all", "check-runs", "actions/runs"])
def test_gh_errors_are_tooling_failures(tmp_path: Path, tool_error: str) -> None:
    result = _invoke(tmp_path, [], tool_error=tool_error)
    assert result.returncode == 2, result.stdout + result.stderr
    assert "API unavailable" in result.stderr


def test_missing_gh_is_a_tooling_failure(tmp_path: Path) -> None:
    result = _invoke(tmp_path, [], missing_gh=True)
    assert result.returncode == 2, result.stdout + result.stderr
    assert "gh" in result.stderr


def test_missing_jq_is_a_tooling_failure(tmp_path: Path) -> None:
    result = _invoke(tmp_path, [], missing_jq=True)
    assert result.returncode == 2, result.stdout + result.stderr
    assert "jq" in result.stderr


@pytest.mark.parametrize(
    "response", [("CHECKS", "invalid JSON"), ("RUNS", "{}"), ("CHECKS", "[{}]"),
                 ("RUNS", "[{}]"), ("HEAD_SHA", "null")],
)
def test_malformed_responses_are_tooling_failures(tmp_path: Path, response: tuple[str, str]) -> None:
    result = _invoke(tmp_path, [], response=response)
    assert result.returncode == 2, result.stdout + result.stderr
    assert "tooling failure" in result.stderr


def test_missing_workflow_association_is_refused(tmp_path: Path) -> None:
    result = _invoke(
        tmp_path, [("completed", "success", "pull_request")],
        response=("RUNS", '[{"workflow_runs": []}]'),
    )
    assert result.returncode == 3, result.stdout + result.stderr
    assert "event=unknown" in result.stderr
    assert "success" in result.stderr


@pytest.mark.parametrize("conclusion", ["success", "skipped"])
def test_all_pages_are_checked(tmp_path: Path, conclusion: str) -> None:
    result = _invoke(
        tmp_path, [("completed", "skipped", "push"), ("completed", conclusion, "pull_request")],
        paginate=True,
    )
    assert result.returncode == (0 if conclusion == "success" else 3), result.stdout + result.stderr
    calls = (tmp_path / "calls").read_text().splitlines()
    assert all("--paginate --slurp" in call for call in calls[1:])
    assert "filter=all" in calls[1]
    if conclusion == "skipped":
        assert result.stderr.count("  check=") == 2
        assert "event=push" in result.stderr
        assert "event=pull_request" in result.stderr


@pytest.mark.parametrize("args", [(), ("bad",), ("0",), ("42", "gate", "extra"), ("42", "")])
def test_usage_errors(tmp_path: Path, args: tuple[str, ...]) -> None:
    result = _invoke(tmp_path, [], args=args)
    assert result.returncode == 2, result.stdout + result.stderr
    assert "Usage:" in result.stderr


def test_optional_context(tmp_path: Path) -> None:
    result = _invoke(
        tmp_path, [("completed", "success", "pull_request")],
        args=("2274", "custom gate"), context="custom gate",
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_unrelated_context_cannot_satisfy_gate(tmp_path: Path) -> None:
    result = _invoke(tmp_path, [("completed", "success", "pull_request")], context="other")
    assert result.returncode == 3, result.stdout + result.stderr
    assert "absent" in result.stdout + result.stderr


def test_stale_head_cannot_satisfy_gate(tmp_path: Path) -> None:
    result = _invoke(tmp_path, [("completed", "success", "pull_request")], head="b" * 40)
    assert result.returncode == 3, result.stdout + result.stderr
    assert "success" in result.stdout + result.stderr
