"""Regression tests for generation-profile workflow wiring."""

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
from scripts.embed_dashboard_data import _attestation_verification
from scripts.tests.test_attestations import fixture_root, write
from scripts.verify_attestation_binding import verify_contract

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


def _fast_path_preservation_script() -> str:
    workflow = _read(DEPLOY_WORKFLOW)
    match = re.search(
        r"(?ms)^      - name: Preserve served attestation plane \(fast path\)\n"
        r".*?^        run: \|\n(.*?)(?=^      - name: Run release-build)",
        workflow,
    )
    assert match is not None, "fast path must preserve the served attestation plane"
    return match.group(1)


def test_fast_path_preserves_a_newer_valid_served_attestation_plane(tmp_path: Path) -> None:
    """A health-only artifact keeps the served P1 plane, never checkout's stale plane."""
    served_root, key = fixture_root(tmp_path / "served")
    first = datetime(2026, 8, 22, 1, tzinfo=timezone.utc)
    second = first + timedelta(days=1)
    health = json.loads((served_root / "health/latest.json").read_text(encoding="utf-8"))
    health["checked_at"] = "2026-08-22T00:00:00Z"
    health["datasets"][0]["last_checked"] = health["checked_at"]
    write(served_root / "health/latest.json", health)
    ga.generate(served_root, key, first)
    health = json.loads((served_root / "health/latest.json").read_text(encoding="utf-8"))
    health["checked_at"] = "2026-08-23T00:00:00Z"
    health["datasets"][0]["last_checked"] = health["checked_at"]
    write(served_root / "health/latest.json", health)
    ga.generate(served_root, key, second)
    assert verify_contract(served_root, now=second + timedelta(hours=1))["claims"][
        "artifact_signed"
    ] is True

    checkout = tmp_path / "checkout"
    shutil.copytree(served_root, checkout)
    (checkout / "scripts").mkdir()
    shutil.copy2(ROOT / "scripts/verify_attestation_binding.py", checkout / "scripts")
    stale = checkout / "attestations"
    shutil.rmtree(stale)
    shutil.copytree(served_root / "attestations/2026-08-22", stale / "2026-08-22")
    shutil.copytree(served_root / "attestations/latest", stale / "latest")
    (stale / "latest/index.json").write_bytes(
        (served_root / "attestations/2026-08-22/index.json").read_bytes()
    )
    (stale / "latest/chain_head.json").write_bytes(
        (served_root / "attestations/2026-08-22/chain_head.json").read_bytes()
    )

    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    fake_curl = fake_bin / "curl"
    fake_curl.write_text(
        """#!/usr/bin/env bash
set -Eeuo pipefail
output=""
url=""
while (( $# > 0 )); do
  case "$1" in
    --output) output="$2"; shift 2 ;;
    *) url="$1"; shift ;;
  esac
done
path="${url#https://data-pulse.my/}"
[[ "$path" == .well-known/* ]] && path="docs/$path"
[[ "$path" != "$url" && -f "${MOCK_SERVED_ROOT:?}/$path" ]] || {
  printf 'missing %s\n' "$url" >&2
  exit 22
}
mkdir -p "$(dirname "$output")"
cp "${MOCK_SERVED_ROOT:?}/$path" "$output"
""",
        encoding="utf-8",
    )
    fake_curl.chmod(0o755)

    environment = os.environ.copy()
    environment.update(
        PATH=f"{fake_bin}:{environment['PATH']}",
        MOCK_SERVED_ROOT=str(served_root),
        RUNNER_TEMP=str(tmp_path / "runner-temp"),
    )
    completed = subprocess.run(
        ["bash", "-c", _fast_path_preservation_script()],
        cwd=checkout,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    preserved = tmp_path / "runner-temp/preserved-attestations"
    assert (preserved / "attestations/latest/binding.json").read_bytes() == (
        served_root / "attestations/latest/binding.json"
    ).read_bytes()
    assert (preserved / "attestations/latest/chain_head.json").read_bytes() == (
        served_root / "attestations/latest/chain_head.json"
    ).read_bytes()
    assert (preserved / "attestations/2026-08-23/sample.json").is_file()
    assert not (preserved / "attestations/2026-08-22/sample.json").exists()

    # The fast health update has no matching P1 binding, so it must not inherit
    # a claim from the preserved (older) served health bytes.
    shutil.rmtree(checkout / "attestations")
    shutil.copytree(preserved / "attestations", checkout / "attestations")
    shutil.copy2(
        preserved / "docs/.well-known/datapulse-probe-keys.json",
        checkout / "docs/.well-known/datapulse-probe-keys.json",
    )
    health = json.loads((checkout / "health/latest.json").read_text(encoding="utf-8"))
    health["checked_at"] = "2026-08-24T00:00:00Z"
    health["datasets"][0]["last_checked"] = health["checked_at"]
    write(checkout / "health/latest.json", health)
    assert _attestation_verification(checkout)["claims"] == {
        "artifact_signed": False,
        "rekor_witnessed": False,
        "source_truth_verified": False,
    }


def test_fast_path_fails_closed_when_served_binding_cannot_be_preserved() -> None:
    script = _fast_path_preservation_script()
    assert "python3 scripts/verify_attestation_binding.py --root \"$preserved_root\"" in script
    workflow = _read(DEPLOY_WORKFLOW)
    assert "cp -R health deltas record-evidence badges samples data _site/" in workflow
    assert "rm -rf _site/attestations" in workflow
    assert 'cp -R "$RUNNER_TEMP/preserved-attestations/attestations" _site/' in workflow


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
