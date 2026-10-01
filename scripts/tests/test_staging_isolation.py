"""Executable isolation contract for the Cloudflare Pages staging environment.

This is the regression test for the staging-isolation defect: the Pages project
``datapulse-p4b-preview`` previously bound both its ``preview`` and
``production`` environments to the same ``DATAPULSE_HEALTH_INDEX`` KV namespace,
deployed staging on a throwaway per-run branch, and promoted production in the
same run with no gate on the staging deploy.

The tests below pin the production staging boundary and the PR rehearsal:

* the repository declares per-environment KV bindings,
* the preview environment resolves to a namespace that is not production's,
* production is still declared and bound to ``DATAPULSE_HEALTH_INDEX``,
* the staging deploy uses a stable branch and production is gated on it.
* PR builds are uncredentialed; only protected-main workflow code can deploy
  an exact immutable static artifact. Forks cannot pass the staged check.
"""

from __future__ import annotations

import copy
import hashlib
import json
import os
import re
import stat
import subprocess
import sys
import tomllib
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest
import yaml

from scripts import gen_attestations, verify_release_artifact


ROOT = Path(__file__).resolve().parents[2]
WRANGLER_CONFIG = ROOT / "wrangler.toml"
WORKFLOW = ROOT / ".github/workflows/deploy-cloudflare-pages.yml"
PR_PREVIEW_WORKFLOW = ROOT / ".github/workflows/preview-verify.yml"
TRUSTED_PREVIEW_WORKFLOW = ROOT / ".github/workflows/preview-deploy.yml"


def test_pr_controlled_workflow_has_no_deploy_authority() -> None:
    text = PR_PREVIEW_WORKFLOW.read_text()
    assert "secrets." not in text
    assert "pages deploy" not in text
    assert "environment:" not in text
    assert TRUSTED_PREVIEW_WORKFLOW.is_file()

BINDING = "DATAPULSE_HEALTH_INDEX"
STAGING_NAMESPACE = "DATAPULSE_HEALTH_INDEX_STAGING"
STAGING_BRANCH = "staging"

PREVIEW_DEPLOY = "Deploy isolated Cloudflare Pages preview artifact"
PRODUCTION_DEPLOY = "Deploy canonical Cloudflare Pages artifact"


def _pages_config() -> dict[str, Any]:
    assert WRANGLER_CONFIG.is_file(), (
        "the Pages KV binding must be declarative in the repository; "
        f"{WRANGLER_CONFIG.name} is missing so staging isolation is dashboard-only state"
    )
    return tomllib.loads(WRANGLER_CONFIG.read_text(encoding="utf-8"))


def _steps() -> list[dict[str, Any]]:
    workflow = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    return workflow["jobs"]["deploy"]["steps"]


def _step(name: str) -> dict[str, Any]:
    return next(step for step in _steps() if step.get("name") == name)


def _env_binding(config: dict[str, Any], environment: str) -> dict[str, Any]:
    bindings = [
        entry
        for entry in config["env"][environment]["kv_namespaces"]
        if entry.get("binding") == BINDING
    ]
    assert len(bindings) == 1, (
        f"the {environment!r} Pages environment must declare exactly one "
        f"{BINDING!r} KV binding, found {len(bindings)}"
    )
    return bindings[0]


def test_repository_declares_isolated_kv_namespaces_per_environment() -> None:
    config = _pages_config()

    assert config["name"] == "datapulse-p4b-preview"
    assert config["pages_build_output_dir"]
    # Both environments must be declared, otherwise a misreading implies
    # production silently moved with the preview binding.
    assert {"preview", "production"} <= set(config["env"])

    production = _env_binding(config, "production")
    preview = _env_binding(config, "preview")

    # Production stays on the production namespace and binding name.
    assert production["binding"] == BINDING

    # Preview keeps the binding NAME the Functions read, but must resolve to a
    # dedicated namespace that is not production's.
    #
    # The namespace ids are opaque hex, so the property has to be stated in terms
    # of the ids themselves: both are real 32-hex ids, neither is a leftover
    # placeholder, and they differ. An earlier revision asserted that the staging
    # namespace TITLE appeared inside the id, which passed only because the
    # placeholder string happened to contain that title and proved nothing once
    # a real id was substituted.
    assert preview["binding"] == BINDING
    for label, entry in (("production", production), ("preview", preview)):
        assert re.fullmatch(r"[0-9a-f]{32}", entry["id"]), (
            f"the {label} KV binding id must be a real namespace id, "
            f"found {entry['id']!r} — a placeholder or a title is not a binding"
        )
        assert "REPLACE" not in entry["id"].upper(), (
            f"the {label} KV binding id is still a placeholder: {entry['id']!r}"
        )
    assert preview["id"] != production["id"], (
        "preview and production must not share a KV namespace, which is the "
        "defect this file exists to prevent"
    )

    # The top-level default is production; only preview may move off it.
    top_level = [
        entry for entry in config["kv_namespaces"] if entry.get("binding") == BINDING
    ]
    assert len(top_level) == 1
    assert top_level[0]["id"] == production["id"]


def test_staging_deploy_uses_a_stable_branch() -> None:
    preview_run = _step(PREVIEW_DEPLOY)["run"]

    branch = re.search(r"--branch=(\S+)", preview_run)
    assert branch is not None, "the staging deploy must pass an explicit --branch"
    assert branch.group(1) == STAGING_BRANCH
    assert STAGING_BRANCH != "main"
    assert "github.run_id" not in preview_run
    assert "GITHUB_RUN_ID" not in preview_run

    served_run = _step(
        "Verify isolated Pages preview before production promotion"
    )["run"]
    assert f'preview_branch="{STAGING_BRANCH}"' in served_run
    assert "GITHUB_RUN_ID" not in served_run


def test_production_deploy_is_gated_on_the_staging_deploy() -> None:
    preview = _step(PREVIEW_DEPLOY)
    production = _step(PRODUCTION_DEPLOY)

    assert preview["id"] == "deploy_preview"
    assert production.get("if") == "steps.deploy_preview.outcome == 'success'"

    # The production branch itself is unchanged by this isolation work.
    assert "--branch=main" in production["run"]


def _assert_pr_preview_isolated(text: str) -> None:
    workflow = yaml.safe_load(text)
    assert set(workflow.get("on", workflow.get(True, {}))) == {"pull_request"}
    assert workflow["permissions"] == {"contents": "read"}
    assert set(workflow["jobs"]) == {"build"}
    assert "secrets." not in text
    assert "environment:" not in text
    assert "pages deploy" not in text
    assert "pull_request_target" not in text
    assert "write" not in json.dumps(workflow["permissions"])
    build = workflow["jobs"]["build"]
    assert "if" not in build, "forks must be allowed to build"
    checkout = build["steps"][0]
    assert checkout["uses"] == "actions/checkout@v4"
    assert checkout["with"] == {"persist-credentials": False, "ref": "${{ github.event.pull_request.head.sha }}"}
    upload = build["steps"][-1]
    assert upload["uses"] == "actions/upload-artifact@v4"
    assert upload["with"] == {
        "name": "preview-pages-${{ github.run_id }}-${{ github.run_attempt }}",
        "path": "${{ runner.temp }}/preview-artifact/", "if-no-files-found": "error",
        "include-hidden-files": True, "retention-days": 1,
    }
    assert "outputs" not in build, "PR outputs must not supply deployment commands"
    assert not any(step.get("continue-on-error") for step in build["steps"])


def _assert_trusted_preview_isolated(text: str) -> None:
    workflow = yaml.safe_load(text)
    assert workflow["on"] == {"workflow_run": {"workflows": ["Verify pull request preview"], "types": ["completed"]}}
    assert workflow["permissions"] == {}
    assert "pull_request_target" not in text
    assert "actions/checkout" not in text and "actions/cache" not in text
    assert "scripts/" not in text
    assert "github.event.pull_request" not in text
    assert "--branch=main" not in text and "data-pulse.my" not in text
    assert "secrets.CLOUDFLARE_API_TOKEN" not in text
    jobs = workflow["jobs"]
    assert set(jobs) == {"validate", "deploy_preview", "preview"}
    assert jobs["validate"]["permissions"] == {"actions": "read", "contents": "read", "pull-requests": "read"}
    deploy = jobs["deploy_preview"]
    assert deploy["needs"] == "validate" and deploy["environment"] == "datapulse-preview"
    assert deploy["permissions"] == jobs["validate"]["permissions"]
    assert "env" not in deploy
    steps = deploy["steps"]
    assert steps[0]["name"] == "Revalidate run and PR after environment approval"
    assert steps[1]["name"] == "Verify protected environment and secret provenance"
    assert steps[2]["name"] == "Download and verify immutable static archive"
    assert steps[2]["env"]["EXPECTED_STATE"] == "${{ needs.validate.outputs.state }}"
    assert sum("secrets." in json.dumps(step) for step in steps) == 1
    credential = next(step for step in steps if step.get("id") == "deploy_preview")
    assert credential["env"] == {
        "CLOUDFLARE_PREVIEW_API_TOKEN": "${{ secrets.CLOUDFLARE_PREVIEW_API_TOKEN }}",
        "CLOUDFLARE_ACCOUNT_ID": "${{ vars.CLOUDFLARE_ACCOUNT_ID }}",
        "PR_NUMBER": "${{ fromJSON(needs.validate.outputs.state).pr_number }}",
        "PREVIEW_HEAD_SHA": "${{ fromJSON(needs.validate.outputs.state).head_sha }}",
    }
    assert "--project-name=datapulse-p4b-preview" in credential["run"]
    assert 'branch="pr-$PR_NUMBER"' in credential["run"]
    assert '--branch="$branch" --commit-hash="$PREVIEW_HEAD_SHA"' in credential["run"]
    assert '[[ "$branch" =~ ^pr-[0-9]+$ ]]' in credential["run"]
    assert 'preview_url="https://${branch}.datapulse-p4b-preview.pages.dev"' in credential["run"]
    assert "npx" not in credential["run"]
    assert "--ignore-scripts" in steps[3]["run"]
    assert jobs["preview"]["needs"] == ["validate", "deploy_preview"]
    assert jobs["preview"]["if"] == "always()"
    assert jobs["preview"]["permissions"]["checks"] == "write"
    assert "environment" not in jobs["preview"]
    for job in jobs.values():
        assert "env" not in job
        for step in job["steps"]:
            assert not step.get("continue-on-error")
            assert "uses" not in step, "privileged jobs execute only fixed inline programs"
            assert "${{" not in step["run"], "event data must never be interpolated into commands"


def test_pull_request_preview_workflow_cannot_deploy_to_production() -> None:
    _assert_pr_preview_isolated(PR_PREVIEW_WORKFLOW.read_text())
    _assert_trusted_preview_isolated(TRUSTED_PREVIEW_WORKFLOW.read_text())


@pytest.mark.parametrize(("old", "new"), [
    ("pull_request:", "pull_request_target:"), ("contents: read", "contents: write"),
    ("persist-credentials: false", "persist-credentials: true"),
    ("name: Build release artifact", "name: Build release artifact\n        env: {TOKEN: '${{ secrets.CLOUDFLARE_PREVIEW_API_TOKEN }}'}"),
])
def test_pr_preview_contract_rejects_unsafe_mutations(old: str, new: str) -> None:
    text = PR_PREVIEW_WORKFLOW.read_text()
    assert old in text
    with pytest.raises(AssertionError):
        _assert_pr_preview_isolated(text.replace(old, new, 1))


@pytest.mark.parametrize(("old", "new"), [
    ("workflow_run:", "pull_request_target:"),
    ("environment: datapulse-preview", "environment: unprotected"),
    ("secrets.CLOUDFLARE_PREVIEW_API_TOKEN", "secrets.CLOUDFLARE_API_TOKEN"),
    ("--project-name=datapulse-p4b-preview", "--project-name=datapulse-production"),
    ('--branch="$branch"', '--branch=main'), ("if: always()", "if: success()"),
    ("python3 - <<'PY'", "bash scripts/deploy.sh\n        python3 - <<'PY'"),
    ("python3 - <<'PY'", "echo '${{ github.event.workflow_run.head_branch }}'\n        python3 - <<'PY'"),
])
def test_trusted_preview_contract_rejects_unsafe_mutations(old: str, new: str) -> None:
    text = TRUSTED_PREVIEW_WORKFLOW.read_text()
    assert old in text
    with pytest.raises(AssertionError):
        _assert_trusted_preview_isolated(text.replace(old, new, 1))


def test_pr_preview_signer_is_temporary_and_removed_before_packaging() -> None:
    text = PR_PREVIEW_WORKFLOW.read_text(encoding="utf-8")
    steps = yaml.safe_load(text)["jobs"]["build"]["steps"]
    build = next(step["run"] for step in steps if step["name"] == "Build release artifact")
    assert 'umask 077' in build
    assert 'mktemp -d "$RUNNER_TEMP/datapulse-preview-signer.XXXXXX"' in build
    assert 'export DATAPULSE_ATTESTATION_PRIVATE_KEY_FILE="$signer_dir/private-key.json"' in build
    assert "trap 'rm -f \"$DATAPULSE_ATTESTATION_PRIVATE_KEY_FILE\"; rmdir \"$signer_dir\"' EXIT" in build
    assert "python3 scripts/init_keys.py" in build
    assert '--purpose attestation-chain-signing' in build
    assert '--registry docs/.well-known/datapulse-probe-keys.json' in build
    assert build.index("scripts/init_keys.py") < build.index("bash scripts/generate.sh release-build")
    assert build.count("reuse_existing_day") >= 2
    assert 'registry["current_key_id"]' in build
    assert "--force" not in build
    assert "GITHUB_ENV" not in build
    assert "GITHUB_OUTPUT" not in build
    assemble = next(step["run"] for step in steps if step["name"] == "Assemble canonical Pages artifact")
    assert "private_key_base64|BEGIN ([A-Z0-9]+ )?PRIVATE KEY" in assemble
    assert "DATAPULSE_ATTESTATION_PRIVATE_KEY_FILE" not in assemble
    assert 'cp -R functions _site/' not in assemble, "preview artifact is static"


@pytest.mark.parametrize("reuse", [False, True], ids=["fresh", "same-day-reuse"])
@pytest.mark.parametrize("fail_build", [False, True], ids=["success", "build-failure"])
def test_pr_preview_executes_safe_signer_lifecycle(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, reuse: bool, fail_build: bool,
) -> None:
    """Execute the workflow's signer shell with real generation and verification.

    Release generation unrelated to signing is excluded; no network is used.
    """
    root = tmp_path / "checkout"
    runner = tmp_path / "runner"
    runner.mkdir()
    now = datetime.now(timezone.utc)
    observed_at = now.isoformat()
    inputs = {
        "datapulse.json": {"datasets": [{"id": "sample", "url": "https://example.test/data"}]},
        "health/latest.json": {
            "checked_at": observed_at,
            "datasets": [{"dataset_id": "sample", "status": "fresh", "last_checked": observed_at}],
        },
        "health/trends.json": {"datasets": []},
        "health/drift.json": {"datasets": []},
        "health/reconciliation.json": {"groups": []},
    }
    for relative, value in inputs.items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value), encoding="utf-8")
    scripts = root / "scripts"
    scripts.mkdir()
    (scripts / "init_keys.py").write_bytes((ROOT / "scripts/init_keys.py").read_bytes())
    registry_path = root / "docs/.well-known/datapulse-probe-keys.json"
    old_key = runner / "previous-test-key.json"
    subprocess.run(
        [sys.executable, str(scripts / "init_keys.py"), "--private-key", str(old_key),
         "--registry", str(registry_path), "--purpose", "attestation-chain-signing"],
        check=True, capture_output=True, text=True,
    )
    # Signing time must follow creation of the key's not_before timestamp.
    now = datetime.now(timezone.utc)
    registry = json.loads(registry_path.read_text())
    old_rows = registry["keys"]
    old_id = old_rows[0]["key_id"]
    registry["current_key_id"] = old_id
    registry_path.write_text(json.dumps(registry), encoding="utf-8")
    monkeypatch.setattr(gen_attestations, "discover_git_anchors", lambda _: {})
    if reuse:
        gen_attestations.generate(root, old_key, now)
    old_key.unlink()
    dated = root / "attestations" / now.date().isoformat()
    immutable = {path.name: path.read_bytes() for path in dated.glob("*.json")}

    steps = yaml.safe_load(PR_PREVIEW_WORKFLOW.read_text())["jobs"]["build"]["steps"]
    build = next(step["run"] for step in steps if step["name"] == "Build release artifact")
    setup = build.split("export DATAPULSE_SOURCE_COMMIT_DATE=", 1)[0]
    verification = build.split("bash scripts/generate.sh release-build\n", 1)[1].split(
        "python3 scripts/gen_per_dataset_receipt.py", 1,
    )[0]
    generate = """python3 - <<'PY'
import os
import stat
from datetime import datetime, timezone
from pathlib import Path
from scripts import gen_attestations
key = Path(os.environ["DATAPULSE_ATTESTATION_PRIVATE_KEY_FILE"])
assert key.parent.parent == Path(os.environ["RUNNER_TEMP"])
assert stat.S_IMODE(key.stat().st_mode) == 0o600
assert stat.S_IMODE(key.parent.stat().st_mode) == 0o700
gen_attestations.discover_git_anchors = lambda _: {}
gen_attestations.generate(Path.cwd(), key, datetime.now(timezone.utc))
PY
"""
    environment = {
        "PATH": f"{Path(sys.executable).parent}:{os.defpath}",
        "PYTHONPATH": str(ROOT),
        "RUNNER_TEMP": str(runner),
    }
    result = subprocess.run(
        ["bash", "-c", setup + generate + ("exit 7\n" if fail_build else verification)],
        cwd=root, env=environment, capture_output=True, text=True,
    )
    assert result.returncode == (7 if fail_build else 0), result.stderr
    assert not list(runner.iterdir()), "temporary private key must be removed on either exit path"
    registry = json.loads(registry_path.read_text())
    assert registry["keys"][:-1] == old_rows, "historical public registry rows must survive"
    temporary_id = registry["keys"][-1]["key_id"]
    assert temporary_id != old_id
    binding = json.loads((dated / "binding.json").read_text())
    assert registry["current_key_id"] == binding["payload"]["ed25519"]["key_id"]
    assert gen_attestations.reuse_existing_day(root, now.date().isoformat())
    if reuse:
        assert registry["current_key_id"] == old_id
        assert {path.name: path.read_bytes() for path in dated.glob("*.json")} == immutable
        assert "no temporary signature claimed" in result.stdout
    else:
        assert registry["current_key_id"] == temporary_id
    if not fail_build:
        assert "Preview attestation signatures verified" in result.stdout
    # Public JSON and logs may carry public keys, never private-key fields.
    assert all("private_key_base64" not in path.read_text() for path in root.rglob("*.json"))
    assert "private_key_base64" not in result.stdout + result.stderr
    binding_path = dated / "binding.json"
    verified_binding = binding_path.read_bytes()
    binding["signature_base64"] = "AA=="
    binding_path.write_text(json.dumps(binding), encoding="utf-8")
    with pytest.raises(ValueError, match="same-day attestation is corrupt"):
        gen_attestations.reuse_existing_day(root, now.date().isoformat())
    binding_path.write_bytes(verified_binding)


@pytest.mark.parametrize(
    "content", ["public artifact", '{"private_key_base64": "test marker"}',
                "-----BEGIN PRIVATE KEY-----", None],
    ids=["public", "private-json", "private-pem", "scan-error"],
)
def test_pr_preview_artifact_scan_fails_closed(tmp_path: Path, content: str | None) -> None:
    steps = yaml.safe_load(PR_PREVIEW_WORKFLOW.read_text())["jobs"]["build"]["steps"]
    assemble = next(step["run"] for step in steps if step["name"] == "Assemble canonical Pages artifact")
    scan = "private_scan_status=0" + assemble.split("private_scan_status=0", 1)[1]
    if content is not None:
        site = tmp_path / "_site"
        site.mkdir()
        (site / "artifact.txt").write_text(content, encoding="utf-8")
    result = subprocess.run(["bash", "-c", scan], cwd=tmp_path, capture_output=True, text=True)
    assert result.returncode == (0 if content == "public artifact" else 1)
    assert "test marker" not in result.stdout + result.stderr


def test_pr_preview_missing_token_fails_without_deploying() -> None:
    steps = yaml.safe_load(TRUSTED_PREVIEW_WORKFLOW.read_text())["jobs"]["deploy_preview"]["steps"]
    deploy = next(step for step in steps if step.get("id") == "deploy_preview")
    result = subprocess.run(
        ["bash", "-c", deploy["run"]],
        env={"PATH": os.defpath, "CLOUDFLARE_PREVIEW_API_TOKEN": ""},
        capture_output=True, text=True,
    )
    assert result.returncode == 1
    assert "protected datapulse-preview environment must provide" in result.stderr


def _deploy_step(name: str) -> dict[str, Any]:
    steps = yaml.safe_load(TRUSTED_PREVIEW_WORKFLOW.read_text())["jobs"]["deploy_preview"]["steps"]
    return next(step for step in steps if step.get("name") == name)


def _inline_python(step: dict[str, Any]) -> str:
    return step["run"].split("python3 - <<'PY'\n", 1)[1].split("\nPY", 1)[0]


@pytest.mark.parametrize(
    "case", ["protected", "missing-environment", "unprotected", "empty-reviewers",
             "repository-secret-only", "wrong-secret", "denied-metadata", "invalid-metadata",
             "unrestricted-branches", "all-protected-branches", "wildcard-branch", "tag-policy",
             "extra-branch", "missing-branch-policy"],
)
def test_pr_preview_environment_provenance_fails_closed(case: str) -> None:
    """Exercise metadata responses; no credential value or live API is read."""
    verifier = _inline_python(_deploy_step("Verify protected environment and secret provenance"))
    environment = {"name": "datapulse-preview", "protection_rules": [
        {"type": "required_reviewers", "reviewers": [{"type": "User", "reviewer": {"id": 1}}]},
    ], "deployment_branch_policy": {"protected_branches": False, "custom_branch_policies": True}}
    branch_policies = {"total_count": 1, "branch_policies": [{"name": "main", "type": "branch"}]}
    secret = {"name": "CLOUDFLARE_PREVIEW_API_TOKEN"}
    if case == "unprotected":
        environment["protection_rules"] = []
    if case == "empty-reviewers":
        environment["protection_rules"][0]["reviewers"] = []
    if case == "wrong-secret":
        secret["name"] = "CLOUDFLARE_API_TOKEN"
    if case == "unrestricted-branches":
        environment["deployment_branch_policy"] = None
    if case == "all-protected-branches":
        environment["deployment_branch_policy"] = {"protected_branches": True, "custom_branch_policies": False}
    if case == "wildcard-branch":
        branch_policies["branch_policies"][0]["name"] = "*"
    if case == "tag-policy":
        branch_policies["branch_policies"][0]["type"] = "tag"
    if case == "extra-branch":
        branch_policies["total_count"] = 2
        branch_policies["branch_policies"].append({"name": "feature/*", "type": "branch"})
    if case == "missing-branch-policy":
        branch_policies = {"total_count": 0, "branch_policies": []}
    stub = f'''import io, json, urllib.request
from urllib.error import HTTPError
environment = {environment!r}
secret = {secret!r}
branch_policies = {branch_policies!r}
case = {case!r}
def metadata(request, timeout):
    url = request.full_url
    if case in ("denied-metadata", "missing-environment") or (case == "repository-secret-only" and "/secrets/" in url):
        raise HTTPError(url, 403 if case == "denied-metadata" else 404, "denied", {{}}, None)
    if case == "invalid-metadata":
        return io.BytesIO(b"invalid JSON")
    assert url.startswith("https://api.github.test/repos/owner/repo/environments/datapulse-preview")
    value = secret if "/secrets/" in url else branch_policies if "/deployment-branch-policies" in url else environment
    return io.BytesIO(json.dumps(value).encode())
urllib.request.urlopen = metadata
'''
    result = subprocess.run(
        [sys.executable, "-c", stub + verifier], capture_output=True, text=True,
        env={"PATH": os.defpath, "GITHUB_REPOSITORY": "owner/repo",
             "GITHUB_API_URL": "https://api.github.test", "GH_TOKEN": "unused-test-value"},
    )
    assert result.returncode == (0 if case == "protected" else 1), result.stderr
    assert "unused-test-value" not in result.stdout + result.stderr
    if case != "protected":
        assert "This staged check has not passed" in result.stderr


def test_pr_preview_change_preserves_production_workflow_byte_exactly() -> None:
    baseline = subprocess.run(
        ["git", "show", "origin/main:.github/workflows/deploy-cloudflare-pages.yml"],
        cwd=ROOT, check=True, capture_output=True,
    ).stdout
    assert WORKFLOW.read_bytes() == baseline


def _trusted_step(job: str, name: str) -> dict[str, Any]:
    workflow = yaml.safe_load(TRUSTED_PREVIEW_WORKFLOW.read_text())
    return next(step for step in workflow["jobs"][job]["steps"] if step["name"] == name)


def _run_payload_program(
    tmp_path: Path, code: str, event: dict[str, Any], responses: dict[str, Any],
    overrides: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    """Run the actual workflow program, replacing only the GitHub HTTP boundary."""
    payload = tmp_path / "event.json"
    payload.write_text(json.dumps(event))
    fixtures = tmp_path / "responses.json"
    fixtures.write_text(json.dumps(responses))
    stub = '''import io, json, os, urllib.request
from pathlib import Path
responses = json.loads(Path(os.environ["TEST_RESPONSES"]).read_text())
def urlopen(request, timeout):
    prefix = "https://api.github.test/repos/r3dz4r/datapulse-my"
    assert request.full_url.startswith(prefix)
    path = request.full_url.removeprefix(prefix)
    if request.data is not None:
        assert path == "/check-runs"
        Path(os.environ["TEST_CHECK"]).write_bytes(request.data)
        return io.BytesIO(b'{}')
    if path not in responses:
        raise OSError("metadata unavailable")
    return io.BytesIO(json.dumps(responses[path]).encode())
urllib.request.urlopen = urlopen
'''
    environment = {
        "PATH": os.defpath, "GITHUB_REPOSITORY": "r3dz4r/datapulse-my",
        "GITHUB_REF": "refs/heads/main",
        "GITHUB_WORKFLOW_REF": "r3dz4r/datapulse-my/.github/workflows/preview-deploy.yml@refs/heads/main",
        "GITHUB_API_URL": "https://api.github.test", "GITHUB_EVENT_PATH": str(payload),
        "GITHUB_OUTPUT": str(tmp_path / "output"), "GITHUB_RUN_ID": "999",
        "GH_TOKEN": "unused-test-token", "TEST_RESPONSES": str(fixtures),
        "TEST_CHECK": str(tmp_path / "check.json"),
    }
    environment.update(overrides or {})
    result = subprocess.run([sys.executable, "-c", stub + code], env=environment,
                            cwd=tmp_path, capture_output=True, text=True)
    assert "unused-test-token" not in result.stdout + result.stderr
    return result


def _run_fixture() -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    repo = {"id": 7, "full_name": "r3dz4r/datapulse-my", "default_branch": "main"}
    run = {"id": 123, "run_attempt": 2, "workflow_id": 15,
           "name": "Verify pull request preview", "path": ".github/workflows/preview-verify.yml",
           "event": "pull_request", "status": "completed", "conclusion": "success",
           "head_sha": "a" * 40, "head_branch": "feature-$(touch-pwned)",
           "repository": repo, "head_repository": repo,
           "pull_requests": [{"number": 17, "head": {"sha": "a" * 40}}]}
    artifact = {"id": 456, "name": "preview-pages-123-2", "expired": False,
                "size_in_bytes": 1000, "digest": "sha256:" + "b" * 64,
                "workflow_run": {"id": 123, "repository_id": 7, "head_repository_id": 7,
                                 "head_sha": "a" * 40}}
    responses = {
        "": repo, "/branches/main": {"protected": True}, "/actions/runs/123": copy.deepcopy(run),
        "/actions/workflows/preview-verify.yml": {"id": 15, "name": run["name"], "path": run["path"], "state": "active"},
        "/pulls/17": {"number": 17, "state": "open",
                      "head": {"repo": repo, "sha": "a" * 40, "ref": run["head_branch"]},
                      "base": {"repo": repo, "ref": "main"}},
        "/actions/runs/123/artifacts?per_page=100": {"total_count": 1, "artifacts": [artifact]},
    }
    state = {"repository": repo["full_name"], "run_id": 123, "run_attempt": 2, "pr_number": 17,
             "head_sha": "a" * 40, "workflow": run["name"], "event": "pull_request",
             "artifact_id": 456, "artifact_digest": artifact["digest"], "artifact_size": 1000}
    return {"workflow_run": run}, responses, state


@pytest.mark.parametrize("case", [
    "valid", "valid-approved", "pr-definition", "wrong-ref", "unprotected-main", "wrong-default",
    "workflow-path", "workflow-name", "workflow-id", "inactive-workflow", "wrong-event",
    "failed-run", "incomplete-run", "fork", "cross-repository-run", "missing-pr", "ambiguous-pr",
    "stale-attempt", "closed-pr", "stale-head", "fork-pr", "wrong-base", "wrong-branch",
    "missing-artifact", "ambiguous-artifact", "expired", "artifact-attempt", "artifact-run",
    "artifact-repository", "artifact-fork", "artifact-head", "missing-digest", "oversize",
    "denied-metadata", "changed-during-approval",
])
def test_trusted_preview_provenance_uses_real_event_and_api_shapes(tmp_path: Path, case: str) -> None:
    event, responses, state = _run_fixture()
    trigger = event["workflow_run"]
    run = responses["/actions/runs/123"]
    workflow = responses["/actions/workflows/preview-verify.yml"]
    pr = responses["/pulls/17"]
    artifacts = responses["/actions/runs/123/artifacts?per_page=100"]
    artifact = artifacts["artifacts"][0]
    overrides = {}
    if case == "pr-definition": overrides["GITHUB_WORKFLOW_REF"] = "r3dz4r/datapulse-my/.github/workflows/preview-deploy.yml@refs/pull/17/merge"
    elif case == "wrong-ref": overrides["GITHUB_REF"] = "refs/pull/17/merge"
    elif case == "unprotected-main": responses["/branches/main"]["protected"] = False
    elif case == "wrong-default": responses[""]["default_branch"] = "other"
    elif case == "workflow-path": trigger["path"] = ".github/workflows/evil.yml"
    elif case == "workflow-name": trigger["name"] = "Other workflow"
    elif case == "workflow-id": trigger["workflow_id"] = 99
    elif case == "inactive-workflow": workflow["state"] = "disabled_manually"
    elif case == "wrong-event": trigger["event"] = "pull_request_target"
    elif case == "failed-run": run["conclusion"] = "failure"
    elif case == "incomplete-run": run["status"] = "in_progress"
    elif case == "fork": trigger["head_repository"] = {"id": 9, "full_name": "fork/repo"}
    elif case == "cross-repository-run": trigger["repository"] = {"id": 9, "full_name": "other/repo"}
    elif case == "missing-pr": trigger["pull_requests"] = []
    elif case == "ambiguous-pr": trigger["pull_requests"] *= 2
    elif case == "stale-attempt": run["run_attempt"] = 3
    elif case == "closed-pr": pr["state"] = "closed"
    elif case == "stale-head": pr["head"]["sha"] = "c" * 40
    elif case == "fork-pr": pr["head"]["repo"] = {"id": 9, "full_name": "fork/repo"}
    elif case == "wrong-base": pr["base"]["ref"] = "release"
    elif case == "wrong-branch": pr["head"]["ref"] = "other-branch"
    elif case == "missing-artifact": artifacts.update(total_count=0, artifacts=[])
    elif case == "ambiguous-artifact": artifacts.update(total_count=2, artifacts=[artifact, artifact])
    elif case == "expired": artifact["expired"] = True
    elif case == "artifact-attempt": artifact["name"] = "preview-pages-123-1"
    elif case == "artifact-run": artifact["workflow_run"]["id"] = 100
    elif case == "artifact-repository": artifact["workflow_run"]["repository_id"] = 9
    elif case == "artifact-fork": artifact["workflow_run"]["head_repository_id"] = 9
    elif case == "artifact-head": artifact["workflow_run"]["head_sha"] = "c" * 40
    elif case == "missing-digest": artifact["digest"] = None
    elif case == "oversize": artifact["size_in_bytes"] = 201 * 1024 * 1024
    elif case == "denied-metadata": responses.pop("/branches/main")
    elif case in {"valid-approved", "changed-during-approval"}:
        if case == "changed-during-approval":
            state["artifact_id"] = 999
        overrides["EXPECTED_STATE"] = json.dumps(state)
    job, name = ("deploy_preview", "Revalidate run and PR after environment approval") if case in {"valid-approved", "changed-during-approval"} else ("validate", "Validate protected-main and triggering build provenance")
    result = _run_payload_program(tmp_path, _inline_python(_trusted_step(job, name)), event, responses, overrides)
    assert result.returncode == (0 if case in {"valid", "valid-approved"} else 1), result.stderr
    assert not (tmp_path / "pwned").exists(), "PR-controlled branch text must stay data"
    if case in {"valid", "valid-approved"}:
        assert json.loads((tmp_path / "output").read_text().removeprefix("state=")) == state
    else:
        assert not (tmp_path / "output").exists()


def _archive_fixture(tmp_path: Path) -> tuple[dict[str, bytes], dict[str, Any]]:
    site = tmp_path / "build-site"
    site.mkdir()
    for name in ("index.html", "404.html", "_headers", "_redirects", "datapulse.json",
                 "health/latest.json", "health/history.jsonl", "health/archives/month.jsonl.gz",
                 ".well-known/datapulse-probe-keys.json"):
        path = site / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("static public bytes\n")
    manifest_path = tmp_path / "manifest.json"
    verify_release_artifact.create_manifest(site, manifest_path, "a" * 40)
    files = {"_site/" + str(path.relative_to(site)): path.read_bytes() for path in site.rglob("*") if path.is_file()}
    files["release-artifact-manifest.json"] = manifest_path.read_bytes()
    _, _, state = _run_fixture()
    binding = {key: state[key] for key in ("repository", "run_id", "run_attempt", "pr_number", "head_sha", "workflow", "event")}
    binding["manifest_sha256"] = hashlib.sha256(manifest_path.read_bytes()).hexdigest()
    files["preview-binding.json"] = json.dumps(binding).encode()
    return files, state


@pytest.mark.parametrize("case", [
    "valid", "site-bytes", "extra-file", "missing-static", "wrong-manifest-source", "aggregate",
    "manifest-hash", "duplicate-json", "binding-repository", "binding-run", "binding-attempt",
    "binding-pr", "binding-head", "binding-workflow", "binding-event", "archive-digest", "archive-size",
    "traversal", "absolute", "backslash", "duplicate-path", "symlink", "fifo", "executable",
    "functions-directory", "worker", "nested-config", "script", "root-member", "private-json", "private-pem",
    "oversize-member", "member-count", "expanded-total", "untrusted-storage", "download-error",
])
def test_privileged_archive_validation_rejects_attacker_data_before_writing(
    tmp_path: Path, case: str,
) -> None:
    files, state = _archive_fixture(tmp_path)
    manifest = json.loads(files["release-artifact-manifest.json"])
    binding = json.loads(files["preview-binding.json"])
    if case.startswith("binding-"):
        key = {"repository": "repository", "run": "run_id", "attempt": "run_attempt", "pr": "pr_number",
               "head": "head_sha", "workflow": "workflow", "event": "event"}[case.removeprefix("binding-")]
        binding[key] = 999 if type(binding[key]) is int else "wrong"
    elif case == "manifest-hash": binding["manifest_sha256"] = "0" * 64
    elif case == "site-bytes": files["_site/index.html"] = b"tampered"
    elif case == "extra-file": files["_site/extra.json"] = b"extra"
    elif case == "missing-static": files.pop("_site/404.html")
    elif case == "wrong-manifest-source": manifest["source_commit"] = "c" * 40
    elif case == "aggregate": manifest["aggregate_sha256"] = "0" * 64
    elif case == "traversal": files["_site/../../escape.json"] = b"bad"
    elif case == "absolute": files["/escape.json"] = b"bad"
    elif case == "backslash": files["_site\\escape.json"] = b"bad"
    elif case == "functions-directory": files["_site/functions/"] = b""
    elif case == "worker": files["_site/_worker.js"] = b"throw Error('no execution')"
    elif case == "nested-config": files["_site/assets/wrangler.json"] = b"{}"
    elif case == "script": files["_site/evil.sh"] = b"touch pwned"
    elif case == "root-member": files["package.json"] = b"{}"
    elif case == "private-json": files["_site/evil.json"] = b'{"private_key_base64":"test marker"}'
    elif case == "private-pem": files["_site/evil.txt"] = b"-----BEGIN RSA PRIVATE KEY-----"
    elif case == "oversize-member": files["_site/large.json"] = b"x" * (25 * 1024 * 1024 + 1)
    elif case == "member-count": files.update({f"_site/{i}.json": b"" for i in range(25001)})
    elif case == "expanded-total":
        large_static = b"x" * (25 * 1024 * 1024)
        files.update({f"_site/{i}.json": large_static for i in range(21)})
    if case in {"wrong-manifest-source", "aggregate"}:
        files["release-artifact-manifest.json"] = json.dumps(manifest).encode()
        binding["manifest_sha256"] = hashlib.sha256(files["release-artifact-manifest.json"]).hexdigest()
    files["preview-binding.json"] = json.dumps(binding).encode()
    if case == "duplicate-json":
        files["preview-binding.json"] = files["preview-binding.json"][:-1] + b',"pr_number":17}'
    archive_path = tmp_path / "download.zip"
    with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, content in files.items(): archive.writestr(name, content)
        if case == "duplicate-path":
            with pytest.warns(UserWarning, match="Duplicate name"):
                archive.writestr("_site/index.html", b"duplicate")
        if case in {"symlink", "fifo", "executable"}:
            entry = zipfile.ZipInfo("_site/special.json")
            entry.create_system = 3
            mode = {"symlink": stat.S_IFLNK | 0o777, "fifo": stat.S_IFIFO | 0o600,
                    "executable": stat.S_IFREG | 0o755}[case]
            entry.external_attr = mode << 16
            archive.writestr(entry, b"index.html")
    raw = archive_path.read_bytes()
    state.update(artifact_size=len(raw), artifact_digest="sha256:" + hashlib.sha256(raw).hexdigest())
    if case == "archive-digest": state["artifact_digest"] = "sha256:" + "0" * 64
    elif case == "archive-size": state["artifact_size"] += 1
    stub = '''import io, os, urllib.request
from pathlib import Path
from urllib.error import HTTPError
class Response(io.BytesIO):
    pass
class Opener:
    def open(self, request, timeout):
        if isinstance(request, urllib.request.Request):
            assert request.full_url == "https://api.github.test/repos/r3dz4r/datapulse-my/actions/artifacts/456/zip"
            if os.environ["TEST_CASE"] == "download-error":
                raise HTTPError(request.full_url, 403, "denied", {}, None)
            host = "evil.test" if os.environ["TEST_CASE"] == "untrusted-storage" else "test.blob.core.windows.net"
            raise HTTPError(request.full_url, 302, "found", {"Location": "https://" + host + "/archive"}, None)
        assert isinstance(request, str), "token must not be forwarded to storage"
        return Response(Path(os.environ["TEST_ARCHIVE"]).read_bytes())
urllib.request.build_opener = lambda *args: Opener()
'''
    result = subprocess.run([sys.executable, "-c", stub + _inline_python(_deploy_step("Download and verify immutable static archive"))],
                            cwd=tmp_path, capture_output=True, text=True,
                            env={"PATH": os.defpath, "RUNNER_TEMP": str(tmp_path), "EXPECTED_STATE": json.dumps(state),
                                 "GH_TOKEN": "unused-test-token", "GITHUB_API_URL": "https://api.github.test",
                                 "GITHUB_REPOSITORY": "r3dz4r/datapulse-my", "TEST_CASE": case,
                                 "TEST_ARCHIVE": str(archive_path)})
    assert result.returncode == (0 if case == "valid" else 1), result.stderr
    assert "unused-test-token" not in result.stdout + result.stderr
    if case == "valid":
        assert (tmp_path / "preview-artifact/_site/index.html").read_bytes() == files["_site/index.html"]
    else:
        assert not (tmp_path / "preview-artifact").exists(), "Reject before extraction or credential access"
    assert not (tmp_path / "escape.json").exists()
    assert not (tmp_path / "pwned").exists()


@pytest.mark.parametrize(("validate", "deploy", "mutation", "expected"), [
    ("success", "success", None, "success"),
    ("failure", "skipped", None, "failure"), ("success", "failure", None, "failure"),
    ("success", "skipped", None, "failure"), ("success", "cancelled", None, "failure"),
    ("cancelled", "skipped", None, "failure"),
    ("success", "success", "stale-head", "failure"), ("success", "success", "stale-attempt", "failure"),
    ("success", "success", "fork", "failure"), ("success", "success", "closed", "failure"),
])
def test_required_preview_check_never_treats_missing_actual_preview_as_success(
    tmp_path: Path, validate: str, deploy: str, mutation: str | None, expected: str,
) -> None:
    event, responses, state = _run_fixture()
    if mutation == "stale-head": responses["/pulls/17"]["head"]["sha"] = "c" * 40
    elif mutation == "stale-attempt": responses["/actions/runs/123"]["run_attempt"] = 3
    elif mutation == "fork": responses["/pulls/17"]["head"]["repo"] = {"full_name": "fork/repo"}
    elif mutation == "closed": responses["/pulls/17"]["state"] = "closed"
    result = _run_payload_program(tmp_path, _inline_python(_trusted_step("preview", "Publish fail-closed required preview check")),
                                  event, responses, {"VALIDATE_RESULT": validate, "DEPLOY_RESULT": deploy,
                                                     "EXPECTED_STATE": json.dumps(state)})
    check = json.loads((tmp_path / "check.json").read_text())
    assert check["name"] == "Build and verify isolated PR preview"
    assert check["head_sha"] == "a" * 40
    assert check["conclusion"] == expected
    assert result.returncode == (0 if expected == "success" else 1), result.stderr


def test_workflow_programs_are_syntax_valid_without_pr_expression_execution() -> None:
    for path in (PR_PREVIEW_WORKFLOW, TRUSTED_PREVIEW_WORKFLOW):
        workflow = yaml.safe_load(path.read_text())
        for job in workflow["jobs"].values():
            for step in job["steps"]:
                if "run" not in step: continue
                program = step["run"]
                result = subprocess.run(["bash", "-n"], input=program, capture_output=True, text=True)
                assert result.returncode == 0, (step["name"], result.stderr)
                for match in re.finditer(r"python3 (?:-[^\n]* )?<<'(PY|PYTHON)'\n(.*?)\n\1", program, re.DOTALL):
                    compile(match.group(2), str(path) + ":" + step["name"], "exec")


def test_pr_modified_workflow_and_scripts_cannot_supply_privileged_commands(tmp_path: Path) -> None:
    # Deliberately place a malicious PR workflow and script beside the verifier.
    # The actual main-owned program reads only payload/API metadata.
    malicious = tmp_path / ".github/workflows"
    malicious.mkdir(parents=True)
    (malicious / "preview-deploy.yml").write_text("run: touch pwned\n")
    (tmp_path / "deploy.sh").write_text("touch pwned\n")
    event, responses, _ = _run_fixture()
    result = _run_payload_program(tmp_path, _inline_python(_trusted_step("validate", "Validate protected-main and triggering build provenance")), event, responses)
    assert result.returncode == 0, result.stderr
    assert not (tmp_path / "pwned").exists()
    _assert_trusted_preview_isolated(TRUSTED_PREVIEW_WORKFLOW.read_text())


@pytest.mark.parametrize("case", ["valid", "symlink", "special", "nested-functions", "script", "private"])
def test_pr_upload_scanner_checks_real_static_members(tmp_path: Path, case: str) -> None:
    files, _ = _archive_fixture(tmp_path)
    root = tmp_path / "preview-artifact"
    for name, content in files.items():
        target = root / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
    extra = root / "_site/assets/extra.json"
    extra.parent.mkdir()
    if case == "symlink": extra.symlink_to(root / "_site/index.html")
    elif case == "special": os.mkfifo(extra)
    elif case == "nested-functions": (root / "_site/assets/functions").mkdir()
    elif case == "script": (root / "_site/evil.py").write_text("raise Exception('must not run')")
    elif case == "private": extra.write_text('{"private_key_base64":"test marker"}')
    if case != "valid": (root / "preview-binding.json").unlink()
    payload = tmp_path / "pr-event.json"
    payload.write_text('{"number":17}')
    build = yaml.safe_load(PR_PREVIEW_WORKFLOW.read_text())["jobs"]["build"]
    step = next(step for step in build["steps"] if step["name"] == "Package verified static artifact")
    program = step["run"].split("python3 - <<'PYTHON'\n", 1)[1].split("\nPYTHON", 1)[0]
    result = subprocess.run([sys.executable, "-c", program], capture_output=True, text=True,
                            env={"PATH": os.defpath, "RUNNER_TEMP": str(tmp_path),
                                 "GITHUB_EVENT_PATH": str(payload), "GITHUB_REPOSITORY": "r3dz4r/datapulse-my",
                                 "GITHUB_RUN_ID": "123", "GITHUB_RUN_ATTEMPT": "2", "PREVIEW_HEAD_SHA": "a" * 40})
    assert result.returncode == (0 if case == "valid" else 1), result.stderr
    assert (root / "preview-binding.json").exists() == (case == "valid")
    assert "test marker" not in result.stdout + result.stderr
    if case == "valid":
        binding = json.loads((root / "preview-binding.json").read_text())
        assert binding["pr_number"] == 17 and binding["head_sha"] == "a" * 40


@pytest.mark.parametrize("case", ["valid", "wrong-bytes", "redirect", "not-found"])
def test_served_preview_requires_exact_host_and_byte_identity(tmp_path: Path, case: str) -> None:
    files, _ = _archive_fixture(tmp_path)
    root = tmp_path / "preview-artifact"
    root.mkdir()
    (root / "release-artifact-manifest.json").write_bytes(files["release-artifact-manifest.json"])
    stub = '''import io, os, urllib.request
from urllib.error import HTTPError
class Response(io.BytesIO):
    status = 200
class Opener:
    def open(self, url, timeout):
        assert url in {"https://pr-17.datapulse-p4b-preview.pages.dev/", "https://pr-17.datapulse-p4b-preview.pages.dev/datapulse.json", "https://pr-17.datapulse-p4b-preview.pages.dev/health/latest.json"}
        case = os.environ["TEST_CASE"]
        if case in {"redirect", "not-found"}:
            raise HTTPError(url, 302 if case == "redirect" else 404, "rejected", {"Location":"https://evil.test/"}, None)
        return Response(b"wrong bytes" if case == "wrong-bytes" else b"static public bytes\\n")
def opener(*handlers):
    assert len(handlers) == 1
    handler = handlers[0]() if isinstance(handlers[0], type) else handlers[0]
    assert handler.redirect_request(None, None, 302, "redirect", {}, "https://evil.test/") is None
    return Opener()
urllib.request.build_opener = opener
'''
    result = subprocess.run([sys.executable, "-c", stub + _inline_python(_deploy_step("Verify served static preview"))],
                            capture_output=True, text=True,
                            env={"PATH": os.defpath, "RUNNER_TEMP": str(tmp_path), "TEST_CASE": case,
                                 "PREVIEW_URL": "https://pr-17.datapulse-p4b-preview.pages.dev"})
    assert result.returncode == (0 if case == "valid" else 1), result.stderr
    if case == "wrong-bytes":
        assert "Served preview does not match this build" in result.stderr
    elif case in {"redirect", "not-found"}:
        assert "HTTP Error" in result.stderr
