"""Tests for the generated/code-derived health methodology content."""

from __future__ import annotations

import subprocess
from pathlib import Path

from scripts.tests.test_generate_profiles import _stage_source


ROOT = Path(__file__).resolve().parents[2]


SECTIONS = (
    "schema-version",
    "history-schema",
    "retention-and-archives",
    "probe-outcomes",
    "probe-cadence",
    "status-taxonomy",
    "anomaly-mode",
    "freshness-baselines",
)


def run_methodology(source: Path, timer: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["python3", "scripts/gen_health_methodology.py", "--timer", str(timer)],
        cwd=source,
        capture_output=True,
        text=True,
    )


def test_methodology_extracts_all_sections_and_is_idempotent(tmp_path: Path) -> None:
    source = _stage_source(tmp_path)
    timer = source / "datapulse-health.timer"
    timer.write_text("[Timer]\nOnCalendar=*:0/5\n", encoding="utf-8")

    first = run_methodology(source, timer)
    assert first.returncode == 0, first.stderr
    generated = source / "docs/health-methodology.md"
    first_bytes = generated.read_bytes()

    extracted = (source / "docs/.health-methodology/extracted.md").read_text(encoding="utf-8")
    for name in SECTIONS:
        assert f"<!-- BEGIN EXTRACTED: {name} -->" in extracted
        assert f"<!-- END EXTRACTED: {name} -->" in extracted

    assert "**7 days**" in generated.read_text(encoding="utf-8")
    assert "every **5 minutes**" in generated.read_text(encoding="utf-8")
    assert "datapulse/v0.4/dataset-health" in generated.read_text(encoding="utf-8")
    assert "datapulse-history/health-YYYY-MM.jsonl.gz" in generated.read_text(encoding="utf-8")

    second = run_methodology(source, timer)
    assert second.returncode == 0, second.stderr
    assert generated.read_bytes() == first_bytes


def test_methodology_html_retains_rendered_structure(tmp_path: Path) -> None:
    source = _stage_source(tmp_path)
    timer = source / "datapulse-health.timer"
    timer.write_text("[Timer]\nOnCalendar=*:0/5\n", encoding="utf-8")
    result = run_methodology(source, timer)
    assert result.returncode == 0, result.stderr

    rendered = subprocess.run(
        ["python3", "scripts/gen_health_methodology_html.py"],
        cwd=source,
        capture_output=True,
        text=True,
    )
    assert rendered.returncode == 0, rendered.stderr
    page = (source / "docs/health-methodology.html").read_text(encoding="utf-8")
    css = (ROOT / "docs/assets/datapulse.css").read_text(encoding="utf-8")
    assert "Health methodology" in page
    assert "5 minutes" in page
    assert "assets/datapulse.css" in page
    assert ":where(main) > :where(p)" in css
    assert '<main id="main-content" class="wrap prose">' in page
    assert 'style="max-width:52rem; padding-block:2.5rem"' not in page
