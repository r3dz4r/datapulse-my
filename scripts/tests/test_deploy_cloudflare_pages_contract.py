"""Contract tests for the canonical native Cloudflare Pages deployment."""

from __future__ import annotations

import json
import re
import os
from pathlib import Path
import subprocess
import tempfile
import textwrap

import pytest
import yaml

from scripts.classify_change import is_health_only_change
from scripts.attestation_fetch_refs import fetch_refs


ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github/workflows/deploy-cloudflare-pages.yml"
SERVED_VERIFIER = ROOT / "scripts/verify_served_release.sh"


def _workflow() -> str:
    return WORKFLOW.read_text(encoding="utf-8")


def _deploy_step(name: str) -> dict:
    steps = yaml.safe_load(_workflow())["jobs"]["deploy"]["steps"]
    return next(step for step in steps if step.get("name") == name)


def _write_site_json(site: Path, reference: str, value: dict) -> None:
    path = site / reference
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


def test_pages_attestation_selection_keeps_chain_and_citations(tmp_path: Path) -> None:
    site = tmp_path / "_site"
    old = "attestations/2026-10-03"
    recent = "attestations/2026-10-04"
    cited = "attestations/2026-10-09/revisions/" + "a" * 64
    current = "attestations/2026-10-10"
    directories = (old, recent, cited, current)
    heads = {str(index): f"{directory}/chain_head.json" for index, directory in enumerate(directories)}
    _write_site_json(site, "attestations/chain-index.json", {
        "heads": heads, "envelopes": {key: {} for key in heads},
    })
    _write_site_json(site, "attestations/latest/index.json", {
        "date": "2026-10-10", "attestations": {"example": f"{current}/example.json"},
    })
    _write_site_json(site, "attestations/latest/binding.json", {})
    for directory in directories:
        for name in ("chain_head", "index", "scores", "example", "uncited"):
            _write_site_json(site, f"{directory}/{name}.json", {})
        _write_site_json(site, f"{directory}/binding.json", {"payload": {}})
    proof = "attestations/rekor/2026-10-03/reference.json"
    _write_site_json(site, proof, {})
    _write_site_json(site, f"{old}/binding.json", {"payload": {}, "rekor": {"reference_ref": proof}})
    (site / "data").mkdir()
    (site / "data/example.md").write_text(f"Verify {old}/example.json and {cited}/chain_head.json")

    step = _deploy_step("Keep verifier-reachable attestation history")
    result = subprocess.run(["bash", "-c", step["run"]], cwd=tmp_path, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert (site / "attestations/chain-index.json").is_file()
    assert (site / "attestations/latest/binding.json").is_file()
    assert (site / f"{current}/example.json").is_file()
    assert (site / f"{recent}/uncited.json").is_file()
    assert (site / f"{cited}/uncited.json").is_file()
    assert (site / f"{old}/chain_head.json").is_file()
    assert (site / f"{old}/binding.json").is_file()
    assert (site / proof).is_file()
    assert (site / f"{old}/example.json").is_file()
    assert not (site / f"{old}/uncited.json").exists()


def test_pages_attestation_selection_fails_on_missing_published_reference(tmp_path: Path) -> None:
    site = tmp_path / "_site"
    _write_site_json(site, "attestations/chain-index.json", {"heads": {}, "envelopes": {}})
    _write_site_json(site, "attestations/latest/index.json", {
        "date": "2026-10-10", "attestations": {"example": "attestations/2026-10-10/missing.json"},
    })
    step = _deploy_step("Keep verifier-reachable attestation history")
    result = subprocess.run(["bash", "-c", step["run"]], cwd=tmp_path, capture_output=True, text=True)
    assert result.returncode != 0
    assert "published attestation reference is missing" in result.stderr


def test_pages_file_count_guard_reports_count_and_largest_directory(tmp_path: Path) -> None:
    site = tmp_path / "_site"
    (site / "attestations").mkdir(parents=True)
    for index in range(5):
        (site / "attestations" / f"{index}.json").write_text("{}")
    (site / "index.html").write_text("ok")
    step = _deploy_step("Guard Cloudflare Pages file ceiling")
    assert "18000" in step["run"] and "20000" in step["run"]
    passing = subprocess.run(["bash", "-c", step["run"]], cwd=tmp_path, capture_output=True, text=True)
    assert passing.returncode == 0, passing.stderr
    assert "6 files; largest directory attestations: 5 files" in passing.stdout
    failing = subprocess.run(
        ["bash", "-c", step["run"].replace("18000", "4")],
        cwd=tmp_path, capture_output=True, text=True,
    )
    assert failing.returncode != 0
    assert "artifact has 6 files" in failing.stderr
    assert "largest directory attestations: 5 files" in failing.stderr


def _append_acceptance_step() -> dict:
    steps = yaml.safe_load(_workflow())["jobs"]["sign_health"]["steps"]
    return next(
        step for step in steps
        if step.get("name") == "Require authoritative acceptance before signing publication"
    )


@pytest.mark.parametrize(
    ("committed", "pulls", "gh_status", "expected_submit", "expected_append"),
    [
        (True, [], 0, False, None),
        (False, [], 0, True, None),
        (False, [{"number": 12, "headRefName": "feature/other"}], 0, True, None),
        (False, [{"number": 998, "headRefName": "attestation/append-abc123"}], 0, False, "#998 (attestation/append-abc123)"),
        (False, [
            {"number": 12, "headRefName": "feature/other"},
            {"number": 996, "headRefName": "attestation/append-def456"},
        ], 0, False, "#996 (attestation/append-def456)"),
        (False, [
            {"number": number, "headRefName": f"feature/{number}"}
            for number in range(1000)
        ], 0, False, None),
        (False, [], 2, False, None),
    ],
)
def test_append_acceptance_guard_is_fail_closed_and_deterministic(
    tmp_path: Path,
    committed: bool,
    pulls: list[dict],
    gh_status: int,
    expected_submit: bool,
    expected_append: str | None,
) -> None:
    step = _append_acceptance_step()
    assert step["env"]["GH_TOKEN"] == "${{ steps.append-token.outputs.token }}"
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    (tmp_path / "scripts").mkdir()
    (bin_dir / "python3").write_text(
        '#!/bin/bash\nprintf "verify %s\\n" "$*" >> "$CALL_LOG"\n'
        '[[ "$*" != *--require-committed* ]] || [[ "$COMMITTED" == 1 ]]\n'
    )
    (bin_dir / "gh").write_text(
        '#!/bin/bash\nprintf "gh %s\\n" "$*" >> "$CALL_LOG"\n'
        'printf "%s\\n" "$OPEN_PRS"\nexit "$GH_STATUS"\n'
    )
    (tmp_path / "scripts/submit_attestation_append.sh").write_text(
        'printf "submit\\n" >> "$CALL_LOG"\n'
    )
    for stub in (bin_dir / "python3", bin_dir / "gh"):
        stub.chmod(0o755)
    log = tmp_path / "calls.log"
    env = {
        **os.environ,
        "PATH": f"{bin_dir}:{os.environ['PATH']}",
        "GITHUB_REPOSITORY": "example/data-pulse",
        "GH_TOKEN": "test-token",
        "CALL_LOG": str(log),
        "COMMITTED": "1" if committed else "0",
        "OPEN_PRS": json.dumps(pulls),
        "GH_STATUS": str(gh_status),
    }
    outputs = []
    for _ in range(2):
        log.write_text("")
        result = subprocess.run(
            ["/bin/bash", "-c", step["run"]],
            cwd=tmp_path, env=env, capture_output=True, text=True, check=False,
        )
        calls = log.read_text().splitlines()
        outputs.append((result.returncode, result.stdout, result.stderr, calls))
        assert ("submit" in calls) is expected_submit
        assert "verify scripts/verify_attestation_append.py --base HEAD" in calls
        assert "verify scripts/verify_attestation_append.py --base HEAD --require-committed" in calls
        if not committed:
            assert "gh pr list --repo example/data-pulse --state open --limit 1000 --json number,headRefName" in calls
        else:
            assert not any(call.startswith("gh ") for call in calls)
        if expected_append:
            assert expected_append in result.stderr
            assert "already open" in result.stderr
        if len(pulls) == 1000:
            assert "list reached 1000" in result.stderr
        if committed:
            assert result.returncode == 0
        else:
            assert result.returncode != 0
    assert outputs[0] == outputs[1]


def _served_verifier() -> str:
    return SERVED_VERIFIER.read_text(encoding="utf-8")


def _preview_seed_step() -> dict:
    steps = yaml.safe_load(_workflow())["jobs"]["deploy"]["steps"]
    names = [step.get("name") for step in steps]
    name = "Publish health artifacts to isolated preview KV"
    assert name in names
    assert names.index("Verify release artifact before preview deployment") < names.index(name)
    assert names.index(name) < names.index("Deploy isolated Cloudflare Pages preview artifact")
    return steps[names.index(name)]


def test_preview_kv_publication_uses_existing_writer_and_fails_closed() -> None:
    step = _preview_seed_step()
    assert "if" not in step and "continue-on-error" not in step
    assert step["env"]["DATAPULSE_KV_WRITE"] == "${{ secrets.CLOUDFLARE_API_TOKEN }}"
    assert 'python3 scripts/publish_health_index.py --health health/latest.json' in step["run"]
    assert 'DATAPULSE_KV_PUBLICATION_STATE' in step["env"]


@pytest.mark.parametrize("config_case", ["isolated", "production", "default", "missing", "snapshot_mismatch"])
@pytest.mark.parametrize("publisher_status", [0, 2])
def test_preview_kv_step_selects_configured_namespace_and_propagates_errors(
    tmp_path: Path, config_case: str, publisher_status: int,
) -> None:
    step = _preview_seed_step()
    production, default, preview = "1" * 32, "2" * 32, "3" * 32
    selected = {"production": production, "default": default}.get(config_case, preview)
    config = (
        '[[kv_namespaces]]\nbinding="DATAPULSE_HEALTH_INDEX"\nid="' + default + '"\n'
        '[[env.production.kv_namespaces]]\nbinding="DATAPULSE_HEALTH_INDEX"\nid="' + production + '"\n'
    )
    if config_case != "missing":
        config += '[[env.preview.kv_namespaces]]\nbinding="DATAPULSE_HEALTH_INDEX"\nid="' + selected + '"\n'
    (tmp_path / "wrangler.toml").write_text(config)
    for directory in ("health", "_site/health"):
        (tmp_path / directory).mkdir(parents=True)
        (tmp_path / directory / "latest.json").write_text('{"datasets": []}')
    if config_case == "snapshot_mismatch":
        (tmp_path / "_site/health/latest.json").write_text('{"datasets": [1]}')
    (tmp_path / "scripts").mkdir()
    (tmp_path / "scripts/publish_health_index.py").write_text(
        "import json, os, pathlib, sys\n"
        "pathlib.Path('publication.json').write_text(json.dumps([os.environ['DATAPULSE_KV_NAMESPACE_ID'], sys.argv[1:]]))\n"
        f"raise SystemExit({publisher_status})\n"
    )
    result = subprocess.run(["bash", "-c", step["run"]], cwd=tmp_path, capture_output=True, text=True)
    publication = tmp_path / "publication.json"
    if config_case == "isolated":
        assert result.returncode == publisher_status, result.stderr
        assert json.loads(publication.read_text()) == [preview, ["--health", "health/latest.json"]]
    else:
        assert result.returncode != 0
        assert not publication.exists()


def _classifies_as_health_only(paths: tuple[str, ...]) -> bool:
    return is_health_only_change(paths)


def _assert_deploy_resilience(workflow: str) -> None:
    """Require no coalescing gate and bounded rate-limit handling for both Pages deploys."""
    parsed = yaml.safe_load(workflow)
    steps = parsed["jobs"]["deploy"]["steps"]
    assert "superseded_run" not in workflow

    for name, branch in (
        ("Deploy isolated Cloudflare Pages preview artifact", "--branch=staging"),
        ("Deploy canonical Cloudflare Pages artifact", "--branch=main"),
    ):
        deploy = next(step for step in steps if step.get("name") == name)
        run = deploy["run"]
        assert "for attempt in 1 2 3 4; do" in run
        assert "npx --yes wrangler@3.90.0 pages deploy _site --project-name=datapulse-p4b-preview" in run
        assert branch in run
        assert 'grep -q "10429" "$output"' in run
        assert 'if ! grep -q "10429" "$output"; then' in run
        assert "non-rate-limit failure on attempt $attempt; not retrying." in run
        assert 'exit "$status"' in run
        assert 'if [[ "$attempt" -eq 4 ]]; then' in run
        assert 'delay="$((attempt * 60))"' in run
        assert 'sleep "$delay"' in run

    # The staging deploy always runs; the production deploy is conditional on it
    # having succeeded in the same run.
    preview_deploy = next(
        step for step in steps
        if step.get("name") == "Deploy isolated Cloudflare Pages preview artifact"
    )
    assert "if" not in preview_deploy
    production_deploy = next(
        step for step in steps
        if step.get("name") == "Deploy canonical Cloudflare Pages artifact"
    )
    assert production_deploy["if"] == "steps.deploy_preview.outcome == 'success'"


def test_pages_deploy_resilience_contract_and_mutation_proofs() -> None:
    workflow = _workflow()

    _assert_deploy_resilience(workflow)

    mutations = (
        workflow.replace(
            "      - name: Deploy isolated Cloudflare Pages preview artifact",
            "      - id: superseded_run\n      - name: Deploy isolated Cloudflare Pages preview artifact",
            1,
        ),
        workflow.replace("for attempt in 1 2 3 4; do", "for attempt in 1 2 3; do", 1),
        workflow.replace('if ! grep -q "10429" "$output"; then', "if false; then", 1),
    )
    for mutated in mutations:
        with pytest.raises(AssertionError):
            _assert_deploy_resilience(mutated)


def _alias_helper() -> str:
    """Extract the deployed shell helper for direct state-machine testing."""
    match = re.search(r"(?ms)^retrieve\(\) \{.*?^\}\n^fetch_alias\(\) \{.*?^\}\n", _served_verifier())
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
base_url="$website_origin"
fetch_max_time=120
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
    return subprocess.run(
        ["bash", "-c", script],
        check=False,
        capture_output=True,
        text=True,
        # The extracted helper shells out to `mktemp -d`, which trusts TMPDIR
        # blindly. `tempfile.gettempdir()` has already resolved a writable
        # fallback, so a sandboxed unwritable TMPDIR cannot fail the suite.
        env={**os.environ, "TMPDIR": tempfile.gettempdir()},
    )


_ALIAS_BODY = (
    '<title>DataPulse dataset register</title>\n'
    '<link rel="canonical" href="/">\n'
    '<meta http-equiv="refresh" content="0; url=/">\n'
    '<a href="/">DataPulse dataset register</a>\n'
)


def _declared_surface_helper() -> str:
    """Extract the declared-surface content gate for direct state-machine testing."""
    match = re.search(r"(?ms)^verify_declared_surface_content\(\) \{.*?^\}\n", _served_verifier())
    assert match is not None, "the declared-surface content gate must remain executable and contract-tested"
    return textwrap.dedent(match.group(0))


def _run_declared_surface_check(surface: str, body: str, tmp_path: Path) -> subprocess.CompletedProcess[str]:
    """Run the workflow content gate against one deterministic served body."""
    body_path = tmp_path / "surface.body"
    body_path.write_text(body, encoding="utf-8")
    script = f"""
set -Eeuo pipefail
fail() {{ echo "::error title=Cloudflare Pages contract failed::$1" >&2; return 1; }}
{_declared_surface_helper()}
verify_declared_surface_content '{surface}' '{body_path}'
"""
    return subprocess.run(["bash", "-c", script], check=False, capture_output=True, text=True)


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


def test_declared_surface_content_gate_rejects_spa_fallback_for_the_receipt_entry_point(tmp_path: Path) -> None:
    """HTTP 200 with the dashboard SPA fallback must fail the observation surface."""
    result = _run_declared_surface_check(
        "/observation-receipts/chain_head.json",
        "<!doctype html><html><head><title>DataPulse</title></head><body>SPA fallback</body></html>",
        tmp_path,
    )

    assert result.returncode != 0
    assert "datapulse/v1/observation-chain-head" in result.stderr


def test_declared_surface_content_gate_accepts_the_receipt_chain_head_json(tmp_path: Path) -> None:
    result = _run_declared_surface_check(
        "/observation-receipts/chain_head.json",
        json.dumps({"schema": "datapulse/v1/observation-chain-head", "head": "abc"}),
        tmp_path,
    )

    assert result.returncode == 0, result.stderr


def test_declared_surface_content_gate_rejects_json_without_the_declared_marker(tmp_path: Path) -> None:
    result = _run_declared_surface_check(
        "/observation-receipts/chain_head.json",
        json.dumps({"schema": "datapulse/v1/health-snapshot"}),
        tmp_path,
    )

    assert result.returncode != 0
    assert "datapulse/v1/observation-chain-head" in result.stderr


def test_declared_surface_content_gate_leaves_other_declared_surfaces_untouched(tmp_path: Path) -> None:
    result = _run_declared_surface_check("/health/latest.json", "<html>not json</html>", tmp_path)

    assert result.returncode == 0, result.stderr


def test_served_verifier_wires_the_receipt_entry_point_into_the_content_gate() -> None:
    verify = _served_verifier()

    assert "/observation-receipts/chain_head.json" in verify
    assert '.schema == "datapulse/v1/observation-chain-head"' in verify
    assert 'verify_declared_surface_content "$path" "$smoke_dir/surfaces${path%/}/index"' in verify


def test_health_only_path_is_selected_only_by_the_generated_output_classifier() -> None:
    """Commit messages must not choose a production deployment security mode."""
    workflow = _workflow()

    classify = workflow.split("      - id: classify\n", 1)[1].split("\n  sign_health:\n", 1)[0]
    assert "python3 scripts/classify_change.py" in classify
    assert "skip deploy" not in classify.lower()
    assert "head_commit.message" not in workflow
    assert "Embed canonical health dashboard (health-only path)" in workflow
    assert "if: needs.classify.outputs.health_only == 'true'" in workflow
    assert "if: needs.classify.outputs.health_only != 'true'" in workflow
    deploy_job = workflow.split("  deploy:\n", 1)[1].split("    steps:\n", 1)[0]
    assert "if:" not in deploy_job
    assert "Deploy canonical Cloudflare Pages artifact" in workflow


def test_pages_concurrency_serializes_all_production_candidates() -> None:
    workflow = yaml.safe_load(_workflow())

    assert workflow["concurrency"] == {
        "group": "cloudflare-pages-production",
        "cancel-in-progress": False,
    }
    assert "concurrency" not in workflow["jobs"]["sign_health"]
    assert "concurrency" not in workflow["jobs"]["deploy"]


def test_attestation_state_machine_fails_closed_outside_health_only_signer_degradation() -> None:
    """Only a classifier-scoped signer outage may take the degraded publication path."""
    workflow = _workflow()
    parsed = yaml.safe_load(workflow)
    sign_job = parsed["jobs"]["sign_health"]
    deploy_steps = parsed["jobs"]["deploy"]["steps"]

    assert sign_job["outputs"]["attestation_state"] == "${{ steps.attestation_result.outputs.state }}"
    assert "DATAPULSE_ALLOW_UNATTESTED_HEALTH" not in workflow
    assert "--allow-unattested-health" not in workflow
    assert workflow.count("continue-on-error: true") == 1
    assert "Attempt pinned Cosign signer installation for health-only degradation" in workflow
    assert "Require signed attestation for full release" in workflow
    full_release_gate = next(
        step for step in deploy_steps if step.get("name") == "Require signed attestation for full release"
    )
    assert full_release_gate["if"] == (
        "needs.classify.outputs.health_only != 'true' && "
        "needs.sign_health.outputs.attestation_state != 'signed'"
    )
    assert "signer_down" in full_release_gate["run"]
    preserve = next(
        step for step in deploy_steps if step.get("name") == "Preserve served attestation plane (health-only path)"
    )
    assert preserve["if"] == (
        "needs.classify.outputs.health_only == 'true' && "
        "needs.sign_health.outputs.attestation_state == 'signer_down'"
    )


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


def test_observation_receipt_changes_select_the_full_release_profile() -> None:
    """Observation receipts are site inputs: a receipts change is never health-only."""
    assert not _classifies_as_health_only(("observation-receipts/chain_head.json",))
    assert not _classifies_as_health_only(
        ("observation-receipts/days/2026-09-18.json", "health/latest.json")
    )


@pytest.mark.parametrize(
    "disallowed_path",
    (
        ".github/workflows/ci.yml",
        "docs/health-methodology.md",
        "unrecognized/generated-output.json",
        "health/unrecognized.json",
        "record-evidence/pharmaceutical_products/nested/latest.json",
        "attestations/latest/unrecognized.json",
        ".attestations/latest/not-json.txt",
        "deltas/not-json.txt",
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
        "if [ -d observation-receipts ]; then cp -R observation-receipts _site/; fi",
        "cp -R attestations _site/",
        "cp -R .attestations _site/",
    ):
        assert copy in workflow
    assert "test \"$(grep -c '[^[:space:]]' _site/_redirects)\" -ge 4" in workflow
    for redirect_rule in (
        "/methodology /health-methodology 301",
        "/trust-contract /trust-contract.md 301",
        "/okf/ /okf/index.md 301",
        "/okf /okf/index.md 301",
    ):
        assert f"grep -qxF '{redirect_rule}' _site/_redirects" in workflow
    assert "cat _site/" + '_redirects)" = ' not in workflow
    verifier = _served_verifier()
    assert 'fetch_alias landing.html "$base_url/landing.html"' in verifier
    assert 'fetch_alias landing "$base_url/landing"' in verifier
    assert 'fetch_alias dashboard "$base_url/dashboard"' in verifier
    assert "normalized alias redirects again" in verifier


def test_pages_assembly_includes_bounded_public_summary_artifact() -> None:
    """The explicit root-file copy list must publish the advertised summary."""
    steps = yaml.safe_load(_workflow())["jobs"]["deploy"]["steps"]
    assemble = next(step for step in steps if step.get("name") == "Assemble canonical Pages artifact")
    root_file_copy = next(command for command in assemble["run"].splitlines() if command.startswith("cp llms.txt"))

    assert "datapulse_summary.json" in root_file_copy


def test_health_latest_json_cache_rule_is_effective() -> None:
    """Pin the ``_headers`` cache contract for the served health snapshot.

    The rule must use the ``/health/latest.json*`` splat form and keep the exact
    300-second TTL with stale-while-revalidate, so no edit silently drops the
    health snapshot to a shorter or absent edge cache. Cloudflare does not apply
    ``_headers`` to the Pages Function that also serves this path
    (``functions/health/[[path]].js``); the served header is owned there, and
    this test pins the static-layer half of the contract.
    """
    lines = (ROOT / "docs/_headers").read_text(encoding="utf-8").splitlines()

    assert "/health/latest.json*" in lines
    assert "/health/latest.json" not in lines
    rule_index = lines.index("/health/latest.json*")
    assert lines[rule_index + 1].strip() == (
        "Cache-Control: public, max-age=300, stale-while-revalidate=60"
    )

    # The catch-all discovery block and the asset cache rule must both survive.
    assert (
        '  Link: </.well-known/ard.json>; rel="ard", '
        '</.well-known/ai-catalog.json>; rel="ai-catalog"' in lines
    )
    assets_index = lines.index("/assets/*")
    assert lines[assets_index + 1].strip() == "Cache-Control: public, max-age=86400"


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
    match = re.search(r"'verification timestamp':r'([^']+)'", _served_verifier())
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
        "needs.sign_health.outputs.attestation_state == 'signer_down'"
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


def test_served_rekor_references_are_limited_to_the_binding_day_directory(tmp_path: Path) -> None:
    """Preservation accepts the documented Rekor layout without widening fetches."""
    steps = yaml.safe_load(_workflow())["jobs"]["deploy"]["steps"]
    preserve = next(
        step for step in steps if step.get("name") == "Preserve served attestation plane (health-only path)"
    )
    assert 'python3 scripts/attestation_fetch_refs.py --root "$preserved_root" --proofs' in preserve["run"]
    directory = "attestations/2026-09-15"
    (tmp_path / "attestations/latest").mkdir(parents=True)
    (tmp_path / directory).mkdir()
    (tmp_path / "attestations/latest/index.json").write_text(json.dumps({"chain_head_ref": directory + "/chain_head.json"}))
    (tmp_path / "attestations/chain-index.json").write_text(json.dumps({"schema": "datapulse/v1/chain-index"}))
    binding = tmp_path / directory / "binding.json"
    for reference in (
        "attestations/rekor/2026-09-15/reference.json",
        "attestations/rekor/2026-09-15/health.sigstore.bundle.json",
        "attestations/2026-09-15/reference.json",
    ):
        binding.write_text(json.dumps({"payload": {"date": "2026-09-15"}, "rekor": {"reference_ref": reference}}))
        assert fetch_refs(tmp_path, proofs=True) == [reference]
    for reference in (
        "attestations/rekor/2026-09-15/../reference.json",
        "attestations/rekor/not-a-date/reference.json",
        "/attestations/rekor/2026-09-15/reference.json",
        "attestations/rekor/2026-09-15/nested/reference.json",
        "attestations/rekor/2026-09-16/reference.json",
    ):
        binding.write_text(json.dumps({"payload": {"date": "2026-09-15"}, "rekor": {"reference_ref": reference}}))
        with pytest.raises(ValueError, match="unsafe Rekor proof reference"):
            fetch_refs(tmp_path, proofs=True)


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
    assert "cloudflare/wrangler-action@v3" not in workflow
    assert "npx --yes wrangler@3.90.0" in workflow
    assert "pages deploy _site --project-name=datapulse-p4b-preview --branch=main" in workflow
    assert "secrets.CLOUDFLARE_API_TOKEN" in workflow
    assert "secrets.CLOUDFLARE_ACCOUNT_ID" in workflow
    assert "secrets.DATAPULSE_ATTESTATION_PRIVATE_KEY_FILE" in workflow
    assert "actions/deploy-pages" not in workflow
    assert "pages: write" not in workflow


def test_native_pages_stages_and_verifies_the_assembled_artifact_before_production() -> None:
    """The exact assembled artifact must pass preview invariants before promotion."""
    steps = yaml.safe_load(_workflow())["jobs"]["deploy"]["steps"]
    assemble_index = next(
        index for index, step in enumerate(steps)
        if step.get("name") == "Assemble canonical Pages artifact"
    )
    staging_index = next(
        index for index, step in enumerate(steps)
        if step.get("name") == "Deploy isolated Cloudflare Pages preview artifact"
    )
    preview_index = next(
        index for index, step in enumerate(steps)
        if step.get("name") == "Verify isolated Pages preview before production promotion"
    )
    production_index = next(
        index for index, step in enumerate(steps)
        if step.get("name") == "Deploy canonical Cloudflare Pages artifact"
    )

    staging = steps[staging_index]
    preview = steps[preview_index]
    production = steps[production_index]
    staging_command = staging["run"]
    preview_run = preview["run"]

    assert assemble_index < staging_index < preview_index < production_index
    assert staging["id"] == "deploy_preview"
    assert "pages deploy _site --project-name=datapulse-p4b-preview" in staging_command
    assert re.search(r"--branch=staging(?:\s|$)", staging_command)
    assert "github.run_id" not in staging_command
    assert "GITHUB_RUN_ID" not in staging_command
    assert "--branch=main" not in staging_command
    assert "data-pulse.my" not in staging_command
    assert "www.data-pulse.my" not in staging_command
    assert "if" not in preview
    assert 'preview_branch="staging"' in preview_run
    assert "GITHUB_RUN_ID" not in preview_run
    assert 'preview_origin="https://${preview_branch}.datapulse-p4b-preview.pages.dev"' in preview_run
    assert "bash scripts/verify_served_release.sh" in preview_run
    assert '--base-url "$preview_origin"' in preview_run
    assert '--sigstore-signed "${{ needs.sign_health.outputs.signed }}"' in preview_run
    assert '--sigstore-publication "$RUNNER_TEMP/sigstore-publication"' in preview_run
    assert "verify_release_invariants.sh" not in preview_run
    assert production["id"] == "deploy"
    assert "pages deploy _site --project-name=datapulse-p4b-preview --branch=main" in production["run"]


def test_native_pages_binds_preview_and_promotion_to_one_release_artifact_manifest() -> None:
    """No `_site` generation may occur after its temp-only inventory is recorded."""
    steps = yaml.safe_load(_workflow())["jobs"]["deploy"]["steps"]
    asset_guard_index = next(
        index for index, step in enumerate(steps)
        if step.get("name") == "Exclude oversized Pages assets before upload"
    )
    manifest_create_index = next(
        index for index, step in enumerate(steps)
        if step.get("name") == "Record deterministic release artifact manifest"
    )
    preview_verify_index = next(
        index for index, step in enumerate(steps)
        if step.get("name") == "Verify release artifact before preview deployment"
    )
    preview_served_index = next(
        index for index, step in enumerate(steps)
        if step.get("name") == "Verify isolated Pages preview before production promotion"
    )
    post_preview_verify_index = next(
        index for index, step in enumerate(steps)
        if step.get("name") == "Verify release artifact after preview served verification"
    )
    promotion_verify_index = next(
        index for index, step in enumerate(steps)
        if step.get("name") == "Verify release artifact before canonical production deployment"
    )
    production_index = next(
        index for index, step in enumerate(steps)
        if step.get("name") == "Deploy canonical Cloudflare Pages artifact"
    )

    selection_index = next(
        index for index, step in enumerate(steps)
        if step.get("name") == "Keep verifier-reachable attestation history"
    )
    ceiling_guard_index = next(
        index for index, step in enumerate(steps)
        if step.get("name") == "Guard Cloudflare Pages file ceiling"
    )
    assert selection_index == next(
        index for index, step in enumerate(steps)
        if step.get("name") == "Assemble canonical Pages artifact"
    ) + 1
    assert asset_guard_index == selection_index + 1
    assert ceiling_guard_index == asset_guard_index + 1
    assert manifest_create_index == ceiling_guard_index + 1
    assert "set -Eeuo pipefail" in steps[asset_guard_index]["run"]
    assert "python3 scripts/check_pages_asset_sizes.py _site" in steps[asset_guard_index]["run"]
    assert preview_verify_index < next(
        index for index, step in enumerate(steps)
        if step.get("name") == "Deploy isolated Cloudflare Pages preview artifact"
    )
    assert preview_served_index + 1 == post_preview_verify_index
    assert post_preview_verify_index + 1 == promotion_verify_index
    assert promotion_verify_index + 1 == production_index

    manifest_path = '"$RUNNER_TEMP/release-artifact-manifest.json"'
    lifecycle_indices = (
        manifest_create_index,
        preview_verify_index,
        post_preview_verify_index,
        promotion_verify_index,
    )
    for index in lifecycle_indices:
        run = steps[index]["run"]
        assert "python3 scripts/verify_release_artifact.py" in run
        assert manifest_path in run
        assert '--source-commit "$GITHUB_SHA"' in run
    assert " create " in steps[manifest_create_index]["run"]
    assert all(" verify " in steps[index]["run"] for index in lifecycle_indices[1:])

    for step in steps[manifest_create_index + 1 :]:
        run = step.get("run", "")
        assert "scripts/generate.sh" not in run
        assert "scripts/embed_dashboard_data.py" not in run
        assert "scripts/gen_" not in run


def test_post_deploy_verification_rejects_timestamp_count_and_surface_drift() -> None:
    workflow = _workflow()
    verify = _served_verifier()

    assert 'fetch "dataset register" "$base_url/" "$smoke_dir/index.html"' in verify
    assert 'fetch_alias landing.html "$base_url/landing.html"' in verify
    assert 'fetch_alias landing "$base_url/landing"' in verify
    assert 'fetch_alias dashboard "$base_url/dashboard"' in verify
    assert 'normalized alias redirects again' in verify
    assert 'DataPulse dataset register' in verify
    assert 'expected_dataset_count="$(jq -er' in verify
    assert '"$site_dir/datapulse.json"' in verify
    assert '[[ "$observed_register_rows" -eq "$expected_dataset_count" ]]' in verify
    assert "origin root register rows mismatch: expected $expected_dataset_count, observed $observed_register_rows" in verify
    assert "389 register rows" not in verify
    assert "'/health/index.json'" in verify
    assert 'fetch "health snapshot" "$base_url/health/latest.json"' in verify
    assert 'fetch "dashboard health projection" "$base_url/health/index.json" "$smoke_dir/health/index.json"' in verify
    assert 'for path in "${pages[@]}" "${artifacts[@]}"' in verify
    assert "dashboard health projection is older than served health/latest.json" in verify
    assert "dashboard health projection dataset count differs from served health/latest.json" in verify
    assert "dashboard health projection dataset IDs differ from served health/latest.json" in verify
    assert "--proto '=https'" in verify
    assert "--retry-all-errors" in verify
    assert "exit 1" in verify
    assert "projection['checked_at'] < health['checked_at']" in verify


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
        if step.get("name") == "Upload verified Sigstore bundle"
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

    # Full releases also publish the accepted sign-time head and manifest.
    overlay_condition = 'if [[ "${{ needs.sign_health.outputs.signed }}" == "true" ]]; then'
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
