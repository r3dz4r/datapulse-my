"""Contract for the credential-free pull-request release rehearsal.

The pull-request lane rehearses ``bash scripts/generate.sh release-build`` but
has no ``DATAPULSE_ATTESTATION_PRIVATE_KEY_FILE``. The opt-in
``DATAPULSE_ALLOW_UNSIGNED_BUILD=1`` lets that lane skip attestation signing
explicitly. These tests pin the three properties the escape must preserve:

* the default stays fail-closed when a key is absent and the published key
  registry exists, in every profile;
* only the literal value ``1`` skips the stage, and it reports honestly that
  attestations were NOT regenerated and the run is unsigned;
* a key that is present is never bypassed by the opt-in, even when unusable.

They also pin the workflow wiring: the opt-in is set only on the release-build
step, the preview lane deploys with a preview-scoped credential, and it never
references the production credential.
"""

from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

import pytest
import yaml

from scripts import verify_release_reproducible as verifier

ROOT = Path(__file__).resolve().parents[2]
GENERATE_SH = ROOT / "scripts/generate.sh"
PREVIEW_WORKFLOW = ROOT / ".github/workflows/preview-verify.yml"

FAIL_CLOSED_MESSAGE = "set DATAPULSE_ATTESTATION_PRIVATE_KEY_FILE for attestation generation"
UNSIGNED_MESSAGE = (
    "DATAPULSE_ALLOW_UNSIGNED_BUILD=1: WARNING: attestations were NOT regenerated; "
    "this release-build is UNSIGNED"
)

# Every generator the two profiles reference. Stubs keep the test focused on the
# attestation branch instead of executing the real pipeline.
PYTHON_GENERATORS = (
    "gen_readme.py",
    "stamp_manifest_origin.py",
    "gen_mcp_reference.py",
    "inject_openwiki_canonical_facts.py",
    "gen_llms_summary.py",
    "gen_public_discovery.py",
    "gen_dashboard_sections.py",
    "gen_health_methodology.py",
    "gen_catalog_snapshot.py",
    "gen_health_history.py",
    "gen_trends.py",
    "gen_drift.py",
    "gen_reconciliation.py",
    "gen_attestations.py",
    "gen_dataset_deltas.py",
    "gen_record_evidence.py",
    "gen_evidence_coverage.py",
    "gen_catalog_graph.py",
    "gen_json_envelope.py",
    "gen_jsonld_catalog.py",
    "gen_dashboard_filters.py",
    "embed_dashboard_data.py",
    "check_url_drift.py",
    "gen_trust_snapshot.py",
    "gen_health_methodology_html.py",
    "gen_landing_page.py",
    "gen_site_nav.py",
    "verify_distribution_sync.py",
)
SHELL_GENERATORS = ("gen_data_reports.sh", "gen_badges.sh", "gen_rss.sh")

ATTESTATION_STUB = """\
from __future__ import annotations

import os
import sys
from pathlib import Path

log = os.environ.get("STUB_ATTESTATION_LOG")
if log:
    Path(log).write_text("\\n".join(sys.argv[1:]), encoding="utf-8")
raise SystemExit(int(os.environ.get("STUB_ATTESTATION_EXIT", "0")))
"""

NOOP_STUB = "raise SystemExit(0)\n"


def _stage_stub_repo(tmp_path: Path, *, registry: bool = True) -> Path:
    """Create a throwaway tree whose generators are no-op stubs."""
    source = tmp_path / "stub-repo"
    scripts = source / "scripts"
    scripts.mkdir(parents=True)
    (scripts / "generate.sh").write_text(GENERATE_SH.read_text(encoding="utf-8"), encoding="utf-8")
    for name in PYTHON_GENERATORS:
        content = ATTESTATION_STUB if name == "gen_attestations.py" else NOOP_STUB
        (scripts / name).write_text(content, encoding="utf-8")
    for name in SHELL_GENERATORS:
        (scripts / name).write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")
    if registry:
        well_known = source / "docs/.well-known"
        well_known.mkdir(parents=True)
        (well_known / "datapulse-probe-keys.json").write_text("{}\n", encoding="utf-8")
    return source


def _run_generate(
    source: Path,
    profile: str,
    *,
    escape: str | None = None,
    key_path: Path | None = None,
    attestation_exit: int = 0,
) -> subprocess.CompletedProcess[str]:
    environment = {
        "PATH": os.environ.get("PATH", os.defpath),
        "DATAPULSE_ARCHIVES_DIR": str(source / ".archives"),
        "STUB_ATTESTATION_LOG": str(source / "attestation-invocation.txt"),
        "STUB_ATTESTATION_EXIT": str(attestation_exit),
    }
    if escape is not None:
        environment["DATAPULSE_ALLOW_UNSIGNED_BUILD"] = escape
    if key_path is not None:
        environment["DATAPULSE_ATTESTATION_PRIVATE_KEY_FILE"] = str(key_path)
    return subprocess.run(
        ["bash", "scripts/generate.sh", profile],
        cwd=source,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )


def _attestation_log(source: Path) -> str | None:
    log = source / "attestation-invocation.txt"
    return log.read_text(encoding="utf-8") if log.is_file() else None


@pytest.mark.parametrize("profile", ("health-cycle", "release-build"))
def test_default_still_fails_closed_without_a_key(tmp_path: Path, profile: str) -> None:
    source = _stage_stub_repo(tmp_path)

    result = _run_generate(source, profile)

    assert result.returncode != 0
    assert FAIL_CLOSED_MESSAGE in result.stderr
    assert _attestation_log(source) is None


@pytest.mark.parametrize("profile", ("health-cycle", "release-build"))
def test_escape_skips_attestation_and_reports_unsigned(tmp_path: Path, profile: str) -> None:
    source = _stage_stub_repo(tmp_path)

    result = _run_generate(source, profile, escape="1")

    assert result.returncode == 0, result.stderr
    assert UNSIGNED_MESSAGE in result.stderr
    assert FAIL_CLOSED_MESSAGE not in result.stderr
    assert _attestation_log(source) is None


@pytest.mark.parametrize("value", ("0", "true", "yes", "01", ""))
def test_escape_is_ignored_for_any_other_value(tmp_path: Path, value: str) -> None:
    source = _stage_stub_repo(tmp_path)

    result = _run_generate(source, "release-build", escape=value)

    assert result.returncode != 0
    assert FAIL_CLOSED_MESSAGE in result.stderr
    assert UNSIGNED_MESSAGE not in result.stderr


def test_escape_is_ignored_when_the_signing_key_is_present(tmp_path: Path) -> None:
    source = _stage_stub_repo(tmp_path)
    key_path = tmp_path / "attestation-key.json"
    key_path.write_text('{"key": "usable"}\n', encoding="utf-8")

    result = _run_generate(
        source, "release-build", escape="1", key_path=key_path, attestation_exit=0
    )

    assert result.returncode == 0, result.stderr
    assert UNSIGNED_MESSAGE not in result.stderr
    invocation = _attestation_log(source)
    assert invocation is not None
    assert "--private-key" in invocation
    assert str(key_path) in invocation


def test_escape_does_not_mask_a_present_but_unusable_key(tmp_path: Path) -> None:
    source = _stage_stub_repo(tmp_path)
    key_path = tmp_path / "attestation-key.json"
    key_path.write_text("not a usable key\n", encoding="utf-8")

    result = _run_generate(
        source, "release-build", escape="1", key_path=key_path, attestation_exit=7
    )

    assert result.returncode != 0
    assert UNSIGNED_MESSAGE not in result.stderr
    assert _attestation_log(source) is not None


def _preview_workflow() -> dict:
    return yaml.safe_load(PREVIEW_WORKFLOW.read_text(encoding="utf-8"))


def test_preview_workflow_sets_the_escape_only_on_the_build_step() -> None:
    workflow_text = PREVIEW_WORKFLOW.read_text(encoding="utf-8")
    steps = _preview_workflow()["jobs"]["preview"]["steps"]

    assert workflow_text.count("DATAPULSE_ALLOW_UNSIGNED_BUILD") == 1
    opted_in = [
        step
        for step in steps
        if "DATAPULSE_ALLOW_UNSIGNED_BUILD" in (step.get("env") or {})
    ]
    assert [step["name"] for step in opted_in] == ["Build release artifact"]
    assert opted_in[0]["env"]["DATAPULSE_ALLOW_UNSIGNED_BUILD"] == "1"
    for step in steps:
        assert "DATAPULSE_ALLOW_UNSIGNED_BUILD" not in step.get("run", "")


def test_preview_workflow_never_references_the_production_credential() -> None:
    workflow_text = PREVIEW_WORKFLOW.read_text(encoding="utf-8")

    references = re.findall(r"secrets\.[A-Za-z0-9_]+", workflow_text)
    assert sorted(set(references)) == [
        "secrets.CLOUDFLARE_ACCOUNT_ID",
        "secrets.CLOUDFLARE_PREVIEW_API_TOKEN",
    ]
    assert references.count("secrets.CLOUDFLARE_PREVIEW_API_TOKEN") == 1
    assert references.count("secrets.CLOUDFLARE_ACCOUNT_ID") == 1
    assert "secrets.CLOUDFLARE_API_TOKEN" not in workflow_text
    assert not any("ATTESTATION" in reference for reference in references)


def test_preview_workflow_uses_preview_credentials_for_deploy_and_served_check() -> None:
    steps = {step.get("name"): step for step in _preview_workflow()["jobs"]["preview"]["steps"]}

    deploy = steps["Deploy isolated Cloudflare Pages preview"]
    assert deploy["env"] == {
        "CLOUDFLARE_API_TOKEN": "${{ secrets.CLOUDFLARE_PREVIEW_API_TOKEN }}",
        "CLOUDFLARE_ACCOUNT_ID": "${{ secrets.CLOUDFLARE_ACCOUNT_ID }}",
    }
    assert deploy["if"] == "${{ github.event.pull_request.head.repo.full_name == github.repository }}"
    assert "DATAPULSE_ALLOW_UNSIGNED_BUILD" not in deploy
    assert "--project-name=datapulse-p4b-preview" in deploy["run"]
    assert "DATAPULSE_ALLOW_UNSIGNED_BUILD" not in steps["Verify served preview"].get("env", {})


def test_isolated_reproducibility_build_forwards_opt_in_only_when_set(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    captured: dict[str, object] = {}

    def fake_run(*args: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
        captured.update(kwargs)
        return subprocess.CompletedProcess(args, 0, "", "")

    monkeypatch.delenv("DATAPULSE_ALLOW_UNSIGNED_BUILD", raising=False)
    monkeypatch.delenv("DATAPULSE_ATTESTATION_PRIVATE_KEY_FILE", raising=False)
    monkeypatch.setattr(verifier, "_copy_source", lambda destination: None)
    monkeypatch.setattr(verifier.subprocess, "run", fake_run)
    monkeypatch.setattr(
        verifier,
        "_capture",
        lambda root, source: verifier.BuildCapture({}, {}, root),
    )

    verifier._build(ROOT, tmp_path, "/tmp/fake-git-dir", "2026-10-01T00:00:00Z")
    assert "DATAPULSE_ALLOW_UNSIGNED_BUILD" not in captured["env"]

    monkeypatch.setenv("DATAPULSE_ALLOW_UNSIGNED_BUILD", "1")
    verifier._build(ROOT, tmp_path, "/tmp/fake-git-dir", "2026-10-01T00:00:00Z")
    assert captured["env"]["DATAPULSE_ALLOW_UNSIGNED_BUILD"] == "1"
    assert "DATAPULSE_ATTESTATION_PRIVATE_KEY_FILE" not in captured["env"]
