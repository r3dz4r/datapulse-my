"""Executable isolation contract for the Cloudflare Pages staging environment.

This is the regression test for the staging-isolation defect: the Pages project
``datapulse-p4b-preview`` previously bound both its ``preview`` and
``production`` environments to the same ``DATAPULSE_HEALTH_INDEX`` KV namespace,
deployed staging on a throwaway per-run branch, and promoted production in the
same run with no gate on the staging deploy.

The tests below fail on the tree before the fix. They pin four properties:

* the repository declares per-environment KV bindings,
* the preview environment resolves to a namespace that is not production's,
* production is still declared and bound to ``DATAPULSE_HEALTH_INDEX``,
* the staging deploy uses a stable branch and production is gated on it.
"""

from __future__ import annotations

import re
import tomllib
from pathlib import Path
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parents[2]
WRANGLER_CONFIG = ROOT / "wrangler.toml"
WORKFLOW = ROOT / ".github/workflows/deploy-cloudflare-pages.yml"

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
