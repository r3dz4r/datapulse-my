"""Regression tests for the active Cloudflare Pages workflow wiring."""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
import yaml

from scripts import gen_attestations as ga
from scripts.tests.test_attestations import fixture_rekor_reference, fixture_root, write
from scripts.verify_attestation_binding import verify_contract

ROOT = Path(__file__).resolve().parents[2]
SYSTEMD_UNIT = ROOT / "deploy/systemd/datapulse-health.service"
CANONICAL_SYSTEMD_UNIT = Path(
    os.environ.get("DOTFILES_DIR", "/home/redza/dotfiles")
) / "system" / "datapulse-health.service"
CANONICAL_PIPELINE = Path(
    os.environ.get("DOTFILES_DIR", "/home/redza/dotfiles")
) / "scripts" / "datapulse-pipeline.sh"
DEPLOY_WORKFLOW = ROOT / ".github/workflows/deploy-cloudflare-pages.yml"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _exec_start(unit: str) -> str:
    return unit.split("ExecStart=", 1)[1].split("\nStandardOutput=", 1)[0]


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
        "health/ deltas/ record-evidence/ badges/ feed.xml README.md "
        "catalog-snapshot.json changelog.json attestations/ datapulse.json"
    )

    git_add = re.search(r"git add ([^;\n]+)", exec_start)
    assert git_add is not None
    assert git_add.group(1) == expected


def test_systemd_unit_emits_lock_skip_telemetry() -> None:
    if not CANONICAL_SYSTEMD_UNIT.exists():
        pytest.skip(f"dotfiles not co-located: {CANONICAL_SYSTEMD_UNIT}")
    unit = _read(CANONICAL_SYSTEMD_UNIT)
    assert "--status skipped" in unit
    assert "lock_busy" in unit


def test_cloudflare_workflow_uses_release_build_and_declared_inputs() -> None:
    workflow = _read(DEPLOY_WORKFLOW)
    paths_block = workflow.split("    paths:\n", 1)[1].split("  workflow_dispatch:", 1)[0]

    assert "bash scripts/generate.sh release-build" in workflow
    assert '"scripts/**"' in paths_block
    assert '"health/**"' in paths_block
    assert "cloudflare/wrangler-action@v3" in workflow
    assert "actions/deploy-pages" not in workflow


def test_cloudflare_release_and_proof_steps_keep_protected_attestation_key_setup() -> None:
    workflow = _read(DEPLOY_WORKFLOW)
    setup_lines = (
        'DATAPULSE_ATTESTATION_PRIVATE_KEY_CONTENT: ${{ secrets.DATAPULSE_ATTESTATION_PRIVATE_KEY_FILE }}',
        'echo "$DATAPULSE_ATTESTATION_PRIVATE_KEY_CONTENT" > /tmp/datapulse-attestation-key.json',
        "chmod 600 /tmp/datapulse-attestation-key.json",
        "export DATAPULSE_ATTESTATION_PRIVATE_KEY_FILE=/tmp/datapulse-attestation-key.json",
    )
    release_step = workflow.split("      - name: Run release-build generation profile (non-health path)\n", 1)[1].split("      - name: Verify full release contract (non-health path)\n", 1)[0]
    proof_step = workflow.split("      - name: Verify full release contract (non-health path)\n", 1)[1].split("      - name: Preserve served release proof (health-only path)\n", 1)[0]

    for line in setup_lines:
        assert line in release_step
        assert line in proof_step
    assert "--verify-proof docs/release-verification.md" in proof_step


def test_cloudflare_workflow_permissions_and_concurrency_are_not_broadened() -> None:
    workflow = yaml.safe_load(_read(DEPLOY_WORKFLOW))
    concurrency = workflow["concurrency"]

    assert workflow["permissions"] == {"contents": "read"}
    assert "cloudflare-pages-health" in concurrency["group"]
    assert "cloudflare-pages-release" in concurrency["group"]
    assert "[skip deploy]" in concurrency["cancel-in-progress"]


def test_sigstore_oidc_is_isolated_to_a_least_privilege_job() -> None:
    workflow = yaml.safe_load(_read(DEPLOY_WORKFLOW))
    signing = workflow["jobs"]["sign_health"]

    assert workflow["permissions"] == {"contents": "read"}
    assert signing["permissions"] == {"contents": "read", "id-token": "write"}
    assert "permissions" not in workflow["jobs"]["deploy"]
    assert "permissions" not in workflow["jobs"]["classify"]
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


def test_sigstore_failure_is_non_blocking_and_cannot_publish_partial_output() -> None:
    parsed = yaml.safe_load(_read(DEPLOY_WORKFLOW))
    steps = parsed["jobs"]["sign_health"]["steps"]
    install = next(step for step in steps if step.get("id") == "install_cosign")
    sign = next(step for step in steps if step.get("id") == "sign_current_health")
    upload = next(step for step in steps if step.get("id") == "upload_sigstore")
    result = next(step for step in steps if step.get("id") == "sigstore_result")

    assert install["continue-on-error"] is True
    assert sign["continue-on-error"] is True
    assert upload["continue-on-error"] is True
    assert ".health.latest.sigstore.json.tmp" in sign["run"]
    assert "verify_sigstore_bundle.py" in sign["run"]
    assert sign["run"].index("verify_sigstore_bundle.py") < sign["run"].index(
        'mv "$bundle_tmp" "$publication/health.latest.sigstore.json"'
    )
    assert result["if"] == "always()"
    assert "::warning title=Sigstore health signing unavailable" in result["run"]
    assert "signed=false" in result["run"]
    assert "signed=true" in result["run"]


def test_per_dataset_receipts_are_generated_signed_and_staged_only_for_releases() -> None:
    workflow = _read(DEPLOY_WORKFLOW)
    signing = workflow.split("  sign_health:\n", 1)[1].split("\n  deploy:\n", 1)[0]
    deploy = workflow.split("  deploy:\n", 1)[1]

    assert "Generate per-dataset evidence statements" in signing
    assert "Sign per-dataset evidence statements" in signing
    assert "python3 scripts/gen_per_dataset_receipt.py" in signing
    assert "python3 scripts/sign_per_dataset_receipts.py" in signing
    assert "python3 scripts/verify_per_dataset_receipt.py" in signing
    assert "--certificate-identity \"$SIGSTORE_IDENTITY\"" in signing
    assert "needs.classify.outputs.health_only != 'true'" in signing
    assert "continue-on-error: true" in signing
    assert "receipts_signed" in signing
    assert "Generate per-dataset evidence statements (release artifact)" in deploy
    assert "cp \"$RUNNER_TEMP/sigstore-publication/data/\"*.receipt.sigstore.json _site/data/" in deploy


def test_cloudflare_publishes_only_a_current_verified_optional_bundle() -> None:
    workflow = _read(DEPLOY_WORKFLOW)
    assembly = workflow.split("      - name: Assemble canonical Pages artifact\n", 1)[1].split(
        "      - name: Deploy canonical Cloudflare Pages artifact\n", 1
    )[0]
    served = workflow.split("      - name: Verify canonical served surface\n", 1)[1]

    assert "needs.sign_health.outputs.signed == 'true'" in workflow
    assert "actions/download-artifact@d3f86a106a0bac45b974a628896c90dbdf5c8093" in workflow
    assert 'mkdir -p _site/signatures' in assembly
    assert 'cp "$RUNNER_TEMP/sigstore-publication/health.latest.sigstore.json" _site/signatures/' in assembly
    assert "signatures/health.latest.sigstore.json" in served
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
    assert "bash scripts/generate.sh release-build" in _read(DEPLOY_WORKFLOW)


def test_canonical_pipeline_stages_and_validates_record_evidence() -> None:
    if not CANONICAL_PIPELINE.exists():
        pytest.skip(f"dotfiles not co-located: {CANONICAL_PIPELINE}")
    pipeline = _read(CANONICAL_PIPELINE)

    assert "record-evidence" in pipeline.split("ARTIFACT_PATHS=", 1)[1].split(")", 1)[0]
    assert re.search(r"(?:\$\{PYTHON_BIN\}|python3)\s+scripts/gen_record_evidence\.py", pipeline)
    assert "validate_record_evidence(envelope, full=False)" in pipeline


def _fast_path_preservation_script() -> str:
    workflow = _read(DEPLOY_WORKFLOW)
    match = re.search(
        r"(?ms)^      - name: Preserve served attestation plane \(health-only path\)\n"
        r".*?^        run: \|\n(.*?)(?=^      - name: (?:Download verified optional Sigstore bundle|Assemble canonical Pages artifact))",
        workflow,
    )
    assert match is not None, "fast path must preserve the served attestation plane"
    return match.group(1)


def test_cloudflare_fast_path_preserves_valid_served_attestation_plane(tmp_path: Path) -> None:
    """A health-only artifact reads the served P1 plane, not checkout evidence."""
    served_root, key = fixture_root(tmp_path / "served")
    now = datetime.now(timezone.utc).replace(microsecond=0)
    day = now.date().isoformat()
    health = json.loads((served_root / "health/latest.json").read_text(encoding="utf-8"))
    health["checked_at"] = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    health["datasets"][0]["last_checked"] = health["checked_at"]
    write(served_root / "health/latest.json", health)
    ga.generate(served_root, key, now)
    ga.generate(served_root, key, now, fixture_rekor_reference(served_root, day))
    assert verify_contract(served_root, now=now + timedelta(hours=1))["claims"]["artifact_signed"] is True

    checkout = tmp_path / "checkout"
    shutil.copytree(served_root, checkout)
    (checkout / "scripts").mkdir()
    for script in ("verify_attestation_binding.py", "verify_attestation_plane_state.py"):
        shutil.copy2(ROOT / "scripts" / script, checkout / "scripts")
    (checkout / "config").mkdir()
    shutil.copy2(ROOT / "config/public-surfaces.json", checkout / "config")
    stale = checkout / "attestations/latest/binding.json"
    stale.write_text("{}\n", encoding="utf-8")
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    fake_curl = fake_bin / "curl"
    fake_curl.write_text(
        """#!/usr/bin/env bash
set -Eeuo pipefail
output=""; url=""
while (( $# > 0 )); do case "$1" in --output) output="$2"; shift 2 ;; *) url="$1"; shift ;; esac; done
path="${url#https://www.data-pulse.my/}"
[[ "$path" == .well-known/* ]] && path="docs/$path"
[[ "$path" != "$url" && -f "${MOCK_SERVED_ROOT:?}/$path" ]] || exit 22
mkdir -p "$(dirname "$output")"; cp "${MOCK_SERVED_ROOT:?}/$path" "$output"
""",
        encoding="utf-8",
    )
    fake_curl.chmod(0o755)
    environment = os.environ.copy()
    environment.update(PATH=f"{fake_bin}:{environment['PATH']}", MOCK_SERVED_ROOT=str(served_root), RUNNER_TEMP=str(tmp_path / "runner-temp"))
    completed = subprocess.run(["bash", "-c", _fast_path_preservation_script()], cwd=checkout, env=environment, capture_output=True, text=True, check=False)

    assert completed.returncode == 0, completed.stderr
    preserved = tmp_path / "runner-temp/preserved-attestations"
    assert (preserved / "attestations/latest/binding.json").read_bytes() == (served_root / "attestations/latest/binding.json").read_bytes()


def test_cloudflare_fast_path_uses_p6_classifier_and_carries_fail_closed_plane() -> None:
    script = _fast_path_preservation_script()

    assert 'attestation_plane_state="$(python3 scripts/verify_attestation_plane_state.py --planedir "$preserved_root")"' in script
    assert "Signer lane down (P6); attestation failed-closed" in script
    assert "preserving it unchanged" in script
    assert "Run a full release-build deployment to heal the public trust plane." in script


def test_cloudflare_fast_path_refuses_inconsistent_served_plane() -> None:
    script = _fast_path_preservation_script()

    assert 'fail "served health/binding plane is inconsistent; Run a full release-build deployment to heal the public trust plane."' in script
    assert 'python3 scripts/verify_attestation_binding.py --root "$preserved_root"' in script


def test_cloudflare_fast_path_overwrites_checkout_attestations_after_broad_copies() -> None:
    workflow = _read(DEPLOY_WORKFLOW)

    assert "cp -R health deltas record-evidence badges samples data _site/" in workflow
    assert "cp -R attestations _site/" in workflow
    assert "rm -rf _site/attestations" in workflow
    assert 'cp -R "$RUNNER_TEMP/preserved-attestations/attestations" _site/' in workflow
    assert "rm -f _site/attestations/latest/binding.json" in workflow
    assert workflow.index("Preserve served attestation plane (health-only path)") < workflow.index("Assemble canonical Pages artifact")


def test_cloudflare_fast_path_overwrites_checkout_release_proof_after_docs_copy() -> None:
    workflow = _read(DEPLOY_WORKFLOW)
    proof_step = workflow.split("      - name: Preserve served release proof (health-only path)\n", 1)[1].split("      - name: Preserve served attestation plane (health-only path)\n", 1)[0]
    assembly = workflow.split("      - name: Assemble canonical Pages artifact\n", 1)[1].split("      - name: Deploy canonical Cloudflare Pages artifact\n", 1)[0]

    assert '"${website_origin}/release-verification.md" --output "$preserved_proof"' in proof_step
    assert "cp -R docs/. _site/" in assembly
    assert 'cp "$RUNNER_TEMP/preserved-release-proof/release-verification.md" _site/release-verification.md' in assembly


def test_cloudflare_health_only_classifier_is_scoped_to_pipeline_outputs() -> None:
    workflow = _read(DEPLOY_WORKFLOW)
    classifier = workflow.split("      - id: classify\n", 1)[1].split("\n  deploy:", 1)[0]

    assert '"health/latest.json" in paths' in classifier
    assert 'path.startswith("health/")' in classifier
    assert 'path.startswith("attestations/latest/")' in classifier
    assert 'path == ".attestations/chain_head.json"' in classifier
    assert 'all(is_health_cycle_output(path) for path in paths)' in classifier


def test_cloudflare_full_release_keeps_fresh_cryptographic_verification() -> None:
    workflow = _read(DEPLOY_WORKFLOW)
    release_step = workflow.split("      - name: Verify full release contract (non-health path)\n", 1)[1].split("      - name: Preserve served release proof (health-only path)\n", 1)[0]

    assert "python3 scripts/verify_release_reproducible.py" in release_step
    assert "--verify-proof docs/release-verification.md" in release_step
    assert "bash scripts/verify_release_invariants.sh --local" in release_step


def test_cloudflare_workflow_retains_dynamic_public_artifact_contracts() -> None:
    workflow = _read(DEPLOY_WORKFLOW)
    paths_block = workflow.split("    paths:\n", 1)[1].split("  workflow_dispatch:", 1)[0]

    assert '"health/**"' in paths_block
    assert 'fetch "dataset register" "${website_origin}/"' in workflow
    assert 'fetch_redirect "dashboard" "${website_origin}/dashboard" 301' in workflow
    assert 'fetch "health snapshot" "${website_origin}/health/latest.json"' in workflow
    for artifact in ("health/trends.json", "health/drift.json", "health/reconciliation.json"):
        assert artifact in workflow
    assert '.tools | type == "array" and length > 0' in workflow
    assert '.inputSchema | type == "object"' in workflow
    assert "<!-- BEGIN mcp-tools -->" in workflow
    assert "<!-- END mcp-tools -->" in workflow


def test_cloudflare_served_fetches_remain_bounded_and_https_only() -> None:
    workflow = _read(DEPLOY_WORKFLOW)
    verify_step = workflow.split("      - name: Verify canonical served surface\n", 1)[1]

    assert "fetch() {" in verify_step
    for flag in ("--proto '=https'", "--retry 3", "--retry-delay 5", "--retry-all-errors", "--connect-timeout 10", "--max-time 30"):
        assert flag in verify_step
