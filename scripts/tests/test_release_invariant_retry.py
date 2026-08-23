"""Regression coverage for Pages-propagation release fetches."""

from __future__ import annotations

import os
import re
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from scripts import gen_attestations as ga
from scripts.tests.test_attestations import fixture_root
from scripts.verify_attestation_binding import ContractError, verify_contract


ROOT = Path(__file__).resolve().parents[2]
VERIFY_SCRIPT = ROOT / "scripts/verify_release_invariants.sh"


def test_local_gate_accepts_pre_generation_source_without_binding() -> None:
    """CI validates source contracts before release-build creates a binding."""
    assert not (ROOT / "attestations/latest/binding.json").exists()

    completed = subprocess.run(
        ["bash", str(VERIFY_SCRIPT), "--local"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    assert "Local pre-generation attestation structure: PASS" in completed.stdout


def test_generated_contract_still_rejects_a_missing_binding(tmp_path: Path) -> None:
    """The source exception must not let a generated artifact skip its binding."""
    root, key = fixture_root(tmp_path)
    now = datetime(2026, 8, 15, 1, tzinfo=timezone.utc)
    ga.generate(root, key, now)
    (root / "attestations/latest/binding.json").unlink()

    with pytest.raises(ContractError, match="latest binding is missing or invalid"):
        verify_contract(root, now=now + timedelta(hours=1))


def test_served_mode_keeps_binding_verification_outside_the_local_exception() -> None:
    """Only source validation may omit the generated binding contract."""
    script = VERIFY_SCRIPT.read_text(encoding="utf-8")
    served_contract = re.search(
        r"(?ms)^if ! \$local_mode; then\n(.*?)^fi\n\nvertical_ids=", script
    )

    assert served_contract is not None
    assert 'python3 scripts/verify_attestation_binding.py "${binding_args[@]}"' in served_contract.group(1)
    assert "DATAPULSE_ALLOW_UNATTESTED_HEALTH" in served_contract.group(1)


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
