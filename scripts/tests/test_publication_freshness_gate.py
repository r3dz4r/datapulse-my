#!/usr/bin/env python3
"""Production age must remain visible even when publication is skipped."""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

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


@pytest.mark.parametrize(
    "identity_status, age_hours, expected_code, expected_state",
    [
        ("404", 1, 0, "first accepted publication"),
        ("200", 1, 0, "current"),
        ("200", 37, 1, "expired"),
        ("503", 1, 1, "error"),
        ("transport", 1, 1, "error"),
        ("malformed", 1, 1, "error"),
    ],
)
def test_served_report_freshness_step(
    tmp_path: Path, identity_status: str, age_hours: int,
    expected_code: int, expected_state: str,
) -> None:
    step = next(s for s in _freshness_job()["steps"]
                if s.get("name") == "Measure canonical production report age")
    assert "--write-out" in step["run"] and ' -o "$report/identity.json"' in step["run"]
    report_time = (datetime.fromisoformat(NOW.replace("Z", "+00:00"))
                   - timedelta(hours=age_hours)).isoformat().replace("+00:00", "Z")
    health = {"checked_at": report_time, "datasets": [{"dataset_id": "fixture"}]}
    health_bytes = json.dumps(health).encode()
    (tmp_path / "health.json").write_bytes(health_bytes)
    published = report_time
    binding = {"payload": {
        "health": {"artifact_ref": "health/latest.json",
                   "artifact_sha256": hashlib.sha256(health_bytes).hexdigest(),
                   "dataset_count": 1,
                   "dataset_ids_sha256": hashlib.sha256(
                       json.dumps(["fixture"], ensure_ascii=False, sort_keys=True,
                                  separators=(",", ":")).encode()).hexdigest(),
                   "observed_at": report_time},
        "published_at": published,
        "freshness": {"max_age_seconds": 129600},
        "ed25519": {"chain_head": "a" * 64},
    }}
    (tmp_path / "binding.json").write_text(json.dumps(binding))
    (tmp_path / "identity.json").write_text(json.dumps({
        "health_snapshot_ref": "attestations/2026-10-18/health.json",
        "health_sha256": hashlib.sha256(health_bytes).hexdigest(),
        "accepted_chain_head": "a" * 64,
        "observed_at": report_time,
        "published_at": published,
    }))
    (tmp_path / "malformed.json").write_text("{invalid json")
    bin_path = tmp_path / "bin"
    bin_path.mkdir()
    curl = bin_path / "curl"
    curl.write_text('''#!/bin/bash
url=""; output=""
while (($#)); do
  case "$1" in
    --output|-o) output="$2"; shift 2 ;;
    https://*) url="$1"; shift ;;
    *) shift ;;
  esac
done
printf '%s\\n' "$url" >> "$REQUEST_LOG"
case "$url" in
  */publication-identity.json)
    if [[ "$IDENTITY_STATUS" == 200 ]]; then cp "$FIXTURE/identity.json" "$output"; fi
    if [[ "$IDENTITY_STATUS" == malformed ]]; then cp "$FIXTURE/malformed.json" "$output"; printf 200; exit; fi
    if [[ "$IDENTITY_STATUS" == transport ]]; then printf 000; exit 7; fi
    printf '%s' "$IDENTITY_STATUS" ;;
  */binding.json) cp "$FIXTURE/binding.json" "$output" ;;
  */health.json) cp "$FIXTURE/health.json" "$output" ;;
  *) exit 99 ;;
esac
''')
    curl.chmod(0o755)
    runner = tmp_path / "runner"
    runner.mkdir()
    env = {**os.environ, "PATH": f"{bin_path}:{os.environ['PATH']}",
           "FIXTURE": str(tmp_path), "IDENTITY_STATUS": identity_status,
           "REQUEST_LOG": str(tmp_path / "requests"), "RUNNER_TEMP": str(runner),
           "GITHUB_STEP_SUMMARY": str(tmp_path / "summary")}
    command = step["run"].replace("scripts/select_accepted_health.py",
                                   f"scripts/select_accepted_health.py --now {NOW}")
    result = subprocess.run(["bash", "-c", command], cwd=ROOT, env=env,
                            text=True, capture_output=True, check=False)
    if expected_code:
        assert result.returncode != 0, result.stdout + result.stderr
    else:
        assert result.returncode == 0, result.stdout + result.stderr
    requests = (tmp_path / "requests").read_text().splitlines()
    if identity_status == "404":
        assert "first accepted publication" in result.stdout
        assert "first accepted publication" in (tmp_path / "summary").read_text()
        assert len(requests) == 1
        assert "Report age:" not in result.stdout
    elif identity_status == "200":
        assert expected_state in result.stdout
        assert f'"observation_age_seconds": {age_hours * 3600}.0' in result.stdout
        assert "Report age:" in (tmp_path / "summary").read_text()
        assert len(requests) == 3
    else:
        assert "first accepted publication" not in result.stdout
        assert len(requests) == 1
