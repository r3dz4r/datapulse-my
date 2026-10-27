#!/usr/bin/env python3
"""Publication diagnoses accepted-input failures without candidate waits or retries."""
from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

import pytest
import yaml

from scripts.tests.test_deploy_cloudflare_pages_contract import _accepted_workflow_case, _select_step
from scripts.tests.test_attestation_projections import git

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github/workflows/deploy-cloudflare-pages.yml"


@pytest.mark.parametrize("damage,diagnostic", [
    ("revision", "accepted main commit must be a pinned full SHA"),
    ("snapshot", "content-addressed health snapshot is missing"),
    ("manifest", "pinned manifest membership differs from accepted report"),
])
def test_selection_failure_is_diagnosed_without_claiming_acceptance(
    tmp_path: Path, damage: str, diagnostic: str,
) -> None:
    root, _, _, env = _accepted_workflow_case(tmp_path)
    if damage == "revision":
        env["PROMOTION_SOURCE_SHA"] = "malformed"
    else:
        if damage == "snapshot":
            for path in (root / "attestations").rglob("health.json*"):
                path.unlink()
        else:
            manifest = json.loads((root / "datapulse.json").read_bytes())
            manifest["datasets"][0]["id"] = "wrong"
            (root / "datapulse.json").write_text(json.dumps(manifest))
        git(root, "add", "-A")
        git(root, "commit", "-m", "invalid accepted inputs")
        env["PROMOTION_SOURCE_SHA"] = git(root, "rev-parse", "HEAD")
    result = subprocess.run(["bash", "-c", _select_step()["run"]], cwd=root, env=env,
                            capture_output=True, text=True, timeout=30)
    assert result.returncode != 0
    assert "REFUSED:" in result.stdout + result.stderr
    assert diagnostic in result.stdout + result.stderr
    assert not Path(env["GITHUB_OUTPUT"]).exists()
    assert "state=accepted" not in result.stdout


def test_report_measurement_prints_expired_age_before_refusal(tmp_path: Path) -> None:
    root, _, _, env = _accepted_workflow_case(tmp_path)
    selected = subprocess.run(["bash", "-c", _select_step()["run"]], cwd=root, env=env,
                              capture_output=True, text=True, timeout=30)
    assert selected.returncode == 0, selected.stdout + selected.stderr
    publication = Path(env["RUNNER_TEMP"]) / "sigstore-publication"
    # Move only the verification clock; do not forge an accepted envelope.
    from datetime import datetime, timedelta
    identity = json.loads((publication / "publication-identity.json").read_bytes())
    now = datetime.fromisoformat(identity["observed_at"].replace("Z", "+00:00")) + timedelta(hours=37)
    measured = subprocess.run([
        sys.executable, str(ROOT / "scripts/select_accepted_health.py"), "--measure-age",
        "--health", str(publication / "health/latest.json"),
        "--binding", str(publication / "attestations/latest/binding.json"), "--now", now.isoformat(),
    ], env=env, capture_output=True, text=True, timeout=10)
    assert measured.returncode == 1
    assert '\"report_age_status\": \"expired\"' in measured.stdout
    assert '\"observation_age_seconds\": 133200.0' in measured.stdout
    assert "36h): expired" in Path(env["GITHUB_STEP_SUMMARY"]).read_text()


def test_publication_has_no_acceptance_budget_and_keeps_newest_wins_concurrency() -> None:
    contents = WORKFLOW.read_text()
    workflow = yaml.safe_load(contents)
    for removed in ("APPEND_", "existing_append", "append_submission", "append_acceptance",
                    "gh pr", "submit_attestation_append.sh", "--wait-for-acceptance"):
        assert removed not in contents
    assert workflow["jobs"]["sign_health"]["timeout-minutes"] == 30
    assert "continue-on-error" not in _select_step()
    assert workflow["concurrency"] == {
        "group": "cloudflare-pages-deploy", "cancel-in-progress": False, "queue": "single",
    }
