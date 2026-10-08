"""Contracts for the unique required CI check context and bounded jobs."""

from __future__ import annotations

from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[2]
CI_WORKFLOW = ROOT / ".github/workflows/ci.yml"
REQUIRED_JOB = "deterministic-safety-net"


def _workflow() -> dict[str, object]:
    return yaml.load(CI_WORKFLOW.read_text(encoding="utf-8"), Loader=yaml.BaseLoader)


def test_required_context_is_not_produced_by_push_events() -> None:
    job = _workflow()["jobs"][REQUIRED_JOB]
    condition = job["if"]

    assert "github.event_name == 'push'" not in condition
    assert "health_only" not in condition


def test_required_context_is_produced_for_merge_queue_events() -> None:
    workflow = _workflow()
    assert set(workflow["on"]) == {
        "push",
        "pull_request",
        "workflow_dispatch",
        "merge_group",
    }

    job = workflow["jobs"][REQUIRED_JOB]
    assert job["if"] == (
        "github.event_name == 'pull_request' || "
        "github.event_name == 'workflow_dispatch' || "
        "github.event_name == 'merge_group'"
    )

    append_step = next(
        step for step in job["steps"]
        if step.get("name") == "Verify immutable attestation append against accepted base"
    )
    assert append_step["if"] == (
        "github.event_name == 'pull_request' || github.event_name == 'merge_group'"
    )
    assert append_step["env"]["ACCEPTED_BASE"] == (
        "${{ github.event.pull_request.base.sha || github.event.merge_group.base_sha }}"
    )


def test_every_ci_job_declares_a_timeout() -> None:
    jobs = _workflow()["jobs"]

    assert jobs
    assert all("timeout-minutes" in job for job in jobs.values())


def test_required_context_keeps_its_job_identity_and_dependency() -> None:
    jobs = _workflow()["jobs"]

    assert REQUIRED_JOB in jobs
    assert jobs[REQUIRED_JOB]["needs"] == "classify"
