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


def test_local_gate_does_not_require_current_release_proof() -> None:
    """Local source validation must not read stale or absent generated proof."""
    script = VERIFY_SCRIPT.read_text(encoding="utf-8")

    proof_fetch = re.search(
        r"(?ms)^if ! \$local_mode; then\n  fetch release-verification\.md release-verification\.md\n  fetch index\.html docs/index\.html\n  fetch npra\.html docs/npra\.html\n  fetch buyer-api-reference\.md docs/buyer-api-reference\.md\n^fi\n",
        script,
    )

    assert "fetch release-verification.md docs/release-verification.md" not in script
    assert proof_fetch is not None
    proof_validation = re.search(
        r"(?ms)^if ! \$local_mode; then\npython3 - \"\$work_dir/release-verification\.md\".*?^PY\n^fi\n",
        script,
    )

    assert proof_validation is not None
    assert "source_sha" in proof_validation.group(0)


def test_served_gate_keeps_release_proof_drift_validation_strict() -> None:
    """Served validation must still reject proof metadata drift."""
    script = VERIFY_SCRIPT.read_text(encoding="utf-8")
    proof_validation = re.search(
        r"(?ms)^if ! \$local_mode; then\npython3 - \"\$work_dir/release-verification\.md\".*?^PY\n^fi\n",
        script,
    )

    assert proof_validation is not None
    validation = proof_validation.group(0)
    assert '"- Status: `current generated release proof`"' in validation
    assert 'f"- Source SHA: `{source_sha}`"' in validation
    assert 'f"- Health checked at: `{health[\'checked_at\']}`"' in validation
    assert 'f"- MCP tool count: `{len(tools)}`"' in validation
    assert '"release proof drift: "' in validation


def test_local_gate_skips_only_generated_p5b_surface_parity() -> None:
    """Local mode keeps source contracts while deferring generated page parity."""
    script = VERIFY_SCRIPT.read_text(encoding="utf-8")

    generated_fetches = re.search(
        r"(?ms)^if ! \$local_mode; then\n  fetch release-verification\.md.*?^fi\n",
        script,
    )
    assert generated_fetches is not None
    assert 'fetch index.html docs/index.html' in generated_fetches.group(0)
    assert 'fetch npra.html docs/npra.html' in generated_fetches.group(0)
    assert 'fetch buyer-api-reference.md docs/buyer-api-reference.md' in generated_fetches.group(0)

    p5b_validation = re.search(
        r"(?ms)^if ! \$local_mode; then\npython3 - \"\$work_dir\" <<'PY'.*?^fi\n\nPYTHONPATH=mcp",
        script,
    )
    assert p5b_validation is not None
    assert "P5B generated surface assertions: PASS" in p5b_validation.group(0)
    assert "dashboard-summary" in p5b_validation.group(0)
    assert "buyer-api-pagination" in p5b_validation.group(0)

    common_source = script.split('if ! $local_mode; then\npython3 - "$work_dir" <<\'PY\'', 1)[0]
    assert 'load_public_surfaces(Path.cwd())' in common_source
    assert 'assert surfaces["pages"]' in common_source
    assert 'dashboard-summary' not in common_source


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


def _url_audit_function() -> str:
    script = VERIFY_SCRIPT.read_text(encoding="utf-8")
    match = re.search(r"(?ms)^check_url_file\(\) \{\n.*?^\}\n", script)
    assert match is not None
    return match.group(0)


def _run_url_audit(tmp_path: Path, statuses: str, *, label: str = "JSON-LD/report", url_content: str | None = None) -> subprocess.CompletedProcess[str]:
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    fake_curl = fake_bin / "curl"
    fake_curl.write_text(
        """#!/usr/bin/env bash
set -euo pipefail
url="${@: -1}"
state_file="${MOCK_CURL_STATE:?}/$(printf '%s' "$url" | sha256sum | cut -d' ' -f1)"
attempt=0
if [[ -f "$state_file" ]]; then
  attempt=$(<"$state_file")
fi
attempt=$((attempt + 1))
printf '%s\n' "$attempt" > "$state_file"
read -r -a statuses <<< "${MOCK_CURL_STATUSES:?}"
has_all_errors=false
has_retry_delay=false
for arg in "$@"; do
  [[ "$arg" == "--retry-all-errors" ]] && has_all_errors=true
  [[ "$arg" == "--retry-delay" ]] && has_retry_delay=true
done
if [[ "$has_all_errors" == true && "$has_retry_delay" == true && "${#statuses[@]}" -gt 1 ]]; then
  printf '%s\n' "${statuses[1]}"
else
  printf '%s\n' "${statuses[0]:-500}"
fi
printf 'fake curl diagnostic for %s (attempt %s)\n' "$url" "$attempt" >&2
""",
        encoding="utf-8",
    )
    fake_curl.chmod(0o755)

    url_file = tmp_path / "urls.txt"
    exact_url = "https://example.invalid/data/report.json"
    url_file.write_text(url_content if url_content is not None else f"{exact_url}\n", encoding="utf-8")
    state_dir = tmp_path / "state"
    state_dir.mkdir()
    environment = os.environ.copy()
    environment["PATH"] = f"{fake_bin}:{environment['PATH']}"
    environment["MOCK_CURL_STATE"] = str(state_dir)
    environment["MOCK_CURL_STATUSES"] = statuses
    command = "\n".join(
        (
            "set -Eeuo pipefail",
            _url_audit_function(),
            f"check_url_file {label!r} {str(url_file)!r}",
        )
    )
    return subprocess.run(
        ["bash", "-c", command],
        cwd=ROOT,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )


@pytest.mark.parametrize("transient_status", ["404", "503"])
def test_url_audit_recovers_transient_pages_errors_and_records_curl_retry_flags(
    tmp_path: Path, transient_status: str
) -> None:
    completed = _run_url_audit(tmp_path, f"{transient_status} 200")

    assert completed.returncode == 0, completed.stderr
    assert "JSON-LD/report URLs: PASS (1 checked)" in completed.stdout


def test_url_audit_reports_exact_url_status_and_stderr_on_persistent_failure(tmp_path: Path) -> None:
    completed = _run_url_audit(tmp_path, "404 404 404")

    assert completed.returncode != 0
    assert "JSON-LD/report URL validation failed" in completed.stderr
    assert "URL_AUDIT_FAILURE label=JSON-LD/report final=HTTP_404 url=https://example.invalid/data/report.json" in completed.stderr
    assert "fake curl diagnostic" in completed.stderr


@pytest.mark.parametrize("url_content", ["\n", "not-a-url\n", "ftp://example.invalid/report.json\n"])
def test_url_audit_rejects_empty_or_malformed_input(tmp_path: Path, url_content: str) -> None:
    completed = _run_url_audit(tmp_path, "200", url_content=url_content)

    assert completed.returncode != 0
    assert "invalid URL input" in completed.stderr


@pytest.mark.parametrize("status", ["406", "415"])
def test_url_audit_accepts_documented_non_success_statuses(tmp_path: Path, status: str) -> None:
    completed = _run_url_audit(tmp_path, status)

    assert completed.returncode == 0, completed.stderr


def test_gate_8_fetches_public_methodology_path() -> None:
    script = VERIFY_SCRIPT.read_text(encoding="utf-8")
    assert 'fetch "health-methodology.html" "health-methodology.html"' in script
    assert 'fetch "health-methodology.html" "$methodology_file"' not in script
