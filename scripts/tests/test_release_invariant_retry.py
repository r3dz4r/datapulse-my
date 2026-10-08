"""Regression coverage for Pages-propagation release fetches."""

from __future__ import annotations

import hashlib
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from scripts import gen_attestations as ga
from scripts.tests.test_attestations import fixture_rekor_reference, fixture_root, write
from scripts.verify_attestation_binding import ContractError, verify_contract


ROOT = Path(__file__).resolve().parents[2]
VERIFY_SCRIPT = ROOT / "scripts/verify_release_invariants.sh"


def test_local_gate_accepts_readme_prepared_source_without_binding() -> None:
    """Source CI prepares README before validating a checkout without a binding."""
    with tempfile.TemporaryDirectory() as worktree_dir:
        worktree = Path(worktree_dir)
        subprocess.run(
            ["git", "worktree", "add", "--detach", str(worktree), "HEAD"],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
        try:
            shutil.copy2(VERIFY_SCRIPT, worktree / "scripts/verify_release_invariants.sh")
            snapshot = subprocess.run(
                [sys.executable, "scripts/gen_catalog_snapshot.py"],
                cwd=worktree,
                capture_output=True,
                text=True,
                check=False,
            )
            assert snapshot.returncode == 0, snapshot.stderr
            prepared = subprocess.run(
                [sys.executable, "scripts/gen_readme.py"],
                cwd=worktree,
                capture_output=True,
                text=True,
                check=False,
            )
            assert prepared.returncode == 0, prepared.stderr
            completed = subprocess.run(
                ["bash", str(worktree / "scripts/verify_release_invariants.sh"), "--local"],
                cwd=worktree,
                capture_output=True,
                text=True,
                check=False,
            )
        finally:
            subprocess.run(
                ["git", "worktree", "remove", "--force", str(worktree)],
                cwd=ROOT,
                check=True,
                capture_output=True,
                text=True,
            )

    assert completed.returncode == 0, completed.stderr
    assert "Local pre-generation attestation structure: PASS" in completed.stdout


def _shadow_checkout(destination: Path) -> Path:
    """Materialize a mutable copy of the checkout for a release-gate run.

    Read-only trees are symlinked so the copy stays cheap, while every path the
    release build rewrites is a real copy so the test never mutates ROOT.
    """
    shadow = destination / "checkout"
    shadow.mkdir()
    mutable = {
        "datapulse.json",
        "health",
        "docs",
        "scripts",
        "attestations",
        ".attestations",
        "catalog-snapshot.json",
        "changelog.json",
        "README.md",
    }
    for entry in ROOT.iterdir():
        if entry.name == ".git" or entry.name in mutable:
            continue
        (shadow / entry.name).symlink_to(entry)
    shutil.copy2(ROOT / "datapulse.json", shadow / "datapulse.json")
    (shadow / "health").mkdir()
    for name in (
        "latest.json",
        "trends.json",
        "drift.json",
        "reconciliation.json",
        "history.jsonl",
        "probe_counts.json",
    ):
        source = ROOT / "health" / name
        if source.is_file():
            shutil.copy2(source, shadow / "health" / name)
    shutil.copytree(ROOT / "docs", shadow / "docs")
    shutil.copytree(ROOT / "scripts", shadow / "scripts")
    (shadow / "attestations").mkdir()
    shutil.copytree(ROOT / ".attestations", shadow / ".attestations")
    for name in ("catalog-snapshot.json", "changelog.json", "README.md"):
        source = ROOT / name
        if source.is_file():
            shutil.copy2(source, shadow / name)
    return shadow


def test_shadow_checkout_isolates_attestations(tmp_path: Path) -> None:
    real_chain_head = ROOT / ".attestations/chain_head.json"
    before = hashlib.sha256(real_chain_head.read_bytes()).hexdigest()

    shadow = _shadow_checkout(tmp_path)
    signing_root, key = fixture_root(tmp_path / "signing")
    shutil.copy2(
        signing_root / "docs/.well-known/datapulse-probe-keys.json",
        shadow / "docs/.well-known/datapulse-probe-keys.json",
    )
    ga.generate(shadow, key, datetime(2026, 10, 6, 7, tzinfo=timezone.utc))

    after = hashlib.sha256(real_chain_head.read_bytes()).hexdigest()
    assert after == before


def test_release_invariant_retry_corrected_index(tmp_path: Path) -> None:
    """A same-day correction must still pass the release contract.

    The worktree case above exercises the committed flat dated set. A corrected
    day instead publishes its head beneath a content-addressed
    revisions/<64-hex>/ directory, which is the deliberate form
    gen_attestations.py produces and verify_attestation_binding.py accepts.
    """
    shadow = _shadow_checkout(tmp_path)
    signing_root, key = fixture_root(tmp_path / "signing")
    shutil.copy2(
        signing_root / "docs/.well-known/datapulse-probe-keys.json",
        shadow / "docs/.well-known/datapulse-probe-keys.json",
    )
    now = datetime(2026, 10, 6, 7, tzinfo=timezone.utc)
    ga.generate(shadow, key, now)
    health = shadow / "health/latest.json"
    # Same rows, new bytes: this is what triggers the content-addressed revision.
    health.write_bytes(health.read_bytes() + b"\n")
    ga.generate(shadow, key, now + timedelta(hours=1))

    corrected_ref = ga.load(shadow / "attestations/latest/index.json")["chain_head_ref"]
    assert re.fullmatch(
        r"attestations/[0-9]{4}-[0-9]{2}-[0-9]{2}/revisions/[0-9a-f]{64}/chain_head\.json",
        corrected_ref,
    ), corrected_ref

    for generator in ("gen_catalog_snapshot.py", "gen_readme.py"):
        prepared = subprocess.run(
            [sys.executable, f"scripts/{generator}"],
            cwd=shadow,
            capture_output=True,
            text=True,
            check=False,
        )
        assert prepared.returncode == 0, prepared.stderr

    completed = subprocess.run(
        ["bash", "scripts/verify_release_invariants.sh", "--local"],
        cwd=shadow,
        env={**os.environ, "TMPDIR": str(tmp_path), "PYTHONDONTWRITEBYTECODE": "1"},
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    assert "Local pre-generation attestation structure: PASS" in completed.stdout


@pytest.mark.parametrize("missing_revision_binding", [False, True])
def test_nonlocal_fetch_resolves_signed_same_day_correction(
    tmp_path: Path, missing_revision_binding: bool
) -> None:
    served, key = fixture_root(tmp_path / "served")
    now = datetime.now(timezone.utc).replace(microsecond=0)
    day = now.date().isoformat()
    original_at = now - timedelta(seconds=2)
    corrected_at = now - timedelta(seconds=1)
    health = json.loads((served / "health/latest.json").read_text(encoding="utf-8"))
    health["checked_at"] = original_at.strftime("%Y-%m-%dT%H:%M:%SZ")
    health["datasets"][0]["last_checked"] = health["checked_at"]
    write(served / "health/latest.json", health)
    ga.generate(served, key, original_at, fixture_rekor_reference(served, f"rekor/{day}"))
    health["datasets"][0]["status"] = "stale"
    write(served / "health/latest.json", health)
    ga.generate(
        served,
        key,
        corrected_at,
        fixture_rekor_reference(served, f"rekor/{day}/correction"),
    )
    index = ga.load(served / "attestations/latest/index.json")
    revision = Path(index["chain_head_ref"]).parent
    assert "revisions" in revision.parts

    work = tmp_path / "fetched"
    contract = work / "contract-root"
    for source, target in (
        ("attestations/latest/index.json", "attestations/latest/index.json"),
        ("attestations/latest/chain_head.json", "attestations/latest/chain_head.json"),
        ("attestations/latest/binding.json", "attestations/latest/binding.json"),
        ("health/latest.json", "health/latest.json"),
        ("docs/.well-known/datapulse-probe-keys.json", "docs/.well-known/datapulse-probe-keys.json"),
    ):
        destination = contract / target
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(served / source, destination)
    for name in ("index", "binding"):
        shutil.copy2(served / f"attestations/latest/{name}.json", work / f"attestation-{name}.json")
    if missing_revision_binding:
        (served / revision / "binding.json").unlink()

    stub = tmp_path / "bin"
    stub.mkdir()
    curl = stub / "curl"
    curl.write_text(
        f"#!{sys.executable}\n"
        "import os, pathlib, sys\n"
        "args = sys.argv[1:]\n"
        "url = next(arg for arg in args if arg.startswith('https://'))\n"
        "path = url.split('://', 1)[1].split('/', 1)[1]\n"
        "with open(os.environ['FETCH_LOG'], 'a') as log: log.write(path + '\\n')\n"
        "source = pathlib.Path(os.environ['SERVED_ROOT']) / path\n"
        "output = pathlib.Path(args[args.index('--output') + 1])\n"
        "if not source.is_file():\n"
        " print('404', end='')\n"
        " sys.exit(22)\n"
        "output.write_bytes(source.read_bytes())\n"
        "print('200', end='')\n",
        encoding="utf-8",
    )
    curl.chmod(0o755)
    script = VERIFY_SCRIPT.read_text(encoding="utf-8")
    functions = [
        re.search(rf"(?ms)^{name}\(\) \{{\n.*?^\}}\n", script).group(0)
        for name in ("fetch", "fetch_optional", "fetch_attestation_contract_root")
    ]
    command = "\n".join(
        (
            "set -Eeuo pipefail",
            "local_mode=false",
            f"work_dir={shlex.quote(str(work))}",
            'base_url="https://fixture.example.test"',
            *functions,
            f"fetch_attestation_contract_root {shlex.quote(str(contract))}",
        )
    )
    environment = {
        **os.environ,
        "PATH": f"{stub}:{os.environ['PATH']}",
        "SERVED_ROOT": str(served),
        "FETCH_LOG": str(tmp_path / "fetch.log"),
    }
    fetched = subprocess.run(
        ["bash", "-c", command], cwd=ROOT, env=environment,
        capture_output=True, text=True, check=False,
    )
    binding = subprocess.run(
        [sys.executable, "scripts/verify_attestation_binding.py", "--root", str(contract), "--head-only"],
        cwd=ROOT, capture_output=True, text=True, check=False,
    )
    if missing_revision_binding:
        assert fetched.returncode != 0
        assert str(revision / "binding.json") in fetched.stderr
        assert binding.returncode != 0
        return

    assert fetched.returncode == 0, fetched.stderr
    requested = set((tmp_path / "fetch.log").read_text(encoding="utf-8").splitlines())
    for set_dir in (Path("attestations") / day, revision):
        for name in ("chain_head.json", "binding.json", "index.json"):
            assert str(set_dir / name) in requested
    assert str(revision / "health.json") in requested
    for name in (f"attestations/rekor/{day}/reference.json", f"attestations/rekor/{day}/bundle.json",
                 f"attestations/rekor/{day}/correction/reference.json", f"attestations/rekor/{day}/correction/bundle.json"):
        assert name in requested
    assert binding.returncode == 0, binding.stderr
    plane = subprocess.run(
        [sys.executable, "scripts/verify_attestation_plane_state.py", "--planedir", str(contract), "--head-only"],
        cwd=ROOT, capture_output=True, text=True, check=False,
    )
    assert plane.returncode == 0, plane.stderr
    assert plane.stdout.strip() == "healthy"


def test_readme_health_parity_still_rejects_an_inconsistent_generated_readme(
    tmp_path: Path,
) -> None:
    """Release-mode parity remains a hard failure for generated artifacts."""
    script = VERIFY_SCRIPT.read_text(encoding="utf-8")
    parity_function = script.split("assert_readme_health_parity() {\n", 1)[1].split(
        "\nfetch manifest.json", 1
    )[0]

    health_file = tmp_path / "latest.json"
    health_file.write_text(
        '{"_trust_summary":{"by_status":{"fresh":2,"stale":1}}}',
        encoding="utf-8",
    )
    readme_file = tmp_path / "README.md"
    readme_file.write_text(
        "Current distribution (`_trust_summary`): [1 fresh] · [1 stale]\n",
        encoding="utf-8",
    )
    completed = subprocess.run(
        [
            "bash",
            "-c",
            f"set -Eeuo pipefail\npython_bin=python3\n"
            f"assert_readme_health_parity() {{\n{parity_function}\n"
            f"assert_readme_health_parity {health_file!s} {readme_file!s}",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 1
    assert "README trust-summary disagrees with health/latest.json" in completed.stderr


def test_local_gate_explains_that_readme_health_parity_is_release_scoped() -> None:
    """Cadence lag must be visibly skipped, never silently accepted locally."""
    script = VERIFY_SCRIPT.read_text(encoding="utf-8")

    assert "if $local_mode; then\n  printf 'README-to-health distribution parity: SKIPPED" in script
    assert 'assert_readme_health_parity "$work_dir/health.json" README.md' in script


def test_local_gate_does_not_require_current_release_proof() -> None:
    """Local source validation must not read stale or absent generated proof."""
    script = VERIFY_SCRIPT.read_text(encoding="utf-8")

    proof_fetch = re.search(
        r"(?ms)^if ! \$local_mode; then\n  fetch release-verification\.md release-verification\.md\n  fetch index\.html dashboard\n  fetch landing\.html landing\.html\n  fetch npra\.html npra\.html\n^fi\n",
        script,
    )

    assert "fetch release-verification.md docs/release-verification.md" not in script
    assert proof_fetch is not None
    proof_validation = re.search(
        r'(?ms)^if ! \$local_mode; then\n"\$python_bin" - "\$work_dir/release-verification\.md".*?^PY\n^fi\n',
        script,
    )

    assert proof_validation is not None
    assert "source_sha" in proof_validation.group(0)


def test_served_gate_keeps_release_proof_drift_validation_strict() -> None:
    """Served validation must still reject proof metadata drift."""
    script = VERIFY_SCRIPT.read_text(encoding="utf-8")
    proof_validation = re.search(
        r'(?ms)^if ! \$local_mode; then\n"\$python_bin" - "\$work_dir/release-verification\.md".*?^PY\n^fi\n',
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
    assert 'fetch index.html dashboard' in generated_fetches.group(0)
    assert 'fetch landing.html landing.html' in generated_fetches.group(0)
    assert 'fetch npra.html npra.html' in generated_fetches.group(0)
    assert not re.search(r'^\s*fetch\s+\S+\s+/?docs/', generated_fetches.group(0), re.MULTILINE)

    p5b_validation = re.search(
        r'''(?ms)^if ! \$local_mode; then\n"\$python_bin" - "\$work_dir" <<'PY'.*?^fi\n\nPYTHONPATH=mcp''',
        script,
    )
    assert p5b_validation is not None
    assert "P5B generated surface assertions: PASS" in p5b_validation.group(0)
    assert "dashboard-summary" in p5b_validation.group(0)

    common_source = script.split('if ! $local_mode; then\n"$python_bin" - "$work_dir" <<\'PY\'', 1)[0]
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
    assert '"$python_bin" scripts/verify_attestation_binding.py "${binding_args[@]}"' in served_contract.group(1)
    assert "DATAPULSE_ALLOW_UNATTESTED_HEALTH" not in served_contract.group(1)


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
if [[ "$retry" == 3 && "$delay" == 5 && "$all_errors" == true ]]; then
  printf '200\n' >> "$MOCK_CURL_ATTEMPTS"
  printf 'propagated\n' > "$output"
  printf '200'
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


def test_served_fetch_rejects_docs_prefix_and_reports_persistent_failure(tmp_path: Path) -> None:
    script = VERIFY_SCRIPT.read_text(encoding="utf-8")
    match = re.search(r"(?ms)^fetch\(\) \{\n.*?^\}\n", script)
    assert match is not None

    command = "\n".join(
        (
            "set -Eeuo pipefail",
            "local_mode=false",
            f"work_dir={tmp_path!s}",
            'base_url="https://example.invalid"',
            match.group(0),
            'fetch dashboard "docs/index.html"',
        )
    )
    completed = subprocess.run(
        ["bash", "-c", command], cwd=ROOT, capture_output=True, text=True, check=False
    )

    assert completed.returncode != 0
    assert "PAGES_FETCH_FAILURE surface=dashboard final=invalid_path" in completed.stderr
    assert "url=https://example.invalid/docs/index.html" in completed.stderr


def test_local_mode_maps_canonical_pages_to_docs_sources() -> None:
    script = VERIFY_SCRIPT.read_text(encoding="utf-8")

    assert 'index.html|landing.html|dashboard.html|register.html|npra.html|health-methodology.html|privacy.html|.well-known/*)' in script
    assert 'path="docs/$path"' in script


def test_served_fetch_call_sites_never_request_docs_paths() -> None:
    script = VERIFY_SCRIPT.read_text(encoding="utf-8")
    fetch_calls = re.findall(r"(?m)^\s*fetch\s+\S+\s+(\S+)", script)

    assert fetch_calls
    assert not [path for path in fetch_calls if path.lstrip('"').startswith("docs/")]


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


def test_gate_8_fetches_public_privacy_path() -> None:
    script = VERIFY_SCRIPT.read_text(encoding="utf-8")
    assert 'fetch "privacy.html" "privacy.html"' in script
    assert 'fetch "privacy.html" "$privacy_file"' not in script


def test_generate_shell_rejects_ambient_allow_unattested_health_bypass() -> None:
    generate_sh = (ROOT / "scripts/generate.sh").read_text(encoding="utf-8")
    assert "DATAPULSE_ALLOW_UNATTESTED_HEALTH" not in generate_sh
    assert "skipping attestation generation" not in generate_sh


def test_release_build_generates_readme_before_public_surface_preflight() -> None:
    generate_sh = (ROOT / "scripts/generate.sh").read_text(encoding="utf-8")
    release_profile = generate_sh.split('  release-build)\n', 1)[1].split('  *)\n', 1)[0]

    assert release_profile.index('"gen_readme.py"') < release_profile.index('"public_surface_preflight"')
    assert release_profile.count('"gen_readme.py"') == 1
    assert "python3 scripts/gen_readme.py --validate-only" in generate_sh
