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


def test_agent_guidance_is_exempt_only_from_terminology_and_volatile_literals(tmp_path: Path) -> None:
    verifier = _module()
    root = _fixture(tmp_path, "# Guide\n")
    (root / "docs/guide.md").unlink()
    (root / "docs/AGENTS.md").write_text(
        "# An industry-leading guide\n419 datasets are listed.\n", encoding="utf-8"
    )
    (root / "config/public-surfaces.json").write_text(
        json.dumps({"artifacts": ["/AGENTS.md"]}), encoding="utf-8"
    )

    result = verifier.verify(root, generated_checks={})

    assert result.exit_code == 0
    assert not [finding for finding in result.findings if not finding.startswith("REPORT ")]


def test_ordinary_document_keeps_terminology_and_volatile_literal_findings(tmp_path: Path) -> None:
    verifier = _module()
    root = _fixture(tmp_path, "# An industry-leading guide\n419 datasets are listed.\n")

    result = verifier.verify(root, generated_checks={})

    assert result.exit_code == 1
    assert any("banned claim: industry-leading" in finding for finding in result.findings)
    assert any("volatile literal: 419 datasets" in finding for finding in result.findings)


def test_exempt_files_keep_link_and_banned_claim_checks(tmp_path: Path) -> None:
    verifier = _module()
    root = _fixture(tmp_path, "# Guide\n")
    (root / "docs/guide.md").unlink()
    (root / "docs/AGENTS.md").write_text("[missing](missing.md)\n", encoding="utf-8")
    (root / "docs/generated.md").write_text(
        "<!-- generated: scripts/gen_guide.py -->\nAn industry-leading guide.\n", encoding="utf-8"
    )

    result = verifier.verify(root, generated_checks={})

    assert result.exit_code == 1
    assert "docs/AGENTS.md -> missing.md" in result.findings
    assert any("docs/generated.md" in finding and "banned claim: industry-leading" in finding for finding in result.findings)


def test_historical_record_exempts_volatile_literals_but_not_banned_claims(tmp_path: Path) -> None:
    verifier = _module()
    root = _fixture(tmp_path, "# Guide\n")
    (root / "docs/guide.md").unlink()
    (root / "docs/trust-snapshot-2026-01-01.md").write_text(
        "419 datasets are listed.\nAn industry-leading record.\n", encoding="utf-8"
    )

    result = verifier.verify(root, generated_checks={})

    assert result.exit_code == 1
    assert not any("volatile literal" in finding for finding in result.findings)
    assert any("banned claim: industry-leading" in finding for finding in result.findings)


def test_generated_surface_exempts_volatile_literals(tmp_path: Path) -> None:
    verifier = _module()
    root = _fixture(tmp_path, "<!-- generated: scripts/gen_guide.py -->\n419 datasets are listed.\n")

    marker_owned = verifier.verify(root, generated_checks={})
    (root / "docs/guide.md").write_text("<!-- BEGIN generated -->\n419 datasets are listed.\n<!-- END generated -->\n", encoding="utf-8")
    block_owned = verifier.verify(root, generated_checks={})

    assert marker_owned.exit_code == 0
    assert block_owned.exit_code == 0
    assert not [finding for finding in marker_owned.findings if not finding.startswith("REPORT ")]
    assert not [finding for finding in block_owned.findings if not finding.startswith("REPORT ")]


def test_generator_injection_precondition_is_informational_but_drift_fails(tmp_path: Path) -> None:
    verifier = _module()
    root = _fixture(tmp_path)
    injection = root / "scripts/gen_injection.py"
    injection.write_text("import sys\nprint('source commit SHA must be explicitly injected')\nsys.exit(1)\n", encoding="utf-8")
    drift = root / "scripts/gen_drift.py"
    drift.write_text("import sys\nprint('outputs are stale')\nsys.exit(1)\n", encoding="utf-8")

    informational = verifier.verify(
        root, generated_checks={"scripts/gen_injection.py": (sys.executable, "scripts/gen_injection.py", "--check")}
    )
    failed = verifier.verify(
        root, generated_checks={"scripts/gen_drift.py": (sys.executable, "scripts/gen_drift.py", "--check")}
    )

    assert informational.exit_code == 0
    assert not [finding for finding in informational.findings if not finding.startswith("REPORT ")]
    assert "informational: scripts/gen_injection.py requires injection: source commit SHA must be explicitly injected" in informational.informational
    assert failed.exit_code == 1
    assert any("outputs are stale" in finding for finding in failed.findings)


def test_escaping_link_is_informational_only_when_artifact_root_target_exists(tmp_path: Path) -> None:
    verifier = _module()
    root = _fixture(tmp_path, "[schema](../record-evidence.schema.json)\n")
    (root / "record-evidence.schema.json").write_text("{}\n", encoding="utf-8")

    resolved = verifier.verify(root, generated_checks={})
    (root / "record-evidence.schema.json").unlink()
    missing = verifier.verify(root, generated_checks={})
    (root / "docs/guide.md").write_text("[tmp](/tmp/private.md)\n", encoding="utf-8")
    absolute = verifier.verify(root, generated_checks={})

    assert resolved.exit_code == 0
    assert resolved.informational == [
        "informational: docs/guide.md -> ../record-evidence.schema.json resolves outside docs/ and is served from the artifact root"
    ]
    assert missing.exit_code == 1
    assert "docs/guide.md -> ../record-evidence.schema.json: path escapes docs/" in missing.findings
    assert absolute.exit_code == 1
    assert "docs/guide.md -> /tmp/private.md: absolute filesystem path" in absolute.findings


def test_report_only_prints_real_findings_but_exits_zero(tmp_path: Path, capsys) -> None:
    verifier = _module()
    root = _fixture(tmp_path, "# An industry-leading guide\n")
    original_argv = sys.argv
    try:
        sys.argv = [str(SCRIPT), "--root", str(root), "--report-only"]
        assert verifier.main() == 0
    finally:
        sys.argv = original_argv

    output = capsys.readouterr().out
    assert "banned claim: industry-leading" in output
    assert "findings were reported and not enforced" in output
