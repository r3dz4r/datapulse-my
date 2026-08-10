"""Offline integration coverage for shared HTTP probe templates."""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CHECK_SCRIPT = ROOT / "scripts/check.sh"


def test_shared_template_applies_headers_and_nested_freshness_path(tmp_path: Path) -> None:
    manifest = {
        "datasets": [
            {
                "id": "bnm_opr",
                "url": "https://api.bnm.gov.my/public/opr",
                "refresh_frequency": "as-required",
                "namespace": "government_open_data",
            },
            {
                "id": "plain_dataset",
                "url": "https://example.invalid/plain.json",
                "refresh_frequency": "daily (weekdays)",
                "namespace": "test",
            }
        ]
    }
    policy = {
        "version": 1,
        "defaults": {"adapter": "direct", "freshness-fallback": "last-modified"},
        "templates": {
            "bnm-open-api": {
                "type": "http",
                "headers": {
                    "Accept": "application/vnd.BNM.API.v1+json",
                    "User-Agent": "Mozilla/5.0 (compatible; DataPulseMY/1.0)",
                },
                "freshness": {
                    "content-date-field": "meta.last_updated",
                    "extraction-mode": "max",
                    "fallback": "last-modified",
                },
            }
        },
        "datasets": {"bnm_opr": {"template": "bnm-open-api"}},
    }
    (tmp_path / "datapulse.json").write_text(json.dumps(manifest) + "\n", encoding="utf-8")
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
accept_seen=false
user_agent_seen=false
while (( $# > 0 )); do
  case "$1" in
    --output) output_path="$2"; shift 2 ;;
    --dump-header) headers_path="$2"; shift 2 ;;
    --max-time|--write-out) shift 2 ;;
    --header)
      [[ "$2" == 'Accept: application/vnd.BNM.API.v1+json' ]] && accept_seen=true
      [[ "$2" == 'User-Agent: Mozilla/5.0 (compatible; DataPulseMY/1.0)' ]] && user_agent_seen=true
      shift 2
      ;;
    http*) request_url="$1"; shift ;;
    *) shift ;;
  esac
done
if [[ "$output_path" == "-" ]]; then
  exit 0
fi
if [[ "$request_url" == *api.bnm.gov.my* && ("$accept_seen" != true || "$user_agent_seen" != true) ]]; then
  printf '403'
  exit 0
fi
printf '%s\n' '{"data":{"new_opr_level":2.75},"meta":{"last_updated":"2026-08-10T01:02:03Z"}}' > "$output_path"
printf '%s\r\n\r\n' 'HTTP/1.1 200 OK' > "$headers_path"
printf '200'
""",
        encoding="utf-8",
    )
    fake_curl.chmod(0o755)

    environment = os.environ.copy()
    environment["PATH"] = f"{fake_bin}:{environment['PATH']}"
    environment["DATAPULSE_PROBE_POLICY"] = str(policy_path)
    completed = subprocess.run(
        [
            "bash",
            str(CHECK_SCRIPT),
            "--due",
            "--cadence-minutes",
            "999999",
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
    rows = {row["dataset_id"]: row for row in json.loads(completed.stdout)["datasets"]}
    assert rows["bnm_opr"]["http_status"] == 200
    assert rows["bnm_opr"]["content_freshness_date"] == "2026-08-10"
    assert rows["plain_dataset"]["http_status"] == 200
