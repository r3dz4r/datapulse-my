"""Contract tests for the canonical native Cloudflare Pages deployment."""

from __future__ import annotations

import json
import ast
import builtins
from datetime import datetime, timedelta, timezone
import re
import os
from pathlib import Path
import subprocess
import tempfile
import textwrap
import shutil
import sys
from types import SimpleNamespace

import pytest
import yaml

from scripts.classify_change import is_health_only_change
from scripts.attestation_fetch_refs import fetch_refs
from scripts.tests.test_attestation_projections import accepted_root
from scripts.tests.test_attestations import fixture_root


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


def _stage_attestation_selector(fixture_root: Path) -> None:
    scripts = fixture_root / "scripts"
    scripts.mkdir()
    (scripts / "select_served_attestations.py").write_bytes(
        (ROOT / "scripts/select_served_attestations.py").read_bytes()
    )


def test_pages_passes_explicit_full_revision_depth_without_raising_guard() -> None:
    run = _deploy_step("Keep verifier-reachable attestation history")["run"]
    assert "--full-revisions-per-day 1" in run
    assert "--max-files 18000" in run


@pytest.mark.parametrize(("omitted", "present", "status", "expected"), [
    (True, False, "404", 0),
    (False, False, "404", 1),
    (True, False, "200", 0),
    (True, False, "503", 0),
    (False, True, "404", 1),
    (False, True, "200", 0),
])
def test_served_evidence_distinguishes_retention_from_broken_files(
    tmp_path: Path, omitted: bool, present: bool, status: str, expected: int,
) -> None:
    site = tmp_path / "site"
    reference = "attestations/2026-10-13/revisions/" + "a" * 64 + "/dataset.json"
    _write_site_json(site, "attestations/served-retention.json", {
        "schema": "datapulse/v1/served-attestation-retention",
        "not_served": [reference] if omitted else [],
    })
    if present:
        _write_site_json(site, reference, {})
    source = SERVED_VERIFIER.read_text()
    helpers = source.split("verify_attestation_surface() {", 1)[1].split("# Permit Pages propagation", 1)[0]
    shell = '''set -Eeuo pipefail
site_dir="$1"; smoke_dir="$2"; base_url=https://example.test; status="$3"
fail() { echo "$1" >&2; exit 1; }
retrieve() { echo "retrieved $2"; last_status="$status"; printf '{}' > "$3"; }
fetch() { mkdir -p "$(dirname "$3")"; retrieve "$@"; [[ "$last_status" == 200 ]] || fail "missing or stale served surface (HTTP $last_status)"; }
'''
    result = subprocess.run(
        ["bash", "-c", shell + "verify_attestation_surface() {" + helpers
         + '\nverify_dataset_attestation "$4"', "verify", str(site), str(tmp_path / "smoke"), status, reference],
        text=True, capture_output=True, check=False,
    )
    assert result.returncode == expected, result.stdout + result.stderr
    if expected == 0 and omitted:
        assert "not served (retention policy)" in result.stdout
        assert "retrieved" not in result.stdout
    if not present and not omitted:
        assert "missing required evidence" in result.stderr
    if present and status == "404":
        assert "missing or stale served surface (HTTP 404)" in result.stderr


def test_pages_attestation_selection_keeps_chain_and_citations(tmp_path: Path) -> None:
    _stage_attestation_selector(tmp_path)
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
    _stage_attestation_selector(tmp_path)
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
    assert "if: needs.sign_health.outputs.health_only == 'true'" in workflow
    assert "if: needs.sign_health.outputs.health_only != 'true'" in workflow
    deploy_job = workflow.split("  deploy:\n", 1)[1].split("    steps:\n", 1)[0]
    assert (
        "if: needs.sign_health.outputs.report_state == 'accepted'"
    ) in deploy_job
    assert "Deploy canonical Cloudflare Pages artifact" in workflow


def test_publication_classifier_invocations_pass_no_profile_flags() -> None:
    # Both initial classification and re-settlement must preserve full receipt releases.
    workflow = yaml.safe_load(_workflow())
    invocations = [
        line.strip()
        for job in workflow["jobs"].values()
        for step in job.get("steps", [])
        for line in step.get("run", "").splitlines()
        if re.search(r"\bpython3\s+scripts/classify_change\.py\b", line)
    ]
    assert len(invocations) == 1
    assert all(line.endswith("python3 scripts/classify_change.py; then") for line in invocations)


def test_pages_concurrency_keeps_one_pending_deploy_candidate() -> None:
    workflow = yaml.safe_load(_workflow())

    # New arrivals replace pending deploys without canceling the active run.
    assert workflow["concurrency"] == {
        "group": "cloudflare-pages-deploy",
        "cancel-in-progress": False,
        "queue": "single",
    }
    assert "concurrency" not in workflow["jobs"]["sign_health"]
    assert "concurrency" not in workflow["jobs"]["deploy"]


def test_pages_signing_pins_the_code_build_without_reselecting_main() -> None:
    jobs = yaml.safe_load(_workflow())["jobs"]
    guard = next(step for step in jobs["sign_health"]["steps"] if step.get("id") == "settled_main")
    assert '$(git rev-parse HEAD)' in guard["run"]
    assert "gh api" not in guard["run"] and "git checkout" not in guard["run"]
    assert jobs["sign_health"]["outputs"]["settled_sha"] == "${{ steps.settled_main.outputs.settled_sha }}"
    assert jobs["deploy"]["env"]["PROMOTION_SOURCE_SHA"] == "${{ needs.sign_health.outputs.settled_sha }}"



@pytest.mark.parametrize(("sha", "reason"), [("a" * 40, "quiet"), ("b" * 40, "ceiling"), ("", "")])
def test_pages_logs_classify_promotion_source_before_consumption(sha: str, reason: str) -> None:
    steps = yaml.safe_load(_workflow())["jobs"]["classify"]["steps"]
    settlement = next(step for step in steps if step.get("id") == "settled_main")
    diagnostic = next(step for step in steps if step.get("name") == "Log promotion source resolution")
    checkout = next(step for step in steps if step.get("uses") == "actions/checkout@v4")
    assert steps.index(settlement) < steps.index(diagnostic) < steps.index(checkout)
    assert diagnostic["env"] == {
        "SETTLED_SHA": "${{ steps.settled_main.outputs.settled_sha }}",
        "SETTLEMENT_REASON": "${{ steps.settled_main.outputs.settlement_reason }}",
    }
    result = subprocess.run(
        ["bash", "-c", diagnostic["run"]], capture_output=True, text=True, check=True,
        env={**os.environ, "SETTLED_SHA": sha, "SETTLEMENT_REASON": reason},
    )
    assert result.stdout.splitlines() == [
        f"settled_sha={sha or '<empty>'}", f"settlement_reason={reason or '<empty>'}",
    ]


def test_pages_settlement_is_bounded_and_pins_the_promoted_revision() -> None:
    workflow = yaml.safe_load(_workflow())
    jobs = workflow["jobs"]
    steps = jobs["classify"]["steps"]
    settlement = next(
        (step for step in steps if step.get("name") == "Wait for settled main before promoting"),
        None,
    )
    assert settlement is not None, "Pages has no settlement step before signing"
    quiet = workflow["env"]["PROMOTION_SETTLED_QUIET_SECONDS"]
    ceiling = workflow["env"]["PROMOTION_SETTLED_MAX_WAIT_SECONDS"]
    assert str(quiet).isdigit() and str(ceiling).isdigit()
    assert int(quiet) == 300 and int(ceiling) == 900
    assert 0 < int(quiet) < int(ceiling)
    assert int(quiet) + int(ceiling) < jobs["sign_health"]["timeout-minutes"] * 60
    assert int(ceiling) + 10 < jobs["classify"]["timeout-minutes"] * 60
    assert jobs["sign_health"]["needs"] == "classify"
    assert steps.index(settlement) < next(i for i, step in enumerate(steps) if step.get("id") == "classify")
    run = settlement["run"]
    assert 'timeout -k 5s "$((PROMOTION_SETTLED_MAX_WAIT_SECONDS + 5))s" python3' in run
    assert '["timeout", "-k", "5s",' in run
    assert "timeout=call_budget" in run
    assert "time.monotonic()" in run
    assert 'commit["committer"]["date"]' in run
    assert "sha != previous_sha" in run
    assert 'reason = "ceiling"' in run and 'reason = "quiet"' in run
    assert 'settled_sha={sha}' in run and 'settlement_reason={reason}' in run
    assert "::warning title=Main settlement ceiling reached::" in run
    # There is one shell command and one subprocess call in the poll. Both
    # must keep their timeout wrappers; parsing catches additional bare calls.
    shell, source = run.split("<<'PY'\n", 1)
    assert len(shell.strip().splitlines()) == 2
    calls = [node for node in ast.walk(ast.parse(source.rsplit("\nPY", 1)[0]))
             if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
             and isinstance(node.func.value, ast.Name) and node.func.value.id == "subprocess"]
    assert len(calls) == 1 and calls[0].func.attr == "run"
    assert isinstance(calls[0].args[0], ast.List)
    assert [ast.literal_eval(item) for item in calls[0].args[0].elts[:3]] == ["timeout", "-k", "5s"]
    assert any(keyword.arg == "timeout" for keyword in calls[0].keywords)
    for job_name in ("sign_health", "deploy"):
        job = jobs[job_name]
        source_job = "classify" if job_name == "sign_health" else "sign_health"
        selected = "${{ needs." + source_job + ".outputs.settled_sha }}"
        checkout = next(step for step in job["steps"] if step.get("uses") == "actions/checkout@v4")
        assert checkout["with"]["ref"] == selected
        assert job["env"]["PROMOTION_SOURCE_SHA"] == selected
        assert all("$GITHUB_SHA" not in step.get("run", "") for step in job["steps"])
    assert jobs["classify"]["outputs"]["settled_sha"] == "${{ steps.settled_main.outputs.settled_sha }}"
    classifier = next(step for step in steps if step.get("id") == "classify")
    assert classifier["env"]["AFTER_SHA"] == "${{ steps.settled_main.outputs.settled_sha }}"
    guard = next(step for step in jobs["sign_health"]["steps"]
                 if step.get("name") == "Require settled main before signing")
    assert '$(git rev-parse HEAD)' in guard["run"]
    assert "gh api" not in guard["run"]
    assert jobs["sign_health"]["steps"].index(guard) < next(
        i for i, step in enumerate(jobs["sign_health"]["steps"])
        if step.get("id") == "select_accepted_health"
    )


@pytest.mark.parametrize("scenario", ["already_quiet", "recent", "backdated_move", "confirmation_move", "busy", "lookup_failure"])
def test_pages_settlement_poll_exercises_quiet_ceiling_and_head_changes(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], scenario: str,
) -> None:
    step = next(step for step in yaml.safe_load(_workflow())["jobs"]["classify"]["steps"]
                if step.get("id") == "settled_main")
    source = step["run"].split("<<'PY'\n", 1)[1].rsplit("\nPY", 1)[0]
    clock = [0.0]
    calls = []
    epoch = 1_800_000_000
    output = tmp_path / "output"

    class ClockDateTime(datetime):
        @classmethod
        def now(cls, tz: timezone | None = None) -> datetime:
            return datetime.fromtimestamp(epoch + clock[0], tz)

    def sleep(seconds: float) -> None:
        assert 0 <= seconds <= 15
        clock[0] += seconds
        assert clock[0] <= 900

    def read_head(command: list[str], **kwargs: object) -> SimpleNamespace:
        assert command[:3] == ["timeout", "-k", "5s"]
        assert command[4:6] == ["gh", "api"]
        assert command[6].endswith("/commits/refs/heads/main")
        call_budget = float(command[3].removesuffix("s"))
        assert 0 < call_budget <= min(30, 900 - clock[0])
        assert kwargs["timeout"] == call_budget + 6
        assert kwargs["check"] is True
        if scenario == "lookup_failure":
            raise subprocess.CalledProcessError(1, command, stderr="lookup unavailable")
        clock[0] += 0.25
        moved = ((scenario == "backdated_move" and clock[0] >= 60)
                 or (scenario == "confirmation_move" and bool(calls)))
        sha = ("b" if moved else "a") * 40
        timestamp = epoch if scenario == "recent" or (scenario == "backdated_move" and not moved) else epoch - 1000
        if scenario == "busy":
            revision = int(clock[0] // 31)
            sha = f"{revision:040x}"
            timestamp = epoch + revision * 31
        calls.append((clock[0], sha))
        date = datetime.fromtimestamp(timestamp, timezone.utc).isoformat()
        return SimpleNamespace(stdout=json.dumps({"sha": sha, "commit": {"committer": {"date": date}}}))

    modules = {
        "time": SimpleNamespace(monotonic=lambda: clock[0], sleep=sleep),
        "datetime": SimpleNamespace(datetime=ClockDateTime, timezone=timezone),
        "subprocess": SimpleNamespace(run=read_head),
        "os": SimpleNamespace(environ={
            "PROMOTION_SETTLED_QUIET_SECONDS": "300", "PROMOTION_SETTLED_MAX_WAIT_SECONDS": "900",
            "GITHUB_REPOSITORY": "fixture/datapulse", "GITHUB_OUTPUT": str(output),
        }),
    }

    def import_module(name: str, *args: object, **kwargs: object) -> object:
        return modules[name] if name in modules else builtins.__import__(name, *args, **kwargs)

    namespace = {"__builtins__": {**vars(builtins), "__import__": import_module}}
    if scenario == "lookup_failure":
        with pytest.raises(subprocess.CalledProcessError):
            exec(compile(source, str(WORKFLOW), "exec"), namespace)
        assert not output.exists()
        return
    exec(compile(source, str(WORKFLOW), "exec"), namespace)
    outputs = dict(line.split("=", 1) for line in output.read_text().splitlines())
    assert outputs["settled_sha"] == calls[-1][1]
    jobs = yaml.safe_load(_workflow())["jobs"]
    assert jobs["classify"]["outputs"]["settled_sha"] == "${{ steps.settled_main.outputs.settled_sha }}"
    assert jobs["sign_health"]["env"]["PROMOTION_SOURCE_SHA"] == "${{ needs.classify.outputs.settled_sha }}"
    if scenario == "busy":
        assert clock[0] == 900
        assert outputs["settled_sha"] == f"{int(clock[0] // 31):040x}"
        assert outputs["settlement_reason"] == "ceiling"
        assert "::warning title=Main settlement ceiling reached::" in capsys.readouterr().out
    else:
        assert outputs["settlement_reason"] == "quiet"
        assert clock[0] < 900
        if scenario == "already_quiet":
            assert len(calls) == 2 and clock[0] < 1
        elif scenario == "recent":
            assert clock[0] >= 300
        elif scenario == "backdated_move":
            assert clock[0] >= 360 and outputs["settled_sha"] == "b" * 40
        elif scenario == "confirmation_move":
            assert clock[0] >= 300 and outputs["settled_sha"] == "b" * 40


@pytest.mark.parametrize("matching", [True, False])
def test_signing_revision_guard_refuses_unbuilt_revision(tmp_path: Path, matching: bool) -> None:
    step = next(step for step in yaml.safe_load(_workflow())["jobs"]["sign_health"]["steps"] if step.get("id") == "settled_main")
    sha = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    output = tmp_path / "output"
    result = subprocess.run(["bash", "-c", step["run"]], cwd=ROOT, env=os.environ | {
        "PROMOTION_SOURCE_SHA": sha if matching else "a" * 40, "PROMOTION_HEALTH_ONLY": "true",
        "GITHUB_OUTPUT": str(output),
    }, capture_output=True, text=True)
    assert (result.returncode == 0) == matching
    if matching:
        assert f"settled_sha={sha}" in output.read_text()
    else:
        assert not output.exists()



def test_attestation_state_machine_preserves_the_accepted_report_during_signer_outage() -> None:
    workflow = _workflow()
    parsed = yaml.safe_load(workflow)
    assert workflow.count("continue-on-error: true") == 1
    assert "--allow-unattested-health" not in workflow
    steps = parsed["jobs"]["deploy"]["steps"]
    gate = next(step for step in steps if step.get("name") == "Require signed attestation for full release")
    assert gate["if"] == "needs.sign_health.outputs.health_only != 'true' && needs.sign_health.outputs.attestation_state != 'signed'"
    overlay = next(step for step in steps if step.get("name") == "Bind built dashboard to accepted sign-time trust plane")
    assert "if" not in overlay
    assert 'cp "$publication/health/latest.json" health/latest.json' in overlay["run"]
    assert "verify_attestation_binding.py --root ." in overlay["run"]
    assert "preserved-attestations" not in workflow



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
        "      - name: Consume verified release build (non-health path)\n", 1
    )[0]

    assert "python3 scripts/embed_dashboard_data.py --health health/latest.json" in fast_path
    assert "health/trends.json" not in fast_path
    assert "health/drift.json" not in fast_path
    assert "health/reconciliation.json" not in fast_path
    assert "curl " not in fast_path


def test_native_pages_preserves_full_release_build_and_surface_contract() -> None:
    workflow = _workflow()

    assert 'cp -R "$VERIFIED_PAGES_BUILD/." .' in workflow
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


def test_selected_report_artifact_is_transported_even_when_sigstore_is_down() -> None:
    jobs = yaml.safe_load(_workflow())["jobs"]
    upload = next(step for step in jobs["sign_health"]["steps"] if step.get("id") == "upload_sigstore")
    assert upload["if"] == "steps.select_accepted_health.outputs.state == 'accepted'"
    download = _deploy_step("Download accepted report and optional Sigstore bundle")
    assert "if" not in download
    assert upload["with"]["include-hidden-files"] is True



def test_report_overlay_cannot_inherit_a_different_served_binding() -> None:
    run = _deploy_step("Bind built dashboard to accepted sign-time trust plane")["run"]
    assert "rm -rf attestations .attestations" in run
    assert 'cp -R "$publication/attestations" "$publication/.attestations" .' in run
    assert 'cp "$publication/docs/.well-known/datapulse-probe-keys.json" docs/.well-known/' in run
    assert "curl" not in run



def test_served_rekor_references_are_limited_to_the_binding_day_directory(tmp_path: Path) -> None:
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
        index for index, step in enumerate(steps) if step.get("name") == "Consume verified release build (non-health path)"
    )
    install_step = steps[install_index]

    assert install_index < release_build_index
    assert install_step["if"] == "needs.sign_health.outputs.health_only != 'true'"
    assert install_step["run"] == (
        "python -m pip install jsonschema --requirement mcp/requirements.txt "
        "'datacontract-cli[duckdb]==0.12.5'"
    )


def test_native_pages_runs_contract_validation_only_for_full_releases() -> None:
    """Contract drift blocks release builds but never a health-only publication."""
    steps = yaml.safe_load(_workflow())["jobs"]["deploy"]["steps"]
    validation = next(step for step in steps if step.get("name") == "Validate DataPulse contract (non-health path)")

    assert validation["if"] == "needs.sign_health.outputs.health_only != 'true'"
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
        if step.get("name") == "Consume verified release build (non-health path)"
    )
    pandoc_step = steps[pandoc_index]

    assert pandoc_index < release_build_index
    assert pandoc_step["if"] == "needs.sign_health.outputs.health_only != 'true'"
    assert pandoc_step["run"].splitlines() == [
        "sudo apt-get update",
        "sudo apt-get install -y pandoc=3.1.3+ds-2",
        "pandoc --version | sed -n '1p'",
    ]


def test_pages_cannot_generate_a_private_substitute_for_an_accepted_report() -> None:
    workflow = _workflow()
    assert "DATAPULSE_ATTESTATION_PRIVATE_KEY" not in workflow
    assert "scripts/generate.sh release-build" not in workflow
    run = _deploy_step("Consume verified release build (non-health path)")["run"]
    assert 'test -n "$VERIFIED_PAGES_BUILD"' in run
    assert 'cp -R "$VERIFIED_PAGES_BUILD/." .' in run



def test_native_pages_uses_only_cloudflare_secrets_and_project() -> None:
    workflow = _workflow()
    parsed = yaml.safe_load(workflow)

    assert parsed["permissions"] == {"contents": "read"}
    assert "cloudflare/wrangler-action@v3" not in workflow
    assert "npx --yes wrangler@3.90.0" in workflow
    assert "pages deploy _site --project-name=datapulse-p4b-preview --branch=main" in workflow
    assert "secrets.CLOUDFLARE_API_TOKEN" in workflow
    assert "secrets.CLOUDFLARE_ACCOUNT_ID" in workflow
    assert "secrets.DATAPULSE_ATTESTATION_PRIVATE_KEY_FILE" not in workflow
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
    projection_guard_index = next(
        index for index, step in enumerate(steps)
        if step.get("name") == "Verify accepted report identity and disclose observation time"
    )
    ceiling_guard_index = next(
        index for index, step in enumerate(steps)
        if step.get("name") == "Guard Cloudflare Pages file ceiling"
    )
    assert selection_index == next(
        index for index, step in enumerate(steps)
        if step.get("name") == "Assemble canonical Pages artifact"
    ) + 1
    assert projection_guard_index == selection_index + 1
    assert asset_guard_index == projection_guard_index + 1
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
        assert '--source-commit "$PROMOTION_SOURCE_SHA"' in run
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


def test_sign_health_selects_accepted_inputs_before_signing() -> None:
    steps = yaml.safe_load(_workflow())["jobs"]["sign_health"]["steps"]
    select = next(step for step in steps if step.get("id") == "select_accepted_health")
    generate = next(step for step in steps if step.get("name") == "Generate deterministic health attestation statement")
    assert steps.index(select) < steps.index(generate)
    assert '--revision "$PROMOTION_SOURCE_SHA"' in select["run"]
    assert '--health health/latest.json' in generate["run"]
    assert '--manifest datapulse.json' in generate["run"]
    assert '--legacy-chain-head .attestations/chain_head.json' in generate["run"]



def test_health_only_signed_artifact_carries_and_overlays_the_generated_attestation_plane() -> None:
    """Health-only deployment must publish the generated sign-time trust plane."""
    workflow = _workflow()
    sign_health = workflow.split("  sign_health:\n", 1)[1].split("\n  deploy:\n", 1)[0]
    upload = next(
        step
        for step in yaml.safe_load(_workflow())["jobs"]["sign_health"]["steps"]
        if step.get("name") == "Upload accepted report and optional Sigstore bundle"
    )
    sign_step = sign_health.split("      - name: Sign and verify accepted health DSSE bundle\n", 1)[1].split(
        "      - name: Stage statement into Sigstore publication\n", 1
    )[0]
    assemble = workflow.split("      - name: Assemble canonical Pages artifact\n", 1)[1].split(
        "      - name: Deploy canonical Cloudflare Pages artifact\n", 1
    )[0]

    assert 'cmp health/latest.json "$publication/health/latest.json"' in sign_step
    assert 'cmp datapulse.json "$publication/datapulse.json"' in sign_step
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


def test_pages_never_creates_or_waits_for_acceptance() -> None:
    workflow = _workflow()
    for forbidden in ("existing_append", "append_submission", "append_acceptance", "APPEND_",
                      "submit_attestation_append.sh", "refresh_chain_head.sh", "bind_candidate_witness.py"):
        assert forbidden not in workflow
    assert "select_accepted_health.py" in workflow
    assert yaml.safe_load(workflow)["jobs"]["deploy"]["if"] == "needs.sign_health.outputs.report_state == 'accepted'"


def _accepted_workflow_case(tmp_path: Path) -> tuple[Path, str, bytes, dict[str, str]]:
    """A real accepted H0 with a newer H1 on main, without a candidate producer."""
    from scripts import gen_attestations as ga
    from scripts.tests.test_attestation_projections import git

    root, key = fixture_root(tmp_path / 'repo')
    now = datetime.now(timezone.utc).replace(microsecond=0)
    document = json.loads((root / 'health/latest.json').read_bytes())
    document['checked_at'] = (now - timedelta(hours=2)).isoformat().replace('+00:00', 'Z')
    document['datasets'][0]['last_checked'] = document['checked_at']
    _write_site_json(root, 'health/latest.json', document)
    git(root, 'init', '-b', 'main')
    git(root, 'config', 'user.name', 'Test')
    git(root, 'config', 'user.email', 'test@example.test')
    (root / '.gitignore').write_text('private.json\n')
    ga.generate(root, key, now - timedelta(hours=1))
    h0 = (root / 'health/latest.json').read_bytes()
    git(root, 'add', '-A')
    git(root, 'commit', '-m', 'accepted H0')
    document['checked_at'] = now.isoformat().replace('+00:00', 'Z')
    _write_site_json(root, 'health/latest.json', document)
    git(root, 'add', 'health/latest.json')
    git(root, 'commit', '-m', 'main has newer H1')
    revision = git(root, 'rev-parse', 'HEAD')
    (root / 'scripts').symlink_to(ROOT / 'scripts', target_is_directory=True)
    runner = tmp_path / 'runner'
    runner.mkdir()
    env = os.environ | {
        'PATH': f'{Path(sys.executable).parent}:{os.environ["PATH"]}',
        'RUNNER_TEMP': str(runner), 'GITHUB_OUTPUT': str(tmp_path / 'output'),
        'GITHUB_STEP_SUMMARY': str(tmp_path / 'summary'), 'PROMOTION_SOURCE_SHA': revision,
    }
    return root, revision, h0, env


def _select_step() -> dict:
    return next(step for step in yaml.safe_load(_workflow())['jobs']['sign_health']['steps']
                if step.get('id') == 'select_accepted_health')


def test_frozen_main_h1_publishes_accepted_h0_with_its_observation_time(tmp_path: Path) -> None:
    root, revision, h0, env = _accepted_workflow_case(tmp_path)
    h1 = (root / 'health/latest.json').read_bytes()
    assert h1 != h0
    result = subprocess.run(['bash', '-c', _select_step()['run']], cwd=root, env=env,
                            capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr
    # Assert on the workflow's own decision, not just the selector function.
    outputs = dict(line.split('=', 1) for line in Path(env['GITHUB_OUTPUT']).read_text().splitlines())
    assert outputs == {'state': 'accepted', 'observed_at': json.loads(h0)['checked_at']}
    assert (root / 'health/latest.json').read_bytes() == h0
    publication = Path(env['RUNNER_TEMP']) / 'sigstore-publication'
    assert (publication / 'health/latest.json').read_bytes() == h0
    identity = json.loads((publication / 'publication-identity.json').read_bytes())
    assert identity['accepted_main_commit'] == revision
    assert identity['observed_at'] == outputs['observed_at']
    assert 'report_age_status' not in identity
    assert '"report_age_status": "current"' in result.stdout
    assert outputs['observed_at'] in Path(env['GITHUB_STEP_SUMMARY']).read_text()
    assert 'Report age:' in result.stdout
    assert yaml.safe_load(_workflow())['jobs']['deploy']['if'] == "needs.sign_health.outputs.report_state == 'accepted'"


@pytest.mark.parametrize('damage', ['snapshot', 'membership', 'url', 'head', 'missing_snapshot'])
def test_workflow_refuses_unrecoverable_or_mismatched_accepted_inputs(tmp_path: Path, damage: str) -> None:
    import gzip
    from scripts.tests.test_attestation_projections import git

    root, _, _, env = _accepted_workflow_case(tmp_path)
    chain = json.loads((root / 'attestations/chain-index.json').read_bytes())
    directory = root / Path(chain['heads'][chain['current_head']]).parent
    if damage in ('snapshot', 'missing_snapshot'):
        snapshot = next(path for path in directory.glob('health.json*'))
        if damage == 'snapshot':
            snapshot.write_bytes(gzip.compress(b'{}'))
        else:
            snapshot.unlink()
    elif damage in ('membership', 'url'):
        manifest = json.loads((root / 'datapulse.json').read_bytes())
        manifest['datasets'][0]['id' if damage == 'membership' else 'url'] = 'wrong'
        _write_site_json(root, 'datapulse.json', manifest)
    else:
        head = json.loads((directory / 'chain_head.json').read_bytes())
        head['chain_head'] = 'a' * 64
        _write_site_json(directory, 'chain_head.json', head)
    git(root, 'add', '-A')
    git(root, 'commit', '-m', 'broken accepted input')
    env['PROMOTION_SOURCE_SHA'] = git(root, 'rev-parse', 'HEAD')
    result = subprocess.run(['bash', '-c', _select_step()['run']], cwd=root, env=env,
                            capture_output=True, text=True, timeout=30)
    assert result.returncode != 0, result.stdout
    assert not Path(env['GITHUB_OUTPUT']).exists()


@pytest.mark.parametrize('clock', ['observation', 'publication'])
@pytest.mark.parametrize('age_hours,expected', [(35, 0), (36, 0), (37, 1)])
def test_report_age_is_independent_of_a_fresh_deploy(
    tmp_path: Path, clock: str, age_hours: int, expected: int,
) -> None:
    from scripts.gen_attestations import health_binding
    root, _ = fixture_root(tmp_path)
    now = datetime(2026, 8, 17, tzinfo=timezone.utc)
    health = json.loads((root / 'health/latest.json').read_bytes())
    observed = now - timedelta(hours=age_hours if clock == 'observation' else 1)
    health['checked_at'] = observed.isoformat().replace('+00:00', 'Z')
    _write_site_json(root, 'health/latest.json', health)
    published = now - timedelta(hours=age_hours if clock == 'publication' else 1)
    _write_site_json(root, 'attestations/latest/binding.json', {'payload': {
        'health': health_binding(root, health), 'published_at': published.isoformat(),
        'freshness': {'max_age_seconds': 129600},
        'ed25519': {'chain_head': 'a' * 64},
    }})
    import hashlib
    _write_site_json(root, 'identity.json', {
        'health_snapshot_ref': 'attestations/2026-08-15/health.json.gz',
        'health_sha256': hashlib.sha256((root / 'health/latest.json').read_bytes()).hexdigest(),
        'accepted_chain_head': 'a' * 64, 'observed_at': health['checked_at'],
        'published_at': published.isoformat(),
    })
    (root / 'scripts').symlink_to(ROOT / 'scripts', target_is_directory=True)
    runner = root / 'runner'
    runner.mkdir()
    # Only the transport is stubbed; execute both workflow age steps and real gates.
    bin_dir = root / 'bin'
    bin_dir.mkdir()
    curl = bin_dir / 'curl'
    curl.write_text('#!/bin/bash\nwrite_out=false\n'
                    '[[ "$*" != *--write-out* ]] || write_out=true\n'
                    'if [[ "$*" == *api.cloudflare.com* ]]; then\n'
                    '  printf \'%s\\n\' "$DEPLOYMENT_RESPONSE"\nelse\n'
                    '  compressed=false\n'
                    '  if [[ "$*" == *binding.json* ]]; then source="$AGE_ROOT/attestations/latest/binding.json"; '
                    'elif [[ "$*" == *publication-identity.json* ]]; then source="$AGE_ROOT/identity.json"; '
                    'else source="$AGE_ROOT/health/latest.json"; compressed=true; fi\n'
                    '  while [[ "$1" != -o ]]; do shift; done\n'
                    '  if $compressed; then gzip -c "$source" > "$2"; else cp "$source" "$2"; fi\n'
                    '  if $write_out; then printf 200; fi\nfi\n')
    curl.chmod(0o755)
    env = os.environ | {'PATH': f'{bin_dir}:{Path(sys.executable).parent}:{os.environ["PATH"]}',
        'RUNNER_TEMP': str(runner), 'AGE_ROOT': str(root), 'GITHUB_STEP_SUMMARY': str(root / 'summary'),
        'CLOUDFLARE_API_TOKEN': 'test', 'CLOUDFLARE_ACCOUNT_ID': 'test',
        'DEPLOYMENT_RESPONSE': json.dumps({'success': True, 'result': {'canonical_deployment': {
            'environment': 'production', 'latest_stage': {'name': 'deploy', 'status': 'success'},
            'created_on': now.isoformat()}}}),
    }
    steps = yaml.safe_load(_workflow())['jobs']['publication_freshness']['steps']
    age_steps = [step for step in steps if step.get('name', '').startswith('Measure canonical production')]
    assert len(age_steps) == 2 and all(step['if'] == 'always()' for step in age_steps)
    results = []
    for step in age_steps:
        command = step['run'].replace('scripts/publication_freshness_gate.py',
            f'scripts/publication_freshness_gate.py --now {now.isoformat()}').replace(
            'scripts/select_accepted_health.py', f'scripts/select_accepted_health.py --now {now.isoformat()}')
        results.append(subprocess.run(['bash', '-c', command], cwd=root, env=env,
                                     capture_output=True, text=True, timeout=10))
    assert results[0].returncode == 0, results[0].stdout + results[0].stderr
    assert results[1].returncode == expected, results[1].stdout + results[1].stderr
    summary = (root / 'summary').read_text()
    assert 'Deployment age (24h policy): fresh' in summary
    assert ('expired' if expected else 'current') in summary
    assert '36h' in summary and health['checked_at'] in summary


def test_assembled_report_discloses_exact_observation_time_and_identity(tmp_path: Path) -> None:
    root, revision, h0, env = _accepted_workflow_case(tmp_path)
    selected = subprocess.run(['bash', '-c', _select_step()['run']], cwd=root, env=env,
                              capture_output=True, text=True, timeout=30)
    assert selected.returncode == 0, selected.stdout + selected.stderr
    site = root / '_site'
    site.mkdir()
    for path in ('health', 'attestations', '.attestations'):
        shutil.copytree(root / path, site / path)
    shutil.copy2(root / 'datapulse.json', site / 'datapulse.json')
    (site / 'index.html').write_text('<html><body><main>Status: fresh</main></body></html>')
    step = _deploy_step('Verify accepted report identity and disclose observation time')
    env |= {'ACCEPTED_MAIN_COMMIT': revision, 'ACCEPTED_OBSERVED_AT': json.loads(h0)['checked_at']}
    result = subprocess.run(['bash', '-c', step['run']], cwd=root, env=env,
                            capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, result.stdout + result.stderr
    html = (site / 'index.html').read_text()
    assert html.index('Accepted health report observed at') < html.index('Status: fresh')
    assert f'<time datetime="{env["ACCEPTED_OBSERVED_AT"]}">' in html
    assert json.loads((site / 'publication-identity.json').read_bytes())['observed_at'] == env['ACCEPTED_OBSERVED_AT']
    assert env['ACCEPTED_OBSERVED_AT'] in result.stdout


@pytest.mark.parametrize('forbidden', ['submit_attestation_append.sh', 'refresh_chain_head.sh',
    'bind_candidate_witness.py', 'append_acceptance', 'APPEND_ACCEPTANCE_PATIENCE_SECONDS', 'gh pr view'])
def test_workflow_contract_forbids_resurrection(tmp_path: Path, forbidden: str) -> None:
    from scripts.verify_attestation_workflow_contract import ContractError, verify_workflows
    pages = tmp_path / 'pages.yml'
    pages.write_text(_workflow() + f'\n# {forbidden}\n')
    with pytest.raises(ContractError, match='forbidden acceptance machinery'):
        verify_workflows(ROOT / '.github/workflows/datapulse-attest-daily.yml', pages)


def test_selection_pins_git_inputs_and_ignores_stale_latest_pointers(tmp_path: Path) -> None:
    from scripts.tests.test_attestation_projections import git
    root, _, h0, env = _accepted_workflow_case(tmp_path)
    # Main's derived selectors may lag the immutable ledger. Neither they nor
    # a dirty local health file are selection authorities.
    for path in ('attestations/latest/index.json', 'attestations/latest/binding.json',
                 'attestations/latest/chain_head.json'):
        _write_site_json(root, path, {'current_head': 'a' * 64})
    git(root, 'add', 'attestations')
    git(root, 'commit', '-m', 'stale selectors')
    env['PROMOTION_SOURCE_SHA'] = git(root, 'rev-parse', 'HEAD')
    _write_site_json(root, 'datapulse.json', {'datasets': []})
    result = subprocess.run(['bash', '-c', _select_step()['run']], cwd=root, env=env,
                            capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr
    assert 'state=accepted' in Path(env['GITHUB_OUTPUT']).read_text()
    assert (root / 'health/latest.json').read_bytes() == h0


@pytest.mark.parametrize('field,value', [
    ('artifact_sha256', 'a' * 64), ('dataset_count', 2), ('dataset_count', True),
    ('dataset_ids_sha256', 'b' * 64), ('observed_at', '2026-08-15T00:00:01Z'),
])
def test_report_measurement_requires_exact_health_claim(tmp_path: Path, field: str, value: object) -> None:
    from scripts.gen_attestations import health_binding
    from scripts.select_accepted_health import SelectionError, report_age
    root, _ = fixture_root(tmp_path)
    health = json.loads((root / 'health/latest.json').read_bytes())
    claim = health_binding(root, health)
    claim[field] = value
    binding = root / 'binding.json'
    binding.write_text(json.dumps({'payload': {'health': claim, 'published_at': health['checked_at'],
                                              'freshness': {'max_age_seconds': 129600}}}))
    with pytest.raises(SelectionError, match='digest/count/ids/observation'):
        report_age(root / 'health/latest.json', binding, datetime(2026, 8, 15, 1, tzinfo=timezone.utc))


@pytest.mark.parametrize('step_name,origin', [
    ('Verify isolated Pages preview before production promotion', 'preview_origin'),
    ('Verify canonical served surface', 'website_origin'),
])
@pytest.mark.parametrize('damage', ['none', 'identity', 'disclosure'])
def test_served_observation_check_refuses_wrong_identity_or_missing_disclosure(
    tmp_path: Path, step_name: str, origin: str, damage: str,
) -> None:
    # Isolate the added checks; the existing served verifier has its own parity tests.
    run = _deploy_step(step_name)['run']
    command = 'set -Eeuo pipefail\n' + run[run.index('observed_at="$(jq'):]
    observed = '2026-10-26T18:15:45Z'
    site = tmp_path / '_site'
    site.mkdir()
    identity = {'observed_at': observed, 'accepted_main_commit': 'a' * 40}
    _write_site_json(site, 'publication-identity.json', identity)
    served = tmp_path / 'served'
    served.mkdir()
    remote = identity | ({'observed_at': '2026-10-27T00:00:00Z'} if damage == 'identity' else {})
    _write_site_json(served, 'publication-identity.json', remote)
    (served / 'index.html').write_text('<body>' + ('' if damage == 'disclosure' else
        f'Accepted health report observed at <time datetime="{observed}">{observed}</time>.') + '</body>')
    curl = tmp_path / 'curl'
    curl.write_text('#!/bin/bash\nwrite_out=false\n'
                    '[[ "$*" != *--write-out* ]] || write_out=true\n'
                    'source="$SERVED/index.html"\n'
                    '[[ "$*" != *publication-identity.json* ]] || source="$SERVED/publication-identity.json"\n'
                    'while [[ "$1" != -o ]]; do shift; done\ncp "$source" "$2"\n'
                    'if $write_out; then printf 200; fi\n')
    curl.chmod(0o755)
    env = os.environ | {'PATH': f'{tmp_path}:{os.environ["PATH"]}', 'SERVED': str(served),
                        'RUNNER_TEMP': str(tmp_path), origin: 'https://test.invalid'}
    result = subprocess.run(['bash', '-c', command], cwd=tmp_path, env=env,
                            capture_output=True, text=True, timeout=5)
    assert (result.returncode == 0) == (damage == 'none'), result.stdout + result.stderr


def test_accepted_report_retains_pinned_git_order_for_historical_siblings(tmp_path: Path) -> None:
    from scripts import gen_attestations as ga
    from scripts.select_accepted_health import select_report
    from scripts.tests.test_append_set_isolation import NOW
    from scripts.tests.test_attestation_projections import git

    root, key = accepted_root(tmp_path / 'accepted')
    base = git(root, 'rev-parse', 'HEAD')
    sibling = tmp_path / 'sibling'
    shutil.copytree(root, sibling)
    ga.generate(root, key, NOW + timedelta(days=1))
    older = next((root / 'attestations/2026-08-16/revisions').glob('*/chain_head.json'))
    accepted_head = json.loads(older.read_bytes())['chain_head']
    git(root, 'restore', '.')
    git(root, 'switch', '-c', 'older')
    git(root, 'add', 'attestations/2026-08-16')
    git(root, 'commit', '-m', 'older signed child')
    ga.generate(sibling, sibling / key.name, NOW + timedelta(days=2))
    newer = next((sibling / 'attestations/2026-08-17/revisions').glob('*/chain_head.json'))
    git(root, 'switch', '-c', 'newer', base)
    shutil.copytree(newer.parent, root / newer.parent.relative_to(sibling))
    git(root, 'add', 'attestations/2026-08-17')
    git(root, 'commit', '-m', 'newer signed sibling')
    git(root, 'switch', 'main')
    git(root, 'merge', '--no-ff', '-m', 'accept older child', 'older')
    git(root, 'merge', '--no-ff', '-m', 'retain newer sibling', 'newer')
    revision = git(root, 'rev-parse', 'HEAD')
    out = tmp_path / 'report'
    result = select_report(root, revision, out, NOW + timedelta(days=1, hours=1))
    assert result['accepted_chain_head'] == accepted_head
    assert git(out, 'rev-parse', 'HEAD') == revision
    assert result['report_age_status'] == 'current'
    upload = next(step for step in yaml.safe_load(_workflow())['jobs']['sign_health']['steps']
                  if step.get('id') == 'upload_sigstore')
    assert '!${{ runner.temp }}/sigstore-publication/.git' in upload['with']['path']


def test_published_report_identity_is_stable_while_run_age_is_measured_again(tmp_path: Path) -> None:
    from scripts.select_accepted_health import select_report
    from scripts.tests.test_append_set_isolation import NOW
    from scripts.tests.test_attestation_projections import git
    root, _ = accepted_root(tmp_path / 'accepted')
    revision = git(root, 'rev-parse', 'HEAD')
    first = select_report(root, revision, tmp_path / 'first', NOW + timedelta(hours=1))
    second = select_report(root, revision, tmp_path / 'second', NOW + timedelta(hours=2))
    assert first['observation_age_seconds'] + 3600 == second['observation_age_seconds']
    assert (tmp_path / 'first/publication-identity.json').read_bytes() == (
        tmp_path / 'second/publication-identity.json').read_bytes()


def test_frozen_report_can_pass_the_inverted_release_proof_health_guard(tmp_path: Path) -> None:
    """Exercise the served verifier with H0 older and smaller than the code build."""
    from scripts.tests.test_preview_served_verification import _stage_accepted_fixture, _run_verifier
    root, built, served, publication = _stage_accepted_fixture(tmp_path)
    result = _run_verifier(tmp_path, root, built, served, publication=publication)
    assert result.returncode == 0, result.stdout + result.stderr
    assert 'Report age:' in result.stdout
