"""Contract for the pull-request preview served verification.

The preview lane used to verify its deployed preview with
``scripts/verify_external.py``, whose first check refuses any origin that is not
the production site. The step could therefore never pass. It now uses the
repository's own served-release verifier, ``scripts/verify_served_release.sh``,
with the preview URL and the assembled ``_site`` artifact.

These tests pin four properties:

* the workflow invokes the served-release verifier with the preview URL, the
  assembled site, the unsigned declaration, the full-release health mode and an
  explicit source commit, and never calls the production-only verifier;
* the unsigned run needs no ``--sigstore-publication`` while a signed run still
  requires it, because that directory stages a signature the unsigned preview
  does not carry;
* the verifier passes end to end against a local fixture site, so the happy
  path is real and not a skipped check;
* a deliberately mismatched built artifact fails the served comparison for the
  behavioural reason, which is the bounded negative control the workflow also
  runs against the deployed preview.

The fixture serves the verifier through a stub ``curl`` and a no-op ``sleep`` so
the test stays offline; no preview is uploaded and no production origin is
contacted.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[2]
PREVIEW_WORKFLOW = ROOT / ".github/workflows/preview-verify.yml"
PRODUCTION_WORKFLOW = ROOT / ".github/workflows/deploy-cloudflare-pages.yml"
SERVED_VERIFIER = ROOT / "scripts/verify_served_release.sh"
PUBLIC_SURFACES = ROOT / "config/public-surfaces.json"

BASE_URL = "https://preview.example.test"
SOURCE_COMMIT = "abc1234def5678"
HEALTH_CHECKED_AT = "2026-10-01T00:00:00Z"
STALE_SERVED_CHECKED_AT = "2025-01-01T00:00:00Z"
STALER_PROJECTION_CHECKED_AT = "2024-01-01T00:00:00Z"
KV_EXCLUSION_FLAG = "--kv-surfaces-published-elsewhere"
VERIFY_STEP = "Verify served preview"
NEGATIVE_CONTROL_STEP = (
    "Negative control: a mismatched built artifact must fail served verification"
)

CURL_STUB = '''#!__PYTHON__
"""Serve fixture files for the verifier and report curl-shaped metrics."""
from __future__ import annotations

import os
import sys
from pathlib import Path


VALUE_FLAGS = {
    "--output",
    "--dump-header",
    "--write-out",
    "--proto",
    "--retry",
    "--retry-delay",
    "--connect-timeout",
    "--max-time",
}


def main() -> int:
    output = None
    dump = None
    url = None
    args = sys.argv[1:]
    index = 0
    while index < len(args):
        arg = args[index]
        if arg in VALUE_FLAGS:
            if arg == "--output":
                output = args[index + 1]
            elif arg == "--dump-header":
                dump = args[index + 1]
            index += 2
        elif arg.startswith("https://"):
            url = arg
            index += 1
        else:
            index += 1
    if url is None:
        raise SystemExit("curl stub requires an https URL")
    served = Path(os.environ["FIXTURE_SERVED_ROOT"])
    path = url.split("://", 1)[1]
    path = path[path.index("/"):] if "/" in path else "/"
    candidate = served / ("index.html" if path == "/" else path.lstrip("/"))
    if candidate.is_dir() and (candidate / "index.html").is_file():
        candidate = candidate / "index.html"
    if candidate.is_file():
        body = candidate.read_bytes()
        status = 200
    else:
        body = b""
        status = 404
    if dump is not None:
        header_path = Path(dump)
        header_path.parent.mkdir(parents=True, exist_ok=True)
        header_path.write_text(f"HTTP/2 {status}\\n", encoding="utf-8")
    if output is not None:
        body_path = Path(output)
        body_path.parent.mkdir(parents=True, exist_ok=True)
        body_path.write_bytes(body)
    sys.stdout.write(f"{status} 0.001 {len(body)}")
    return 0


raise SystemExit(main())
'''


def _preview_steps() -> list[dict]:
    workflow = yaml.safe_load(PREVIEW_WORKFLOW.read_text(encoding="utf-8"))
    return workflow["jobs"]["preview"]["steps"]


def _step(name: str) -> dict:
    return next(step for step in _preview_steps() if step.get("name") == name)


def test_preview_workflow_verifies_the_served_preview_with_the_release_verifier() -> None:
    run = _step(VERIFY_STEP)["run"]

    assert "bash scripts/verify_served_release.sh" in run
    assert '--base-url "$PREVIEW_URL"' in run
    assert "--site _site" in run
    assert "--sigstore-signed false" in run
    assert "--health-only false" in run
    assert '--source-commit "$GITHUB_SHA"' in run
    # The unsigned preview carries no signature to compare, so it must not claim
    # staged signing inputs.
    assert "--sigstore-publication" not in run
    assert "verify_external" not in run


def test_preview_workflow_never_calls_the_production_only_verifier() -> None:
    workflow = PREVIEW_WORKFLOW.read_text(encoding="utf-8")

    assert "verify_external.py" not in workflow
    assert "verify_served_release.sh" in workflow


def test_preview_workflow_negative_control_is_bounded_and_behavioural() -> None:
    run = _step(NEGATIVE_CONTROL_STEP)["run"]

    # It reuses the served verifier against the real preview URL with a tampered
    # copy of the built artifact, and demands the specific comparison failure.
    assert "bash scripts/verify_served_release.sh" in run
    assert '--base-url "$PREVIEW_URL"' in run
    assert "negative_site" in run
    assert "datapulse.json" in run
    assert "origin root register rows mismatch" in run
    assert "exit 1" in run


def test_preview_workflow_negative_control_runs_after_the_happy_path() -> None:
    names = [step.get("name") for step in _preview_steps()]

    assert names.index(VERIFY_STEP) < names.index(NEGATIVE_CONTROL_STEP)


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _proof(tool_count: int, dataset_count: int, source_commit: str) -> str:
    return "\n".join(
        (
            "<!-- generated: scripts/verify_release_reproducible.py; do not hand-edit -->",
            "# Release reproducibility verification",
            "",
            "- Status: `current generated release proof`",
            f"- Source SHA: `{source_commit}`",
            f"- MCP tool count: `{tool_count}`",
            "- Protocol result: `byte-identical isolated release-build runs`",
            f"- Health checked at: `{HEALTH_CHECKED_AT}`",
            f"- Dataset count: `{dataset_count}`",
            "",
        )
    )


def _stage_fixture(tmp_path: Path) -> tuple[Path, Path, Path]:
    """Assemble a built site, a matching served fixture and a verifier root."""
    root = tmp_path / "fixture-root"
    built = root / "_site"
    served = tmp_path / "served"
    datasets = [{"dataset_id": "alpha"}, {"dataset_id": "beta"}]
    health = {"checked_at": HEALTH_CHECKED_AT, "datasets": datasets}
    mcp = {"tools": [{"name": "get_fixture", "inputSchema": {}}]}
    proof = _proof(len(mcp["tools"]), len(datasets), SOURCE_COMMIT)

    _write(built / "datapulse.json", json.dumps({"datasets": datasets}))
    _write(built / "health/latest.json", json.dumps(health))
    _write(built / "okf/index.md", "okf fixture\n")
    _write(built / "badges/badge.svg", "<svg/>\n")

    alias_body = (
        "<title>DataPulse dataset register</title>\n"
        '<link rel="canonical" href="/">\n'
        '<meta http-equiv="refresh" content="0; url=/">\n'
        '<a href="/">DataPulse dataset register</a>\n'
    )
    _write(
        served / "index.html",
        "<!doctype html>\n"
        "<title>DataPulse Dataset Register</title>\n"
        "<script>fetch('/health/index.json')</script>\n"
        '<article class="register-row">alpha</article>\n'
        '<article class="register-row">beta</article>\n',
    )
    _write(served / "health/latest.json", json.dumps(health))
    _write(served / "health/index.json", json.dumps(health))
    _write(
        served / "health/trends.json",
        json.dumps(
            {
                "schema": "datapulse/v1/dataset-trends",
                "datasets": [{} for _ in datasets],
                "summary": {"datasets_total": len(datasets)},
            }
        ),
    )
    _write(
        served / "health/drift.json",
        json.dumps(
            {
                "schema": "datapulse/v1/dataset-drift",
                "datasets": [{} for _ in datasets],
                "summary": {"datasets_total": len(datasets)},
            }
        ),
    )
    _write(
        served / "health/reconciliation.json",
        json.dumps(
            {
                "schema": "datapulse/v1/dataset-reconciliation",
                "summary": {
                    "datasets_total": len(datasets),
                    "datasets_grouped": 1,
                    "datasets_single_source": 1,
                },
            }
        ),
    )
    _write(served / "mcp.json", json.dumps(mcp))
    _write(
        served / "llms.txt",
        "<!-- BEGIN mcp-tools -->\nget_fixture\n<!-- END mcp-tools -->\n",
    )
    _write(served / "release-verification.md", proof)
    _write(
        served / "observation-receipts/chain_head.json",
        json.dumps({"schema": "datapulse/v1/observation-chain-head", "head": "fixture"}),
    )
    for alias in ("landing.html", "landing", "dashboard", "register"):
        _write(served / alias, alias_body)

    # The declared-surface loop resolves collection paths against the built site
    # and fetches the resolved path. Give every declared page and artifact a
    # served 2xx body; the chain head keeps its schema marker above.
    surfaces = json.loads(PUBLIC_SURFACES.read_text(encoding="utf-8"))
    for declared in surfaces["pages"] + surfaces["artifacts"]:
        if declared.endswith("/"):
            directory = built / declared.lstrip("/")
            resolved = sorted(path for path in directory.rglob("*") if path.is_file())[0]
            target = served / resolved.relative_to(built)
        else:
            target = served / declared.lstrip("/")
        if not target.exists():
            _write(target, "fixture surface\n")

    # The verifier reads the script, the public-surface config, mcp.json and the
    # staged proof relative to its working directory.
    (root / "scripts").mkdir(parents=True, exist_ok=True)
    (root / "config").mkdir(parents=True, exist_ok=True)
    shutil.copy2(SERVED_VERIFIER, root / "scripts/verify_served_release.sh")
    shutil.copy2(PUBLIC_SURFACES, root / "config/public-surfaces.json")
    _write(root / "mcp.json", json.dumps(mcp))
    _write(root / "docs/release-verification.md", proof)
    return root, built, served


def _stub_bin(tmp_path: Path) -> Path:
    stub = tmp_path / "stub-bin"
    stub.mkdir(exist_ok=True)
    curl = stub / "curl"
    curl.write_text(CURL_STUB.replace("__PYTHON__", sys.executable), encoding="utf-8")
    curl.chmod(0o755)
    sleep = stub / "sleep"
    sleep.write_text(
        "#!/usr/bin/env bash\n"
        'printf "%s\\n" "$*" >> "${FIXTURE_SLEEP_LOG:?}"\n'
        "exit 0\n",
        encoding="utf-8",
    )
    sleep.chmod(0o755)
    return stub


def _run_verifier(
    tmp_path: Path,
    root: Path,
    site: Path,
    served: Path,
    *,
    sigstore_signed: str = "false",
    publication: Path | None = None,
    kv_surfaces_published_elsewhere: bool = False,
) -> subprocess.CompletedProcess[str]:
    stub = _stub_bin(tmp_path)
    tmpdir = tmp_path / "tmp"
    tmpdir.mkdir(exist_ok=True)
    environment = os.environ.copy()
    environment["PATH"] = f"{stub}{os.pathsep}{environment.get('PATH', os.defpath)}"
    environment["FIXTURE_SERVED_ROOT"] = str(served)
    environment["FIXTURE_SLEEP_LOG"] = str(tmp_path / "sleep.log")
    environment["TMPDIR"] = str(tmpdir)
    command = [
        "bash",
        "scripts/verify_served_release.sh",
        "--base-url",
        BASE_URL,
        "--site",
        str(site),
        "--sigstore-signed",
        sigstore_signed,
        "--health-only",
        "false",
        "--source-commit",
        SOURCE_COMMIT,
    ]
    if publication is not None:
        command += ["--sigstore-publication", str(publication)]
    if kv_surfaces_published_elsewhere:
        command.append(KV_EXCLUSION_FLAG)
    return subprocess.run(
        command,
        cwd=root,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )


def test_unsigned_fixture_site_passes_served_verification(tmp_path: Path) -> None:
    """The happy path runs without a publication directory and proves comparison."""
    root, built, served = _stage_fixture(tmp_path)

    result = _run_verifier(tmp_path, root, built, served)

    assert result.returncode == 0, result.stderr
    # The bounded propagation wait ran, so this is the real terminal path rather
    # than an early return.
    assert (tmp_path / "sleep.log").read_text(encoding="utf-8").strip() == "30"
    assert "served surface=dataset register" in result.stdout
    assert "served surface=health snapshot" in result.stdout


def test_signed_verification_still_requires_a_publication_directory(tmp_path: Path) -> None:
    root, built, served = _stage_fixture(tmp_path)

    result = _run_verifier(tmp_path, root, built, served, sigstore_signed="true")
    combined = result.stdout + result.stderr

    assert result.returncode != 0
    assert "missing staged signing inputs" in combined
    # The refusal is the staging contract, not a URL or site validation error.
    assert "invalid served base URL" not in combined


def test_negative_control_fails_because_the_served_surface_differs(tmp_path: Path) -> None:
    root, built, served = _stage_fixture(tmp_path)
    manifest_path = built / "datapulse.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["datasets"].append({"dataset_id": "tampered"})
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    result = _run_verifier(tmp_path, root, built, served)
    combined = result.stdout + result.stderr

    assert result.returncode != 0
    assert "origin root register rows mismatch" in combined
    # A usage or transport error would not prove the served comparison ran.
    assert "usage:" not in combined
    assert "invalid served base URL" not in combined
    assert "transport failure" not in combined


def _stale_served_health(served: Path) -> None:
    """Age and diverge the served KV-backed health surfaces.

    The snapshot is older than the assembled one *and* the dashboard projection
    is older and differently shaped than the served snapshot, so each of the two
    excluded comparisons fails on its own if the verifier still runs it.
    """
    latest_path = served / "health/latest.json"
    latest = json.loads(latest_path.read_text(encoding="utf-8"))
    latest["checked_at"] = STALE_SERVED_CHECKED_AT
    _write(latest_path, json.dumps(latest))

    projection_path = served / "health/index.json"
    projection = json.loads(projection_path.read_text(encoding="utf-8"))
    projection["checked_at"] = STALER_PROJECTION_CHECKED_AT
    projection["datasets"] = [*projection["datasets"], {"dataset_id": "projection-only"}]
    _write(projection_path, json.dumps(projection))


def test_default_still_fails_on_a_stale_served_health_snapshot(tmp_path: Path) -> None:
    """The exclusion is opt-in: without it the freshness comparison stays strict."""
    root, built, served = _stage_fixture(tmp_path)
    _stale_served_health(served)

    result = _run_verifier(tmp_path, root, built, served)
    combined = result.stdout + result.stderr

    assert result.returncode != 0
    assert "served health snapshot is older than the assembled snapshot" in combined
    assert "published by another lane on its own cadence" not in combined


def test_option_skips_the_kv_backed_surfaces_and_names_them(tmp_path: Path) -> None:
    root, built, served = _stage_fixture(tmp_path)
    _stale_served_health(served)

    result = _run_verifier(
        tmp_path, root, built, served, kv_surfaces_published_elsewhere=True
    )
    combined = result.stdout + result.stderr

    assert result.returncode == 0, combined
    notices = [
        line
        for line in result.stdout.splitlines()
        if "published by another lane on its own cadence" in line
    ]
    # One loud line, naming every excluded surface and the reason.
    assert len(notices) == 1
    assert "served health/latest.json" in notices[0]
    assert "dataset-count" in notices[0]
    assert "release-proof health" in notices[0]
    assert "/health/index.json" in notices[0]
    # The static surfaces were still fetched and compared under the option.
    assert "served surface=dataset register" in result.stdout
    assert "served surface=release reproducibility proof" in result.stdout


def test_option_present_still_fails_on_a_tampered_static_surface(tmp_path: Path) -> None:
    """The exclusion must not widen to the register the lane can genuinely prove."""
    root, built, served = _stage_fixture(tmp_path)
    _stale_served_health(served)
    manifest_path = built / "datapulse.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["datasets"].append({"dataset_id": "tampered"})
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    result = _run_verifier(
        tmp_path, root, built, served, kv_surfaces_published_elsewhere=True
    )
    combined = result.stdout + result.stderr

    assert result.returncode != 0
    assert "origin root register rows mismatch" in combined
    assert "usage:" not in combined
    assert "transport failure" not in combined


def test_option_present_still_compares_the_release_proof(tmp_path: Path) -> None:
    root, built, served = _stage_fixture(tmp_path)
    _stale_served_health(served)
    _write(root / "docs/release-verification.md", "tampered assembled proof\n")

    result = _run_verifier(
        tmp_path, root, built, served, kv_surfaces_published_elsewhere=True
    )
    combined = result.stdout + result.stderr

    assert result.returncode != 0
    assert "served release proof differs from staged artifact" in combined


def test_preview_workflow_passes_the_exclusion_only_to_the_served_verification() -> None:
    workflow = PREVIEW_WORKFLOW.read_text(encoding="utf-8")
    verify_run = _step(VERIFY_STEP)["run"]
    control_run = _step(NEGATIVE_CONTROL_STEP)["run"]

    assert KV_EXCLUSION_FLAG in verify_run
    # Requirement: the exclusion is opted into exactly once, on the served
    # verification, never on the bounded negative control or the deploy step.
    assert workflow.count(KV_EXCLUSION_FLAG) == 1
    assert KV_EXCLUSION_FLAG not in control_run


def test_production_deploy_workflow_does_not_pass_the_exclusion() -> None:
    workflow = PRODUCTION_WORKFLOW.read_text(encoding="utf-8")

    assert "bash scripts/verify_served_release.sh" in workflow
    assert KV_EXCLUSION_FLAG not in workflow
