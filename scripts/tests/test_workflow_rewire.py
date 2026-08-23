"""Regression tests for generation-profile workflow wiring."""

from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
SYSTEMD_UNIT = ROOT / "deploy/systemd/datapulse-health.service"
CANONICAL_SYSTEMD_UNIT = Path(
    os.environ.get("DOTFILES_DIR", "/home/redza/dotfiles")
) / "system" / "datapulse-health.service"
CANONICAL_PIPELINE = Path(
    os.environ.get("DOTFILES_DIR", "/home/redza/dotfiles")
) / "scripts" / "datapulse-pipeline.sh"
DEPLOY_WORKFLOW = ROOT / ".github/workflows/deploy-pages.yml"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _exec_start(unit: str) -> str:
    return unit.split("ExecStart=", 1)[1].split("\nStandardOutput=", 1)[0]


def test_systemd_unit_uses_generate_sh() -> None:
    exec_start = _exec_start(_read(SYSTEMD_UNIT))

    assert "bash scripts/generate.sh health-cycle" in exec_start
    assert "bash scripts/gen_badges.sh" not in exec_start
    assert "bash scripts/gen_rss.sh" not in exec_start
    assert "bash scripts/gen_readme_summary.sh" not in exec_start
    assert "python3 scripts/gen_changelog.py" not in exec_start


def test_systemd_unit_preserves_atomic_health_write() -> None:
    unit = _read(SYSTEMD_UNIT)

    assert "mktemp health/.latest" in unit
    assert 'mv "$$health_tmp" health/latest.json' in unit


def test_systemd_unit_preserves_flock_guard() -> None:
    assert "flock -n /tmp/datapulse-health.lock" in _read(SYSTEMD_UNIT)


def test_systemd_unit_emits_lock_skip_telemetry() -> None:
    if not CANONICAL_SYSTEMD_UNIT.exists():
        pytest.skip(f"dotfiles not co-located: {CANONICAL_SYSTEMD_UNIT}")
    unit = _read(CANONICAL_SYSTEMD_UNIT)
    assert "--status skipped" in unit
    assert "lock_busy" in unit


def test_systemd_unit_preserves_scoped_commit() -> None:
    exec_start = _exec_start(_read(SYSTEMD_UNIT))

    expected = (
        "health/ deltas/ record-evidence/ badges/ feed.xml README.md "
        "catalog-snapshot.json changelog.json attestations/ datapulse.json"
    )
    assert f"git add {expected}" in exec_start
    git_add = re.search(r"git add ([^;\n]+)", exec_start)
    assert git_add is not None
    assert git_add.group(1) == expected


def test_deploy_pages_workflow_uses_release_build() -> None:
    workflow = _read(DEPLOY_WORKFLOW)

    assert "bash scripts/generate.sh release-build" in workflow
    assert "python3 scripts/gen_jsonld_catalog.py" not in workflow
    assert "python3 scripts/gen_mcp_reference.py" not in workflow
    assert not re.search(
        r"^\s+python3 scripts/gen_dashboard_filters\.py\s*$", workflow, re.MULTILINE
    )


def test_deploy_pages_workflow_paths_trigger_includes_generate_sh() -> None:
    workflow = _read(DEPLOY_WORKFLOW)
    paths_block = workflow.split("    paths:\n", 1)[1].split("  workflow_dispatch:", 1)[
        0
    ]

    assert '"scripts/generate.sh"' in paths_block
    assert not re.search(r'"scripts/gen_[^\"]+\.(?:sh|py)"', paths_block)


def test_deploy_pages_workflow_preserves_post_deploy_invariants() -> None:
    workflow = _read(DEPLOY_WORKFLOW)
    invariants = workflow.split("      - name: Post-deploy release invariants\n", 1)[1]

    assert "DEPLOYED_SHA" in invariants
    assert "bash scripts/verify_agent_ready.sh" in invariants
    assert "bash scripts/verify_release_invariants.sh" in invariants
    assert "DATAPULSE_ALLOW_UNATTESTED_HEALTH" in invariants
    assert '"artifact_signed":false,"rekor_witnessed":false,"source_truth_verified":false' in invariants
    for surface in (
        'fetch "dashboard"',
        'fetch "llms.txt"',
        'fetch "JSON-LD catalog"',
        'fetch "MCP advertisement"',
        'fetch "health snapshot"',
        'fetch "drift snapshot"',
        'fetch "reconciliation snapshot"',
    ):
        assert surface in invariants


def test_deploy_pages_publishes_and_verifies_trends_and_drift() -> None:
    workflow = _read(DEPLOY_WORKFLOW)
    paths_block = workflow.split("    paths:\n", 1)[1].split("  workflow_dispatch:", 1)[0]
    assert '"health/**"' in paths_block
    assert 'fetch "trend snapshot"' in workflow
    assert "datapulse/v1/dataset-trends" in workflow
    assert 'fetch "drift snapshot"' in workflow
    assert "datapulse/v1/dataset-drift" in workflow
    assert 'fetch "reconciliation snapshot"' in workflow
    assert "datapulse/v1/dataset-reconciliation" in workflow
    assert '.tools | type == "array" and length > 0' in workflow
    assert "all(.[];" in workflow
    assert '.inputSchema | type == "object"' in workflow
    assert "<!-- BEGIN mcp-tools -->" in workflow
    assert "<!-- END mcp-tools -->" in workflow
    assert "expected 15 tools" not in workflow
    assert "for tool in search_datasets" not in workflow
    assert "[.tools[].name] == [" not in workflow


def test_deploy_workflow_permissions_not_broadened() -> None:
    deploy = yaml.safe_load(_read(DEPLOY_WORKFLOW))

    assert deploy["permissions"] == {
        "contents": "read",
        "pages": "write",
        "id-token": "write",
    }


def test_deploy_pages_concurrency_cancels_only_normal_pushes() -> None:
    """Keep heartbeat pushes isolated while normal pushes shed queued deploys."""
    deploy = yaml.safe_load(_read(DEPLOY_WORKFLOW))
    concurrency = deploy["concurrency"]

    assert "endsWith(github.event.head_commit.message, '[skip deploy]')" in concurrency[
        "group"
    ]
    assert concurrency["cancel-in-progress"] == (
        "${{ github.event_name == 'push' && !contains("
        "github.event.head_commit.message, '[skip deploy]') }}"
    )

    def policy(event_name: str, message: str = "") -> tuple[str, bool]:
        group = (
            "pages-fast"
            if event_name == "push" and message.endswith("[skip deploy]")
            else "pages-deploy"
        )
        cancel = event_name == "push" and "[skip deploy]" not in message
        return group, cancel

    assert policy("push", "fix: refresh dashboard") == ("pages-deploy", True)
    assert policy("push", "chore(health): update [skip deploy]") == (
        "pages-fast",
        False,
    )
    assert policy("workflow_dispatch") == ("pages-deploy", False)


def test_generate_sh_profiles_match_workflow_invocations() -> None:
    profiles = {
        "release-build": DEPLOY_WORKFLOW,
    }

    for profile, workflow_path in profiles.items():
        listed = subprocess.run(
            ["./scripts/generate.sh", profile, "--list"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=True,
        )
        assert f"Profile: {profile}" in listed.stdout
        assert f"bash scripts/generate.sh {profile}" in _read(workflow_path)


def test_canonical_pipeline_stages_and_validates_record_evidence() -> None:
    if not CANONICAL_PIPELINE.exists():
        pytest.skip(f"dotfiles not co-located: {CANONICAL_PIPELINE}")
    pipeline = _read(CANONICAL_PIPELINE)

    assert "record-evidence" in pipeline.split("ARTIFACT_PATHS=", 1)[1].split(")", 1)[0]
    assert re.search(
        r"(?:\$\{PYTHON_BIN\}|python3)\s+scripts/gen_record_evidence\.py",
        pipeline,
    )
    assert "validate_record_evidence(envelope, full=False)" in pipeline
