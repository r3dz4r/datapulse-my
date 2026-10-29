"""Regression tests for the active Cloudflare Pages workflow wiring."""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
import yaml

from scripts.classify_change import is_health_only_change

from scripts import gen_attestations as ga
from scripts.tests.test_attestations import fixture_rekor_reference, fixture_root, write

ROOT = Path(__file__).resolve().parents[2]
SYSTEMD_UNIT = ROOT / "deploy/systemd/datapulse-health.service"
CANONICAL_SYSTEMD_UNIT = Path(
    os.environ.get("DOTFILES_DIR", "/home/redza/dotfiles")
) / "system" / "datapulse-health.service"
CANONICAL_PIPELINE = Path(
    os.environ.get("DOTFILES_DIR", "/home/redza/dotfiles")
) / "scripts" / "datapulse-pipeline.sh"
DEPLOY_WORKFLOW = ROOT / ".github/workflows/deploy-cloudflare-pages.yml"
BUILD_WORKFLOW = ROOT / ".github/workflows/publish-publication.yml"
SERVED_VERIFIER = ROOT / "scripts/verify_served_release.sh"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_merge_lane_schedules_are_hourly_and_repository_has_no_subhourly_crons() -> None:
    append_path = ROOT / ".github/workflows/attestation-append-merge.yml"
    append_workflow = yaml.safe_load(_read(append_path))
    triggers = append_workflow.get(True, append_workflow.get("on"))

    assert isinstance(triggers, dict)
    assert triggers["schedule"] == [{"cron": "37 * * * *"}]

    subhourly_crons: list[str] = []
    for workflow_path in (ROOT / ".github/workflows").glob("*.yml"):
        workflow = yaml.safe_load(_read(workflow_path))
        workflow_triggers = workflow.get(True, workflow.get("on"))
        if not isinstance(workflow_triggers, dict):
            continue
        for schedule in workflow_triggers.get("schedule", []):
            cron = schedule.get("cron", "")
            if re.search(r"(?:^|\s)\*/\d+(?:\s|$)", cron):
                subhourly_crons.append(f"{workflow_path.name}: {cron}")

    assert subhourly_crons == []


def _exec_start(unit: str) -> str:
    return unit.split("ExecStart=", 1)[1].split("\nStandardOutput=", 1)[0]


def _github_path_matches(pattern: str, path: str) -> bool:
    """Return whether a whole repository-relative path matches a GitHub glob."""
    expression = ""
    index = 0
    while index < len(pattern):
        if pattern.startswith("**", index):
            expression += ".*"
            index += 2
        elif pattern[index] == "*":
            expression += "[^/]*"
            index += 1
        else:
            expression += re.escape(pattern[index])
            index += 1
    return re.fullmatch(expression, path) is not None


def _build_trigger_matches(changed_paths: list[str]) -> bool:
    """Return whether any changed path matches the build workflow's push allowlist."""
    workflow = yaml.safe_load(_read(BUILD_WORKFLOW))
    patterns = workflow[True]["push"]["paths"]
    return any(
        _github_path_matches(pattern, path)
        for pattern in patterns
        for path in changed_paths
    )


def test_cloudflare_push_trigger_is_code_plane_allowlist() -> None:
    workflow = yaml.safe_load(_read(BUILD_WORKFLOW))
    deploy = yaml.safe_load(_read(DEPLOY_WORKFLOW))

    assert workflow[True]["push"]["branches"] == ["main"]
    assert workflow[True]["push"]["paths"] == [
        "docs/**",
        "scripts/**",
        "mcp/**",
        "functions/**",
        "observation-receipts/**",
        "attestations/**",
        "config/public-surfaces.json",
        ".github/workflows/deploy-cloudflare-pages.yml",
        ".github/workflows/publish-publication.yml",
        "datapulse.json",
        "mcp.json",
        "requirements.txt",
    ]
    assert "push" not in deploy[True]


def test_cloudflare_push_trigger_excludes_health_cycles_and_keeps_code_plane() -> None:
    assert not _build_trigger_matches(["health/latest.json", "health/trends.json"])
    assert _build_trigger_matches(["attestations/chain-index.json"])
    assert _build_trigger_matches(["docs/index.html"])
    assert _build_trigger_matches(["scripts/publish_health_index.py"])
    assert _build_trigger_matches(["functions/health/[[path]].js"])
    assert _build_trigger_matches(["health/latest.json", "docs/index.html"])


def test_cloudflare_push_trigger_deploys_observation_receipt_changes() -> None:
    """Signed observation receipts are assembled into the site, so they must trigger a deploy."""
    patterns = yaml.safe_load(_read(BUILD_WORKFLOW))[True]["push"]["paths"]

    assert "observation-receipts/**" in patterns
    assert _build_trigger_matches(["observation-receipts/chain_head.json"])
    assert _build_trigger_matches(["observation-receipts/days/2026-09-18.json"])


def test_public_surfaces_declares_only_the_servable_observation_receipt_entry_point() -> None:
    """Declare the fetchable receipt head, never a directory-style receipt index."""
    artifacts = json.loads(_read(ROOT / "config/public-surfaces.json"))["artifacts"]

    assert "/observation-receipts/chain_head.json" in artifacts
    assert "/observation-receipts/days/" not in artifacts
    assert not any(
        path.startswith("/observation-receipts/") and path.endswith("/")
        for path in artifacts
    )


def test_llms_owned_blocks_do_not_publish_legacy_or_docs_urls() -> None:
    contents = _read(ROOT / "llms.txt")
    owned_blocks = re.findall(r"(?ms)<!-- BEGIN [^>]+ -->(.*?)<!-- END [^>]+ -->", contents)

    assert owned_blocks
    owned = "\n".join(owned_blocks)
    assert "github.io" not in owned
    assert not re.search(r"https?://[^/]+/docs(?:/|\b)", owned)


def test_systemd_unit_uses_generate_sh_and_preserves_atomic_health_write() -> None:
    unit = _read(SYSTEMD_UNIT)
    exec_start = _exec_start(unit)

    assert "bash scripts/generate.sh health-cycle" in exec_start
    assert "mktemp health/.latest" in unit
    assert 'mv "$$health_tmp" health/latest.json' in unit
    assert "flock -n /tmp/datapulse-health.lock" in unit


def test_systemd_unit_does_not_reintroduce_superseded_generators() -> None:
    exec_start = _exec_start(_read(SYSTEMD_UNIT))

    assert "bash scripts/gen_badges.sh" not in exec_start
    assert "bash scripts/gen_rss.sh" not in exec_start
    assert "bash scripts/gen_readme_summary.sh" not in exec_start
    assert "python3 scripts/gen_changelog.py" not in exec_start


def test_systemd_unit_preserves_scoped_commit() -> None:
    exec_start = _exec_start(_read(SYSTEMD_UNIT))
    expected = (
        "health/ deltas/ record-evidence/ badges/ feed.xml "
        "catalog-snapshot.json changelog.json attestations/ datapulse.json"
    )

    git_add = re.search(r"git add ([^;\n]+)", exec_start)
    assert git_add is not None
    assert git_add.group(1) == expected
    assert "README.md" not in exec_start


def test_source_ci_generates_readme_before_running_source_tests() -> None:
    workflow = yaml.safe_load(_read(ROOT / ".github/workflows/ci.yml"))
    steps = workflow["jobs"]["deterministic-safety-net"]["steps"]
    generate = next(step for step in steps if step.get("name") == "Generate README from canonical inputs")
    tests = next(step for step in steps if step.get("name") == "Run repository-contract and MCP tests")

    assert generate["run"] == "python3 scripts/gen_readme.py"
    assert steps.index(generate) < steps.index(tests)


def test_systemd_unit_emits_lock_skip_telemetry() -> None:
    if not CANONICAL_SYSTEMD_UNIT.exists():
        pytest.skip(f"dotfiles not co-located: {CANONICAL_SYSTEMD_UNIT}")
    unit = _read(CANONICAL_SYSTEMD_UNIT)
    pipeline = _read(CANONICAL_PIPELINE)

    assert "--produce" in unit
    assert re.search(
        r"telemetry\s+lock\s+0\s+skipped\s+'\{\"reason\":\"lock_busy\"\}'",
        pipeline,
    )


def test_cloudflare_workflow_uses_release_build_and_declared_inputs() -> None:
    build = _read(BUILD_WORKFLOW)
    deploy = _read(DEPLOY_WORKFLOW)
    paths_block = build.split("    paths:\n", 1)[1].split("  workflow_dispatch:", 1)[0]

    assert "bash scripts/generate.sh release-build" in build
    assert "bash scripts/generate.sh release-build" not in deploy
    assert "Consume verified release build (non-health path)" in deploy
    assert '"scripts/**"' in paths_block
    assert '"health/**"' not in paths_block
    assert "npx --yes wrangler@3.90.0 pages deploy _site --project-name=datapulse-p4b-preview --branch=main" in deploy
    assert "cloudflare/wrangler-action" not in deploy
    assert "actions/deploy-pages" not in deploy


def test_cloudflare_release_and_proof_steps_consume_verified_inputs_without_private_key() -> None:
    workflow = _read(DEPLOY_WORKFLOW)
    assert "DATAPULSE_ATTESTATION_PRIVATE_KEY_CONTENT" not in workflow
    assert "DATAPULSE_ATTESTATION_PRIVATE_KEY_FILE" not in workflow
    steps = yaml.safe_load(workflow)["jobs"]["deploy"]["steps"]
    consume = next(step for step in steps if step.get("name") == "Consume verified release build (non-health path)")
    proof = next(step for step in steps if step.get("name") == "Verify full release contract (non-health path)")
    assert 'cp -R "$VERIFIED_PAGES_BUILD/." .' in consume["run"]
    assert "verify_release_artifact.py verify" in proof["run"]
    assert "--verify-proof docs/release-verification.md" in proof["run"]


def test_cloudflare_workflow_permissions_and_concurrency_are_not_broadened() -> None:
    workflow = yaml.safe_load(_read(DEPLOY_WORKFLOW))
    concurrency = workflow["concurrency"]

    assert workflow["permissions"] == {"contents": "read"}
    # New deploy candidates replace only pending deploys, never an in-flight run.
    assert concurrency == {
        "group": "cloudflare-pages-deploy",
        "cancel-in-progress": False,
        "queue": "single",
    }
    assert "concurrency" not in workflow["jobs"]["sign_health"]
    assert "concurrency" not in workflow["jobs"]["deploy"]
    assert "[skip deploy]" not in _read(DEPLOY_WORKFLOW)


def test_sigstore_oidc_is_isolated_to_a_least_privilege_job() -> None:
    workflow = yaml.safe_load(_read(DEPLOY_WORKFLOW))
    build = yaml.safe_load(_read(BUILD_WORKFLOW))
    signing = workflow["jobs"]["sign_health"]

    assert build["permissions"] == {"contents": "read"}
    assert workflow["permissions"] == {"contents": "read"}
    assert signing["permissions"] == {"contents": "read", "id-token": "write"}
    assert workflow["jobs"]["deploy"]["permissions"] == {"contents": "read", "actions": "read"}
    assert workflow["jobs"]["classify"]["permissions"] == {"contents": "read", "actions": "read"}
    assert workflow["jobs"]["deploy"]["needs"] == ["classify", "sign_health"]


def test_sigstore_uses_pinned_cosign_dsse_semantics_and_explicit_identity() -> None:
    workflow = _read(DEPLOY_WORKFLOW)
    signing = workflow.split("  sign_health:\n", 1)[1].split("\n  deploy:\n", 1)[0]

    assert "sigstore/cosign-installer@faadad0cce49287aee09b3a48701e75088a2c6ad" in signing
    assert "cosign-release: v3.1.3" in signing
    assert "python3 scripts/gen_sigstore_bundle.py" in signing
    assert "cosign attest-blob" in signing
    assert "--statement" in signing
    assert "cosign sign-blob" not in signing
    assert "python3 scripts/verify_sigstore_bundle.py" in signing
    assert "--certificate-identity \"$SIGSTORE_IDENTITY\"" in signing
    assert "--certificate-oidc-issuer \"$SIGSTORE_ISSUER\"" in signing
    assert (
        "https://github.com/r3dz4r/datapulse-my/.github/workflows/"
        "deploy-cloudflare-pages.yml@refs/heads/main"
    ) in signing
    assert "https://token.actions.githubusercontent.com" in signing


def test_sigstore_signer_down_is_explicit_and_partial_outputs_are_cleaned_up() -> None:
    parsed = yaml.safe_load(_read(DEPLOY_WORKFLOW))
    steps = parsed["jobs"]["sign_health"]["steps"]
    install = next(step for step in steps if step.get("id") == "install_cosign")
    sign = next(step for step in steps if step.get("id") == "sign_current_health")
    upload = next(step for step in steps if step.get("id") == "upload_sigstore")
    attestation = next(step for step in steps if step.get("id") == "attestation_result")
    result = next(step for step in steps if step.get("id") == "sigstore_result")

    assert install["continue-on-error"] is True
    assert "continue-on-error" not in sign
    assert "continue-on-error" not in upload
    assert sign["if"] == (
        "steps.install_cosign.outcome == 'success' && "
        "steps.select_accepted_health.outputs.state == 'accepted'"
    )
    assert ".health.latest.sigstore.json.tmp" in sign["run"]
    assert "state=signer_down" in sign["run"]
    assert "verify_sigstore_bundle.py" in sign["run"]
    assert sign["run"].index("verify_sigstore_bundle.py") < sign["run"].index(
        'mv "$bundle_tmp" "$publication/health.latest.sigstore.json"'
    )
    assert upload["if"] == "steps.select_accepted_health.outputs.state == 'accepted'"
    assert parsed["jobs"]["sign_health"]["outputs"]["attestation_state"] == (
        "${{ steps.attestation_result.outputs.state }}"
    )
    assert attestation["if"] == "always() && steps.select_accepted_health.outputs.state == 'accepted'"
    assert "state=signer_down" in attestation["run"]
    assert "state=signed" in attestation["run"]
    assert "Signer output, verification, or publication was incomplete." in attestation["run"]
    assert result["if"] == "always() && steps.select_accepted_health.outputs.state == 'accepted'"
    assert "rm -f \"$RUNNER_TEMP/sigstore-publication/.health.latest.sigstore.json.tmp\"" in result["run"]
    assert "signed=false" in result["run"]
    assert "signed=true" in result["run"]


def test_per_dataset_receipts_are_generated_signed_and_staged_for_every_deployment_profile() -> None:
    parsed = yaml.safe_load(_read(DEPLOY_WORKFLOW))
    steps = parsed["jobs"]["sign_health"]["steps"]
    generate = next(step for step in steps if step.get("name") == "Generate per-dataset evidence statements")
    sign = next(step for step in steps if step.get("id") == "sign_per_dataset")
    result = next(step for step in steps if step.get("id") == "per_receipt_result")
    assemble = next(
        step for step in parsed["jobs"]["deploy"]["steps"]
        if step.get("name") == "Assemble canonical Pages artifact"
    )

    assert generate["if"] == "steps.select_accepted_health.outputs.state == 'accepted'"
    assert sign["if"] == (
        "steps.sign_current_health.outputs.state == 'signed' && "
        "steps.select_accepted_health.outputs.state == 'accepted'"
    )
    assert "python3 scripts/gen_per_dataset_receipt.py" in generate["run"]
    assert "python3 scripts/sign_per_dataset_receipts.py" in sign["run"]
    assert "python3 scripts/verify_per_dataset_receipt.py" in sign["run"]
    assert "--certificate-identity \"$SIGSTORE_IDENTITY\"" in sign["run"]
    assert "continue-on-error" not in sign
    assert "mkdir -p \"$publication/data\"" in sign["run"]
    assert result["if"] == "always() && steps.select_accepted_health.outputs.state == 'accepted'"
    assert "steps.sign_current_health.outputs.state" in result["run"]
    assert "steps.sign_per_dataset.outcome" in result["run"]
    assert "rm -rf \"$RUNNER_TEMP/sigstore-publication/data\"" in result["run"]
    assert "receipts_signed" in parsed["jobs"]["sign_health"]["outputs"]
    for suffix in ("evidence.json", "statement.json", "sigstore.json"):
        assert f'cp "$RUNNER_TEMP/sigstore-publication/data/"*.receipt.{suffix} _site/data/' in assemble["run"]


def test_attestation_state_fails_closed_for_full_releases_and_keeps_accepted_report() -> None:
    parsed = yaml.safe_load(_read(DEPLOY_WORKFLOW))
    steps = parsed["jobs"]["deploy"]["steps"]
    full_release_gate = next(step for step in steps if step.get("name") == "Require signed attestation for full release")
    assert full_release_gate["if"] == (
        "needs.sign_health.outputs.health_only != 'true' && "
        "needs.sign_health.outputs.attestation_state != 'signed'"
    )
    assert "Full releases require attestation_state=signed" in full_release_gate["run"]
    assert "exit 1" in full_release_gate["run"]
    overlay = next(step for step in steps if step.get("name") == "Bind built dashboard to accepted sign-time trust plane")
    assert "if" not in overlay
    assert 'cp "$publication/health/latest.json" health/latest.json' in overlay["run"]
    assert "python3 scripts/verify_attestation_binding.py --root ." in overlay["run"]
    assert "Preserve served attestation plane" not in _read(DEPLOY_WORKFLOW)


def test_cloudflare_publishes_only_a_current_verified_optional_bundle() -> None:
    workflow = _read(DEPLOY_WORKFLOW)
    assembly = workflow.split("      - name: Assemble canonical Pages artifact\n", 1)[1].split(
        "      - name: Deploy canonical Cloudflare Pages artifact\n", 1
    )[0]
    served = _read(SERVED_VERIFIER)

    assert "needs.sign_health.outputs.signed == 'true'" in workflow
    assert "actions/download-artifact@d3f86a106a0bac45b974a628896c90dbdf5c8093" in workflow
    assert 'mkdir -p _site/signatures' in assembly
    assert 'cp "$RUNNER_TEMP/sigstore-publication/health.latest.sigstore.json" _site/signatures/' in assembly
    assert "signatures/health.latest.sigstore.json" in served
    assert "signatures/datapulse.json" in served
    assert 'fetch "signed manifest snapshot" "$base_url/signatures/datapulse.json"' in served
    assert '--manifest "$smoke_dir/signatures/datapulse.json"' in served
    assert '--manifest "$publication_dir/datapulse.json"' not in served
    assert "cmp -s" in served
    assert "python3 scripts/verify_sigstore_bundle.py" in served
    assert "stale Sigstore bundle is still served" in served


def test_generate_sh_release_profile_matches_cloudflare_workflow() -> None:
    listed = subprocess.run(
        ["./scripts/generate.sh", "release-build", "--list"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    assert "Profile: release-build" in listed.stdout
    assert "bash scripts/generate.sh release-build" in _read(BUILD_WORKFLOW)
    assert "bash scripts/generate.sh release-build" not in _read(DEPLOY_WORKFLOW)


def test_canonical_pipeline_stages_and_validates_record_evidence() -> None:
    if not CANONICAL_PIPELINE.exists():
        pytest.skip(f"dotfiles not co-located: {CANONICAL_PIPELINE}")
    pipeline = _read(CANONICAL_PIPELINE)

    assert "record-evidence" in pipeline.split("ARTIFACT_PATHS=", 1)[1].split(")", 1)[0]
    assert re.search(r"(?:\$\{PYTHON_BIN\}|python3)\s+scripts/gen_record_evidence\.py", pipeline)
    assert "validate_record_evidence(envelope, full=False)" in pipeline


def _accepted_selection_script() -> str:
    steps = yaml.safe_load(_read(DEPLOY_WORKFLOW))["jobs"]["sign_health"]["steps"]
    return next(step["run"] for step in steps if step.get("id") == "select_accepted_health")


def _select_plane(tmp_path: Path, source_root: Path, *, label: str) -> tuple[subprocess.CompletedProcess[str], Path]:
    """Run the actual selection step against committed, signed fixture evidence."""
    checkout = tmp_path / f"checkout-{label}"
    shutil.copytree(source_root, checkout)
    subprocess.run(["git", "init", "-b", "main"], cwd=checkout, check=True, capture_output=True)
    for key, value in (("user.name", "Test"), ("user.email", "test@example.test")):
        subprocess.run(["git", "config", key, value], cwd=checkout, check=True)
    subprocess.run(["git", "add", "datapulse.json", "docs", "health", "attestations", ".attestations"], cwd=checkout, check=True)
    subprocess.run(["git", "commit", "-m", "accepted evidence"], cwd=checkout, check=True, capture_output=True)
    revision = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=checkout, text=True).strip()
    (checkout / "scripts").symlink_to(ROOT / "scripts", target_is_directory=True)
    runner = tmp_path / f"runner-{label}"
    runner.mkdir()
    environment = os.environ | {
        "PATH": f"{Path(sys.executable).parent}:{os.environ['PATH']}",
        "RUNNER_TEMP": str(runner), "PROMOTION_SOURCE_SHA": revision,
        "GITHUB_OUTPUT": str(runner / "output"), "GITHUB_STEP_SUMMARY": str(runner / "summary"),
    }
    completed = subprocess.run(["bash", "-c", _accepted_selection_script()], cwd=checkout, env=environment,
                               capture_output=True, text=True, check=False, timeout=30)
    return completed, runner / "sigstore-publication"


@pytest.mark.parametrize("append_revision", [False, True])
def test_cloudflare_fast_path_selects_accepted_plane_without_served_fallback(tmp_path: Path, append_revision: bool) -> None:
    source, key = fixture_root(tmp_path / "accepted")
    now = datetime.now(timezone.utc).replace(microsecond=0)
    day = now.date().isoformat()
    health = json.loads((source / "health/latest.json").read_bytes())
    health["checked_at"] = now.isoformat().replace("+00:00", "Z")
    health["datasets"][0]["last_checked"] = health["checked_at"]
    write(source / "health/latest.json", health)
    reference = fixture_rekor_reference(source, f"rekor/{day}")
    ga.generate(source, key, now, reference)
    if append_revision:
        manifest = json.loads((source / "datapulse.json").read_bytes())
        manifest["datasets"][0]["url"] = "https://example.test/revised"
        write(source / "datapulse.json", manifest)
        ga.generate(source, key, now, reference)
    result, selected = _select_plane(tmp_path, source, label="valid")
    assert result.returncode == 0, result.stdout + result.stderr
    for path in ("health/latest.json", "attestations/latest/binding.json", ".attestations/chain_head.json"):
        assert (selected / path).read_bytes() == (source / path).read_bytes()
    assert "curl" not in _accepted_selection_script()


def test_cloudflare_fast_path_selects_correction_and_refuses_corruption(tmp_path: Path) -> None:
    source, key = fixture_root(tmp_path / "accepted")
    now = datetime.now(timezone.utc).replace(microsecond=0)
    day = now.date().isoformat()
    health = json.loads((source / "health/latest.json").read_bytes())
    health["checked_at"] = (now - timedelta(seconds=2)).isoformat().replace("+00:00", "Z")
    health["datasets"][0]["last_checked"] = health["checked_at"]
    write(source / "health/latest.json", health)
    reference = fixture_rekor_reference(source, f"rekor/{day}")
    ga.generate(source, key, now - timedelta(seconds=2), reference)
    health["datasets"][0]["status"] = "stale"
    write(source / "health/latest.json", health)
    ga.generate(source, key, now - timedelta(seconds=1),
                fixture_rekor_reference(source, f"rekor/{day}/correction"))
    result, selected = _select_plane(tmp_path, source, label="corrected")
    assert result.returncode == 0, result.stdout + result.stderr
    index = json.loads((source / "attestations/latest/index.json").read_bytes())
    revision = Path(index["chain_head_ref"]).parent
    assert "/revisions/" in index["chain_head_ref"]
    assert (selected / revision / "health.json.gz").read_bytes() == (source / revision / "health.json.gz").read_bytes()
    (source / revision / "health.json.gz").write_bytes(b"{}")
    refused, _ = _select_plane(tmp_path, source, label="corrupt")
    assert refused.returncode != 0
    assert "REFUSED" in refused.stdout + refused.stderr


def test_cloudflare_fast_path_keeps_classifier_scoped_degradation() -> None:
    workflow = _read(DEPLOY_WORKFLOW)
    assert "signer_down is permitted only for classifier-scoped health-only publication" in workflow
    assert "Health-only publication retains the selected accepted Ed25519 report" in workflow
    assert "preserved-attestations" not in workflow


def test_cloudflare_fast_path_requires_verified_binding_before_assembly() -> None:
    workflow = _read(DEPLOY_WORKFLOW)
    bind = workflow.index("Bind built dashboard to accepted sign-time trust plane")
    assert bind < workflow.index("Assemble canonical Pages artifact")
    run = next(step["run"] for step in yaml.safe_load(workflow)["jobs"]["deploy"]["steps"]
               if step.get("name") == "Bind built dashboard to accepted sign-time trust plane")
    assert run.index('cp -R "$publication/attestations"') < run.index("verify_attestation_binding.py")
    assert run.index("verify_attestation_binding.py") < run.index("embed_dashboard_data.py")


def test_cloudflare_fast_path_overwrites_checkout_attestations_before_broad_copies() -> None:
    workflow = _read(DEPLOY_WORKFLOW)
    assert "cp -R health deltas record-evidence badges samples data _site/" in workflow
    bind = workflow.index("Bind built dashboard to accepted sign-time trust plane")
    assert bind < workflow.index("Assemble canonical Pages artifact")
    assert 'cp -R "$publication/attestations" "$publication/.attestations" .' in workflow
    assert 'cp -R "$RUNNER_TEMP/sigstore-publication/attestations" _site/' in workflow


def test_cloudflare_fast_path_overwrites_checkout_release_proof_after_docs_copy() -> None:
    workflow = _read(DEPLOY_WORKFLOW)
    proof_step = workflow.split("      - name: Preserve served release proof (health-only path)\n", 1)[1].split("      - name: Download accepted report and optional Sigstore bundle\n", 1)[0]
    assembly = workflow.split("      - name: Assemble canonical Pages artifact\n", 1)[1].split("      - name: Deploy canonical Cloudflare Pages artifact\n", 1)[0]

    assert '"${website_origin}/release-verification.md" --output "$preserved_proof"' in proof_step
    assert "cp -R docs/. _site/" in assembly
    assert 'cp "$RUNNER_TEMP/preserved-release-proof/release-verification.md" _site/release-verification.md' in assembly


def test_cloudflare_health_only_classifier_is_scoped_to_pipeline_outputs() -> None:
    workflow = _read(DEPLOY_WORKFLOW)
    classifier = workflow.split("      - id: classify\n", 1)[1].split("\n  sign_health:", 1)[0]

    assert "python3 scripts/classify_change.py" in classifier
    assert "python3 - <<'PY'" not in classifier
    assert "HEALTH_CYCLE_CHANGED_PATHS" not in classifier

    assert is_health_only_change(
        (
            "health/latest.json",
            "health/trends.json",
            "record-evidence/dosm/latest.json",
            "attestations/latest/binding.json",
            ".attestations/latest/2026-09-08.json",
            ".attestations/chain_head.json",
            "deltas/2026-09-08.json",
            "catalog-snapshot.json",
        )
    )
    for rejected_path in (
        "health/../latest.json",
        "health/unrelated.json",
        "record-evidence/dosm/archive.json",
        "attestations/latest/unrelated.json",
        ".attestations/latest/../../chain_head.json",
        "deltas/2026-09-08.txt",
        "scripts/embed_dashboard_data.py",
    ):
        assert not is_health_only_change(("health/latest.json", rejected_path))


def test_health_and_source_candidates_share_the_newest_wins_deploy_lane() -> None:
    workflow = yaml.safe_load(_read(DEPLOY_WORKFLOW))

    # One pending deploy can be replaced without canceling an in-flight promotion.
    assert workflow["concurrency"] == {
        "group": "cloudflare-pages-deploy",
        "cancel-in-progress": False,
        "queue": "single",
    }
    for job_name in ("classify", "sign_health", "deploy"):
        assert "concurrency" not in workflow["jobs"][job_name]


def test_daily_attestation_queues_in_a_separate_never_evict_lane() -> None:
    workflow = yaml.safe_load(_read(ROOT / ".github/workflows/datapulse-attest-daily.yml"))
    deploy = yaml.safe_load(_read(DEPLOY_WORKFLOW))

    # Frequent deploy arrivals must not evict a pending daily append producer.
    assert workflow["concurrency"] == {
        "group": "cloudflare-pages-production",
        "cancel-in-progress": False,
        "queue": "max",
    }
    assert workflow["concurrency"]["group"].casefold() != deploy["concurrency"]["group"].casefold()


def test_ci_and_release_please_delegate_health_path_decisions_to_shared_classifier() -> None:
    ci = _read(ROOT / ".github/workflows/ci.yml")
    release_please = _read(ROOT / ".github/workflows/release-please.yml")

    for workflow in (ci, release_please):
        assert "python3 scripts/classify_change.py" in workflow
        assert "git diff --name-only" in workflow
    assert "health-integrity:" in ci
    assert "needs.classify.outputs.health_only == 'true'" in ci
    assert "if: needs.classify.outputs.health_only != 'true'" in release_please


def test_cloudflare_full_release_keeps_fresh_cryptographic_verification() -> None:
    workflow = _read(DEPLOY_WORKFLOW)
    release_step = workflow.split("      - name: Verify full release contract (non-health path)\n", 1)[1].split("      - name: Preserve served release proof (health-only path)\n", 1)[0]

    assert "python3 scripts/verify_release_reproducible.py" in release_step
    assert "--verify-proof docs/release-verification.md" in release_step
    assert "verify_release_artifact.py verify" in release_step
    assert "bash scripts/verify_release_invariants.sh --local" in _read(DEPLOY_WORKFLOW)


def test_cloudflare_workflow_retains_dynamic_public_artifact_contracts() -> None:
    build = _read(BUILD_WORKFLOW)
    paths_block = build.split("    paths:\n", 1)[1].split("  workflow_dispatch:", 1)[0]

    assert '"health/**"' not in paths_block
    assert '"scripts/**"' in paths_block
    served = _read(SERVED_VERIFIER)
    assert 'fetch "dataset register" "$base_url/"' in served
    assert 'fetch_alias dashboard "$base_url/dashboard"' in served
    assert 'fetch "health snapshot" "$base_url/health/latest.json"' in served
    assert 'for kind in trends drift reconciliation' in served
    assert '.tools | type == "array" and length > 0' in served
    assert '.inputSchema | type == "object"' in served
    assert "<!-- BEGIN mcp-tools -->" in served
    assert "<!-- END mcp-tools -->" in served


def test_cloudflare_served_fetches_remain_bounded_and_https_only() -> None:
    workflow = _read(DEPLOY_WORKFLOW)
    verify_step = _read(SERVED_VERIFIER)

    assert "fetch() {" in verify_step
    for flag in ("--proto '=https'", "--retry 3", "--retry-delay 5", "--retry-all-errors", "--connect-timeout 10"):
        assert flag in verify_step
    assert '--max-time "$fetch_max_time"' in verify_step
    fetch_max_time_default = re.search(
        r'^fetch_max_time="\$\{FETCH_MAX_TIME:-([0-9]+)\}"$',
        verify_step,
        re.MULTILINE,
    )
    assert fetch_max_time_default is not None
    # A literal that a future edit can bump arbitrarily is weaker than parsing and bounding the default.
    assert 30 <= int(fetch_max_time_default.group(1)) <= 300


def test_ci_jsonschema_and_cryptography_installs_use_matching_pins() -> None:
    ci = _read(ROOT / ".github/workflows/ci.yml")
    dependency_installs = [
        line
        for line in ci.splitlines()
        if "pip install" in line and ("jsonschema" in line or "cryptography" in line)
    ]

    assert len(dependency_installs) == 2
    assert all(
        re.search(
            r"pip install jsonschema==4\.25\.0 cryptography==50\.0\.0(?:\s|$)",
            line,
        )
        for line in dependency_installs
    )


def _append_workflow_jobs() -> dict:
    workflow = yaml.safe_load(_read(ROOT / ".github/workflows/attestation-append-merge.yml"))
    return workflow["jobs"]


def _run_append_policy_check(tmp_path: Path, ref: str, *, api_failure: bool = False, policy_drift: bool = False) -> subprocess.CompletedProcess[str]:
    jobs = _append_workflow_jobs()
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    curl = fake_bin / "curl"
    curl.write_text(
        "#!/usr/bin/env bash\n"
        "if [[ \"${MOCK_API_FAILURE:-false}\" == true ]]; then\n"
        "  echo 'Resource not accessible by integration' >&2\n"
        "  exit 1\n"
        "fi\n"
        "if [[ \"$*\" == *deployment-branch-policies* ]]; then\n"
        "  printf '%s\\n' \"$MOCK_POLICIES_JSON\"\n"
        "else\n"
        "  printf '%s\\n' \"$MOCK_ENVIRONMENT_JSON\"\n"
        "fi\n",
        encoding="utf-8",
    )
    curl.chmod(0o755)
    environment = os.environ.copy()
    environment.update(
        PATH=f"{fake_bin}:{environment['PATH']}",
        GH_REPO="r3dz4r/datapulse-my",
        GITHUB_REF_NAME=ref,
        GITHUB_OUTPUT=str(tmp_path / "output"),
        MOCK_API_FAILURE=str(api_failure).lower(),
        MOCK_ENVIRONMENT_JSON=json.dumps({
            "deployment_branch_policy": {"protected_branches": False, "custom_branch_policies": True},
        }),
        MOCK_POLICIES_JSON=json.dumps({
            "total_count": 3 if policy_drift else 2,
            "branch_policies": [{"name": "health-automation"}, {"name": "main"}],
        }),
    )
    return subprocess.run(
        ["bash", "-c", jobs["check_production_ref"]["steps"][0]["run"]],
        cwd=ROOT,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )


def test_append_branch_policy_refusal_is_a_clean_decision(tmp_path: Path) -> None:
    jobs = _append_workflow_jobs()
    merge = jobs["merge"]
    assert merge["needs"] == "check_production_ref"
    assert "needs.check_production_ref.outputs.admitted == 'true'" in merge["if"]
    assert "head_repository.full_name == github.repository" in merge["if"]
    assert merge["environment"] == "production"
    assert "continue-on-error" not in _read(ROOT / ".github/workflows/attestation-append-merge.yml")

    result = _run_append_policy_check(tmp_path, "attestation/append-c34eda8c")
    assert result.returncode == 0, result.stderr
    assert 'Branch "attestation/append-c34eda8c" is not allowed to deploy to production due to environment protection rules.' in result.stdout
    assert (tmp_path / "output").read_text(encoding="utf-8") == "admitted=false\n"


@pytest.mark.parametrize("api_failure, policy_drift", [(True, False), (False, True)])
def test_append_policy_check_fails_on_unrelated_refusal_or_drift(tmp_path: Path, api_failure: bool, policy_drift: bool) -> None:
    result = _run_append_policy_check(tmp_path, "attestation/append-c34eda8c", api_failure=api_failure, policy_drift=policy_drift)
    assert result.returncode != 0
    assert not (tmp_path / "output").exists()
    if api_failure:
        assert "Resource not accessible by integration" in result.stderr
    else:
        assert "Production policy changed" in result.stdout


def test_append_admitted_ref_reaches_protected_job(tmp_path: Path) -> None:
    result = _run_append_policy_check(tmp_path, "main")
    assert result.returncode == 0, result.stderr
    assert (tmp_path / "output").read_text(encoding="utf-8") == "admitted=true\n"


def test_append_siblings_close_only_after_merge_and_preserve_branches() -> None:
    workflow = yaml.safe_load(_read(ROOT / ".github/workflows/attestation-append-merge.yml"))
    steps = workflow["jobs"]["merge"]["steps"]
    arm = next(step for step in steps if step.get("name") == "Enable auto-merge")
    close = next(step for step in steps if step.get("name") == "Close same-day superseded append pull requests")

    assert steps.index(arm) < steps.index(close)
    assert close["if"] == "steps.candidate.outputs.number != ''"
    assert '[[ "$state" == "MERGED" ]]' in close["run"]
    assert "select_superseded_siblings" in close["run"]
    assert "gh pr comment" in close["run"] and "gh pr close" in close["run"]
    assert "The branch is kept as evidence." in close["run"]
    assert "::warning" in close["run"]


@pytest.mark.parametrize(
    "merge_error, recover, expected_exit, expected_attempts",
    [
        ("Pull request is in unstable status (enablePullRequestAutoMerge)", True, 0, 2),
        ("Permission denied (enablePullRequestAutoMerge)", False, 1, 1),
    ],
)
def test_append_arm_retries_only_recognized_refusal(
    tmp_path: Path, merge_error: str, recover: bool, expected_exit: int, expected_attempts: int,
) -> None:
    merge = _append_workflow_jobs()["merge"]
    assert merge["timeout-minutes"] == 30
    script = next(step for step in merge["steps"] if step.get("name") == "Enable auto-merge")["run"]
    attempts = re.search(r"ARM_MAX_ATTEMPTS:-([0-9]+)", script)
    seconds = re.search(r"ARM_RETRY_SECONDS:-([0-9]+)", script)
    assert attempts is not None and seconds is not None
    retry_budget = (int(attempts.group(1)) - 1) * int(seconds.group(1))
    assert retry_budget > 945
    assert merge["timeout-minutes"] * 60 - retry_budget >= 300
    expression = 'number="${{ steps.candidate.outputs.number }}"'
    assert expression in script
    script = script.replace(expression, 'number="42"')
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    gh = fake_bin / "gh"
    gh.write_text(
        "#!/usr/bin/env bash\n"
        "if [[ \"$1 $2\" == 'pr view' ]]; then\n"
        "  echo false\n"
        "  exit 0\n"
        "fi\n"
        "if [[ \"$1 $2\" == 'pr merge' ]]; then\n"
        "  count=0\n"
        "  [[ ! -f \"$MOCK_COUNT_FILE\" ]] || count=$(cat \"$MOCK_COUNT_FILE\")\n"
        "  count=$((count + 1))\n"
        "  echo \"$count\" > \"$MOCK_COUNT_FILE\"\n"
        "  if [[ \"$MOCK_RECOVER\" == true && $count -eq 2 ]]; then\n"
        "    exit 0\n"
        "  fi\n"
        "  echo \"$MOCK_MERGE_ERROR\" >&2\n"
        "  exit 1\n"
        "fi\n"
        "exit 99\n",
        encoding="utf-8",
    )
    gh.chmod(0o755)
    environment = os.environ.copy()
    environment.update(
        PATH=f"{fake_bin}:{environment['PATH']}",
        ARM_MAX_ATTEMPTS="3",
        ARM_RETRY_SECONDS="0",
        MOCK_COUNT_FILE=str(tmp_path / "attempts"),
        MOCK_MERGE_ERROR=merge_error,
        MOCK_RECOVER=str(recover).lower(),
    )
    result = subprocess.run(["bash", "-c", script], cwd=ROOT, env=environment, capture_output=True, text=True, check=False)
    assert result.returncode == expected_exit, result.stdout + result.stderr
    assert (tmp_path / "attempts").read_text(encoding="utf-8").strip() == str(expected_attempts)
