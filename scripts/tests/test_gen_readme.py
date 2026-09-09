#!/usr/bin/env python3
"""Tests for deterministic README rendering from canonical inputs."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from scripts.gen_readme import GenerationError, generate


def _write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def _fixture_root(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    (root / "scripts/templates").mkdir(parents=True)
    (root / "scripts/templates/README.md.tmpl").write_text(
        "Narrative stays unchanged.\n\n"
        "<!-- BEGIN readme-hero -->\nold\n<!-- END readme-hero -->\n\n"
        "<!-- BEGIN readme-cover -->old<!-- END readme-cover -->\n\n"
        "<!-- BEGIN readme-health -->\nold\n<!-- END readme-health -->\n\n"
        "<!-- BEGIN readme-licences -->old<!-- END readme-licences -->\n\n"
        "<!-- BEGIN readme-inventory -->\nold\n<!-- END readme-inventory -->\n\n"
        "<!-- BEGIN readme-cadence -->\nold\n<!-- END readme-cadence -->\n\n"
        "<!-- BEGIN mcp-tools -->\nowned elsewhere\n<!-- END mcp-tools -->\n\n"
        "<!-- BEGIN public-discovery -->\nowned elsewhere\n<!-- END public-discovery -->\n",
        encoding="utf-8",
    )
    _write_json(root / "custodians.json", {"custodians": {"agency": {"name": "Agency"}}})
    _write_json(
        root / "datapulse.json",
        {"datasets": [{"id": "alpha", "name": "Alpha", "custodian": "agency", "licence": {"name": "CC BY 4.0"}, "health_report": "data/alpha.md", "refresh_frequency": "daily"}]},
    )
    _write_json(
        root / "health/latest.json",
        {"_trust_summary": {"datasets_total": 1, "by_status": {"fresh": 1, "stale": 0}}},
    )
    return root


def test_render_is_deterministic_and_preserves_other_owners(tmp_path: Path) -> None:
    root = _fixture_root(tmp_path)

    assert generate(root)
    first = (root / "README.md").read_bytes()
    assert not generate(root)
    assert (root / "README.md").read_bytes() == first
    text = first.decode("utf-8")
    assert "Narrative stays unchanged." in text
    assert "owned elsewhere" in text
    assert "1 official Malaysian datasets" in text


def test_fake_onboarding_updates_derived_blocks_without_mutating_template(tmp_path: Path) -> None:
    root = _fixture_root(tmp_path)
    template_before = (root / "scripts/templates/README.md.tmpl").read_bytes()
    manifest = json.loads((root / "datapulse.json").read_text(encoding="utf-8"))
    manifest["datasets"].append({"id": "zeta", "name": "Zeta", "custodian": "new-publisher", "licence": {"name": "ODC-BY"}, "health_report": "data/zeta.md", "refresh_frequency": "monthly"})
    _write_json(root / "datapulse.json", manifest)
    _write_json(root / "health/latest.json", {"_trust_summary": {"datasets_total": 2, "by_status": {"fresh": 2}}})

    generate(root)

    text = (root / "README.md").read_text(encoding="utf-8")
    assert "2 official Malaysian datasets" in text
    assert "[Zeta](data/zeta.md)" in text
    assert "new-publisher" in text
    assert "ODC-BY (1)" in text
    assert (root / "scripts/templates/README.md.tmpl").read_bytes() == template_before


def test_check_reports_stale_output_and_balanced_markers(tmp_path: Path) -> None:
    root = _fixture_root(tmp_path)
    assert generate(root)
    command = [sys.executable, str(ROOT / "scripts/gen_readme.py"), "--root", str(root), "--check"]
    assert subprocess.run(command, check=False).returncode == 0
    readme = root / "README.md"
    readme.write_text(readme.read_text(encoding="utf-8").replace("Alpha", "Stale Alpha", 1), encoding="utf-8")
    assert subprocess.run(command, check=False).returncode != 0
    text = readme.read_text(encoding="utf-8")
    assert text.count("<!-- BEGIN readme-") == text.count("<!-- END readme-")


def test_repository_template_is_the_canonical_public_readme_contract() -> None:
    template = (ROOT / "scripts/templates/README.md.tmpl").read_text(encoding="utf-8")

    assert template.startswith("# DataPulse\n")
    assert template.count("## Who this serves") == 1
    assert template.count("## Connect an AI agent") == 1
    assert "## Who it is for" not in template
    assert "## Use this for" not in template
    assert "Authenticated buyer API" not in template
    assert "DataPulse MY" not in template
    assert template.index("## Legal") > template.index("## Privacy")
    for marker in (
        "readme-hero",
        "readme-cover",
        "readme-health",
        "readme-licences",
        "readme-inventory",
        "readme-cadence",
        "mcp-tools",
        "public-discovery",
    ):
        assert template.count(f"<!-- BEGIN {marker} -->") == 1
        assert template.count(f"<!-- END {marker} -->") == 1
