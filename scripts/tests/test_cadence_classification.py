"""Regression tests for cadence-based freshness classification in check.sh."""

from __future__ import annotations

import json
import os
import subprocess
from datetime import datetime, timedelta, timezone
from email.utils import format_datetime
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
CHECK_SCRIPT = ROOT / "scripts/check.sh"


def _classify(
    tmp_path: Path, frequency: str, age_days: int, *, reference: bool = False
) -> dict:
    manifest_row = {
        "id": "fixture_cadence",
        "url": "https://example.invalid/fixture.json",
        "refresh_frequency": frequency,
        "namespace": "test",
    }
    if reference:
        manifest_row["data_type"] = "reference"
    (tmp_path / "datapulse.json").write_text(
        json.dumps({"datasets": [manifest_row]}) + "\n", encoding="utf-8"
    )

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
if [[ "$output_path" == "-" ]]; then
  exit 0
fi
printf '[{"id":1,"name":"fixture"}]\n' > "$output_path"
printf 'HTTP/1.1 200 OK\r\nLast-Modified: %s\r\n\r\n' "$MOCK_LAST_MODIFIED" > "$headers_path"
printf '200'
""",
        encoding="utf-8",
    )
    fake_curl.chmod(0o755)

    environment = os.environ.copy()
    environment["PATH"] = f"{fake_bin}:{environment['PATH']}"
    environment["MOCK_LAST_MODIFIED"] = format_datetime(
        datetime.now(timezone.utc) - timedelta(days=age_days), usegmt=True
    )
    completed = subprocess.run(
        ["bash", str(CHECK_SCRIPT), "datapulse.json"],
        cwd=tmp_path,
        env=environment,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    return json.loads(completed.stdout)["datasets"][0]


@pytest.mark.parametrize(
    ("frequency", "age_days", "expected"),
    [
        ("hourly", 1, "stale"),
        ("30 seconds", 1, "stale"),
        ("biennial to triennial (survey years)", 1200, "aging"),
        ("as-required", 200, "aging"),
        ("as-required", 300, "stale"),
    ],
)
def test_cadence_and_null_fallback_are_conservative(
    tmp_path: Path, frequency: str, age_days: int, expected: str
) -> None:
    row = _classify(tmp_path, frequency, age_days)

    assert row["staleness_status"] == expected
    assert row["status"] == expected


def test_reference_status_precedes_staleness(tmp_path: Path) -> None:
    row = _classify(tmp_path, "as-required", 300, reference=True)

    assert row["staleness_status"] == "stale"
    assert row["status"] == "reference"


def test_bnm_opr_has_monthly_manifest_cadence() -> None:
    manifest = json.loads((ROOT / "datapulse.json").read_text(encoding="utf-8"))
    bnm_opr = next(row for row in manifest["datasets"] if row["id"] == "bnm_opr")

    assert bnm_opr["refresh_frequency"] == "monthly"
