"""Offline classification tests for lookup-table freshness policies."""

from __future__ import annotations

import json
import os
import subprocess
from datetime import datetime, timedelta, timezone
from email.utils import format_datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CHECK_SCRIPT = ROOT / "scripts/check.sh"
POLICY_PATH = ROOT / "scripts/probe-policy.json"
LOOKUP_DATASET_ID = "currency_codes"


def _run_lookup_probe(
    tmp_path: Path, last_modified: datetime | None, *, http_status: int = 200
) -> dict:
    policy = json.loads(POLICY_PATH.read_text(encoding="utf-8"))
    assert policy["datasets"][LOOKUP_DATASET_ID]["freshness"] == {
        "extraction-mode": "structural-hash",
        "fallback": "last-modified",
    }

    manifest = {
        "datasets": [
            {
                "id": LOOKUP_DATASET_ID,
                "data_type": "reference",
                "url": "https://example.invalid/lookup.json",
                "refresh_frequency": "daily",
                "namespace": "test",
            }
        ]
    }
    (tmp_path / "datapulse.json").write_text(
        json.dumps(manifest) + "\n", encoding="utf-8"
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
printf '[{"code":"ABC","label":"Lookup value"}]\n' > "$output_path"
printf 'HTTP/1.1 %s Mock\r\n' "${MOCK_HTTP_STATUS:-200}" > "$headers_path"
if [[ -n "${MOCK_LAST_MODIFIED:-}" ]]; then
  printf 'Last-Modified: %s\r\n' "$MOCK_LAST_MODIFIED" >> "$headers_path"
fi
printf '\r\n' >> "$headers_path"
printf '%s' "${MOCK_HTTP_STATUS:-200}"
""",
        encoding="utf-8",
    )
    fake_curl.chmod(0o755)

    environment = os.environ.copy()
    environment["PATH"] = f"{fake_bin}:{environment['PATH']}"
    environment["DATAPULSE_PROBE_POLICY"] = str(POLICY_PATH)
    environment["MOCK_HTTP_STATUS"] = str(http_status)
    if last_modified is not None:
        environment["MOCK_LAST_MODIFIED"] = format_datetime(
            last_modified, usegmt=True
        )
    else:
        environment.pop("MOCK_LAST_MODIFIED", None)

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


def test_reachable_reference_with_fresh_last_modified_is_reference(tmp_path: Path) -> None:
    row = _run_lookup_probe(tmp_path, datetime.now(timezone.utc) - timedelta(hours=1))

    assert row["status"] == "reference"
    assert row["content_freshness_date"] is None
    assert row["freshness_signal_source"] == "last_modified_header"


def test_reachable_reference_with_stale_last_modified_is_reference(tmp_path: Path) -> None:
    row = _run_lookup_probe(tmp_path, datetime.now(timezone.utc) - timedelta(days=4))

    assert row["status"] == "reference"
    assert row["content_freshness_date"] is None
    assert row["freshness_signal_source"] == "last_modified_header"


def test_reachable_reference_without_last_modified_is_reference(tmp_path: Path) -> None:
    row = _run_lookup_probe(tmp_path, None)

    assert row["status"] == "reference"
    assert row["content_freshness_date"] is None
    assert row["freshness_signal_source"] == "none"


def test_unreachable_reference_is_unreachable(tmp_path: Path) -> None:
    row = _run_lookup_probe(tmp_path, None, http_status=503)

    assert row["status"] == "unreachable"
    assert row["http_status"] == 503
