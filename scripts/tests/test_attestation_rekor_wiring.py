"""Offline coverage for binding a new day's health snapshot to Rekor evidence."""

from __future__ import annotations

import json
import hashlib
import os
import subprocess
import textwrap
from datetime import datetime, timezone
from pathlib import Path

import pytest

from scripts import gen_attestations as ga
from scripts.tests.test_attestations import fixture_rekor_reference, fixture_root
from scripts.verify_attestation_binding import ContractError
from scripts.verify_sigstore_bundle import verify_bundle


ROOT = Path(__file__).resolve().parents[2]
ATTEST_DAILY_WORKFLOW = ROOT / ".github/workflows/datapulse-attest-daily.yml"
_GUARD_STEP_HEADER = "      - name: Decide whether today's Rekor witness is needed\n"
_FOLLOWING_STEP_HEADER = "      - name: Install pinned Cosign signer\n"
_GUARD_DAY = "2026-09-16"


def test_daily_rekor_evidence_is_committable_and_staged_with_its_binding() -> None:
    """A witnessed binding must commit the evidence paths it references."""
    gitignore = (ROOT / ".gitignore").read_text(encoding="utf-8")
    daily = (ROOT / ".github/workflows/datapulse-attest-daily.yml").read_text(encoding="utf-8")

    assert "attestations/rekor/" not in gitignore
    commit_step = daily.split("      - name: Commit dated envelopes and open or update their pull request\n", 1)[1]
    assert 'git add -- "attestations/rekor/$day"' in commit_step


def test_matching_rekor_reference_marks_new_binding_as_witnessed(tmp_path: Path) -> None:
    root, key = fixture_root(tmp_path)
    reference = fixture_rekor_reference(root, "rekor-fixture")

    ga.generate(root, key, datetime(2026, 8, 15, 1, tzinfo=timezone.utc), reference)

    binding = json.loads((root / "attestations/2026-08-15/binding.json").read_text())
    assert binding["claims"]["rekor_witnessed"] is True
    assert binding["rekor"] == {
        "reference_ref": "attestations/rekor-fixture/reference.json",
        "bundle_ref": "attestations/rekor-fixture/bundle.json",
    }


def test_rekor_dsse_fixture_is_accepted_by_sigstore_and_binding_verifiers(tmp_path: Path) -> None:
    root, _key = fixture_root(tmp_path)
    reference = fixture_rekor_reference(root, "rekor-fixture")
    bundle = reference.parent / "bundle.json"
    digest = hashlib.sha256((root / "health/latest.json").read_bytes()).hexdigest()

    assert verify_bundle(
        health=root / "health/latest.json",
        manifest=root / "datapulse.json",
        chain_head=root / ".attestations/chain_head.json",
        source_commit="c" * 40,
        bundle=bundle,
        identity="https://example.test/identity",
        issuer="https://example.test/issuer",
    )["subject_sha256"] == digest
    ga.generate(root, _key, datetime(2026, 8, 15, 1, tzinfo=timezone.utc), reference)


def test_mismatched_rekor_reference_is_rejected_before_binding(tmp_path: Path) -> None:
    root, key = fixture_root(tmp_path)
    reference = fixture_rekor_reference(root, "rekor-fixture")
    document = json.loads(reference.read_text())
    document["artifact_sha256"] = "f" * 64
    reference.write_text(json.dumps(document) + "\n")

    with pytest.raises(ContractError, match="does not bind the health digest"):
        ga.generate(root, key, datetime(2026, 8, 15, 1, tzinfo=timezone.utc), reference)

    assert not (root / "attestations/2026-08-15/binding.json").exists()


def _guard_step_text() -> str:
    """Locate the Rekor guard step block inside the daily attestation workflow."""
    workflow = ATTEST_DAILY_WORKFLOW.read_text(encoding="utf-8")
    assert _GUARD_STEP_HEADER in workflow, "the daily workflow must keep the Rekor guard step"
    return workflow.split(_GUARD_STEP_HEADER, 1)[1].split(_FOLLOWING_STEP_HEADER, 1)[0]


def _guard_run_script() -> str:
    return textwrap.dedent(_guard_step_text().split("        run: |\n", 1)[1])


def _run_guard(scratch_root: Path) -> subprocess.CompletedProcess[str]:
    """Execute the guard step's shell against a scratch repository root."""
    script = "\n".join(
        (
            "set -Eeuo pipefail",
            "date() { printf '" + _GUARD_DAY + "\\n'; }",
            'cd "' + str(scratch_root) + '"',
            _guard_run_script(),
        )
    )
    return subprocess.run(
        ["bash", "-c", script],
        check=False,
        capture_output=True,
        text=True,
        env={**os.environ, "GITHUB_OUTPUT": str(scratch_root / "github_output")},
    )


def _write_dated_set(scratch_root: Path) -> None:
    dated = scratch_root / "attestations" / _GUARD_DAY
    dated.mkdir(parents=True)
    (dated / "binding.json").write_text("{}\n", encoding="utf-8")
    (dated / "chain_head.json").write_text("{}\n", encoding="utf-8")


def test_guard_skip_branch_tests_today_s_rekor_reference_not_dated_set_existence() -> None:
    """Skipping on set-existence alone strands a binding that references missing evidence."""
    condition = _guard_step_text().split("if [[", 1)[1].split("]]; then", 1)[0]

    assert '"$rekor_dir/reference.json"' in condition
    assert '"$rekor_dir/health.sigstore.bundle.json"' in condition
    assert "attestations/$day" not in condition


@pytest.mark.parametrize(
    ("reference_body", "bundle_body"),
    (
        pytest.param(None, None, id="evidence-entirely-absent"),
        pytest.param("", "", id="evidence-files-empty"),
        pytest.param("{}", None, id="reference-only"),
        pytest.param(None, "{}", id="bundle-only"),
    ),
)
def test_guard_does_not_skip_rekor_evidence_when_today_s_reference_is_absent(
    tmp_path: Path, reference_body: str | None, bundle_body: str | None
) -> None:
    """A dated set created before the attest run must not suppress the witness upload."""
    scratch_root = tmp_path / "repo"
    _write_dated_set(scratch_root)
    evidence_dir = scratch_root / "attestations" / "rekor" / _GUARD_DAY
    for filename, body in (("reference.json", reference_body), ("health.sigstore.bundle.json", bundle_body)):
        if body is not None:
            evidence_dir.mkdir(parents=True, exist_ok=True)
            (evidence_dir / filename).write_text(body, encoding="utf-8")

    result = _run_guard(scratch_root)

    assert result.returncode == 0, result.stderr
    outputs = (scratch_root / "github_output").read_text(encoding="utf-8")
    assert "needed=true" in outputs
    assert "needed=false" not in outputs
    assert "producing the missing evidence" in result.stdout
    assert evidence_dir.is_dir()


def test_guard_skips_rekor_upload_only_when_today_s_evidence_is_committed(tmp_path: Path) -> None:
    """Committed same-day Rekor evidence, and only that, makes the guard skip."""
    scratch_root = tmp_path / "repo"
    evidence_dir = scratch_root / "attestations" / "rekor" / _GUARD_DAY
    evidence_dir.mkdir(parents=True)
    (evidence_dir / "reference.json").write_text("{}\n", encoding="utf-8")
    (evidence_dir / "health.sigstore.bundle.json").write_text("{}\n", encoding="utf-8")

    result = _run_guard(scratch_root)

    assert result.returncode == 0, result.stderr
    outputs = (scratch_root / "github_output").read_text(encoding="utf-8")
    assert "needed=false" in outputs
    assert "needed=true" not in outputs
    assert (evidence_dir / "reference.json").read_text(encoding="utf-8") == "{}\n"
