"""Regression coverage for Pages-propagation release fetches."""

from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
VERIFY_SCRIPT = ROOT / "scripts/verify_release_invariants.sh"


def test_fetch_retries_http_404_with_pages_budget(tmp_path: Path) -> None:
    script = VERIFY_SCRIPT.read_text(encoding="utf-8")
    match = re.search(r"(?ms)^fetch\(\) \{\n.*?^\}\n", script)
    assert match is not None

    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    fake_curl = fake_bin / "curl"
    fake_curl.write_text(
        """#!/usr/bin/env bash
set -euo pipefail
retry=0
delay=0
all_errors=false
output=""
while (( $# > 0 )); do
  case "$1" in
    --retry) retry="$2"; shift 2 ;;
    --retry-delay) delay="$2"; shift 2 ;;
    --retry-all-errors) all_errors=true; shift ;;
    --connect-timeout|--max-time) shift 2 ;;
    --output) output="$2"; shift 2 ;;
    *) shift ;;
  esac
done
printf '404\n' >> "${MOCK_CURL_ATTEMPTS:?}"
if [[ "$retry" == 12 && "$delay" == 15 && "$all_errors" == true ]]; then
  printf '200\n' >> "$MOCK_CURL_ATTEMPTS"
  printf 'propagated\n' > "$output"
  exit 0
fi
exit 22
""",
        encoding="utf-8",
    )
    fake_curl.chmod(0o755)

    attempts = tmp_path / "attempts.log"
    environment = os.environ.copy()
    environment["PATH"] = f"{fake_bin}:{environment['PATH']}"
    environment["MOCK_CURL_ATTEMPTS"] = str(attempts)
    command = "\n".join(
        (
            "set -Eeuo pipefail",
            "local_mode=false",
            f"work_dir={tmp_path!s}",
            'base_url="https://example.invalid"',
            match.group(0),
            'fetch result.txt "health-methodology.html"',
        )
    )
    completed = subprocess.run(
        ["bash", "-c", command],
        cwd=ROOT,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    assert attempts.read_text(encoding="utf-8").splitlines() == ["404", "200"]
    assert (tmp_path / "result.txt").read_text(encoding="utf-8") == "propagated\n"


def test_gate_8_fetches_public_methodology_path() -> None:
    script = VERIFY_SCRIPT.read_text(encoding="utf-8")
    assert 'fetch "health-methodology.html" "health-methodology.html"' in script
    assert 'fetch "health-methodology.html" "$methodology_file"' not in script
