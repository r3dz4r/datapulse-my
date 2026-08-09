import json
import os
import subprocess
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[2]
CHECK_SCRIPT = ROOT / "scripts/check.sh"


def _write_mock_curl(tmp_path: Path) -> Path:
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    curl = fake_bin / "curl"
    curl.write_text(
        """#!/usr/bin/env bash
set -euo pipefail
url="${!#}"
if [[ "$url" == */robots.txt ]]; then
  printf '%s' "${MOCK_ROBOTS_BODY:-}"
  exit "${MOCK_ROBOTS_EXIT:-0}"
fi
printf '%s\n' "$url" >> "${MOCK_CURL_LOG:?}"
exit 99
""",
        encoding="utf-8",
    )
    curl.chmod(0o755)
    return fake_bin


def _robots_result(tmp_path: Path, robots_body: str, *, curl_exit: int = 0) -> int:
    fake_bin = _write_mock_curl(tmp_path)
    curl_log = tmp_path / "curl.log"
    environment = {
        "PATH": f"{fake_bin}:{os.environ['PATH']}",
        "MOCK_CURL_LOG": str(curl_log),
        "MOCK_ROBOTS_BODY": robots_body,
        "MOCK_ROBOTS_EXIT": str(curl_exit),
    }
    command = (
        f'DATAPULSE_CHECK_SOURCE_ONLY=true source "{CHECK_SCRIPT}"; '
        'respect_robots_txt "test-dataset" "https://example.invalid/data.json"'
    )
    with mock.patch.dict(os.environ, environment, clear=False):
        completed = subprocess.run(
            ["bash", "-c", command],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
    return completed.returncode


def test_allows_when_robots_txt_absent(tmp_path: Path) -> None:
    assert _robots_result(tmp_path, "", curl_exit=22) == 0


def test_allows_when_robots_txt_has_no_disallow(tmp_path: Path) -> None:
    assert _robots_result(tmp_path, "User-agent: *\nAllow: /\n") == 0


def test_blocks_when_robots_txt_disallows_root(tmp_path: Path) -> None:
    assert _robots_result(tmp_path, "User-agent: *\nDisallow: /\n") == 1


def test_blocks_specific_ua_when_listed(tmp_path: Path) -> None:
    assert _robots_result(tmp_path, "User-agent: DataPulseMY\nDisallow: /\n") == 1


def test_allows_when_ua_explicitly_allowed(tmp_path: Path) -> None:
    assert _robots_result(tmp_path, "User-agent: DataPulseMY\nDisallow:\n") == 0


def test_skips_blocked_datasets_in_real_run(tmp_path: Path) -> None:
    fake_bin = _write_mock_curl(tmp_path)
    curl_log = tmp_path / "curl.log"
    manifest = tmp_path / "manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "datasets": [
                    {
                        "id": "blocked-dataset",
                        "url": "https://example.invalid/data.json",
                        "refresh_frequency": "daily",
                        "namespace": "test",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    environment = {
        "PATH": f"{fake_bin}:{os.environ['PATH']}",
        "MOCK_CURL_LOG": str(curl_log),
        "MOCK_ROBOTS_BODY": "User-agent: *\nDisallow: /\n",
        "MOCK_ROBOTS_EXIT": "0",
    }

    with mock.patch.dict(os.environ, environment, clear=False):
        completed = subprocess.run(
            ["bash", str(CHECK_SCRIPT), str(manifest)],
            cwd=tmp_path,
            check=False,
            capture_output=True,
            text=True,
        )

    assert completed.returncode == 0, completed.stderr
    result = json.loads(completed.stdout)
    assert result["datasets"][0]["status"] == "unreachable"
    assert result["datasets"][0]["message"] == "Probe skipped: blocked by robots.txt"
    assert not curl_log.exists()
