"""End-to-end tests for the isolated release reproducibility verifier."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

import pytest

from scripts import verify_release_reproducible as verifier
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
    "README.md (MCP tools)",
    "llms.txt (MCP tools)",
    "catalog-snapshot.json",
    "catalog-graph.json",
    "data/json/",
    "data/jsonld/",
    "docs/mcp-reference.md",
    "mcp.json",
    "agent.json",
    "docs/mcp-deploy.md (MCP tools)",
    "docs/.dashboard_filters.json",
    "docs/.dashboard_sections.json",
    "docs/index.html",
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


def test_build_sets_archives_dir_inside_isolated_workdir(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    workdir = tmp_path / "isolated-build"
    captured: dict[str, object] = {}

    def fake_run(*args: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
        captured.update(kwargs)
        return subprocess.CompletedProcess(args, 0, "", "")

    monkeypatch.setattr(verifier, "_copy_source", lambda destination: None)
    monkeypatch.setattr(verifier.subprocess, "run", fake_run)
    monkeypatch.setattr(
        verifier,
        "_capture",
        lambda root, source: verifier.BuildCapture({}, {}, root),
    )

    verifier._build(ROOT, workdir, "/tmp/fake-git-dir", "2026-08-23T10:06:30Z")

    environment = captured["env"]
    assert isinstance(environment, dict)
    assert environment["DATAPULSE_ARCHIVES_DIR"] == str(workdir / ".archives")
    assert environment["DATAPULSE_ISOLATED_REPRODUCIBILITY_BUILD"] == "1"


def test_build_forwards_the_captured_reproducibility_verification_time(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    workdir = tmp_path / "isolated-build"
    captured: dict[str, object] = {}

    def fake_run(*args: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
        captured.update(kwargs)
        return subprocess.CompletedProcess(args, 0, "", "")

    monkeypatch.setattr(verifier, "_copy_source", lambda destination: None)
    monkeypatch.setattr(verifier.subprocess, "run", fake_run)
    monkeypatch.setattr(
        verifier,
        "_capture",
        lambda root, source: verifier.BuildCapture({}, {}, root),
    )

    verifier._build(
        ROOT,
        workdir,
        "/tmp/fake-git-dir",
        "2026-08-23T10:06:30Z",
    )

    environment = captured["env"]
    assert isinstance(environment, dict)
    assert environment["DATAPULSE_REPRODUCIBILITY_VERIFY_AT"] == "2026-08-23T10:06:30Z"
    assert environment["DATAPULSE_ISOLATED_REPRODUCIBILITY_BUILD"] == "1"


def test_verify_passes_one_captured_time_to_both_isolated_builds(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    created: list[Path] = []
    captured_times: list[str] = []

    def fake_workdir(root: Path, prefix: str) -> Path:
        path = root / f"{prefix}{len(created)}"
        path.mkdir()
        created.append(path)
        return path

    def fake_build(
        source: Path, workdir: Path, git_dir: str, verification_time: str
    ) -> verifier.BuildCapture:
        captured_times.append(verification_time)
        return verifier.BuildCapture({}, {}, workdir)

    monkeypatch.setattr(verifier, "_run_git", lambda *arguments: "/tmp/fake-git-dir")
    monkeypatch.setattr(verifier, "_workdir", fake_workdir)
    monkeypatch.setattr(verifier, "_build", fake_build)
    monkeypatch.setattr(verifier, "_write_hash_table", lambda path, hashes: None)
    monkeypatch.setattr(verifier, "_summary", lambda *args: "proof\n")

    assert verifier.verify(tmp_path, tmp_path / "proof.md", "reproduce") == 0
    assert len(captured_times) == 2
    assert captured_times[0] == captured_times[1]
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\+00:00", captured_times[0])


def test_build_forwards_attestation_key_path_without_key_contents(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    workdir = tmp_path / "isolated-build"
    key_path = tmp_path / "attestation-key.json"
    secret_contents = "private-key-material-must-not-leak"
    key_path.write_text(secret_contents, encoding="utf-8")
    captured: dict[str, object] = {}

    def fake_run(*args: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
        captured.update(kwargs)
        return subprocess.CompletedProcess(args, 0, "", "")

    monkeypatch.setenv("DATAPULSE_ATTESTATION_PRIVATE_KEY_FILE", str(key_path))
    monkeypatch.setattr(verifier, "_copy_source", lambda destination: None)
    monkeypatch.setattr(verifier.subprocess, "run", fake_run)
    monkeypatch.setattr(
        verifier,
        "_capture",
        lambda root, source: verifier.BuildCapture({}, {}, root),
    )

    verifier._build(ROOT, workdir, "/tmp/fake-git-dir", "2026-08-23T10:06:30Z")

    environment = captured["env"]
    assert isinstance(environment, dict)
    assert set(environment) == {
        "PATH",
        "GIT_DIR",
        "DATAPULSE_ARCHIVES_DIR",
        "DATAPULSE_ISOLATED_REPRODUCIBILITY_BUILD",
        "DATAPULSE_REPRODUCIBILITY_VERIFY_AT",
        "DATAPULSE_ATTESTATION_PRIVATE_KEY_FILE",
    }
    assert environment["DATAPULSE_ATTESTATION_PRIVATE_KEY_FILE"] == str(key_path)
    assert secret_contents not in repr(environment)
    captured_output = capsys.readouterr()
    assert secret_contents not in captured_output.out
    assert secret_contents not in captured_output.err


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
        "README.md#mcp-tools",
        "llms.txt#mcp-tools",
        "catalog-snapshot.json",
        "catalog-graph.json",
        "data/json/alpha.json",
        "data/json/beta.json",
        "data/jsonld/alpha.json",
        "data/jsonld/beta.json",
        "data/jsonld/catalog.json",
        "docs/mcp-reference.md",
        "mcp.json",
        "agent.json",
        "docs/mcp-deploy.md#mcp-tools",
        "docs/.dashboard_filters.json",
        "docs/.dashboard_sections.json",
        "docs/index.html",
    }
    assert expected <= hashes.keys()

    retained_builds = list(
        verification_run.workdir_root.glob("datapulse-release-B-*")
    )
    assert len(retained_builds) == 1
    physical_outputs = _capture_outputs(
        retained_builds[0],
        sorted(path for path in expected if "#" not in path),
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


def test_release_verification_md_records_current_release_inputs(
    verification_run: VerificationRun,
) -> None:
    assert verification_run.result.returncode == 0, verification_run.result.stderr
    proof = verification_run.summary.read_text(encoding="utf-8")
    health = json.loads((verification_run.source / "health/latest.json").read_text())
    tools = json.loads((verification_run.source / "mcp.json").read_text())["tools"]
    assert "current generated release proof" in proof
    assert f"Health checked at: `{health['checked_at']}`" in proof
    assert f"Dataset count: `{len(health['datasets'])}`" in proof
    assert f"MCP tool count: `{len(tools)}`" in proof


def test_proof_validator_rejects_stale_source_or_counts(tmp_path: Path) -> None:
    proof = tmp_path / "release-verification.md"
    proof.write_text("# Release reproducibility verification\n", encoding="utf-8")
    with pytest.raises(verifier.VerificationFailure, match="release proof drift"):
        verifier.validate_proof(proof, "a" * 40, 389, 16, "2026-08-23T10:06:30Z")


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
