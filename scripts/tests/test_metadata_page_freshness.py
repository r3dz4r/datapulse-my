"""Offline integration coverage for data.gov.my catalogue-page freshness."""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CHECK_SCRIPT = ROOT / "scripts/check.sh"


def test_catalogue_page_data_as_of_and_missing_value_fallback(tmp_path: Path) -> None:
    manifest = {
        "datasets": [
            {
                "id": "page_date_present",
                "url": "https://api.data.gov.my/data-catalogue?id=fixture_present",
                "canonical_id": "fixture_present",
                "refresh_frequency": "daily",
                "namespace": "test",
            },
            {
                "id": "page_date_missing",
                "url": "https://api.data.gov.my/data-catalogue?id=fixture_missing",
                "canonical_id": "fixture_missing",
                "refresh_frequency": "daily",
                "namespace": "test",
            },
        ]
    }
    freshness = {
        "content-date-field": "data_as_of",
        "extraction-mode": "max",
        "fallback": "last-modified",
        "date-source": "data.gov.my-page",
    }
    policy = {
        "version": 1,
        "defaults": {"adapter": "direct", "freshness-fallback": "last-modified"},
        "datasets": {
            "page_date_present": {"freshness": freshness},
            "page_date_missing": {"freshness": freshness},
        },
    }
    (tmp_path / "datapulse.json").write_text(
        json.dumps(manifest) + "\n", encoding="utf-8"
    )
    policy_path = tmp_path / "probe-policy.json"
    policy_path.write_text(json.dumps(policy) + "\n", encoding="utf-8")

    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    fake_curl = fake_bin / "curl"
    fake_curl.write_text(
        """#!/usr/bin/env bash
set -euo pipefail
output_path=""
headers_path=""
request_url=""
while (( $# > 0 )); do
  case "$1" in
    --output) output_path="$2"; shift 2 ;;
    --dump-header) headers_path="$2"; shift 2 ;;
    --max-time|--write-out) shift 2 ;;
    http*) request_url="$1"; shift ;;
    *) shift ;;
  esac
done
if [[ "$output_path" == "-" ]]; then
  exit 0
fi
if [[ "$request_url" == https://api.data.gov.my/* ]]; then
  printf '[{"metric":"downloads","value":42}]\n' > "$output_path"
  printf 'HTTP/1.1 200 OK\r\n\r\n' > "$headers_path"
  printf '200'
elif [[ "$request_url" == */fixture_present ]]; then
  printf '%s\n' '<html><script id="__NEXT_DATA__" type="application/json">{"props":{"pageProps":{"data_as_of":"2026-08-08 23:59","frequency":"DAILY"}}}</script></html>' > "$output_path"
elif [[ "$request_url" == */fixture_missing ]]; then
  printf '%s\n' '<html><script id="__NEXT_DATA__" type="application/json">{"props":{"pageProps":{"frequency":"DAILY"}}}</script></html>' > "$output_path"
else
  exit 22
fi
""",
        encoding="utf-8",
    )
    fake_curl.chmod(0o755)

    environment = os.environ.copy()
    environment["PATH"] = f"{fake_bin}:{environment['PATH']}"
    environment["DATAPULSE_PROBE_POLICY"] = str(policy_path)
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
    rows = {row["dataset_id"]: row for row in json.loads(completed.stdout)["datasets"]}
    assert rows["page_date_present"]["record_count"] == 1
    assert rows["page_date_present"]["content_freshness_date"] == "2026-08-08"
    assert rows["page_date_present"]["freshness_signal"] == "content-date-parse"
    assert rows["page_date_present"]["freshness_signal_source"] == "content_date_parse"
    assert rows["page_date_missing"]["content_freshness_date"] is None
    assert rows["page_date_missing"]["status"] == "unknown-freshness"
    assert rows["page_date_missing"]["freshness_signal_source"] == "none"
