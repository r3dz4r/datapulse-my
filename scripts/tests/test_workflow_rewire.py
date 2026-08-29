"""Regression tests for the active Cloudflare Pages workflow wiring."""

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


def test_cloudflare_workflow_permissions_and_concurrency_are_not_broadened() -> None:
    workflow = yaml.safe_load(_read(DEPLOY_WORKFLOW))
    concurrency = workflow["concurrency"]

    assert workflow["permissions"] == {"contents": "read"}
    assert "cloudflare-pages-health" in concurrency["group"]
    assert "cloudflare-pages-release" in concurrency["group"]
    assert "[skip deploy]" in concurrency["cancel-in-progress"]


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
