#!/usr/bin/env python3
"""A green deployment run must include a verified served publication.

Run 42475085174 was green after its triggering build was cancelled: classify,
sign_health and deploy all skipped, while the previous publication passed both
age policies. Replay that boundary without GitHub or Cloudflare access.
"""
from __future__ import annotations

import gzip
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest
import yaml


ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github/workflows/deploy-cloudflare-pages.yml"
NOW = "2026-11-08T11:17:55Z"


@pytest.mark.parametrize("deploy_result", ["skipped", "failure", "cancelled", "success"])
def test_green_run_requires_served_publication_despite_passing_age_checks(
    tmp_path: Path, deploy_result: str,
) -> None:
    health = {"checked_at": "2026-11-07T13:01:47Z", "datasets": [{"dataset_id": "example"}]}
    content = json.dumps(health).encode()
    head = "a" * 64
    published = "2026-11-08T03:23:51Z"
    snapshot_ref = "attestations/2026-11-08/health.json.gz"
    claim = {
        "artifact_ref": "health/latest.json",
        "artifact_sha256": hashlib.sha256(content).hexdigest(),
        "dataset_count": 1,
        "dataset_ids_sha256": hashlib.sha256(b'["example"]').hexdigest(),
        "observed_at": health["checked_at"],
    }
    responses = {
        "deployment": {"success": True, "result": {"canonical_deployment": {
            "environment": "production", "created_on": "2026-11-08T05:17:40Z",
            "latest_stage": {"name": "deploy", "status": "success"},
        }}},
        "identity": {"health_snapshot_ref": snapshot_ref, "health_sha256": claim["artifact_sha256"],
                     "accepted_chain_head": head, "observed_at": health["checked_at"],
                     "published_at": published},
        "binding": {"payload": {"health": claim, "ed25519": {"chain_head": head},
                                "published_at": published, "freshness": {"max_age_seconds": 129600}}},
    }
    for name, response in responses.items():
        (tmp_path / name).write_text(json.dumps(response))
    (tmp_path / "snapshot").write_bytes(gzip.compress(content))
    (tmp_path / "scripts").symlink_to(ROOT / "scripts", target_is_directory=True)
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    curl = bin_dir / "curl"
    curl.write_text(f"#!{sys.executable}\n" + '''import os
from pathlib import Path
import sys

args = sys.argv[1:]
root = Path(os.environ["RESPONSES"])
if any("api.cloudflare.com" in arg for arg in args):
    sys.stdout.write((root / "deployment").read_text())
else:
    name = "identity" if any("publication-identity.json" in arg for arg in args) else (
        "binding" if any("binding.json" in arg for arg in args) else "snapshot")
    Path(args[args.index("-o") + 1]).write_bytes((root / name).read_bytes())
    if "--write-out" in args:
        sys.stdout.write("200")
''')
    curl.chmod(0o755)
    env = os.environ | {
        "PATH": f"{bin_dir}:{os.environ['PATH']}", "RESPONSES": str(tmp_path),
        "RUNNER_TEMP": str(tmp_path), "GITHUB_STEP_SUMMARY": str(tmp_path / "summary"),
        "CLOUDFLARE_API_TOKEN": "test", "CLOUDFLARE_ACCOUNT_ID": "test",
    }
    job = yaml.safe_load(WORKFLOW.read_text())["jobs"]["publication_freshness"]
    assert "deploy" in job["needs"] and job["if"] == "always()"
    results = []
    for step in job["steps"]:
        if "run" not in step:
            continue
        step_env = {key: value.replace("${{ needs.deploy.result }}", deploy_result)
                    for key, value in step.get("env", {}).items()}
        command = step["run"].replace("scripts/publication_freshness_gate.py",
            f"scripts/publication_freshness_gate.py --now {NOW}").replace(
            "scripts/select_accepted_health.py", f"scripts/select_accepted_health.py --now {NOW}")
        results.append(subprocess.run(["bash", "-c", command], cwd=tmp_path,
            env=env | step_env, capture_output=True, text=True, timeout=10))
    output = "\n".join(result.stdout + result.stderr for result in results)
    assert "fresh: production deployment age" in output
    assert '"report_age_status": "current"' in output
    failed = any(result.returncode != 0 for result in results)
    assert failed == (deploy_result != "success"), (
        f"deploy={deploy_result}: passing age checks must not make an unpublished run green\n{output}"
    )
    if deploy_result != "success":
        assert "No verified served publication" in output


def test_publication_completion_guard_cannot_be_skipped_or_ignored() -> None:
    job = yaml.safe_load(WORKFLOW.read_text())["jobs"]["publication_freshness"]
    guards = [step for step in job["steps"] if step.get("env", {}).get("DEPLOY_RESULT")
              == "${{ needs.deploy.result }}"]
    assert len(guards) == 1, "Age-only success must require an actual verified served publication"
    assert guards[0]["if"] == "always()"
    assert not guards[0].get("continue-on-error", False)
    assert not job.get("continue-on-error", False)
