"""Tests for the temporary full-probe health canary."""

from __future__ import annotations

import copy
import json
import os
import subprocess
from pathlib import Path

import pytest

from scripts import run_health_canary


ROOT = Path(__file__).resolve().parents[2]
LIVE_HEALTH = json.loads((ROOT / "health/latest.json").read_text(encoding="utf-8"))


def _run_mocked_canary(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    canary: dict,
) -> tuple[int, str]:
    completed = subprocess.CompletedProcess(
        ["bash", "scripts/check.sh"],
        0,
        stdout=(json.dumps(canary) + "\n").encode(),
        stderr=b"",
    )
    monkeypatch.setattr(run_health_canary.subprocess, "run", lambda *args, **kwargs: completed)
    report_path = tmp_path / "health-policy-compatibility.md"

    exit_code = run_health_canary.main(["--output", str(report_path)])

    return exit_code, report_path.read_text(encoding="utf-8")


def _set_status(snapshot: dict, dataset_id: str, status: str) -> None:
    row = next(row for row in snapshot["datasets"] if row["dataset_id"] == dataset_id)
    old_key = row["status"].replace("-", "_")
    new_key = status.replace("-", "_")
    snapshot["_trust_summary"]["by_status"][old_key] -= 1
    snapshot["_trust_summary"]["by_status"][new_key] += 1
    row["status"] = status


def test_canary_exit_zero_when_no_blockers(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    exit_code, report = _run_mocked_canary(
        monkeypatch, tmp_path, copy.deepcopy(LIVE_HEALTH)
    )

    assert exit_code == 0
    assert "# Full-probe health policy compatibility canary" in report


def test_canary_exit_one_when_blocker_detected(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    canary = copy.deepcopy(LIVE_HEALTH)
    missing_id = canary["datasets"].pop()["dataset_id"]

    exit_code, report = _run_mocked_canary(monkeypatch, tmp_path, canary)

    assert exit_code == 1
    assert missing_id in report
    assert "## Blockers" in report


def test_canary_classifies_fresh_to_aging_as_approved(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    canary = copy.deepcopy(LIVE_HEALTH)
    row = next(row for row in canary["datasets"] if row["status"] == "fresh")
    dataset_id = row["dataset_id"]
    _set_status(canary, dataset_id, "aging")

    exit_code, report = _run_mocked_canary(monkeypatch, tmp_path, canary)

    assert exit_code == 0
    approved_section = report.split("## Approved", 1)[1].split("## Blockers", 1)[0]
    blocker_section = report.split("## Blockers", 1)[1].split("## Pending", 1)[0]
    assert dataset_id in approved_section
    assert dataset_id not in blocker_section


def test_canary_detects_record_count_change(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    canary = copy.deepcopy(LIVE_HEALTH)
    row = next(
        row
        for row in canary["datasets"]
        if isinstance(row.get("record_count"), (int, float)) and row["record_count"] > 0
    )
    dataset_id = row["dataset_id"]
    row["record_count"] = row["record_count"] * 2

    exit_code, report = _run_mocked_canary(monkeypatch, tmp_path, canary)

    assert exit_code == 1
    assert "## Record-count changes" in report
    assert dataset_id in report
    assert "more than 10%" in report


def test_discontinued_feed_records_zero_count_not_blocker(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    manifest = json.loads(
        (ROOT / "datapulse.json").read_text(encoding="utf-8")
    )
    canary = copy.deepcopy(LIVE_HEALTH)
    row = next(
        row
        for row in canary["datasets"]
        if isinstance(row.get("record_count"), (int, float))
        and row["record_count"] > 0
    )
    dataset_id = row["dataset_id"]
    manifest_row = next(row for row in manifest["datasets"] if row["id"] == dataset_id)
    manifest_row["real_status"] = "discontinued"
    row["record_count"] = 0
    manifest_path = tmp_path / "datapulse.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    monkeypatch.setattr(run_health_canary, "MANIFEST_PATH", manifest_path)

    exit_code, report = _run_mocked_canary(monkeypatch, tmp_path, canary)

    approved_section = report.split("## Approved", 1)[1].split("## Blockers", 1)[0]
    blocker_section = report.split("## Blockers", 1)[1].split("## Pending", 1)[0]
    assert exit_code == 0
    assert dataset_id in approved_section
    assert dataset_id not in blocker_section


def test_canary_does_not_modify_tracked_workspace(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    def protected_status() -> list[str]:
        status = subprocess.check_output(
            ["git", "status", "--short"], cwd=ROOT, text=True
        ).splitlines()
        protected = ("health/", "badges/", "feed.xml", "changelog.json", "data/")
        return [line for line in status if line[3:].startswith(protected)]

    before = protected_status()
    exit_code, _ = _run_mocked_canary(
        monkeypatch, tmp_path, copy.deepcopy(LIVE_HEALTH)
    )
    monkeypatch.undo()

    assert exit_code == 0
    assert protected_status() == before


def test_canary_report_includes_reproduction_command(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _, report = _run_mocked_canary(monkeypatch, tmp_path, copy.deepcopy(LIVE_HEALTH))

    assert "```bash\npython3 scripts/run_health_canary.py\n```" in report


def test_check_compare_health_runs_against_existing_health(tmp_path: Path) -> None:
    manifest = {
        "datasets": [
            {
                "id": "fixture_daily",
                "url": "https://example.invalid/fixture.json",
                "refresh_frequency": "daily",
                "namespace": "test",
            }
        ]
    }
    prior_health = {
        "schema": "datapulse/v0.3/dataset-health",
        "checked_at": "2026-08-08T00:00:00Z",
        "_trust_summary": {"datasets_total": 1, "by_status": {"fresh": 1}},
        "datasets": [
            {
                "dataset_id": "fixture_daily",
                "last_checked": "2026-08-08T00:00:00Z",
                "status": "fresh",
                "http_status": 200,
                "last_modified": "2026-08-08T00:00:00Z",
                "record_count": 1,
            }
        ],
    }
    (tmp_path / "datapulse.json").write_text(
        json.dumps(manifest) + "\n", encoding="utf-8"
    )
    health_path = tmp_path / "health/latest.json"
    health_path.parent.mkdir()
    health_path.write_text(json.dumps(prior_health) + "\n", encoding="utf-8")
    health_before = health_path.read_bytes()

    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    fake_curl = fake_bin / "curl"
    fake_curl.write_text(
        """#!/usr/bin/env bash
set -euo pipefail
output_path=""
headers_path=""
while (( $# > 0 )); do
  case "$1" in
    --output) output_path="$2"; shift 2 ;;
    --dump-header) headers_path="$2"; shift 2 ;;
    --max-time|--write-out) shift 2 ;;
    *) shift ;;
  esac
done
printf '[{"id":1,"name":"fixture"}]\\n' > "$output_path"
printf '%s\\r\\n' 'HTTP/1.1 200 OK' \\
  'Last-Modified: Sat, 08 Aug 2026 00:00:00 GMT' '' > "$headers_path"
printf '200'
""",
        encoding="utf-8",
    )
    fake_curl.chmod(0o755)
    environment = os.environ.copy()
    environment["PATH"] = f"{fake_bin}:{environment['PATH']}"

    completed = subprocess.run(
        [
            "bash",
            str(ROOT / "scripts/check.sh"),
            "--compare-health",
            "datapulse.json",
        ],
        cwd=tmp_path,
        env=environment,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    report = json.loads(completed.stderr)
    assert report["datasets_compared"] == 1
    assert report["differences"]
    assert report["differences"][0]["dataset_id"] == "fixture_daily"
    assert health_path.read_bytes() == health_before
