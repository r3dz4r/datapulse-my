"""Regression tests for discontinued health-status classification."""

from __future__ import annotations

import json
import os
import subprocess
from datetime import datetime, timedelta, timezone
from email.utils import format_datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CHECK_SCRIPT = ROOT / "scripts/check.sh"


def _classify(
    tmp_path: Path,
    age_days: int,
    *,
    frequency: str = "annual",
    discontinued: bool = False,
    reference: bool = False,
) -> dict:
    manifest_row = {
        "id": "fixture_discontinued",
        "url": "https://example.invalid/fixture.json",
        "refresh_frequency": frequency,
        "namespace": "test",
    }
    if discontinued:
        manifest_row["discontinued"] = True
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


def test_staleness_over_730_days_is_discontinued(tmp_path: Path) -> None:
    assert _classify(tmp_path, 731)["status"] == "discontinued"


def test_manifest_discontinued_flag_wins_for_fresh_data(tmp_path: Path) -> None:
    assert _classify(tmp_path, 1, discontinued=True)["status"] == "discontinued"


def test_null_cadence_over_730_days_is_discontinued(tmp_path: Path) -> None:
    assert _classify(tmp_path, 800, frequency="as-required")["status"] == "discontinued"


def test_reference_data_is_not_reclassified(tmp_path: Path) -> None:
    row = _classify(tmp_path, 800, frequency="as-required", reference=True)

    assert row["status"] == "reference"
