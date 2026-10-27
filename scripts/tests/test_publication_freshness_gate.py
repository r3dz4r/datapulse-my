#!/usr/bin/env python3
"""Production age must remain visible even when publication is skipped."""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys

import pytest
import yaml

from scripts.publication_freshness_gate import freshness_verdict


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/publication_freshness_gate.py"
NOW = "2026-10-18T06:00:00Z"


@pytest.mark.parametrize(
    "timestamp, verdict, code",
    [
        ("2026-10-18T05:00:00Z", "fresh", 0),
        ("2026-10-16T21:57:57.716027Z", "stale", 1),
        ("2026-10-17T06:00:00.000001Z", "fresh", 0),
        ("2026-10-17T06:00:00Z", "fresh", 0),
        ("2026-10-17T05:59:59.999999Z", "stale", 1),
        ("2026-10-18T05:00:00+00:00", "fresh", 0),
        (None, "unknown", 2),
        ("", "unknown", 2),
        ("not-a-timestamp", "unknown", 2),
        ("2026-10-18", "unknown", 2),
        ("2026-10-18T05:00:00", "unknown", 2),
        ("2026-10-18T05:00:00+08:00", "unknown", 2),
        ("2026-10-18T07:00:00Z", "unknown", 2),
    ],
)
def test_core_and_cli_verdicts(timestamp: str | None, verdict: str, code: int) -> None:
    assert freshness_verdict(timestamp, NOW, 24) == verdict
    args = [sys.executable, str(SCRIPT), "--now", NOW]
    if timestamp is not None:
        args.extend(["--timestamp", timestamp])
    result = subprocess.run(args, text=True, capture_output=True, check=False)
    assert result.returncode == code, result.stderr
    assert result.stdout.startswith(f"{verdict}: production deployment age ")
    assert "bound 24h" in result.stdout
    assert len(result.stdout.splitlines()) == 1


@pytest.mark.parametrize("bound", ["0", "-1", "nan", "inf", "bad"])
def test_invalid_bound_is_unknown(bound: str) -> None:
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--timestamp", NOW, "--now", NOW,
         "--max-age-hours", bound], text=True, capture_output=True, check=False,
    )
    assert result.returncode == 2
    assert result.stdout.startswith("unknown:")


def test_custom_bound_and_invalid_now() -> None:
    assert freshness_verdict("2026-10-18T04:00:00Z", NOW, 1) == "stale"
    assert freshness_verdict(NOW, "broken", 24) == "unknown"


def _freshness_job() -> dict:
    workflow = yaml.safe_load((ROOT / ".github/workflows/deploy-cloudflare-pages.yml").read_text())
    return workflow["jobs"]["publication_freshness"]


def test_workflow_runs_after_skipped_deploy_outside_pr_checks() -> None:
    job = _freshness_job()
    assert job["needs"] == ["deploy"]
    assert job["if"] == "always()"
    assert job["environment"] == "production"
    step = next(s for s in job["steps"] if "run" in s)
    assert step["if"] == "always()"
    assert "secrets.CLOUDFLARE_API_TOKEN" in step["env"]["CLOUDFLARE_API_TOKEN"]


@pytest.mark.parametrize(
    "timestamp, environment, api_success, credentials, curl_code, expected_code, verdict",
    [
        ("2026-10-18T05:00:00Z", "production", True, True, 0, 0, "fresh"),
        ("2026-10-16T21:57:57Z", "production", True, True, 0, 1, "stale"),
        (NOW, "preview", True, True, 0, 0, "unknown"),
        (None, "production", True, True, 0, 0, "unknown"),
        ("bad", "production", True, True, 0, 0, "unknown"),
        (NOW, "production", False, True, 0, 0, "unknown"),
        (NOW, "production", True, False, 0, 0, "unknown"),
        (NOW, "production", True, True, 22, 0, "unknown"),
    ],
)
def test_workflow_api_verdict_mapping(
    tmp_path: Path, timestamp: str | None, environment: str, api_success: bool,
    credentials: bool, curl_code: int, expected_code: int, verdict: str,
) -> None:
    """Exercise the actual workflow shell, replacing only its network and clock."""
    step = next(s for s in _freshness_job()["steps"] if "run" in s)
    response = {
        "success": api_success,
        "result": {"canonical_deployment": {
            "created_on": timestamp, "environment": environment,
            "latest_stage": {"name": "deploy", "status": "success"},
        }},
    }
    bin_path = tmp_path / "bin"
    bin_path.mkdir()
    curl = bin_path / "curl"
    curl.write_text('#!/bin/bash\nprintf "%s" "$API_RESPONSE"\nexit "$CURL_CODE"\n')
    curl.chmod(0o755)
    python = bin_path / "python3"
    python.write_text(f'#!/bin/bash\nexec "{sys.executable}" "$@" --now {NOW}\n')
    python.chmod(0o755)
    env = {**os.environ, "PATH": f"{bin_path}:{os.environ['PATH']}",
           "API_RESPONSE": json.dumps(response), "CURL_CODE": str(curl_code),
           "GITHUB_STEP_SUMMARY": str(tmp_path / "summary"),
           "CLOUDFLARE_API_TOKEN": "fixture" if credentials else "",
           "CLOUDFLARE_ACCOUNT_ID": "fixture" if credentials else ""}
    result = subprocess.run(["bash", "-c", step["run"]], cwd=ROOT,
                            env=env, text=True, capture_output=True, check=False)
    assert result.returncode == expected_code, result.stdout + result.stderr
    assert f"{verdict}: production deployment age " in result.stdout
    assert f"Deployment age (24h policy): {verdict}:" in (tmp_path / "summary").read_text()
    assert ("::warning" in result.stdout) == (verdict == "unknown")
