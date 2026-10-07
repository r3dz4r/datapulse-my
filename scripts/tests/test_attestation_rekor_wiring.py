"""Offline coverage for binding a new day's health snapshot to Rekor evidence."""

from __future__ import annotations

import json
import hashlib
import os
import shutil
import subprocess
import sys
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
    assert 'bash scripts/submit_attestation_append.sh' in daily
    commit_step = (ROOT / "scripts/submit_attestation_append.sh").read_text()
    assert '"attestations/rekor/$day"' in commit_step


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
        env={**os.environ, "GITHUB_OUTPUT": str(scratch_root / "github_output"), "GITHUB_ENV": str(scratch_root / "github_env")},
    )


def _write_dated_set(scratch_root: Path, witnessed: bool = False) -> None:
    scratch_root.mkdir(parents=True, exist_ok=True)
    root, key = fixture_root(scratch_root)
    now = datetime.now(timezone.utc)
    health = ga.load(root / "health/latest.json")
    stamp = now.replace(microsecond=0).isoformat().replace("+00:00", "Z")
    health["checked_at"] = stamp
    health["datasets"][0]["last_checked"] = stamp
    ga.dump(root / "health/latest.json", health)
    reference = fixture_rekor_reference(root, "rekor-fixture") if witnessed else None
    ga.generate(root, key, now, reference)
    (root / "scripts").symlink_to(ROOT / "scripts", target_is_directory=True)


def test_guard_requires_verified_binding_instead_of_file_existence() -> None:
    guard = _guard_step_text()
    assert 'verify_attestation_binding.py --root . --require-rekor' in guard
    assert 'rm -rf' not in guard


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
    assert evidence_dir.is_dir()


def test_guard_skips_rekor_upload_only_when_today_s_evidence_is_committed(tmp_path: Path) -> None:
    """Committed same-day Rekor evidence, and only that, makes the guard skip."""
    scratch_root = tmp_path / "repo"
    _write_dated_set(scratch_root, witnessed=True)
    before = (scratch_root / "attestations/rekor-fixture/reference.json").read_bytes()

    result = _run_guard(scratch_root)

    assert result.returncode == 0, result.stderr
    outputs = (scratch_root / "github_output").read_text(encoding="utf-8")
    assert "needed=false" in outputs
    assert "needed=true" not in outputs
    assert (scratch_root / "attestations/rekor-fixture/reference.json").read_bytes() == before


def _git(root: Path, *arguments: str) -> str:
    return subprocess.run(
        ["git", *arguments], cwd=root, check=True, capture_output=True, text=True,
    ).stdout.strip()


@pytest.mark.parametrize(
    ("witnessed", "override", "proceeds"),
    (
        pytest.param(True, None, True, id="witness-required-and-present"),
        pytest.param(False, None, False, id="unwitnessed-refused-by-default"),
        pytest.param(False, "1", True, id="explicit-override-keeps-false-claim"),
        pytest.param(False, "0", False, id="zero-is-not-an-override"),
        pytest.param(False, "true", False, id="true-is-not-an-override"),
        pytest.param(False, "01", False, id="only-literal-one-overrides"),
    ),
)
def test_submission_requires_witness_or_explicit_operator_override(
    tmp_path: Path, witnessed: bool, override: str | None, proceeds: bool,
) -> None:
    """Exercise real validation, staging and Git publication to a local bare repo."""
    root, key = fixture_root(tmp_path / "repo")
    script_dir = root / "scripts"
    script_dir.mkdir()
    for name in (
        "verify_attestation_append.py", "attestation_sets.py",
        "verify_attestation_binding.py", "attestation_commit_back.py",
        "gen_attestations.py",
    ):
        shutil.copyfile(ROOT / "scripts" / name, script_dir / name)
    ga.generate(root, key, datetime(2026, 8, 15, 1, tzinfo=timezone.utc))
    _git(root, "init", "-b", "main")
    _git(root, "config", "user.name", "Test")
    _git(root, "config", "user.email", "test@example.test")
    _git(root, "add", "attestations", ".attestations", "docs", "scripts", "datapulse.json", "health")
    _git(root, "commit", "-m", "accepted fixture")
    source = _git(root, "rev-parse", "HEAD")
    remote = tmp_path / "origin.git"
    _git(tmp_path, "clone", "--bare", str(root), str(remote))
    _git(root, "remote", "add", "origin", str(remote))
    reference = fixture_rekor_reference(root, "rekor/2026-08-16") if witnessed else None
    ga.generate(root, key, datetime(2026, 8, 16, 1, tzinfo=timezone.utc), reference)
    binding = root / "attestations/latest/binding.json"
    before = binding.read_bytes()
    head = ga.load(root / "attestations/chain-index.json")["current_head"]
    branch = "attestation/append-" + head
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    gh = bin_dir / "gh"
    gh.write_text('#!/usr/bin/env bash\nprintf "%s\\n" "$@" > "$PR_ARGS"\n')
    gh.chmod(0o755)
    pr_args = tmp_path / "pr-args"
    env = {**os.environ, "PATH": str(bin_dir) + os.pathsep + os.environ["PATH"], "PR_ARGS": str(pr_args)}
    env.pop("DATAPULSE_ALLOW_UNWITNESSED_PUBLICATION", None)
    env.pop("GH_TOKEN", None)
    if override is not None:
        env["DATAPULSE_ALLOW_UNWITNESSED_PUBLICATION"] = override

    result = subprocess.run(
        ["bash", str(ROOT / "scripts/submit_attestation_append.sh")],
        cwd=root, env=env, capture_output=True, text=True, check=False,
    )

    assert binding.read_bytes() == before
    if proceeds:
        assert result.returncode == 0, result.stderr
        published = json.loads(_git(remote, "show", f"{branch}:attestations/latest/binding.json"))
        assert published["claims"]["rekor_witnessed"] is witnessed
        if witnessed:
            assert _git(remote, "show", f"{branch}:attestations/rekor/2026-08-16/reference.json")
        assert pr_args.read_text().splitlines() == [
            "pr", "create", "--base", "main", "--head", branch,
            "--title", "chore(attestations): append signed set 2026-08-16",
            "--body", f"Append immutable signed evidence from source {source}. Publication must wait for this append to be accepted; existing evidence is preserved.",
        ]
    else:
        assert result.returncode != 0
        assert "rekor_witnessed: false" in result.stderr
        assert "DATAPULSE_ALLOW_UNWITNESSED_PUBLICATION=1" in result.stderr
        assert _git(root, "branch", "--show-current") == "main"
        assert _git(remote, "for-each-ref", "--format=%(refname)", "refs/heads/") == "refs/heads/main"
        assert not pr_args.exists()


def _projection_submission_root(tmp_path: Path) -> tuple[Path, str, Path]:
    """Prepare an append whose accepted base moves after the candidate is cut."""
    root, key = fixture_root(tmp_path / "repo")
    script_dir = root / "scripts"
    script_dir.mkdir()
    for name in (
        "verify_attestation_append.py", "attestation_sets.py",
        "verify_attestation_binding.py", "attestation_commit_back.py",
        "gen_attestations.py",
    ):
        shutil.copyfile(ROOT / "scripts" / name, script_dir / name)
    ga.generate(root, key, datetime(2026, 8, 15, 1, tzinfo=timezone.utc))
    _git(root, "init", "-b", "main")
    _git(root, "config", "user.name", "Test")
    _git(root, "config", "user.email", "test@example.test")
    _git(root, "add", "attestations", ".attestations", "docs", "scripts", "datapulse.json", "health")
    _git(root, "commit", "-m", "accepted fixture")
    source = _git(root, "rev-parse", "HEAD")
    remote = tmp_path / "origin.git"
    _git(tmp_path, "clone", "--bare", str(root), str(remote))
    _git(root, "remote", "add", "origin", str(remote))
    # Main moves after the candidate source was cut: the submission must align
    # to this freshly-fetched base before it derives the projection.
    (root / "advance.txt").write_text("main moved\n", encoding="utf-8")
    _git(root, "add", "advance.txt")
    _git(root, "commit", "-m", "advance accepted base")
    accepted = _git(root, "rev-parse", "HEAD")
    _git(root, "push", "origin", "main")
    _git(root, "reset", "--hard", source)
    ga.generate(root, key, datetime(2026, 8, 16, 1, tzinfo=timezone.utc))
    return root, accepted, remote


def test_projection_is_refreshed_from_the_accepted_base_after_alignment(tmp_path: Path) -> None:
    """A submission that merges a moved base must publish a coherent projection."""
    root, accepted, remote = _projection_submission_root(tmp_path)
    head = ga.load(root / "attestations/chain-index.json")["current_head"]
    branch = "attestation/append-" + head

    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    gh = bin_dir / "gh"
    gh.write_text('#!/usr/bin/env bash\nprintf "%s\\n" "$@" > "$PR_ARGS"\n')
    gh.chmod(0o755)
    env = {
        **os.environ,
        "PATH": str(bin_dir) + os.pathsep + os.environ["PATH"],
        "PR_ARGS": str(tmp_path / "pr-args"),
        "DATAPULSE_ALLOW_UNWITNESSED_PUBLICATION": "1",
    }
    env.pop("GH_TOKEN", None)
    result = subprocess.run(
        ["bash", str(ROOT / "scripts/submit_attestation_append.sh")],
        cwd=root, env=env, capture_output=True, text=True, check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr

    published = tmp_path / "published"
    _git(tmp_path, "clone", str(remote), str(published))
    _git(published, "config", "user.name", "Test")
    _git(published, "config", "user.email", "test@example.test")
    _git(published, "checkout", branch)
    # The append was aligned to the freshly-fetched base before publication.
    assert len(_git(published, "rev-list", "--parents", "-n", "1", "HEAD").split()) == 3

    for name in ("chain_head.json", "index.json", "binding.json", "scores.json"):
        assert (published / "attestations/latest" / name).read_bytes() == (
            published / "attestations/2026-08-16" / name
        ).read_bytes(), name

    verify = subprocess.run(
        [sys.executable, str(published / "scripts/verify_attestation_append.py"), "--base", accepted],
        cwd=published, capture_output=True, text=True,
    )
    assert verify.returncode == 0, verify.stdout + verify.stderr


def test_projection_regeneration_is_positioned_after_the_accepted_base_merge() -> None:
    lines = (ROOT / "scripts/submit_attestation_append.sh").read_text(encoding="utf-8").splitlines()
    merge_lines = [i for i, line in enumerate(lines) if "origin/main" in line]
    refresh_lines = [i for i, line in enumerate(lines) if "refresh_projection" in line]
    assert merge_lines and refresh_lines
    assert min(refresh_lines) > max(merge_lines)
