#!/usr/bin/env python3
"""Exercise the required job's actual expression and classifier shell step."""

from __future__ import annotations

import ast
import os
import re
import subprocess
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
JOBS = yaml.safe_load((ROOT / ".github/workflows/ci.yml").read_text())["jobs"]


def _job_runs(event: str, ref: str, result: str, health_only: str) -> bool:
    expression = JOBS["deterministic-safety-net"]["if"].strip()
    if expression.startswith("${{"):
        expression = expression[3:-2].strip()
    # Actions adds success() unless an explicit status function overrides it.
    if not re.search(r"\b(always|success|failure|cancelled)\s*\(", expression):
        expression = f"success() && ({expression})"
    values = {
        "github.event_name": event,
        "github.ref": ref,
        "needs.classify.result": result,
        "needs.classify.outputs.health_only": health_only,
    }
    expression = re.sub(
        r"\b(?:github|needs)(?:\.[A-Za-z_][A-Za-z_0-9]*)+",
        lambda match: repr(values[match.group()]),
        expression,
    )
    expression = expression.replace("&&", " and ").replace("||", " or ")
    expression = re.sub(r"!(?!=)", " not ", expression).strip()
    tree = ast.parse(expression, mode="eval")
    allowed = (
        ast.Expression, ast.BoolOp, ast.And, ast.Or, ast.UnaryOp, ast.Not,
        ast.Compare, ast.Eq, ast.NotEq, ast.Constant, ast.Call, ast.Name, ast.Load,
    )
    assert all(isinstance(node, allowed) for node in ast.walk(tree))
    functions = {
        "always": lambda: True,
        "success": lambda: result == "success",
        "failure": lambda: result == "failure",
        "cancelled": lambda: result == "cancelled",
    }
    return bool(eval(compile(tree, "<job condition>", "eval"), {"__builtins__": {}}, functions))


@pytest.mark.parametrize("result", ["failure", "cancelled", "skipped", "success"])
@pytest.mark.parametrize("health_only", ["", "false", "true"])
@pytest.mark.parametrize(
    ("event", "ref"),
    [
        ("push", "refs/heads/some-branch"),
        ("pull_request", "refs/pull/42/merge"),
        ("workflow_dispatch", "refs/heads/main"),
        ("merge_group", "refs/heads/gh-readonly-queue/main/pr-42"),
    ],
)
def test_required_gate_runs_despite_classifier_state(
    event: str, ref: str, result: str, health_only: str,
) -> None:
    assert _job_runs(event, ref, result, health_only), (
        f"required gate skipped: {event=} {ref=} {result=} {health_only=}"
    )


@pytest.mark.parametrize("event", ["push", "pull_request", "workflow_dispatch", "merge_group"])
@pytest.mark.parametrize("ref", ["refs/heads/main", "refs/heads/some-branch", "refs/pull/42/merge"])
def test_health_only_skip_is_exclusive_to_pushes_on_main(event: str, ref: str) -> None:
    assert _job_runs(event, ref, "success", "true") == (
        (event, ref) != ("push", "refs/heads/main")
    ), f"health-only skip escaped main push: {event=} {ref=}"


@pytest.mark.parametrize("result", ["failure", "cancelled", "skipped", ""])
def test_failed_classifier_cannot_skip_main_push(result: str) -> None:
    assert _job_runs("push", "refs/heads/main", result, "true")


@pytest.mark.parametrize("before_sha", ["0" * 40, "f" * 40])
def test_push_missing_before_commit_keeps_fail_closed_outputs(
    tmp_path: Path, before_sha: str,
) -> None:
    step = next(step for step in JOBS["classify"]["steps"] if step.get("id") == "classify")
    output = tmp_path / "outputs"
    result = subprocess.run(
        ["bash", "-c", step["run"]], cwd=ROOT, text=True, capture_output=True,
        env={**os.environ, "GITHUB_EVENT_NAME": "push", "BEFORE_SHA": before_sha,
             "AFTER_SHA": "HEAD", "GITHUB_OUTPUT": str(output)},
    )
    assert result.returncode == 0, f"missing before-SHA must run full suite: {result.stderr}"
    assert output.read_text().splitlines() == [
        "health_only=false", "append_only=false", "release_only=false",
        "changed_paths=(diff unavailable)",
    ]


def test_pull_request_missing_commit_keeps_fail_closed_outputs(tmp_path: Path) -> None:
    step = next(step for step in JOBS["classify"]["steps"] if step.get("id") == "classify")
    output = tmp_path / "outputs"
    result = subprocess.run(
        ["bash", "-c", step["run"]], cwd=ROOT, text=True, capture_output=True,
        env={**os.environ, "GITHUB_EVENT_NAME": "pull_request", "BASE_SHA": "0" * 40,
             "HEAD_SHA": "HEAD", "GITHUB_OUTPUT": str(output)},
    )
    assert result.returncode == 0, result.stderr
    assert "health_only=true" not in output.read_text()
    assert "changed_paths=(diff unavailable)" in output.read_text()
