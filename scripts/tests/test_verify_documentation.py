"""Tests for the fail-capable public documentation verifier."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/verify_documentation.py"


def _module():
    spec = importlib.util.spec_from_file_location("verify_documentation", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _fixture(root: Path, text: str = "# Guide\n") -> Path:
    (root / "docs").mkdir(parents=True)
    (root / "config").mkdir()
    (root / "scripts").mkdir()
    (root / "docs/guide.md").write_text(text, encoding="utf-8")
    (root / "config/public-surfaces.json").write_text(
        json.dumps({"artifacts": ["/guide.md"]}), encoding="utf-8"
    )
    return root


def test_clean_fixture_passes(tmp_path: Path) -> None:
    verifier = _module()
    root = _fixture(
        tmp_path,
        "---\naudience: public\ncanonical: /guide.md\nvolatility: stable\nowner: docs\nreview_trigger: release\nlast_verified: 2026-09-26\n---\n# Guide\n",
    )

    result = verifier.verify(root, generated_checks={})

    assert result.exit_code == 0
    assert result.findings == []


def test_broken_link_fails_and_names_target(tmp_path: Path) -> None:
    verifier = _module()
    root = _fixture(tmp_path, "# Guide\n[missing](missing.md)\n")

    result = verifier.verify(root, generated_checks={})

    assert result.exit_code == 1
    assert "docs/guide.md -> missing.md" in result.findings


def test_banned_phrase_fails_and_names_phrase(tmp_path: Path) -> None:
    verifier = _module()
    root = _fixture(tmp_path, "# An industry-leading guide\n")

    result = verifier.verify(root, generated_checks={})

    assert result.exit_code == 1
    assert any("industry-leading" in finding for finding in result.findings)


def test_volatile_literal_requires_a_qualifier(tmp_path: Path) -> None:
    verifier = _module()
    root = _fixture(tmp_path, "# Guide\n419 datasets are listed.\n")

    failed = verifier.verify(root, generated_checks={})
    assert failed.exit_code == 1
    assert any("419 datasets" in finding for finding in failed.findings)

    (root / "docs/guide.md").write_text("# Guide\nAs of 2026-09-26, 419 datasets are listed.\n", encoding="utf-8")
    passed = verifier.verify(root, generated_checks={})
    assert passed.exit_code == 0


def test_front_matter_is_staged_until_strict_mode(tmp_path: Path) -> None:
    verifier = _module()
    root = _fixture(tmp_path)

    report_only = verifier.verify(root, generated_checks={})
    strict = verifier.verify(root, strict_frontmatter=True, generated_checks={})

    assert report_only.exit_code == 0
    assert any(finding.startswith("REPORT docs/guide.md") for finding in report_only.findings)
    assert strict.exit_code == 1
    assert any("docs/guide.md" in finding for finding in strict.findings)


def test_generator_drift_fails_using_injected_check_command(tmp_path: Path) -> None:
    verifier = _module()
    root = _fixture(tmp_path)
    generator = root / "scripts/gen_fake.py"
    generator.write_text("raise SystemExit(1)\n", encoding="utf-8")

    result = verifier.verify(
        root,
        generated_checks={"scripts/gen_fake.py": (sys.executable, "scripts/gen_fake.py", "--check")},
    )

    assert result.exit_code == 1
    assert any("scripts/gen_fake.py" in finding for finding in result.findings)
