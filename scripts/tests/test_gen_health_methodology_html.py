"""Tests for the standalone health methodology HTML renderer."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from scripts import gen_health_methodology_html as renderer


def test_extract_title_and_pandoc_command(tmp_path: Path) -> None:
    source = tmp_path / "methodology.md"
    source.write_text("# Health methodology\n", encoding="utf-8")

    assert renderer.extract_title(source) == "Health methodology"
    command = renderer.pandoc_command(
        "pandoc", source, tmp_path / "template", tmp_path / "output", "Health methodology"
    )
    assert command == [
        "pandoc", "--standalone", "--from=gfm", "--to=html5",
        "--metadata=title:Health methodology", f"--template={tmp_path / 'template'}",
        "--output", str(tmp_path / "output"), str(source),
    ]


def test_extract_title_rejects_missing_heading(tmp_path: Path) -> None:
    source = tmp_path / "methodology.md"
    source.write_text("## Not a title\n", encoding="utf-8")

    with pytest.raises(ValueError, match="no level-one title"):
        renderer.extract_title(source)


def test_rendered_page_has_title_body_and_is_deterministic() -> None:
    first = subprocess.run(["python3", str(renderer.__file__)], capture_output=True, text=True)
    first_page = renderer.OUTPUT.read_bytes()
    second = subprocess.run(["python3", str(renderer.__file__)], capture_output=True, text=True)

    assert first.returncode == second.returncode == 0, first.stderr or second.stderr
    page = renderer.OUTPUT.read_text(encoding="utf-8")
    assert "<title>Health methodology | DataPulse MY</title>" in page
    assert "<h1 id=\"health-methodology\">Health methodology</h1>" in page
    assert "Schema version" in page
    assert first_page == renderer.OUTPUT.read_bytes()


def test_main_fails_clearly_when_pandoc_is_missing(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.setattr(renderer.shutil, "which", lambda _: None)

    assert renderer.main() == 1
    assert "Pandoc executable not found" in capsys.readouterr().err


def test_main_fails_clearly_when_source_is_missing(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.setattr(renderer, "SOURCE", Path("/missing/health-methodology.md"))

    assert renderer.main() == 1
    assert "source is missing" in capsys.readouterr().err


def test_main_reports_pandoc_failure(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(renderer.shutil, "which", lambda _: "/usr/bin/pandoc")

    def fail(*args: object, **kwargs: object) -> None:
        raise subprocess.CalledProcessError(9, ["pandoc"])

    monkeypatch.setattr(renderer.subprocess, "run", fail)

    assert renderer.main() == 9
    assert "Pandoc failed while rendering" in capsys.readouterr().err
