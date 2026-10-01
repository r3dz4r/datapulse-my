"""Contracts for the unique required CI check context and bounded jobs."""

from __future__ import annotations

from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[2]
CI_WORKFLOW = ROOT / ".github/workflows/ci.yml"
REQUIRED_JOB = "deterministic-safety-net"


def _workflow() -> dict[str, object]:
    return yaml.safe_load(CI_WORKFLOW.read_text(encoding="utf-8"))


def test_required_context_is_not_produced_by_push_events() -> None:
    job = _workflow()["jobs"][REQUIRED_JOB]
    condition = job["if"]

    assert "github.event_name == 'push'" not in condition
    assert "health_only" not in condition


def test_every_ci_job_declares_a_timeout() -> None:
    jobs = _workflow()["jobs"]

    assert jobs
    assert all("timeout-minutes" in job for job in jobs.values())


def test_required_context_keeps_its_job_identity_and_dependency() -> None:
    jobs = _workflow()["jobs"]

    assert REQUIRED_JOB in jobs
    assert jobs[REQUIRED_JOB]["needs"] == "classify"
