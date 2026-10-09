"""Contracts for the unique required CI check context and bounded jobs."""

from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess

import pytest

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
        "(github.event_name == 'pull_request' || github.event_name == 'merge_group') "
        "&& env.ARTIFACT_ONLY_FAST_PATH != 'true'"
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


@pytest.mark.parametrize(
    ("changed_paths", "health_only", "append_only"),
    [
        (("health/latest.json",), "true", "false"),
        (("health/latest.json", "scripts/changed.py"), "false", "false"),
        (
            (
                ".attestations/chain_head.json",
                "attestations/2026-10-09/revisions/" + "a" * 64 + "/binding.json",
            ),
            "false",
            "true",
        ),
        (
            (
                ".attestations/chain_head.json",
                "attestations/2026-10-09/revisions/" + "a" * 64 + "/binding.json",
                "README.md",
            ),
            "false",
            "false",
        ),
    ],
)
def test_artifact_only_fast_path_classifies_pr_diff(
    tmp_path: Path, changed_paths: tuple[str, ...], health_only: str, append_only: str
) -> None:
    classify = _workflow()["jobs"]["classify"]
    checkout = classify["steps"][0]
    assert checkout["with"]["fetch-depth"] == (
        "${{ github.event_name == 'pull_request' && '0' || '2' }}"
    )
    assert checkout["with"]["filter"] == "blob:none"
    assert checkout["with"]["sparse-checkout"] == "scripts/classify_change.py"
    assert checkout["with"]["sparse-checkout-cone-mode"] == "false"
    assert classify["outputs"]["append_only"] == "${{ steps.classify.outputs.append_only }}"

    repository = tmp_path / "repository"
    repository.mkdir()
    subprocess.run(["git", "init", "-q", str(repository)], check=True)
    subprocess.run(["git", "config", "user.name", "CI Test"], cwd=repository, check=True)
    subprocess.run(["git", "config", "user.email", "ci@example.invalid"], cwd=repository, check=True)
    (repository / "scripts").mkdir()
    shutil.copy2(ROOT / "scripts/classify_change.py", repository / "scripts/classify_change.py")
    subprocess.run(["git", "add", "."], cwd=repository, check=True)
    subprocess.run(["git", "commit", "-qm", "base"], cwd=repository, check=True)
    base = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repository, text=True).strip()

    for path in changed_paths:
        target = repository / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("changed\n", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=repository, check=True)
    subprocess.run(["git", "commit", "-qm", "candidate"], cwd=repository, check=True)
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repository, text=True).strip()

    output = tmp_path / "github-output"
    environment = os.environ | {
        "GITHUB_EVENT_NAME": "pull_request",
        "GITHUB_OUTPUT": str(output),
        "BEFORE_SHA": "",
        "AFTER_SHA": "",
        "BASE_SHA": base,
        "HEAD_SHA": head,
    }
    result = subprocess.run(
        ["bash", "-c", classify["steps"][1]["run"]],
        cwd=repository,
        env=environment,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    lines = output.read_text(encoding="utf-8").splitlines()
    assert f"health_only={health_only}" in lines
    assert f"append_only={append_only}" in lines


def test_artifact_only_fast_path_preserves_required_verification() -> None:
    job = _workflow()["jobs"][REQUIRED_JOB]
    assert job["env"]["ARTIFACT_ONLY_FAST_PATH"] == (
        "${{ github.event_name == 'pull_request' && needs.classify.outputs.health_only == 'true' }}"
    )
    assert job["env"]["APPEND_ONLY_FAST_PATH"] == (
        "${{ github.event_name == 'pull_request' && needs.classify.outputs.append_only == 'true' }}"
    )
    assert job["env"]["FULL_VERIFICATION"] == (
        "${{ github.event_name != 'pull_request' || "
        "(needs.classify.outputs.health_only != 'true' && "
        "needs.classify.outputs.append_only != 'true') }}"
    )
    steps = {step["name"]: step for step in job["steps"]}
    for name in (
        "Validate manifest and health schemas",
        "Verify repository contract",
        "Verify distribution surfaces match canonical evidence",
        "Verify OpenWiki source contract",
    ):
        assert "if" not in steps[name]
    assert steps["Install artifact verification dependencies"]["if"] == (
        "env.ARTIFACT_ONLY_FAST_PATH == 'true' || env.APPEND_ONLY_FAST_PATH == 'true'"
    )
    assert steps["Install verification dependencies"]["if"] == (
        "env.FULL_VERIFICATION == 'true'"
    )
    assert steps["Verify immutable attestation append against accepted base"]["if"] == (
        "(github.event_name == 'pull_request' || github.event_name == 'merge_group') "
        "&& env.ARTIFACT_ONLY_FAST_PATH != 'true'"
    )
    assert steps["Verify attestation workflow contract"]["if"] == (
        "env.ARTIFACT_ONLY_FAST_PATH != 'true'"
    )
    for name, step in steps.items():
        if name in {
            "Check out repository",
            "Set up Python",
            "Install artifact verification dependencies",
            "Install verification dependencies",
            "Validate manifest and health schemas",
            "Verify repository contract",
            "Verify distribution surfaces match canonical evidence",
            "Verify OpenWiki source contract",
            "Verify immutable attestation append against accepted base",
            "Verify attestation workflow contract",
        }:
            continue
        assert step["if"] == "env.FULL_VERIFICATION == 'true'", name
