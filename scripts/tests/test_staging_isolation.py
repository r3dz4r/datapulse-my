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
* PR rehearsal uses a temporary signer and preview-only credentials, failing
  closed for forks while preserving immutable same-day attestations.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tomllib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest
import yaml

from scripts import gen_attestations


ROOT = Path(__file__).resolve().parents[2]
WRANGLER_CONFIG = ROOT / "wrangler.toml"
WORKFLOW = ROOT / ".github/workflows/deploy-cloudflare-pages.yml"
PR_PREVIEW_WORKFLOW = ROOT / ".github/workflows/preview-verify.yml"

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
    triggers = workflow.get("on", workflow.get(True, {}))
    assert set(triggers) == {"pull_request"}
    assert workflow["permissions"] == {"contents": "read"}
    assert "DATAPULSE_HEALTH_INDEX" not in text, "production KV namespace"
    assert "secrets.CLOUDFLARE_API_TOKEN" not in text, "production deploy token"
    assert "secrets.DATAPULSE_ATTESTATION" not in text, "production signing key"
    assert "--branch=main" not in text, "production branch"
    assert "--branch=production" not in text, "production branch"
    assert "data-pulse.my" not in text, "production origin"
    assert "env" not in workflow, "credentials must not be workflow-wide"
    job = workflow["jobs"]["preview"]
    assert "if" not in job, "a skipped job cannot count as staged verification"
    assert "env" not in job, "credentials must not be job-wide"
    steps = job["steps"]
    assert sum(step.get("id") == "deploy_preview" for step in steps) == 1
    fork = steps[0]
    assert fork["name"] == "Reject fork preview without credentials"
    assert fork["if"] == "github.event.pull_request.head.repo.full_name != github.repository"
    assert "exit 1" in fork["run"]
    assert "maintainer" in fork["run"].lower()
    assert "secrets." not in str(fork)
    checkout = steps[1]
    assert checkout["uses"] == "actions/checkout@v4"
    assert checkout["with"]["persist-credentials"] is False
    for step in steps:
        assert not step.get("continue-on-error", False)
        run = step.get("run", "")
        if "wrangler" in run and "pages deploy" in run:
            assert "if" not in step
            assert step["env"] == {
                "CLOUDFLARE_PREVIEW_API_TOKEN": "${{ secrets.CLOUDFLARE_PREVIEW_API_TOKEN }}",
                "CLOUDFLARE_ACCOUNT_ID": "${{ secrets.CLOUDFLARE_ACCOUNT_ID }}",
            }
            assert '[[ -n "$CLOUDFLARE_PREVIEW_API_TOKEN" ]]' in run
            assert 'CLOUDFLARE_API_TOKEN="$CLOUDFLARE_PREVIEW_API_TOKEN"' in run
            assert "--project-name=datapulse-p4b-preview" in run
            assert 'branch="pr-${{ github.event.pull_request.number }}"' in run
            assert '--branch="$branch"' in run
            assert len(re.findall(r"--branch=", run)) == 1
            assert len(re.findall(r"branch=", run)) == 2
            assert '[[ "$branch" =~ ^pr-[0-9]+$ ]]' in run
            assert r"https://[a-z0-9-]+\.datapulse-p4b-preview\.pages\.dev" in run
        elif "secrets." in str(step):
            raise AssertionError("credentials must be scoped to preview deployment")


def test_pull_request_preview_workflow_cannot_deploy_to_production() -> None:
    _assert_pr_preview_isolated(PR_PREVIEW_WORKFLOW.read_text(encoding="utf-8"))


@pytest.mark.parametrize(
    ("old", "new", "reason"),
    [
        ("secrets.CLOUDFLARE_PREVIEW_API_TOKEN", "secrets.CLOUDFLARE_API_TOKEN", "production deploy token"),
        ('--branch="$branch"', "--branch=main", "production branch"),
        ('--branch="$branch"', "--branch=production", "production branch"),
        ("--project-name=datapulse-p4b-preview", "--project-name=datapulse-production", ""),
        ("pull_request:", "pull_request_target:", ""),
        ("exit 1", "exit 0", ""),
        ("contents: read", "contents: write", ""),
        ("[a-z0-9-]+\\.datapulse-p4b-preview\\.pages\\.dev", "[A-Za-z0-9.-]+\\.pages\\.dev", ""),
    ],
)
def test_pr_preview_contract_rejects_unsafe_mutations(
    tmp_path: Path, old: str, new: str, reason: str,
) -> None:
    original = PR_PREVIEW_WORKFLOW.read_bytes()
    text = original.decode("utf-8")
    assert old in text
    corrupted = tmp_path / "corrupted-preview-verify.yml"
    corrupted.write_text(text.replace(old, new, 1), encoding="utf-8")
    with pytest.raises(AssertionError, match=reason or None):
        _assert_pr_preview_isolated(corrupted.read_text(encoding="utf-8"))
    assert PR_PREVIEW_WORKFLOW.read_bytes() == original
    _assert_pr_preview_isolated(original.decode("utf-8"))


def test_pr_preview_signer_is_temporary_and_removed_before_packaging() -> None:
    text = PR_PREVIEW_WORKFLOW.read_text(encoding="utf-8")
    steps = yaml.safe_load(text)["jobs"]["preview"]["steps"]
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
    assert "upload-artifact" not in text


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

    steps = yaml.safe_load(PR_PREVIEW_WORKFLOW.read_text())["jobs"]["preview"]["steps"]
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
    steps = yaml.safe_load(PR_PREVIEW_WORKFLOW.read_text())["jobs"]["preview"]["steps"]
    assemble = next(step["run"] for step in steps if step["name"] == "Assemble canonical Pages artifact")
    scan = "private_scan_status=0" + assemble.split("private_scan_status=0", 1)[1]
    if content is not None:
        site = tmp_path / "_site"
        site.mkdir()
        (site / "artifact.txt").write_text(content, encoding="utf-8")
    result = subprocess.run(["bash", "-c", scan], cwd=tmp_path, capture_output=True, text=True)
    assert result.returncode == (0 if content == "public artifact" else 1)
    assert "test marker" not in result.stdout + result.stderr


def test_pr_preview_fork_and_missing_token_fail_without_deploying() -> None:
    steps = yaml.safe_load(PR_PREVIEW_WORKFLOW.read_text())["jobs"]["preview"]["steps"]
    fork = steps[0]
    result = subprocess.run(["bash", "-c", fork["run"]], capture_output=True, text=True)
    assert result.returncode == 1
    assert "maintainer" in result.stdout.lower()
    deploy = next(step for step in steps if step.get("id") == "deploy_preview")
    result = subprocess.run(
        ["bash", "-c", deploy["run"]],
        env={"PATH": os.defpath, "CLOUDFLARE_PREVIEW_API_TOKEN": ""},
        capture_output=True, text=True,
    )
    assert result.returncode == 1
    assert "separate preview-scoped credential" in result.stderr
