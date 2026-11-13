#!/usr/bin/env python3
"""Production age must remain visible even when publication is skipped."""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
import yaml

from scripts import publication_freshness_gate as gate
from scripts.publication_freshness_gate import deployment_age_verdict


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
    assert deployment_age_verdict(timestamp, NOW, 24) == verdict
    args = [sys.executable, str(SCRIPT), "--deployment-age-only", "--now", NOW]
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
        [sys.executable, str(SCRIPT), "--deployment-age-only", "--timestamp", NOW, "--now", NOW,
         "--max-age-hours", bound], text=True, capture_output=True, check=False,
    )
    assert result.returncode == 2
    assert result.stdout.startswith("unknown:")


def test_custom_bound_and_invalid_now() -> None:
    assert deployment_age_verdict("2026-10-18T04:00:00Z", NOW, 1) == "stale"
    assert deployment_age_verdict(NOW, "broken", 24) == "unknown"


@pytest.mark.parametrize("served, expected, code", [
    ("2026-11-12T09:26:20Z", "stale", 1),
    ("2026-11-12T10:55:44Z", "fresh", 0),
    ("2026-11-12T10:45:44Z", "fresh", 0),
    ("2026-11-12T10:45:43.999999Z", "stale", 1),
    ("2026-11-12T11:00:44Z", "served_newer", 0),
    (None, "unknown", 2),
    ("invalid", "unknown", 2),
    ("2026-11-12T10:55:44+08:00", "unknown", 2),
])
def test_content_comparison(served: str | None, expected: str, code: int) -> None:
    repository = "2026-11-12T10:55:44Z"
    assert gate.freshness_verdict(served, repository) == expected
    args = [sys.executable, str(SCRIPT), "--repository-checked-at", repository]
    if served is not None:
        args += ["--served-checked-at", served]
    result = subprocess.run(args, text=True, capture_output=True, check=False)
    assert result.returncode == code, result.stdout + result.stderr
    assert result.stdout.startswith(f"{expected}: content freshness")
    assert "2 pipeline cycles (10 minutes)" in result.stdout


@pytest.mark.parametrize("repository", [None, "", "broken", "2026-11-12"])
def test_missing_or_invalid_repository_is_unknown(repository: str | None) -> None:
    assert gate.freshness_verdict(NOW, repository) == "unknown"


def test_fresh_content_is_independent_of_deployment_age() -> None:
    assert gate.freshness_verdict(NOW, NOW) == "fresh"
    assert deployment_age_verdict("2026-10-16T06:00:00Z", NOW) == "stale"


def test_content_is_required_by_default() -> None:
    result = subprocess.run([sys.executable, str(SCRIPT), "--timestamp", NOW],
                            text=True, capture_output=True, check=False)
    assert result.returncode == 2
    assert result.stdout.startswith("unknown: content freshness")


def _freshness_job() -> dict:
    workflow = yaml.safe_load((ROOT / ".github/workflows/deploy-cloudflare-pages.yml").read_text())
    return workflow["jobs"]["publication_freshness"]


@pytest.mark.parametrize("damage, expected_code, verdict", [
    ("none", 0, "fresh: content freshness"),
    ("clock", 1, "served_health_observed_at_mismatch"),
    ("newer", 1, "served_health_observed_at_mismatch"),
    ("digest", 1, "served_health_digest_mismatch"),
    ("missing-clock", 1, "publication_observed_at_missing_or_invalid"),
    ("missing-digest", 1, "publication_health_sha256_missing_or_invalid"),
    ("invalid-digest", 1, "publication_health_sha256_missing_or_invalid"),
    ("empty-identity", 1, "publication_identity_empty"),
    ("empty-health", 1, "served_health_empty"),
    ("invalid-clock", 2, "unknown: content freshness"),
])
def test_workflow_compares_served_content_to_published_artifact(
    tmp_path: Path, damage: str, expected_code: int, verdict: str,
) -> None:
    step = next(s for s in _freshness_job()["steps"]
                if s.get("name") == "Compare served health with published artifact")
    assert "git show" not in step["run"]
    assert step["if"] == "always()"
    checkout = _freshness_job()["steps"][0]
    assert checkout["with"]["fetch-depth"] == 0
    (tmp_path / "scripts").symlink_to(ROOT / "scripts", target_is_directory=True)
    health = tmp_path / "health/latest.json"
    health.parent.mkdir()
    health.write_text(json.dumps({"checked_at": "2026-11-12T10:55:44Z"}))

    def git(*args: str) -> str:
        return subprocess.check_output(["git", *args], cwd=tmp_path, text=True).strip()

    git("init", "-q")
    git("config", "user.name", "Test")
    git("config", "user.email", "test@example.invalid")
    git("add", "health/latest.json")
    git("commit", "-qm", "deployed")
    deployed = git("rev-parse", "HEAD")
    # Both repository clocks differ from the signed report this deploy published.
    health.write_text(json.dumps({"checked_at": "2026-11-12T12:00:00Z"}))
    git("commit", "-qam", "later main")
    bin_path = tmp_path / "bin"
    bin_path.mkdir()
    curl = bin_path / "curl"
    curl.write_text('''#!/bin/bash
output=""
while (($# > 1)); do
  case "$1" in
    --output|-o) output="$2"; shift 2 ;;
    *) shift ;;
  esac
done
case "${@: -1}" in
  */publication-identity.json) printf '%s' "$IDENTITY" > "$output" ;;
  */health/latest.json) printf '%s' "$SERVED_HEALTH" > "$output" ;;
  *) exit 99 ;;
esac
''')
    curl.chmod(0o755)
    observed_at = "bad" if damage == "invalid-clock" else "2026-11-12T09:26:20Z"
    served = json.dumps({"checked_at": observed_at})
    identity = {"accepted_main_commit": deployed, "observed_at": observed_at,
                "health_sha256": hashlib.sha256(served.encode()).hexdigest()}
    if damage in {"clock", "newer"}:
        served = json.dumps({"checked_at": "2026-11-12T09:25:20Z" if damage == "clock"
                             else "2026-11-12T09:27:20Z"})
    elif damage == "digest":
        served += "\n"
    elif damage == "missing-clock":
        del identity["observed_at"]
    elif damage == "missing-digest":
        del identity["health_sha256"]
    elif damage == "invalid-digest":
        identity["health_sha256"] = "not-a-digest"
    env = {**os.environ, "PATH": f"{bin_path}:{os.environ['PATH']}",
           "IDENTITY": "" if damage == "empty-identity" else json.dumps(identity),
           "SERVED_HEALTH": "" if damage == "empty-health" else served,
           "RUNNER_TEMP": str(tmp_path),
           "GITHUB_STEP_SUMMARY": str(tmp_path / "summary")}
    result = subprocess.run(["bash", "-c", step["run"]], cwd=tmp_path, env=env,
                            text=True, capture_output=True, check=False)
    assert result.returncode == expected_code, result.stdout + result.stderr
    assert verdict in result.stdout
    if expected_code == 0:
        assert "published_observed_at=2026-11-12T09:26:20Z" in result.stdout
        assert "Content freshness: fresh:" in (tmp_path / "summary").read_text()


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


def _served_report_case(
    tmp_path: Path, identity_status: str, age_hours: int,
) -> tuple[dict[str, str], str]:
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
    return env, command


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
    env, command = _served_report_case(tmp_path, identity_status, age_hours)
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


@pytest.mark.parametrize(
    "identity_status, age_hours, expected_code, expected_state",
    [("200", 37, 1, "expired"),
     ("404", 1, 0, "first accepted publication"),
     ("200", 1, 0, "current")],
    ids=["expired-still-publishes-then-fails", "unpublished-publishes-and-passes",
         "fresh-publishes-and-passes"],
)
def test_publication_precedes_age_verdict(
    tmp_path: Path, identity_status: str, age_hours: int,
    expected_code: int, expected_state: str,
) -> None:
    """Run real identity/age/deploy shell with signing and preview already successful.

    Only upload, served transport, and the clock are fixtures. The expired case
    also covers a signed report aging past the bound during the build.
    """
    env, served_command = _served_report_case(tmp_path, identity_status, age_hours)
    (tmp_path / "scripts").symlink_to(ROOT / "scripts", target_is_directory=True)
    site = tmp_path / "_site"
    for directory in ("health", "attestations/latest", ".attestations"):
        (site / directory).mkdir(parents=True)
    shutil.copy2(tmp_path / "health.json", site / "health/latest.json")
    shutil.copy2(tmp_path / "binding.json", site / "attestations/latest/binding.json")
    for path in ("attestations/latest/chain_head.json", ".attestations/chain_head.json"):
        (site / path).write_text(json.dumps({"chain_head": "a" * 64}))
    (site / "datapulse.json").write_text("{}")
    (site / "index.html").write_text("<html><body>Fixture</body></html>")
    identity = json.loads((tmp_path / "identity.json").read_text()) | {
        "accepted_main_commit": "b" * 40,
        "manifest_sha256": hashlib.sha256(b"{}").hexdigest(),
    }
    publication = Path(env["RUNNER_TEMP"]) / "sigstore-publication"
    publication.mkdir()
    (publication / "publication-identity.json").write_text(json.dumps(identity))
    env |= {"ACCEPTED_MAIN_COMMIT": "b" * 40,
            "ACCEPTED_OBSERVED_AT": identity["observed_at"],
            "PROMOTION_SOURCE_SHA": "b" * 40,
            "EVENT_LOG": str(tmp_path / "events")}
    bin_path = tmp_path / "bin"
    python = bin_path / "python3"
    python.write_text(
        '#!/bin/bash\nif [[ "$*" == *--measure-age* ]]; then\n'
        '  printf "measure\\n" >> "$EVENT_LOG"\n'
        f'  exec "{sys.executable}" "$@" --now {NOW}\nfi\n'
        f'exec "{sys.executable}" "$@"\n')
    python.chmod(0o755)
    npx = bin_path / "npx"
    npx.write_text('#!/bin/bash\nprintf "publish\\n" >> "$EVENT_LOG"\n')
    npx.chmod(0o755)
    workflow = yaml.safe_load((ROOT / ".github/workflows/deploy-cloudflare-pages.yml").read_text())
    failed = False
    for step in workflow["jobs"]["deploy"]["steps"]:
        command = step.get("run", "")
        if not (step.get("name") == "Verify accepted report identity and disclose observation time"
                or step.get("id") == "deploy" or "--measure-age" in command):
            continue
        if failed and step.get("if") != "always()":
            continue
        result = subprocess.run(["bash", "-c", command], cwd=tmp_path, env=env,
                                text=True, capture_output=True, check=False, timeout=10)
        failed |= result.returncode != 0
    served = subprocess.run(["bash", "-c", served_command], cwd=tmp_path, env=env,
                            text=True, capture_output=True, check=False, timeout=10)
    events = (tmp_path / "events").read_text().splitlines()
    assert "publish" in events, "age refusal skipped canonical publication"
    assert events[0] == "publish", "report age was measured before canonical publication"
    assert served.returncode == expected_code, served.stdout + served.stderr
    assert expected_state in served.stdout
    assert (failed or served.returncode != 0) == bool(expected_code)


def test_age_measurement_cannot_skip_canonical_deploy() -> None:
    jobs = yaml.safe_load((ROOT / ".github/workflows/deploy-cloudflare-pages.yml").read_text())["jobs"]
    deploy = jobs["deploy"]
    steps = deploy["steps"]
    publication_index = next(i for i, step in enumerate(steps) if step.get("id") == "deploy")
    assert not any("--measure-age" in step.get("run", "")
                   for step in steps[:publication_index]), "blocking age measurement precedes deploy"
    gate = next(step for step in steps if step.get("id") == "publication_age_gate_after_deploy")
    assert steps.index(gate) > publication_index
    assert gate["if"] == "always()"
    assert not gate.get("continue-on-error", False)
    assert "--measure-age" in gate["run"]
    assert "publication_freshness" not in deploy["needs"]
    assert "publication_freshness" not in deploy["if"]
    assert jobs["publication_freshness"]["needs"] == ["deploy"]
    assert jobs["publication_freshness"]["if"] == "always()"
