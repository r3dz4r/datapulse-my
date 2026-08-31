"""Regression boundary for the single canonical website publisher."""

from __future__ import annotations

import json
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS = ROOT / ".github/workflows"
RETIRED_WORKFLOW = WORKFLOWS / "deploy-pages.yml"
CANONICAL_WORKFLOW = WORKFLOWS / "deploy-cloudflare-pages.yml"
CURRENT_OPERATIONAL_DOCS = (
    ROOT / "AGENTS.md",
    ROOT / "CONTRIBUTING.md",
    ROOT / "llms.txt",
    ROOT / "docs/AGENTS.md",
    ROOT / "docs/architecture.md",
    ROOT / "docs/operations.md",
    ROOT / "docs/release-process.md",
    ROOT / "docs/troubleshooting.md",
    ROOT / "docs/ai-directory-listings.md",
    ROOT / "scripts/AGENTS.md",
)


def test_cloudflare_pages_is_the_only_website_publisher() -> None:
    assert not RETIRED_WORKFLOW.exists()
    workflow = CANONICAL_WORKFLOW.read_text(encoding="utf-8")

    assert yaml.safe_load(workflow) is not None
    assert "pages deploy _site --project-name=datapulse-p4b-preview --branch=main" in workflow
    assert 'website_origin="$(jq -er' in workflow
    assert 'fetch "dataset register" "${website_origin}/"' in workflow
    assert 'fetch_alias "dashboard" "${website_origin}/dashboard"' in workflow
    assert "actions/deploy-pages" not in workflow
    assert "deploy-pages.yml" not in workflow


def test_cloudflare_health_only_path_preserves_served_trust_artifacts() -> None:
    workflow = CANONICAL_WORKFLOW.read_text(encoding="utf-8")

    assert "Preserve served release proof (health-only path)" in workflow
    assert "Preserve served attestation plane (health-only path)" in workflow
    assert 'website_origin="$(jq -er' in workflow
    assert 'python3 scripts/verify_attestation_plane_state.py --planedir "$preserved_root"' in workflow
    assert 'cp "$RUNNER_TEMP/preserved-release-proof/release-verification.md" _site/release-verification.md' in workflow
    assert 'cp -R "$RUNNER_TEMP/preserved-attestations/attestations" _site/' in workflow
    assert "rm -f _site/attestations/latest/binding.json" in workflow


def test_active_workflows_and_operational_docs_do_not_route_to_github_pages() -> None:
    for workflow_path in WORKFLOWS.glob("*.yml"):
        contents = workflow_path.read_text(encoding="utf-8")
        assert yaml.safe_load(contents) is not None, workflow_path
        assert "actions/deploy-pages" not in contents, workflow_path
        assert "deploy-pages.yml" not in contents, workflow_path

    for doc_path in CURRENT_OPERATIONAL_DOCS:
        contents = doc_path.read_text(encoding="utf-8")
        assert "deploy-pages.yml" not in contents, doc_path
        assert "actions/deploy-pages" not in contents, doc_path


def test_github_automation_and_canonical_origin_remain_available() -> None:
    for workflow_name in (
        "ci.yml",
        "openwiki-update.yml",
        "release-please.yml",
        "publish-mcp.yml",
        "anchor-release-attestation.yml",
        "pipeline-audit.yml",
        "pipeline-freshness.yml",
    ):
        assert (WORKFLOWS / workflow_name).is_file()

    origins = json.loads((ROOT / "config/public-surfaces.json").read_text(encoding="utf-8"))["origins"]
    assert origins["website"] == "https://www.data-pulse.my"
    assert (ROOT / "mcp/server.py").is_file()
