from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from scripts.gen_landing_page import MARKER, REGISTER_STATUS_ORDER, load_landing_config, render
from scripts.public_surface_generation import GenerationError, load_public_surfaces


ROOT = Path(__file__).resolve().parents[2]


def _landing_root(tmp_path: Path) -> Path:
    root = tmp_path / "landing"
    for relative in (
        "config/landing-page.json",
        "config/public-surfaces.json",
        "config/public-surfaces.schema.json",
        "scripts/gen_landing_page.py",
        "scripts/public_surface_generation.py",
        "scripts/templates/landing.html.tmpl",
        "docs/assets/datapulse.css",
        "docs/assets/site-nav.html",
        "health/latest.json",
        "datapulse.json",
    ):
        source = ROOT / relative
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
    return root


def _config(root: Path) -> dict:
    return json.loads((root / "config/landing-page.json").read_text(encoding="utf-8"))


def _write_config(root: Path, value: dict) -> None:
    (root / "config/landing-page.json").write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def _run(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["python3", "scripts/gen_landing_page.py", *args], cwd=root, capture_output=True, text=True, check=False)


def test_landing_page_is_deterministic_generated_and_uses_canonical_links(tmp_path: Path) -> None:
    root = _landing_root(tmp_path)
    first = _run(root)
    assert first.returncode == 0, first.stderr
    output = (root / "docs/landing.html").read_bytes()
    second = _run(root)
    assert second.returncode == 0, second.stderr
    assert (root / "docs/landing.html").read_bytes() == output
    page = output.decode("utf-8")
    assert page.startswith("<!doctype html>\n" + MARKER)
    for href in ("/agent.json", "/mcp.json", "/llms.txt", "/datapulse.json", "/health/latest.json", "/data/jsonld/catalog.json"):
        assert f'href="{href}"' in page
    assert "fetch('/health/latest.json', {cache: 'no-store'" in page
    assert "unavailable; treat freshness as unknown" in page
    assert "<nav class=\"site-nav\"" in page
    assert '<link rel="stylesheet" href="/assets/datapulse.css" crossorigin="anonymous">' in page
    assert '<link rel="stylesheet" href="/assets/datapulse.css">' not in page


def test_landing_page_rejects_malformed_claims_and_manual_mcp_enumeration(tmp_path: Path) -> None:
    root = _landing_root(tmp_path)
    config = _config(root)
    config["rails"][0]["copy"] = "Use search_datasets to find data."
    _write_config(root, config)
    result = _run(root)
    assert result.returncode == 1
    assert "manual MCP tool enumeration" in result.stderr

    config = _config(root)
    config["rails"][0]["copy"] = "A regulatory certification service."
    _write_config(root, config)
    result = _run(root)
    assert result.returncode == 1
    assert "unsupported claim" in result.stderr


def test_landing_page_fails_closed_without_replacing_existing_output(tmp_path: Path) -> None:
    root = _landing_root(tmp_path)
    assert _run(root).returncode == 0
    output = root / "docs/landing.html"
    original = output.read_text(encoding="utf-8")
    config = _config(root)
    config["machine_surfaces"][0]["href"] = "/not-a-public-surface"
    _write_config(root, config)
    result = _run(root)
    assert result.returncode == 1
    assert "not a declared canonical public surface" in result.stderr
    assert output.read_text(encoding="utf-8") == original


def test_landing_page_check_detects_hand_edit_drift(tmp_path: Path) -> None:
    root = _landing_root(tmp_path)
    assert _run(root).returncode == 0
    output = root / "docs/landing.html"
    output.write_text(output.read_text(encoding="utf-8") + "<!-- hand edit -->\n", encoding="utf-8")
    assert _run(root, "--check").returncode == 1
    assert _run(root).returncode == 0
    assert _run(root, "--check").returncode == 0


def test_landing_config_enforces_boundaries_and_runtime_surfaces() -> None:
    surfaces = load_public_surfaces(ROOT)
    config = load_landing_config(ROOT, surfaces)
    assert config["mcp_endpoint"] == "https://mcp.data-pulse.my/mcp"
    assert config["health_href"] == "/health/latest.json"
    page = render(ROOT)
    assert "Payable <span>(Future)</span>" in page
    assert "substantive truth" in page


def test_landing_config_rejects_missing_boundary(tmp_path: Path) -> None:
    root = _landing_root(tmp_path)
    config = _config(root)
    config["boundaries"] = config["boundaries"][:3]
    _write_config(root, config)
    with pytest.raises(GenerationError, match="array with at least 4"):
        load_landing_config(root, load_public_surfaces(root))


def test_landing_page_classes_are_owned_by_the_canonical_stylesheet() -> None:
    page = render(ROOT)
    stylesheet = (ROOT / "docs/assets/datapulse.css").read_text(encoding="utf-8")
    classes = {name for value in re.findall(r'\bclass="([^"]+)"', page) for name in value.split()}
    defined = set(re.findall(r"\.([a-z][a-z0-9-]*)\b", stylesheet))
    assert classes <= defined
    assert {"landing-flow", "receipt", "landing-grid", "surface-list", "boundary-list", "brand-logo"} <= defined
    assert '<a class="skip-link" href="#main-content">' in page
    assert '<main id="main-content">' in page
    assert "aria-labelledby=" in page
    assert "a:focus-visible, button:focus-visible" in stylesheet
    assert "@media (max-width: 768px)" in stylesheet
    assert "@media (prefers-reduced-motion: reduce)" in stylesheet


def test_landing_page_receipt_uses_live_evidence(tmp_path: Path) -> None:
    root = _landing_root(tmp_path)
    page = render(root)
    assert "Preview schema field" not in page
    assert "not verified evidence" not in page
    assert "949 records; within tolerance" in page
    assert "Evidence verdict: use" in page
    assert 'href="/data/fuelprice.md"' in page


def test_landing_page_register_is_live_and_bounded(tmp_path: Path) -> None:
    root = _landing_root(tmp_path)
    page = render(root)

    assert "LIVE REGISTER" in page
    assert "register-title" in page

    health = json.loads((root / "health/latest.json").read_text(encoding="utf-8"))
    datasets = health["datasets"]
    total = len(datasets)

    priority = {status: index for index, status in enumerate(REGISTER_STATUS_ORDER)}
    ordered = sorted(
        datasets,
        key=lambda row: (priority.get(row.get("status"), len(REGISTER_STATUS_ORDER)), str(row.get("dataset_id", ""))),
    )
    first_id = ordered[0]["dataset_id"]
    assert first_id in page

    assert "legend-swatch" in page
    assert f"{total} datasets total" in page
    assert "more datasets" in page
    assert page.count("legend-swatch") < total
