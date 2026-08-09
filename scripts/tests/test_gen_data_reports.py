"""Isolated characterization tests for ``scripts/gen_data_reports.sh``."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from scripts.tests.generator_harness import (
    GeneratorRun,
    run_generator,
    run_generator_twice,
)


ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "scripts/tests/fixtures/generator/report"
GENERATOR = ROOT / "scripts/gen_data_reports.sh"
INPUTS = ["datapulse.json", "health/latest.json", "data"]
OUTPUTS = ["data/alpha.md", "data/beta.md"]


def _run_report_generator() -> GeneratorRun:
    result = run_generator(FIXTURE, GENERATOR, INPUTS, OUTPUTS)
    assert result.returncode == 0, result.stderr
    return result


def _report(result: GeneratorRun, relative: str = "data/alpha.md") -> str:
    output = result.outputs[relative]
    assert output is not None
    return output.decode("utf-8")


def _markdown_section(report: str, heading: str) -> str:
    match = re.search(
        rf"(?ms)^## {re.escape(heading)}\n.*?(?=^## |\Z)",
        report,
    )
    assert match is not None, f"missing section: {heading}"
    return match.group(0)


def test_status_section_refreshes_from_health() -> None:
    result = _run_report_generator()
    report = _report(result)
    health = json.loads((FIXTURE / "health/latest.json").read_text(encoding="utf-8"))
    alpha = next(row for row in health["datasets"] if row["dataset_id"] == "alpha")

    assert f"status: {alpha['status']}" in report
    assert f"last_checked: {alpha['last_checked']}" in report
    assert "**Status:** Fresh" in _markdown_section(report, "Status")
    assert "2026-08-08 at 01:02:03 UTC." in _markdown_section(
        report, "Last checked"
    )
    assert "old status" not in report.lower()


def test_hand_authored_section_preserved() -> None:
    result = _run_report_generator()
    before = (FIXTURE / "data/alpha.md").read_text(encoding="utf-8")
    after = _report(result)

    for heading in ("Quirks", "Schema", "Reproducibility"):
        assert _markdown_section(after, heading) == _markdown_section(before, heading)
    assert "QUIRK_SENTINEL_TEST_DO_NOT_REMOVE_ALPHA" in after

    # Cadence and descriptive metadata are hand-authored frontmatter. The health
    # refresh must not replace them with values from the point-in-time snapshot.
    for line in (
        "next_expected_update: every Monday",
        "schema_version: 1.0",
        "licence: Open Government Licence (Malaysia)",
        "attribution: Alpha Fixture Agency",
        "  - alpha values require normalization",
    ):
        assert line in before
        assert line in after


def test_missing_report_is_skipped() -> None:
    """A missing report is counted as skipped and is not created by the generator."""

    result = run_generator(
        FIXTURE,
        GENERATOR,
        ["datapulse.json", "health/latest.json", "data/beta.md"],
        OUTPUTS,
    )

    assert result.returncode == 0, result.stderr
    assert "Regenerated 1 dataset reports; skipped 1; failed 0." in result.stdout
    assert result.outputs["data/alpha.md"] is None
    assert result.outputs["data/beta.md"] is not None


def test_malformed_health_skips_or_fails(tmp_path: Path) -> None:
    """The harness rejects malformed health with code 2 before any report runs."""

    source = tmp_path / "malformed-source"
    shutil.copytree(FIXTURE, source)
    (source / "health/latest.json").write_text(
        '{"datasets": [{"dataset_id": "alpha"}', encoding="utf-8"
    )

    result = run_generator(
        source,
        GENERATOR,
        INPUTS,
        OUTPUTS,
        workdir_root=tmp_path / "malformed-run",
    )

    assert result.returncode == 2
    assert "unable to parse JSON" in result.stderr
    for relative in OUTPUTS:
        assert result.outputs[relative] == (FIXTURE / relative).read_bytes()


def test_deterministic_second_run() -> None:
    first, second, diff = run_generator_twice(
        FIXTURE,
        GENERATOR,
        INPUTS,
        OUTPUTS,
    )

    assert first.returncode == 0, first.stderr
    assert second.returncode == 0, second.stderr
    assert all(diff[path] is True for path in OUTPUTS)


def test_does_not_touch_tracked_workspace(tmp_path: Path) -> None:
    tracked_paths = (ROOT / "data/alpha.md", ROOT / "data/beta.md")
    before_files = {
        path: path.read_bytes() if path.exists() else None for path in tracked_paths
    }
    before_stat = subprocess.run(
        ["git", "diff", "--stat", "--", "data/"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout

    result = run_generator(
        FIXTURE,
        GENERATOR,
        INPUTS,
        OUTPUTS,
        workdir_root=tmp_path / "isolated-report-run",
    )

    assert result.returncode == 0, result.stderr
    after_stat = subprocess.run(
        ["git", "diff", "--stat", "--", "data/"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    after_files = {
        path: path.read_bytes() if path.exists() else None for path in tracked_paths
    }
    assert after_stat == before_stat
    assert after_files == before_files
    assert result.workdir.is_relative_to(tmp_path)
