"""Contract tests for the canonical native Cloudflare Pages deployment."""

from __future__ import annotations

import re
import os
from pathlib import Path
import subprocess
import sys
import textwrap

import pytest
import yaml


ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github/workflows/deploy-cloudflare-pages.yml"


def _workflow() -> str:
    return WORKFLOW.read_text(encoding="utf-8")


def _health_cycle_classifier() -> str:
    """Return the workflow's path classifier as an executable Python fixture."""
    classify = _workflow().split("      - id: classify\n", 1)[1].split("\n  deploy:\n", 1)[0]
    match = re.search(r"python3 - <<'PY'\n(?P<script>.*?)\n\s*PY", classify, re.DOTALL)
    assert match is not None, "the health-cycle classifier must be executable and contract-tested"
    return textwrap.dedent(match.group("script"))


def _classifies_as_health_only(paths: tuple[str, ...]) -> bool:
    result = subprocess.run(
        [sys.executable, "-c", _health_cycle_classifier()],
        check=False,
        env={**os.environ, "HEALTH_CYCLE_CHANGED_PATHS": "\n".join(paths)},
        capture_output=True,
        text=True,
    )
    assert result.returncode in (0, 1), result.stderr
    return result.returncode == 0


def _alias_helper() -> str:
    """Extract the deployed shell helper for direct state-machine testing."""
    verify = _workflow().split("      - name: Verify canonical served surface\n", 1)[1]
    match = re.search(r"(?ms)^          fetch_alias\(\) \{.*?^          \}\n", verify)
    assert match is not None, "the alias verifier must remain executable and contract-tested"
    return textwrap.dedent(match.group(0))


def _run_alias_helper(requested_path: str, responses: dict[str, tuple[str, str, str]]) -> subprocess.CompletedProcess[str]:
    """Run the workflow helper against deterministic HTTP responses."""
    response_cases = "\n".join(
        f'    https://example.test{path}) status={status!r}; location={location!r}; body={body!r} ;;'
        for path, (status, location, body) in responses.items()
    )
    script = f"""
set -Eeuo pipefail
smoke_dir=$(mktemp -d)
trap 'rm -rf "$smoke_dir"' EXIT
website_origin='https://example.test'
fail() {{ echo "$1" >&2; return 1; }}
curl() {{
  local dump='' output='' url='' arg
  while (($#)); do
    arg="$1"
    case "$arg" in
      --dump-header) dump="$2"; shift 2 ;;
      --output) output="$2"; shift 2 ;;
      --write-out) shift 2 ;;
      https://*) url="$arg"; shift ;;
      *) shift ;;
    esac
  done
  case "$url" in
{response_cases}
    *) return 1 ;;
  esac
  printf 'HTTP/2 %s\n' "$status" > "$dump"
  if [[ -n "$location" ]]; then printf 'Location: %s\n' "$location" >> "$dump"; fi
  printf '%s' "$body" > "$output"
  printf '%s' "$status"
}}
{_alias_helper()}
fetch_alias 'test alias' "$website_origin{requested_path}"
"""
    return subprocess.run(["bash", "-c", script], check=False, capture_output=True, text=True)


_ALIAS_BODY = (
    '<title>DataPulse dataset register</title>\n'
    '<link rel="canonical" href="/">\n'
    '<meta http-equiv="refresh" content="0; url=/">\n'
    '<a href="/">DataPulse dataset register</a>\n'
)


def test_alias_verifier_accepts_documented_html_normalization_chain() -> None:
    result = _run_alias_helper(
        "/landing.html",
        {
            "/landing.html": ("308", "/landing", ""),
            "/landing": ("200", "", _ALIAS_BODY),
        },
    )
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize("path", ("/landing", "/dashboard"))
def test_alias_verifier_accepts_direct_static_alias(path: str) -> None:
    result = _run_alias_helper(path, {path: ("200", "", _ALIAS_BODY)})
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize(
    ("path", "response"),
    (
        ("/landing.html", ("308", "/index.html", "")),
        ("/landing.html", ("308", "/landing.html", "")),
        ("/landing.html", ("308", "https://evil.example/landing", "")),
        ("/landing", ("200", "/landing", _ALIAS_BODY)),
        ("/dashboard", ("200", "", '<title>dashboard SPA</title>')),
    ),
)
def test_alias_verifier_rejects_cycles_wrong_locations_and_spa_fallback(
    path: str, response: tuple[str, str, str]
) -> None:
    result = _run_alias_helper(path, {path: response})
    assert result.returncode != 0


def test_health_only_skip_deploy_push_still_runs_native_pages() -> None:
    """The health trailer selects the fast path; it must never skip deployment."""
    workflow = _workflow()

    assert '"health/latest.json"' in workflow
    assert "endsWith(github.event.head_commit.message, '[skip deploy]')" in workflow
    assert "Embed canonical health dashboard (health-only path)" in workflow
    assert "if: needs.classify.outputs.health_only == 'true'" in workflow
    assert "if: needs.classify.outputs.health_only != 'true'" in workflow
    deploy_job = workflow.split("  deploy:\n", 1)[1].split("    steps:\n", 1)[0]
    assert "if:" not in deploy_job
    assert "Deploy canonical Cloudflare Pages artifact" in workflow


def test_health_cycle_classifier_accepts_verified_multifile_commit_c9a2b943() -> None:
    """A complete health cycle is eligible for the dashboard self-healing path."""
    assert _classifies_as_health_only(
        (
            "attestations/latest/scores.json",
            "catalog-graph.json",
            "catalog-snapshot.json",
            "changelog.json",
            "feed.xml",
            "health/drift.json",
            "health/evidence-coverage.json",
            "health/latest.json",
            "health/reconciliation.json",
            "health/trends.json",
            "record-evidence/pharmaceutical_products/latest.json",
        )
    )


def test_health_cycle_classifier_accepts_verified_multifile_commit_3215ef3b() -> None:
    """The minimal verified health cycle is also eligible for the fast path."""
    assert _classifies_as_health_only(
        (
            "attestations/latest/scores.json",
            "health/latest.json",
            "record-evidence/pharmaceutical_products/latest.json",
        )
    )


def test_health_cycle_classifier_fails_closed_for_mixed_source_and_health_input() -> None:
    """A source change forces the release profile even when health/latest.json changes."""
    assert not _classifies_as_health_only(("datapulse.json", "health/latest.json"))


@pytest.mark.parametrize(
    "disallowed_path",
    (
        ".github/workflows/ci.yml",
        "docs/health-methodology.md",
        "unrecognized/generated-output.json",
    ),
)
def test_health_cycle_classifier_fails_closed_outside_generated_ownership(disallowed_path: str) -> None:
    """Workflow, hand-authored, and unknown paths must select the release profile."""
    assert not _classifies_as_health_only(("health/latest.json", disallowed_path))


def test_native_pages_uses_only_canonical_health_input_and_regenerates_embed() -> None:
    workflow = _workflow()
    fast_path = workflow.split("      - name: Embed canonical health dashboard (health-only path)\n", 1)[1].split(
        "      - name: Run release-build generation profile (non-health path)\n", 1
    )[0]

    assert "python3 scripts/embed_dashboard_data.py --health health/latest.json" in fast_path
    assert "health/trends.json" not in fast_path
    assert "health/drift.json" not in fast_path
    assert "health/reconciliation.json" not in fast_path
    assert "curl " not in fast_path


def test_native_pages_preserves_full_release_build_and_surface_contract() -> None:
    workflow = _workflow()

    assert "bash scripts/generate.sh release-build" in workflow
    assert "python3 scripts/verify_release_reproducible.py" in workflow
    assert "bash scripts/verify_release_invariants.sh" in workflow
    for copy in (
        "cp -R docs/. _site/",
        "cp llms.txt robots.txt sitemap.xml feed.xml",
        "cp -R health deltas record-evidence badges samples data _site/",
        "cp -R attestations _site/",
        "cp -R .attestations _site/",
    ):
        assert copy in workflow
    assert "test ! -e _site/_redirects" in workflow
    assert "fetch_alias \"landing.html\"" in workflow
    assert "fetch_alias \"landing\"" in workflow
    assert "fetch_alias \"dashboard\"" in workflow
    assert "Only the documented landing.html -> landing transition is" in workflow
    assert "normalized alias redirects again" in workflow


def test_health_only_legacy_release_proof_accepts_generated_and_verified_timestamps() -> None:
    workflow = _workflow()
    preserve_step = workflow.split(
        "      - name: Preserve served release proof (health-only path)\n", 1
    )[1].split("      - name: Preserve served attestation plane (health-only path)\n", 1)[0]
    match = re.search(r'"verification timestamp": r"([^"]+)"', preserve_step)
    assert match is not None
    pattern = match.group(1)

    assert re.search(pattern, "- Generated at: `2026-08-29T10:27:58+00:00`\n", re.MULTILINE)
    assert re.search(pattern, "- Verified at: `2026-08-29T10:27:58+00:00`\n", re.MULTILINE)


def test_final_health_only_release_proof_check_accepts_both_timestamp_forms_fail_closed() -> None:
    workflow = _workflow()
    verify_step = workflow.split("      - name: Verify canonical served surface\n", 1)[1]
    match = re.search(r'"verification timestamp": r"([^"]+)"', verify_step)
    assert match is not None
    pattern = match.group(1)

    for timestamp in ("Generated", "Verified"):
        assert re.search(pattern, f"- {timestamp} at: `2026-08-29T10:27:58+00:00`", re.MULTILINE)
    for malformed in (
        "- generated at: `2026-08-29T10:27:58+00:00`",
        "- Generated at: 2026-08-29T10:27:58+00:00",
        "- Generated at: `not-a-timestamp`\nextra",
    ):
        assert re.search(pattern, malformed, re.MULTILINE) is None


def test_health_only_signed_sigstore_bundle_skips_legacy_plane_preservation() -> None:
    """A fresh verified bundle must not be blocked by a stale served plane."""
    steps = yaml.safe_load(_workflow())["jobs"]["deploy"]["steps"]
    preserve = next(
        step for step in steps if step.get("name") == "Preserve served attestation plane (health-only path)"
    )
    download = next(step for step in steps if step.get("name") == "Download verified optional Sigstore bundle")
    assemble = next(step for step in steps if step.get("name") == "Assemble canonical Pages artifact")

    assert preserve["if"] == (
        "needs.classify.outputs.health_only == 'true' && "
        "needs.sign_health.outputs.signed != 'true'"
    )
    assert download["if"] == (
        "needs.sign_health.outputs.signed == 'true' || "
        "needs.sign_health.outputs.receipts_signed == 'true'"
    )
    for artifact in (
        "health.latest.sigstore.json",
        "health.latest.statement.json",
        "chain_head.json",
        "datapulse.json",
    ):
        assert f'test -s "$RUNNER_TEMP/sigstore-publication/{artifact}"' in assemble["run"]
        assert f'cp "$RUNNER_TEMP/sigstore-publication/{artifact}" _site/signatures/' in assemble["run"]


def test_health_only_signer_down_path_preserves_only_a_verified_served_plane() -> None:
    """Absent a fresh bundle, corrupt served evidence must remain deployment-blocking."""
    steps = yaml.safe_load(_workflow())["jobs"]["deploy"]["steps"]
    preserve = next(
        step for step in steps if step.get("name") == "Preserve served attestation plane (health-only path)"
    )
    assemble = next(step for step in steps if step.get("name") == "Assemble canonical Pages artifact")

    assert "python3 scripts/verify_attestation_plane_state.py --planedir \"$preserved_root\"" in preserve["run"]
    assert "served health/binding plane is inconsistent" in preserve["run"]
    assert "rm -f _site/attestations/latest/binding.json" in assemble["run"]


def test_native_pages_installs_release_dependencies_before_generation() -> None:
    parsed = yaml.safe_load(_workflow())
    steps = parsed["jobs"]["deploy"]["steps"]
    install_index = next(
        index for index, step in enumerate(steps) if step.get("name") == "Install release verification dependencies"
    )
    release_build_index = next(
        index for index, step in enumerate(steps) if step.get("name") == "Run release-build generation profile (non-health path)"
    )
    install_step = steps[install_index]

    assert install_index < release_build_index
    assert install_step["if"] == "needs.classify.outputs.health_only != 'true'"
    assert install_step["run"] == (
        "python -m pip install jsonschema --requirement mcp/requirements.txt "
        "'datacontract-cli[duckdb]==0.12.5'"
    )


def test_native_pages_runs_contract_validation_only_for_full_releases() -> None:
    """Contract drift blocks release builds but never a health-only publication."""
    steps = yaml.safe_load(_workflow())["jobs"]["deploy"]["steps"]
    validation = next(step for step in steps if step.get("name") == "Validate DataPulse contract (non-health path)")

    assert validation["if"] == "needs.classify.outputs.health_only != 'true'"
    assert validation["run"] == "bash scripts/run_datacontract_validation.sh"


def test_native_pages_installs_pinned_pandoc_before_non_health_release_build() -> None:
    parsed = yaml.safe_load(_workflow())
    steps = parsed["jobs"]["deploy"]["steps"]
    pandoc_index = next(
        index for index, step in enumerate(steps) if step.get("name") == "Install Pandoc"
    )
    release_build_index = next(
        index
        for index, step in enumerate(steps)
        if step.get("name") == "Run release-build generation profile (non-health path)"
    )
    pandoc_step = steps[pandoc_index]

    assert pandoc_index < release_build_index
    assert pandoc_step["if"] == "needs.classify.outputs.health_only != 'true'"
    assert pandoc_step["run"].splitlines() == [
        "sudo apt-get update",
        "sudo apt-get install -y pandoc=3.1.3+ds-2",
        "pandoc --version | sed -n '1p'",
    ]


def test_native_pages_scopes_attestation_key_setup_to_non_health_release_build() -> None:
    parsed = yaml.safe_load(_workflow())
    steps = parsed["jobs"]["deploy"]["steps"]
    health_step = next(
        step for step in steps if step.get("name") == "Embed canonical health dashboard (health-only path)"
    )
    release_step = next(
        step for step in steps if step.get("name") == "Run release-build generation profile (non-health path)"
    )
    verify_step = next(
        step for step in steps if step.get("name") == "Verify full release contract (non-health path)"
    )

    secret_expression = "${{ secrets.DATAPULSE_ATTESTATION_PRIVATE_KEY_FILE }}"
    release_run = release_step["run"]
    verify_run = verify_step["run"]
    assert release_step["if"] == "needs.classify.outputs.health_only != 'true'"
    assert verify_step["if"] == "needs.classify.outputs.health_only != 'true'"
    assert release_step["env"] == {
        "DATAPULSE_ATTESTATION_PRIVATE_KEY_CONTENT": secret_expression,
    }
    assert verify_step["env"] == {
        "DATAPULSE_ATTESTATION_PRIVATE_KEY_CONTENT": secret_expression,
    }
    assert secret_expression not in release_run
    assert secret_expression not in verify_run
    assert secret_expression not in health_step.get("run", "")
    assert "DATAPULSE_ATTESTATION_PRIVATE_KEY_CONTENT" not in health_step
    assert _workflow().count(secret_expression) == 3

    setup = (
        'if [[ -n "$DATAPULSE_ATTESTATION_PRIVATE_KEY_CONTENT" ]]; then',
        'echo "$DATAPULSE_ATTESTATION_PRIVATE_KEY_CONTENT" > /tmp/datapulse-attestation-key.json',
        "chmod 600 /tmp/datapulse-attestation-key.json",
        "export DATAPULSE_ATTESTATION_PRIVATE_KEY_FILE=/tmp/datapulse-attestation-key.json",
    )
    positions = [release_run.index(line) for line in setup]
    assert positions == sorted(positions)
    assert release_run.index("bash scripts/generate.sh release-build") > positions[-1]
    verify_positions = [verify_run.index(line) for line in setup]
    assert verify_positions == sorted(verify_positions)
    invocations = (
        "python3 scripts/verify_release_reproducible.py",
        "bash scripts/verify_release_invariants.sh --local",
    )
    assert all(verify_run.index(invocation) > verify_positions[-1] for invocation in invocations)
    assert "-----BEGIN" not in _workflow()


def test_native_pages_uses_only_cloudflare_secrets_and_project() -> None:
    workflow = _workflow()
    parsed = yaml.safe_load(workflow)

    assert parsed["permissions"] == {"contents": "read"}
    assert "cloudflare/wrangler-action@v3" in workflow
    assert "pages deploy _site --project-name=datapulse-p4b-preview --branch=main" in workflow
    assert "secrets.CLOUDFLARE_API_TOKEN" in workflow
    assert "secrets.CLOUDFLARE_ACCOUNT_ID" in workflow
    assert "secrets.DATAPULSE_ATTESTATION_PRIVATE_KEY_FILE" in workflow
    assert "actions/deploy-pages" not in workflow
    assert "pages: write" not in workflow


def test_post_deploy_verification_rejects_timestamp_count_and_surface_drift() -> None:
    workflow = _workflow()
    verify = workflow.split("      - name: Verify canonical served surface\n", 1)[1]

    assert 'fetch "dataset register" "${website_origin}/" "$smoke_dir/index.html"' in verify
    assert 'fetch_alias "landing.html" "${website_origin}/landing.html"' in verify
    assert 'fetch_alias "landing" "${website_origin}/landing"' in verify
    assert 'fetch_alias "dashboard" "${website_origin}/dashboard"' in verify
    assert 'Only the documented landing.html -> landing transition is' in verify
    assert 'normalized alias redirects again' in verify
    assert 'DataPulse dataset register' in verify
    assert 'expected_dataset_count="$(jq -er' in verify
    assert "_site/datapulse.json" in verify
    assert '[[ "$observed_register_rows" -eq "$expected_dataset_count" ]]' in verify
    assert "origin root register rows mismatch: expected $expected_dataset_count, observed $observed_register_rows" in verify
    assert "389 register rows" not in verify
    assert 'fetch "health snapshot" "${website_origin}/health/latest.json"' in verify
    assert 'for path in "${pages[@]}" "${artifacts[@]}"' in verify
    assert "embedded dashboard checked_at differs from served health/latest.json" in verify
    assert "embedded dashboard dataset count differs from served health/latest.json" in verify
    assert "dashboard dataset-card count differs from served health/latest.json" in verify
    assert "--proto '=https'" in verify
    assert "--retry-all-errors" in verify
    assert "exit 1" in verify
    assert re.search(r"embedded_health\[\"checked_at\"\].*health\[\"checked_at\"\]", verify, re.DOTALL)


def test_sign_health_refreshes_chain_head_before_signing() -> None:
    """The Sigstore statement must be generated from a freshly refreshed chain head."""
    workflow = _workflow()
    sign_health = workflow.split("  sign_health:\n", 1)[1].split("\n  deploy:\n", 1)[0]

    assert "Refresh legacy chain head before signing" in sign_health
    assert "bash scripts/refresh_chain_head.sh" in sign_health
    assert "Generate deterministic health attestation statement" in sign_health
    assert (
        sign_health.index("Refresh legacy chain head before signing")
        < sign_health.index("Generate deterministic health attestation statement")
    )
    refresh_step = sign_health.split(
        "      - name: Refresh legacy chain head before signing\n", 1
    )[1].split("      - name: Generate deterministic health attestation statement\n", 1)[0]

    assert "if: needs.classify.outputs.health_only != 'true'" not in refresh_step
    assert "${{ secrets.DATAPULSE_ATTESTATION_PRIVATE_KEY_FILE }}" in refresh_step
    assert "bash scripts/refresh_chain_head.sh" in refresh_step


def test_health_only_signed_artifact_carries_and_overlays_the_generated_attestation_plane() -> None:
    """Health-only deployment must publish the generated sign-time trust plane."""
    workflow = _workflow()
    sign_health = workflow.split("  sign_health:\n", 1)[1].split("\n  deploy:\n", 1)[0]
    upload = next(
        step
        for step in yaml.safe_load(_workflow())["jobs"]["sign_health"]["steps"]
        if step.get("name") == "Upload verified optional Sigstore bundle"
    )
    sign_step = sign_health.split("      - name: Sign and verify current health DSSE bundle\n", 1)[1].split(
        "      - name: Stage statement into Sigstore publication\n", 1
    )[0]
    assemble = workflow.split("      - name: Assemble canonical Pages artifact\n", 1)[1].split(
        "      - name: Deploy canonical Cloudflare Pages artifact\n", 1
    )[0]

    assert 'test -s attestations/latest/chain_head.json' in sign_step
    assert 'test -s attestations/latest/index.json' in sign_step
    assert 'test -s attestations/latest/scores.json' in sign_step
    assert 'test -s attestations/latest/binding.json' in sign_step
    assert 'test -s .attestations/chain_head.json' in sign_step
    assert 'test -s "$publication/datapulse.json"' in sign_step
    assert 'cp -R attestations "$publication/attestations"' in sign_step
    assert 'cp -R .attestations "$publication/.attestations"' in sign_step
    assert upload["with"]["include-hidden-files"] is True

    overlay_condition = '"${{ needs.classify.outputs.health_only }}" == "true" && "${{ needs.sign_health.outputs.signed }}" == "true"'
    assert overlay_condition in assemble
    assert 'test -s "$RUNNER_TEMP/sigstore-publication/datapulse.json"' in assemble
    assert 'test -s "$RUNNER_TEMP/sigstore-publication/attestations/latest/chain_head.json"' in assemble
    assert 'rm -rf _site/attestations' in assemble
    assert 'rm -rf _site/.attestations' in assemble
    assert 'cp "$RUNNER_TEMP/sigstore-publication/datapulse.json" _site/datapulse.json' in assemble
    assert 'cp -R "$RUNNER_TEMP/sigstore-publication/attestations" _site/' in assemble
    assert 'cp -R "$RUNNER_TEMP/sigstore-publication/.attestations" _site/' in assemble


def test_refresh_chain_head_script_fails_closed_without_a_signing_key() -> None:
    """Missing key material must stop the refresh before any repository state changes."""
    env = {key: value for key, value in os.environ.items() if key != "DATAPULSE_ATTESTATION_PRIVATE_KEY_FILE"}
    result = subprocess.run(
        ["bash", "scripts/refresh_chain_head.sh"],
        check=False,
        env=env,
        capture_output=True,
        text=True,
        cwd=ROOT,
    )

    assert result.returncode != 0
    assert "DATAPULSE_ATTESTATION_PRIVATE_KEY_FILE" in result.stderr
    assert "gen_attestations" not in result.stdout
