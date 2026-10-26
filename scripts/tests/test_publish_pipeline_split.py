#!/usr/bin/env python3
"""Exercise the build/publication boundary without GitHub or Cloudflare writes."""

from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess

import pytest
import yaml


ROOT = Path(__file__).resolve().parents[2]
BUILD = ROOT / ".github/workflows/publish-publication.yml"
PUBLISH = ROOT / ".github/workflows/deploy-cloudflare-pages.yml"
SOURCE = "b" * 40


def _workflow(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _step(path: Path, job: str, name: str) -> dict:
    return next(step for step in _workflow(path)["jobs"][job]["steps"] if step.get("name") == name)


def _run(script: str, root: Path, **environment: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", "-c", script], cwd=root, capture_output=True, text=True,
        env={**os.environ, **environment}, check=False,
    )


def test_only_completed_builds_enter_the_newest_wins_deploy_lane() -> None:
    build, publish = _workflow(BUILD), _workflow(PUBLISH)
    # PyYAML's YAML 1.1 loader treats the Actions `on` key as True.
    assert build[True]["push"]["branches"] == ["main"]
    assert "push" not in publish[True]
    assert publish[True]["workflow_run"] == {
        "workflows": [build["name"]], "types": ["completed"], "branches": ["main"],
    }
    assert "concurrency" not in build
    assert all("concurrency" not in job for job in build["jobs"].values())
    # Pending deploys may be replaced; in-flight promotions remain protected.
    assert publish["concurrency"] == {
        "group": "cloudflare-pages-deploy", "cancel-in-progress": False, "queue": "single",
    }
    assert build["jobs"]["build"]["if"] == "github.ref == 'refs/heads/main'"
    assert "workflow_run.conclusion == 'success'" in publish["jobs"]["classify"]["if"]
    assert ".github/workflows/publish-publication.yml" in build[True]["push"]["paths"]


def test_build_verifies_before_upload_and_cannot_append_or_publish() -> None:
    workflow = _workflow(BUILD)
    steps = workflow["jobs"]["build"]["steps"]
    names = [step.get("name", "checkout") for step in steps]
    required = [
        "Run release-build generation profile (non-health path)",
        "Generate per-dataset evidence statements (release artifact)",
        "Validate DataPulse contract (non-health path)",
        "Verify full release contract (non-health path)",
        "Stage only generated publication inputs",
        "Upload verified per-commit release build",
    ]
    assert [names.index(name) for name in required] == sorted(names.index(name) for name in required)
    assert "bash scripts/generate.sh release-build" in steps[names.index(required[0])]["run"]
    verify = steps[names.index(required[3])]["run"]
    for gate in ("--workdir-root", "--verify-proof", "verify_release_invariants.sh --local"):
        assert gate in verify
    assert all("if" not in step and "continue-on-error" not in step for step in steps)
    source = BUILD.read_text()
    for forbidden in ("submit_attestation_append", "create-github-app-token", "cosign", "pages deploy", "id-token", "git push"):
        assert forbidden not in source
    upload = steps[-1]["with"]
    assert upload["include-hidden-files"] is True
    assert upload["if-no-files-found"] == "error"
    assert upload["name"] == "pages-build-${{ github.run_id }}-${{ github.run_attempt }}"


def _build_run(number: int, **overrides: object) -> dict:
    return {
        "id": number * 10, "run_number": number, "run_attempt": 1,
        "head_sha": f"{number:040x}", "head_branch": "main", "event": "push",
        "status": "completed", "conclusion": "success",
        "head_repository": {"full_name": "owner/repo"}, **overrides,
    }


@pytest.mark.parametrize("invalid", [False, True])
def test_late_completion_selects_newest_success_by_sequence_not_finish_order(
    tmp_path: Path, invalid: bool,
) -> None:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    gh = bin_dir / "gh"
    gh.write_text("#!/bin/sh\ncat \"$BUILD_RUNS\"\n")
    gh.chmod(0o755)
    # Simulate an old completion triggering after newer builds. Neither failure,
    # an in-progress rerun nor a fork/other branch can supply publication bytes.
    runs = [
        _build_run(1), _build_run(4), _build_run(2),
        _build_run(7, conclusion="failure"),
        _build_run(8, head_repository={"full_name": "fork/repo"}),
        _build_run(9, head_branch="feature"),
        _build_run(10, status="in_progress"),
    ] if not invalid else [_build_run(7, conclusion="failure")]
    payload = tmp_path / "runs.json"
    payload.write_text(json.dumps({"workflow_runs": runs}))
    output, environment = tmp_path / "output", tmp_path / "environment"
    result = _run(
        _step(PUBLISH, "classify", "Select newest successful main build")["run"], tmp_path,
        PATH=f"{bin_dir}:{os.environ['PATH']}", BUILD_RUNS=str(payload),
        GITHUB_REPOSITORY="owner/repo", GITHUB_OUTPUT=str(output), GITHUB_ENV=str(environment),
    )
    if invalid:
        assert result.returncode != 0
        assert not output.exists() and not environment.exists()
    else:
        assert result.returncode == 0, result.stderr
        assert output.read_text().splitlines() == ["run_id=40", "attempt=1"]
        assert environment.read_text().strip() == f"PROMOTION_BUILT_SHA={4:040x}"


@pytest.mark.parametrize("mismatch", [False, True])
def test_settlement_pins_built_source_while_unbuilt_main_keeps_advancing(
    tmp_path: Path, mismatch: bool,
) -> None:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    gh = bin_dir / "gh"
    gh.write_text(
        '#!/bin/sh\nprintf "%s\\n" "$*" >> "$LOOKUPS"\ncat "$COMMIT_RESPONSE"\n'
    )
    gh.chmod(0o755)
    response = tmp_path / "commit.json"
    response.write_text(json.dumps({
        "sha": "c" * 40 if mismatch else SOURCE,
        "commit": {"committer": {"date": "2020-01-01T00:00:00Z"}},
    }))
    output = tmp_path / "output"
    lookups = tmp_path / "lookups"
    result = _run(
        _step(PUBLISH, "classify", "Wait for settled main before promoting")["run"], tmp_path,
        PATH=f"{bin_dir}:{os.environ['PATH']}", COMMIT_RESPONSE=str(response),
        LOOKUPS=str(lookups), GITHUB_REPOSITORY="owner/repo", GITHUB_OUTPUT=str(output),
        PROMOTION_BUILT_SHA=SOURCE,
        PROMOTION_SETTLED_QUIET_SECONDS="300", PROMOTION_SETTLED_MAX_WAIT_SECONDS="900",
    )
    if mismatch:
        assert result.returncode != 0 and not output.exists()
    else:
        assert result.returncode == 0, result.stderr
        assert output.read_text().splitlines() == [f"settled_sha={SOURCE}", "settlement_reason=quiet"]
        assert len(lookups.read_text().splitlines()) == 2
    assert f"commits/{SOURCE}" in lookups.read_text()
    assert "refs/heads/main" not in lookups.read_text()


@pytest.mark.parametrize("relation", ["advance", "same", "regression", "unknown"])
def test_canonical_deployment_is_an_ordering_floor_even_after_served_check_failure(
    tmp_path: Path, relation: str,
) -> None:
    def git(*arguments: str) -> str:
        return subprocess.check_output(["git", *arguments], cwd=tmp_path, text=True).strip()

    git("init", "-q")
    git("config", "user.name", "Fixture")
    git("config", "user.email", "fixture@example.test")
    git("commit", "--quiet", "--allow-empty", "-m", "first")
    first = git("rev-parse", "HEAD")
    git("commit", "--quiet", "--allow-empty", "-m", "second")
    second = git("rev-parse", "HEAD")
    git("remote", "add", "origin", str(tmp_path))
    deployed = first if relation == "advance" else second
    selected = first if relation == "regression" else second
    response = {"success": True, "result": {"canonical_deployment": {
        "deployment_trigger": {"metadata": {"commit_hash": deployed if relation != "unknown" else None}},
    }}}
    payload = tmp_path / "project.json"
    payload.write_text(json.dumps(response))
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    curl = bin_dir / "curl"
    curl.write_text("#!/bin/sh\ncat \"$PROJECT_RESPONSE\"\n")
    curl.chmod(0o755)
    output = tmp_path / "output"
    result = _run(
        _step(PUBLISH, "classify", "Refuse production regression and identify classification base")["run"],
        tmp_path, PATH=f"{bin_dir}:{os.environ['PATH']}", PROJECT_RESPONSE=str(payload),
        CLOUDFLARE_API_TOKEN="fixture", CLOUDFLARE_ACCOUNT_ID="fixture",
        SELECTED_SHA=selected, GITHUB_OUTPUT=str(output),
    )
    if relation in {"advance", "same"}:
        assert result.returncode == 0, result.stderr
        assert output.read_text().strip() == f"source_sha={deployed}"
    else:
        assert result.returncode != 0
        assert not output.exists()


def _stage_build(root: Path) -> Path:
    scripts = root / "scripts"
    scripts.mkdir()
    shutil.copy2(ROOT / "scripts/verify_release_artifact.py", scripts)
    for directory in ("docs", "health", "deltas", "record-evidence", "badges", "samples", "data", "attestations", ".attestations"):
        (root / directory).mkdir()
        (root / directory / "fixture.json").write_text('{"fixture":true}\n')
    (root / "docs/.hidden").write_bytes(b"hidden bytes\n")
    stage = _step(BUILD, "build", "Stage only generated publication inputs")["run"]
    # Populate the explicit root-file list, without allowing the fixture to
    # manufacture a successful verifier or alter the staging implementation.
    copy_line = next(line for line in stage.splitlines() if line.startswith("cp README.md "))
    for name in copy_line.split()[1:-1]:
        (root / name).write_text(f"fixture: {name}\n")
    runner = root / "runner"
    runner.mkdir()
    result = _run(stage, root, RUNNER_TEMP=str(runner), PROMOTION_SOURCE_SHA=SOURCE)
    assert result.returncode == 0, result.stderr
    return runner / "pages-build"


@pytest.mark.parametrize("damage", ["none", "bytes", "missing", "source"])
def test_real_build_inventory_rejects_corruption_missing_bytes_and_wrong_source(
    tmp_path: Path, damage: str,
) -> None:
    build = _stage_build(tmp_path)
    assert not (build / "workspace/attestations").exists()
    assert not (build / "workspace/.attestations").exists()
    assert (build / "workspace/docs/.hidden").read_bytes() == b"hidden bytes\n"
    assert (tmp_path / "attestations/fixture.json").read_text() == '{"fixture":true}\n'
    source = SOURCE
    if damage == "bytes":
        (build / "workspace/docs/.hidden").write_bytes(b"corrupt")
    elif damage == "missing":
        (build / "workspace/docs/.hidden").unlink()
    elif damage == "source":
        source = "c" * 40
    output = tmp_path / "environment"
    result = _run(
        _step(PUBLISH, "deploy", "Verify per-commit build identity and bytes")["run"], tmp_path,
        RUNNER_TEMP=str(build.parent), PROMOTION_SOURCE_SHA=source, GITHUB_ENV=str(output),
    )
    if damage == "none":
        assert result.returncode == 0, result.stderr
        assert output.read_text().strip() == f"VERIFIED_PAGES_BUILD={build}/workspace"
        # The prebuilt branch must copy the verified bytes, not start another
        # generator (the fixture has no generate.sh and no signing key).
        (tmp_path / "docs/obsolete-page.html").write_text("removed by release generation")
        restore = _run(
            _step(PUBLISH, "deploy", "Run release-build generation profile (non-health path)")["run"],
            tmp_path, VERIFIED_PAGES_BUILD=str(build / "workspace"),
        )
        assert restore.returncode == 0, restore.stderr
        assert (tmp_path / "docs/.hidden").read_bytes() == b"hidden bytes\n"
        assert not (tmp_path / "docs/obsolete-page.html").exists()
        assert not (tmp_path / "attestations/.hidden").exists()
    else:
        assert result.returncode != 0
        assert not output.exists(), "Unverified bytes must never enable prebuilt publication"


def test_one_build_identity_reaches_signing_and_download_without_latest_name_lookup() -> None:
    jobs = _workflow(PUBLISH)["jobs"]
    classify, sign, deploy = (jobs[name] for name in ("classify", "sign_health", "deploy"))
    assert classify["outputs"]["build_run_id"] == "${{ steps.build.outputs.run_id }}"
    assert sign["env"]["PROMOTION_BUILT_SHA"] == "${{ needs.classify.outputs.settled_sha }}"
    guard = _step(PUBLISH, "sign_health", "Require settled main before signing")["run"]
    assert 'git merge-base --is-ancestor "$PROMOTION_BUILT_SHA" "$current_sha"' in guard
    assert 'current_sha="$PROMOTION_BUILT_SHA"' in guard
    download = _step(PUBLISH, "deploy", "Download verified per-commit release build")["with"]
    assert download["run-id"] == "${{ needs.classify.outputs.build_run_id }}"
    assert download["name"] == "pages-build-${{ needs.classify.outputs.build_run_id }}-${{ needs.classify.outputs.build_attempt }}"
    assert deploy["env"]["PROMOTION_SOURCE_SHA"] == "${{ needs.sign_health.outputs.settled_sha }}"
    production = _step(PUBLISH, "deploy", "Deploy canonical Cloudflare Pages artifact")["run"]
    assert '--commit-hash="$PROMOTION_SOURCE_SHA"' in production
    assert classify["permissions"]["actions"] == deploy["permissions"]["actions"] == "read"
    preflight = _step(PUBLISH, "classify", "Require available verified build before preparing any append")
    assert "if" not in preflight
    assert preflight["with"]["run-id"] == "${{ steps.build.outputs.run_id }}"
    assert "if" not in _step(PUBLISH, "classify", "Verify build handoff before preparing any append")
    checkout = next(step for step in classify["steps"] if step.get("uses") == "actions/checkout@v4")
    assert checkout["with"]["fetch-depth"] == 0
    assert "filter" not in checkout["with"], "Explicit filter overrides sparse checkout"
    assert "scripts/verify_release_artifact.py" in checkout["with"]["sparse-checkout"]
    # Health-only bypasses derive from everything since production, so a newer
    # health commit cannot bypass an unpublished source change.
    classifier = next(step for step in classify["steps"] if step.get("id") == "classify")
    assert classifier["env"]["BEFORE_SHA"] == "${{ steps.production.outputs.source_sha }}"


def test_dashboard_uses_accepted_signer_plane_when_build_predecessor_has_advanced(tmp_path: Path) -> None:
    root = tmp_path
    runner = root / "runner"
    publication = runner / "sigstore-publication"
    for parent in (root, publication):
        (parent / "attestations/latest").mkdir(parents=True)
        (parent / ".attestations").mkdir()
        (parent / "datapulse.json").write_text("accepted" if parent == publication else "private-build")
        (parent / "attestations/latest/binding.json").write_text("accepted" if parent == publication else "private-build")
    (root / "attestations/private-candidate.json").write_text("must not survive")
    (root / "docs").mkdir()
    (root / "docs/index.html").write_text("private-build")
    (root / "scripts").mkdir()
    # These stubs verify orchestration inputs/order. Generator/binding behavior
    # has its own tests; neither stub can create a candidate or submit an append.
    (root / "scripts/embed_dashboard_data.py").write_text(
        'from pathlib import Path\n'
        'assert Path("attestations/latest/binding.json").read_text() == "accepted"\n'
        'assert not Path("attestations/private-candidate.json").exists()\n'
        'Path("docs/index.html").write_text(Path("datapulse.json").read_text())\n'
    )
    (root / "scripts/verify_release_invariants.sh").write_text(
        'set -Eeuo pipefail\n[[ "$1" == --local ]]\n'
        '[[ "$(cat docs/index.html)" == accepted ]]\n'
    )
    step = _step(PUBLISH, "deploy", "Bind built dashboard to accepted sign-time trust plane")
    assert step["if"] == "needs.sign_health.outputs.health_only != 'true'"
    result = _run(step["run"], root, RUNNER_TEMP=str(runner))
    assert result.returncode == 0, result.stderr
    assert (root / "docs/index.html").read_text() == "accepted"
    names = [step.get("name") for step in _workflow(PUBLISH)["jobs"]["deploy"]["steps"]]
    assert names.index("Download verified optional Sigstore bundle") < names.index(step["name"]) < names.index("Assemble canonical Pages artifact")


def test_signing_bounds_and_served_gates_survive_the_split() -> None:
    workflow = _workflow(PUBLISH)
    assert workflow["env"] == {
        "PROMOTION_SETTLED_QUIET_SECONDS": 300,
        "PROMOTION_SETTLED_MAX_WAIT_SECONDS": 900,
        "APPEND_REQUIRED_CHECK_WORST_OBSERVED_SECONDS": 1185,
        "APPEND_ACCEPTANCE_PATIENCE_SECONDS": 1485,
        "PUBLICATION_CHAIN_MAX_DEPTH": 3,
    }
    jobs = workflow["jobs"]
    assert [jobs[name]["timeout-minutes"] for name in ("classify", "sign_health", "deploy")] == [20, 132, 30]
    sign_steps = jobs["sign_health"]["steps"]
    assert [step["timeout-minutes"] for step in sign_steps if "timeout-minutes" in step] == [32, 40, 51]
    acceptance_step = _step(PUBLISH, "sign_health", "Require authoritative acceptance before signing publication")
    acceptance = acceptance_step["run"]
    for output in ("state", "branch", "head_sha"):
        assert f"steps.append_submission.outputs.{output}" in str(acceptance_step["env"])
    for unchanged in ("timeout -k 5s 3000s bash", "named_timeout()", "refuse_acceptance()", "deterministic-safety-net"):
        assert unchanged in acceptance
    assert "--max-files 18000" in _step(PUBLISH, "deploy", "Keep verifier-reachable attestation history")["run"]
    for gate in ("Verify isolated Pages preview before production promotion", "Verify canonical served surface", "Verify local versus served parity after publication"):
        assert "if" not in _step(PUBLISH, "deploy", gate)
    for path in ROOT.glob(".github/workflows/*.yml"):
        assert "scripts/verify_external.py" not in path.read_text()
