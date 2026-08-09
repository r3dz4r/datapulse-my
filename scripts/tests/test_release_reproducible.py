"""End-to-end tests for the isolated release reproducibility verifier."""

from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

import pytest

from scripts.tests.generator_harness import _capture_outputs
from scripts.tests.test_generate_profiles import _stage_source


ROOT = Path(__file__).resolve().parents[2]
VERIFIER = ROOT / "scripts/verify_release_reproducible.py"
REPORT_FIXTURE = ROOT / "scripts/tests/fixtures/generator/report/data"
OWNED_CATEGORIES = (
    "data/<id>.md",
    "badges/",
    "feed.xml",
    "README.md (trust-summary)",
    "changelog.json",
    "data/json/",
    "data/jsonld/",
    "docs/mcp-reference.md",
    "mcp.json",
    "docs/.dashboard_filters.json",
)


@dataclass(frozen=True)
class VerificationRun:
    result: subprocess.CompletedProcess[str]
    source: Path
    workdir_root: Path
    summary: Path
    status_before: str
    status_after: str


def _git_status() -> str:
    return subprocess.run(
        ["git", "status", "--short", "--untracked-files=no"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout


@pytest.fixture
def verification_run(tmp_path: Path) -> VerificationRun:
    source = _stage_source(tmp_path)
    shutil.copytree(REPORT_FIXTURE, source / "data", dirs_exist_ok=True)
    shutil.copy2(VERIFIER, source / "scripts/verify_release_reproducible.py")
    workdir_root = tmp_path / "isolated-builds"
    summary = source / "docs/release-verification.md"
    status_before = _git_status()
    result = subprocess.run(
        [
            "python3",
            "scripts/verify_release_reproducible.py",
            "--workdir-root",
            str(workdir_root),
            "--output",
            str(summary),
        ],
        cwd=source,
        capture_output=True,
        text=True,
        check=False,
    )
    return VerificationRun(
        result=result,
        source=source,
        workdir_root=workdir_root,
        summary=summary,
        status_before=status_before,
        status_after=_git_status(),
    )


def _metadata_file(run: VerificationRun, name: str) -> Path:
    matches = list(run.workdir_root.glob(f"datapulse-release-meta-*/{name}"))
    assert len(matches) == 1
    return matches[0]


def test_first_build_produces_expected_outputs(
    verification_run: VerificationRun,
) -> None:
    assert verification_run.result.returncode == 0, verification_run.result.stderr
    hashes = json.loads(
        _metadata_file(verification_run, "first_run.json").read_text(encoding="utf-8")
    )
    expected = {
        "data/alpha.md",
        "data/beta.md",
        "badges/alpha.svg",
        "badges/beta.svg",
        "feed.xml",
        "README.md#trust-summary",
        "changelog.json",
        "data/json/alpha.json",
        "data/json/beta.json",
        "data/jsonld/alpha.json",
        "data/jsonld/beta.json",
        "data/jsonld/catalog.json",
        "docs/mcp-reference.md",
        "mcp.json",
        "docs/.dashboard_filters.json",
    }
    assert expected <= hashes.keys()

    retained_builds = list(
        verification_run.workdir_root.glob("datapulse-release-B-*")
    )
    assert len(retained_builds) == 1
    physical_outputs = _capture_outputs(
        retained_builds[0],
        sorted(path for path in expected if path != "README.md#trust-summary"),
    )
    assert all(payload is not None for payload in physical_outputs.values())


def test_second_build_is_byte_identical(verification_run: VerificationRun) -> None:
    assert verification_run.result.returncode == 0, verification_run.result.stderr
    assert "OK: both builds produced byte-identical outputs" in verification_run.result.stdout


def test_release_verification_md_is_generated(
    verification_run: VerificationRun,
) -> None:
    assert verification_run.result.returncode == 0, verification_run.result.stderr
    summary = verification_run.summary.read_text(encoding="utf-8")
    assert "| Path category | File count | First-run hash | Second-run hash | Match? |" in summary
    assert "|---|---:|---|---|:---:|" in summary


def test_release_verification_md_includes_source_sha(
    verification_run: VerificationRun,
) -> None:
    assert verification_run.result.returncode == 0, verification_run.result.stderr
    source_sha = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=verification_run.source,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    assert source_sha in verification_run.summary.read_text(encoding="utf-8")


def test_hash_table_covers_all_owned_paths(
    verification_run: VerificationRun,
) -> None:
    assert verification_run.result.returncode == 0, verification_run.result.stderr
    summary = verification_run.summary.read_text(encoding="utf-8")
    table_categories = {
        line.split("|")[1].strip()
        for line in summary.splitlines()
        if line.startswith("|") and line.count("|") == 6
    }
    assert set(OWNED_CATEGORIES) <= table_categories


def test_does_not_touch_tracked_workspace(
    verification_run: VerificationRun,
) -> None:
    assert verification_run.result.returncode == 0, verification_run.result.stderr
    assert verification_run.status_after == verification_run.status_before
