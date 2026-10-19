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
# The verifier sequence lives in its own job so it runs beside the pytest partition rather than
# after it; the required context only judges results. Shape assertions about the verifiers follow
# the work to that job, while identity and dependency assertions stay on the required context.
VERIFIER_JOB = "safety-net-verifiers"


def _workflow() -> dict[str, object]:
    return yaml.load(CI_WORKFLOW.read_text(encoding="utf-8"), Loader=yaml.BaseLoader)


def test_required_context_runs_for_classified_pushes() -> None:
    job = _workflow()["jobs"][REQUIRED_JOB]
    condition = job["if"]

    assert "github.event_name == 'push'" in condition
    # Fail-safe default: anything that is not the health-only fast path gets the full suite,
    # so a source, release or append push can never land unverified.
    assert "health_only != 'true'" in condition


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
        "always() && ("
        "github.event_name == 'pull_request' || "
        "github.event_name == 'workflow_dispatch' || "
        "github.event_name == 'merge_group' || "
        "(github.event_name == 'push' && "
        "needs.classify.outputs.health_only != 'true'))"
    )

    append_step = next(
        step for step in workflow["jobs"][VERIFIER_JOB]["steps"]
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
    assert jobs[REQUIRED_JOB]["needs"] == ["classify", "pytest-shards", VERIFIER_JOB]
    assert "strategy" not in jobs[REQUIRED_JOB]


def test_pytest_shards_cover_every_file_once_and_keep_history_scoped() -> None:
    jobs = _workflow()["jobs"]
    shards = jobs["pytest-shards"]
    assert shards["needs"] == "classify"
    assert shards["strategy"]["fail-fast"] == "false"
    assert shards["strategy"]["matrix"]["shard"] == ["history", "a", "b"]
    assert shards["if"] == (
        "(github.event_name == 'pull_request' || "
        "github.event_name == 'workflow_dispatch' || "
        "github.event_name == 'merge_group' || "
        "(github.event_name == 'push' && needs.classify.outputs.health_only != 'true')) "
        "&& (github.event_name != 'pull_request' || "
        "(needs.classify.outputs.health_only != 'true' && "
        "needs.classify.outputs.append_only != 'true'))"
    )

    steps = {step["name"]: step for step in shards["steps"]}
    # Every shard must carry full history. A shallow shard made identity-deriving tests fail for a
    # reason unrelated to the change, which is the wrong kind of red, and the shards run in
    # parallel so the clone is not the critical path.
    assert "Check out shallow shard" not in steps
    assert steps["Check out repository"]["with"]["fetch-depth"] == "0"
    assert steps["Install verification dependencies"]["run"] == (
        "python3 -m pip install --requirement requirements-dev.txt"
    )
    assert "pandoc=3.1.3+ds-2" in steps["Install Pandoc"]["run"]
    required_setup = next(
        step for step in jobs[VERIFIER_JOB]["steps"] if step.get("name") == "Set up Python"
    )
    assert steps["Set up Python"]["with"] == required_setup["with"]
    assert steps["Run pytest shard"]["env"]["DEFAULT_BRANCH"] == (
        "${{ github.event.repository.default_branch }}"
    )
    # Discovery provenance must follow the candidate; without this the gate returns green on a stale
    # candidate. The gate restores the ref, which the discovery-gate test asserts independently.
    assert 'git update-ref "$default_ref" HEAD' in steps["Run pytest shard"]["run"]
    assert "trap" in steps["Run pytest shard"]["run"]

    selected: list[str] = []
    for shard in shards["strategy"]["matrix"]["shard"]:
        result = subprocess.run(
            ["bash", "-c", steps["Run pytest shard"]["run"]],
            cwd=ROOT,
            env=os.environ | {"TEST_SHARD": shard, "SHARD_DRY_RUN": "1"},
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, result.stderr
        files = result.stdout.splitlines()
        assert files, shard
        selected.extend(files)
        if shard == "history":
            assert set(files) == {
                "scripts/tests/test_append_fork_resolution.py",
                "scripts/tests/test_attestation_rekor_wiring.py",
                "scripts/tests/test_chain_head_monotonicity.py",
                "scripts/tests/test_deploy_cloudflare_pages_contract.py",
                "scripts/tests/test_publish_pipeline_split.py",
            }

    current = {
        str(path.relative_to(ROOT))
        for directory in (ROOT / "scripts/tests", ROOT / "mcp/tests")
        for path in directory.glob("test_*.py")
    }
    assert len(selected) == len(set(selected))
    assert set(selected) == current


@pytest.mark.parametrize("shard_result", ["failure", "cancelled", "skipped", "success"])
def test_required_context_rejects_red_or_missing_shards(shard_result: str) -> None:
    job = _workflow()["jobs"][REQUIRED_JOB]
    step = next(step for step in job["steps"] if step.get("name") == "Require successful pytest shards")
    assert step["if"] == "always() && env.FULL_VERIFICATION == 'true'"
    assert step["env"]["SHARD_RESULT"] == "${{ needs.pytest-shards.result }}"
    result = subprocess.run(
        ["bash", "-c", step["run"]],
        env=os.environ | {"SHARD_RESULT": shard_result},
        capture_output=True,
        text=True,
    )
    assert (result.returncode == 0) == (shard_result == "success")


@pytest.mark.parametrize(
    ("event_name", "changed_paths", "health_only", "append_only", "release_only"),
    [
        ("pull_request", ("health/latest.json",), "true", "false", "false"),
        (
            "pull_request",
            (
                "health/latest.json",
                "observation-receipts/chain_head.json",
                "observation-receipts/days/2026-10-15.json",
            ),
            "true",
            "false",
            "false",
        ),
        (
            "pull_request", ("health/latest.json", "scripts/changed.py"),
            "false", "false", "false",
        ),
        (
            "pull_request",
            (
                ".attestations/chain_head.json",
                "attestations/2026-10-09/revisions/" + "a" * 64 + "/binding.json",
            ),
            "false",
            "true",
            "false",
        ),
        (
            "pull_request",
            (
                ".attestations/chain_head.json",
                "attestations/2026-10-09/revisions/" + "a" * 64 + "/binding.json",
                "README.md",
            ),
            "false",
            "false",
            "false",
        ),
        (
            "push",
            (".release-please-manifest.json", "CHANGELOG.md", "VERSION.txt", "server.json"),
            "false", "false", "true",
        ),
        ("push", ("VERSION.txt",), "false", "false", "false"),
        ("push", ("health/latest.json",), "true", "false", "false"),
        (
            "push",
            (
                ".attestations/chain_head.json",
                "attestations/2026-10-09/revisions/" + "a" * 64 + "/binding.json",
            ),
            "false", "true", "false",
        ),
    ],
)
def test_classify_step_classifies_diff(
    tmp_path: Path,
    event_name: str,
    changed_paths: tuple[str, ...],
    health_only: str,
    append_only: str,
    release_only: str,
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
    assert classify["outputs"]["release_only"] == "${{ steps.classify.outputs.release_only }}"

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
        "GITHUB_EVENT_NAME": event_name,
        "GITHUB_OUTPUT": str(output),
        "BEFORE_SHA": base,
        "AFTER_SHA": head,
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
    assert f"release_only={release_only}" in lines
    assert f"changed_paths={', '.join(sorted(changed_paths))}" in lines


def test_required_context_judges_results_without_repeating_the_work() -> None:
    """The required context must not carry a checkout or a verifier step.

    Both are what made every source push pay a full-history clone twice, serially. The
    required name stays on a single non-matrix job because branch protection requires that
    exact context; the work it judges lives in its own jobs.
    """
    jobs = _workflow()["jobs"]
    required = jobs[REQUIRED_JOB]
    verifier = jobs[VERIFIER_JOB]

    assert "strategy" not in required
    actions = [step.get("uses", "") for step in required["steps"]]
    assert not any(action.startswith("actions/checkout") for action in actions), (
        "the required context must not check out the repository; the verifier job owns that"
    )
    assert "timeout-minutes" in required
    assert int(required["timeout-minutes"]) <= 5, (
        "a result-checking job that needs a longer bound is doing work again"
    )

    required_names = {step["name"] for step in required["steps"]}
    assert required_names == {"Require successful pytest shards", "Require successful verifier job"}
    assert "pytest-shards" not in (verifier.get("needs") or []), (
        "the verifier job must not wait on the shards; running beside them is the whole saving"
    )
    assert verifier["needs"] == ["classify"]


@pytest.mark.parametrize("verifier_result", ["failure", "cancelled", "success", "skipped"])
def test_required_context_rejects_a_red_verifier_job(verifier_result: str) -> None:
    job = _workflow()["jobs"][REQUIRED_JOB]
    step = next(step for step in job["steps"] if step["name"] == "Require successful verifier job")
    result = subprocess.run(
        ["bash", "-c", step["run"]],
        env=os.environ | {"VERIFIER_RESULT": verifier_result},
        capture_output=True,
        text=True,
    )
    assert (result.returncode == 0) == (verifier_result in {"success", "skipped"})


def test_artifact_only_fast_path_preserves_required_verification() -> None:
    job = _workflow()["jobs"][VERIFIER_JOB]
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
        "Verify live documentation counts",
        "Verify repository contract",
        "Verify distribution surfaces match canonical evidence",
        "Verify OpenWiki source contract",
        "Verify signed chain-head monotonicity",
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
            "Require successful pytest shards",
            "Check out repository",
            "Set up Python",
            "Install artifact verification dependencies",
            "Install verification dependencies",
            "Validate manifest and health schemas",
            "Verify live documentation counts",
            "Verify repository contract",
            "Verify distribution surfaces match canonical evidence",
            "Verify OpenWiki source contract",
            "Verify signed chain-head monotonicity",
            "Verify immutable attestation append against accepted base",
            "Verify attestation workflow contract",
        }:
            continue
        assert step["if"] == "env.FULL_VERIFICATION == 'true'", name


def test_ci_profiles_keep_chain_head_ordering_check_and_its_dependencies() -> None:
    steps = {step["name"]: step for step in _workflow()["jobs"][VERIFIER_JOB]["steps"]}
    check = steps["Verify signed chain-head monotonicity"]
    assert "if" not in check
    assert check["run"] == "python3 -m pytest -q scripts/tests/test_chain_head_monotonicity.py"
    assert "pytest==8.4.1" in steps["Install artifact verification dependencies"]["run"]


def test_ci_classify_call_sites_use_separate_profiles() -> None:
    script = _workflow()["jobs"]["classify"]["steps"][1]["run"]
    invocations = [line.strip() for line in script.splitlines() if "python3 scripts/classify_change.py" in line]
    assert len(invocations) == 3
    assert invocations[0].endswith("python3 scripts/classify_change.py --ci-artifact-profile; then")
    assert invocations[1].endswith("python3 scripts/classify_change.py --append-only; then")
    assert invocations[2].endswith("python3 scripts/classify_change.py --release-only; then")


def test_push_without_available_base_fails_classification(tmp_path: Path) -> None:
    script = _workflow()["jobs"]["classify"]["steps"][1]["run"]
    output = tmp_path / "github-output"
    environment = os.environ | {
        "GITHUB_EVENT_NAME": "push",
        "GITHUB_OUTPUT": str(output),
        "BEFORE_SHA": "0" * 40,
        "AFTER_SHA": "1" * 40,
        "BASE_SHA": "",
        "HEAD_SHA": "",
    }
    result = subprocess.run(
        ["bash", "-c", script], cwd=ROOT, env=environment, capture_output=True, text=True
    )
    assert result.returncode != 0
    assert "diff unavailable" in result.stderr


@pytest.mark.parametrize(
    ("safety", "health", "expected"),
    [
        # A gate ran (whatever its verdict) -> the push was verified.
        ("success", "skipped", 0),
        ("skipped", "success", 0),
        ("failure", "skipped", 0),
        ("skipped", "failure", 0),
        # Neither gate ran -> the push verified nothing, which is the defect.
        ("skipped", "skipped", 1),
    ],
)
def test_main_push_coverage_guard(safety: str, health: str, expected: int) -> None:
    guard = _workflow()["jobs"]["verify-push-gate-coverage"]
    # The guard must observe the gates themselves, not infer coverage from the profile flags.
    assert set(guard["needs"]) == {"classify", "deterministic-safety-net", "health-integrity"}
    assert "always()" in guard["if"]
    assert "github.ref == 'refs/heads/main'" in guard["if"]
    assert int(guard["timeout-minutes"]) <= 5
    step = guard["steps"][0]
    environment = os.environ | {
        "CLASSIFY_RESULT": "success",
        "SAFETY_RESULT": safety,
        "HEALTH_RESULT": health,
        "HEALTH_ONLY": "false",
        "APPEND_ONLY": "false",
        "RELEASE_ONLY": "false",
        "CHANGED_PATHS": "VERSION.txt, scripts/changed.py",
    }
    process = subprocess.run(
        ["bash", "-c", step["run"]], env=environment, capture_output=True, text=True
    )
    assert process.returncode == expected
    if expected:
        assert "verified nothing" in process.stderr
        assert all(profile in process.stderr for profile in ("health_only", "append_only", "release_only"))
        assert "VERSION.txt, scripts/changed.py" in process.stderr


def test_health_integrity_checkout_has_full_history() -> None:
    """Chain linearity needs the commit graph; a depth-1 clone reports a false fork."""
    job = _workflow()["jobs"]["health-integrity"]
    checkout = next(
        step for step in job["steps"] if str(step.get("uses", "")).startswith("actions/checkout")
    )

    assert checkout["with"]["fetch-depth"] == "0"
