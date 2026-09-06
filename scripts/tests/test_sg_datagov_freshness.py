"""Offline coverage for Singapore data.gov production freshness extraction."""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CHECK_SCRIPT = ROOT / "scripts/check.sh"
FIXTURES = ROOT / "scripts/tests/fixtures/sg_datagov"


def _extract(dataset_id: str, fixture: str) -> str:
    completed = subprocess.run(
        [
            "bash",
            "-lc",
            f'DATAPULSE_CHECK_SOURCE_ONLY=true source "{CHECK_SCRIPT}"; '
            f'extract_sg_datagov_freshness "{dataset_id}" "{FIXTURES / fixture}"',
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    return completed.stdout.strip()


def test_sg_source_timestamps_are_normalized_and_newest() -> None:
    assert _extract("sg_datagov_hdb_metadata", "hdb_metadata.json") == "2026-09-06T18:10:24Z"
    assert _extract("sg_datagov_taxi_availability", "taxi.json") == "2026-09-06T16:10:00Z"
    assert _extract("sg_datagov_weather_readings", "weather.json") == "2026-09-06T16:15:00Z"


def test_sg_malformed_or_missing_timestamps_fail_closed() -> None:
    assert _extract("sg_datagov_hdb_metadata", "malformed.json") == ""
    assert _extract("sg_datagov_taxi_availability", "malformed.json") == ""
    assert _extract("sg_datagov_weather_readings", "malformed.json") == ""


def test_hdb_rows_uses_paired_metadata_and_generic_dataset_is_unchanged(tmp_path: Path) -> None:
    manifest = {
        "datasets": [
            {"id": "sg_datagov_hdb_resale_prices", "url": "https://api-production.data.gov.sg/v2/public/api/datasets/d_8b84c4ee58e3cfc0ece0d773c8ca6abc/list-rows", "refresh_frequency": "monthly", "namespace": "test"},
            {"id": "plain_dataset", "url": "https://example.invalid/plain.json", "refresh_frequency": "daily", "namespace": "test"},
        ]
    }
    (tmp_path / "datapulse.json").write_text(json.dumps(manifest), encoding="utf-8")
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    fake_curl = fake_bin / "curl"
    fake_curl.write_text(
        """#!/usr/bin/env bash
set -euo pipefail
output_path=""; headers_path=""; request_url=""; max_time=""; write_status=false
while (( $# > 0 )); do
  case "$1" in
    --output) output_path="$2"; shift 2 ;;
    --dump-header) headers_path="$2"; shift 2 ;;
    --max-time) max_time="$2"; shift 2 ;;
    --write-out) write_status=true; shift 2 ;;
    http*) request_url="$1"; shift ;;
    *) shift ;;
  esac
done
if [[ "$request_url" == *'/metadata' ]]; then
  [[ "$max_time" == 20 ]]
  printf '%s\\n' '{"data":{"lastUpdatedAt":"2026-09-07T02:10:24+08:00"}}' > "$output_path"
else
  printf '%s\\n' '{"data":{"rows":[{"month":"2017-01"}]}}' > "$output_path"
fi
[[ -z "$headers_path" ]] || printf 'HTTP/1.1 200 OK\\r\\n\\r\\n' > "$headers_path"
if [[ "$write_status" == true ]]; then printf '200'; fi
""",
        encoding="utf-8",
    )
    fake_curl.chmod(0o755)
    environment = os.environ.copy()
    environment["PATH"] = f"{fake_bin}:{environment['PATH']}"
    completed = subprocess.run(
        ["bash", str(CHECK_SCRIPT), "--due", "--cadence-minutes", "999999", "datapulse.json"],
        cwd=tmp_path,
        env=environment,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    rows = {row["dataset_id"]: row for row in json.loads(completed.stdout)["datasets"]}
    assert rows["sg_datagov_hdb_resale_prices"]["content_freshness_date"] == "2026-09-06T18:10:24Z"
    assert rows["sg_datagov_hdb_resale_prices"]["freshness_signal_source"] == "content_date_parse"
    assert rows["plain_dataset"]["content_freshness_date"] is None
