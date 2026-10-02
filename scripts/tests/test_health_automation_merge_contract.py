"""Contract for the health-automation auto-merge arming retry loop.

On 2026-10-02 the merge job's "Enable auto-merge" step ran about five seconds
after the push, while the required ``deterministic-safety-net`` check was still
queued. GitHub refused ``gh pr merge --auto`` with "Repository rule violations
found / Required status check ... is queued.", the step exited non-zero on its
single attempt, and nothing retried. The pull request stayed unarmed,
``origin/main`` stayed frozen, and publishing deferred every cycle for over an
hour. This module pins the bounded retry loop that fixes that race.

Set ``HEALTH_AUTOMATION_MERGE_WORKFLOW`` to run the contract against a scratch
copy of the workflow (the mutation proof does exactly that); unset, it runs
against the repository's own workflow definition.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

import pytest
import yaml


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_WORKFLOW = ROOT / ".github/workflows/health-automation-merge.yml"
WORKFLOW_ENV = "HEALTH_AUTOMATION_MERGE_WORKFLOW"

JOB_NAME = "merge"
STEP_NAME = "Enable auto-merge"
REQUIRED_CHECK = "deterministic-safety-net"

MAX_ATTEMPTS_RE = re.compile(r"ARM_MAX_ATTEMPTS:-(\d+)")
RETRY_SECONDS_RE = re.compile(r"ARM_RETRY_SECONDS:-(\d+)")


def _workflow_path() -> Path:
    override = os.environ.get(WORKFLOW_ENV)
    return Path(override) if override else DEFAULT_WORKFLOW


def _workflow_text() -> str:
    path = _workflow_path()
    return path.read_text(encoding="utf-8")


def _job(workflow: object, source: str) -> dict[str, object]:
    if not isinstance(workflow, dict):
        raise AssertionError(f"{source}: top level is not a mapping")
    jobs = workflow.get("jobs")
    if not isinstance(jobs, dict) or JOB_NAME not in jobs:
        raise AssertionError(f"{source}: no {JOB_NAME!r} job")
    job = jobs[JOB_NAME]
    if not isinstance(job, dict):
        raise AssertionError(f"{source}: job {JOB_NAME!r} is not a mapping")
    return job


def _step_script(workflow: object, source: str) -> str:
    job = _job(workflow, source)
    for step in job.get("steps") or []:
        if isinstance(step, dict) and step.get("name") == STEP_NAME:
            script = step.get("run")
            if not isinstance(script, str):
                raise AssertionError(
                    f"{source}: step {STEP_NAME!r} has no run script"
                )
            return script
    raise AssertionError(
        f"{source}: job {JOB_NAME!r} has no step named {STEP_NAME!r}"
    )


def _merge_timeout_minutes(workflow: object, source: str) -> int:
    job = _job(workflow, source)
    timeout = job.get("timeout-minutes")
    if isinstance(timeout, bool) or not isinstance(timeout, int):
        raise AssertionError(
            f"{source}: job {JOB_NAME!r} must declare an integer timeout-minutes"
        )
    return timeout


def _defaults(script: str, source: str) -> tuple[int, int]:
    attempts_match = MAX_ATTEMPTS_RE.search(script)
    retry_match = RETRY_SECONDS_RE.search(script)
    if attempts_match is None or retry_match is None:
        raise AssertionError(
            f"{source}: the arming step must define ARM_MAX_ATTEMPTS and "
            f"ARM_RETRY_SECONDS with shell defaults"
        )
    return int(attempts_match.group(1)), int(retry_match.group(1))


def _assert_retry_contract(workflow_text: str, source: str) -> None:
    workflow = yaml.safe_load(workflow_text)
    script = _step_script(workflow, source)
    attempts, retry_seconds = _defaults(script, source)
    lines = script.splitlines()

    # (a) Bounded retry loop whose bound comes from ARM_MAX_ATTEMPTS.
    while_lines = [line for line in lines if re.search(r"\bwhile\b", line)]
    if not while_lines:
        raise AssertionError(
            f"{source}: {STEP_NAME!r} has no retry loop, so a queued required "
            f"check would strand the pull request again"
        )
    if not any("max_attempts" in line for line in while_lines):
        raise AssertionError(
            f"{source}: the retry loop is not bounded by ARM_MAX_ATTEMPTS"
        )

    # (b) Idempotent already-enabled path that exits 0.
    if ".autoMergeRequest" not in script:
        raise AssertionError(
            f"{source}: the arming step must re-read autoMergeRequest each attempt"
        )
    for index, line in enumerate(lines):
        if "already enabled" in line.lower():
            window = "\n".join(lines[index : index + 3])
            if "exit 0" not in window:
                raise AssertionError(
                    f"{source}: the already-enabled path must print and exit 0"
                )
            break
    else:
        raise AssertionError(
            f"{source}: no idempotent already-enabled path that exits 0"
        )

    # (c) Exhaustion still emits an ::error line and exits non-zero.
    exhaustion = [
        line
        for line in lines
        if "::error" in line and "max_attempts" in line and "last_error" in line
    ]
    if not exhaustion:
        raise AssertionError(
            f"{source}: the exhaustion path must emit an ::error line naming the "
            f"attempt count and the last observed error"
        )
    if not script.rstrip().endswith("exit 1"):
        raise AssertionError(
            f"{source}: the exhaustion path must exit 1, never 0"
        )

    # (d) The merge job timeout comfortably exceeds the loop's maximum wait. Both
    # numbers come from the workflow defaults, not from this test.
    max_wait_seconds = attempts * retry_seconds
    timeout_seconds = _merge_timeout_minutes(workflow, source) * 60
    if timeout_seconds <= max_wait_seconds:
        raise AssertionError(
            f"{source}: merge timeout-minutes={timeout_seconds // 60} does not "
            f"exceed the loop's maximum wait of {attempts} * {retry_seconds}s "
            f"= {max_wait_seconds}s"
        )

    # (e) The required-check-queued refusal is named as retryable.
    if REQUIRED_CHECK not in script:
        raise AssertionError(
            f"{source}: the retryable matcher must name the required check "
            f"{REQUIRED_CHECK!r}"
        )
    if "queued" not in script.lower():
        raise AssertionError(
            f"{source}: the required-check-queued refusal must be retryable"
        )
    if "is_retryable" not in script:
        raise AssertionError(
            f"{source}: the arming step must classify failures as retryable"
        )


def _strip_retry_loop(script: str) -> str:
    kept: list[str] = []
    in_loop = False
    for line in script.splitlines():
        if re.search(r"\bwhile\b", line):
            in_loop = True
            continue
        if in_loop:
            if line.strip() == "done":
                in_loop = False
            continue
        kept.append(line)
    return "\n".join(kept) + "\n"


def test_arming_step_has_bounded_retry_loop() -> None:
    _assert_retry_contract(_workflow_text(), str(_workflow_path()))


def test_negative_control_retry_loop_removed_fails() -> None:
    workflow = yaml.safe_load(_workflow_text())
    job = _job(workflow, str(_workflow_path()))
    for step in job.get("steps") or []:
        if isinstance(step, dict) and step.get("name") == STEP_NAME:
            script = step.get("run")
            assert isinstance(script, str)
            step["run"] = _strip_retry_loop(script)
            break
    mutated = yaml.safe_dump(workflow)

    with pytest.raises(AssertionError, match=r"no retry loop"):
        _assert_retry_contract(mutated, "mutated-health-automation-merge.yml")
