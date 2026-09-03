"""Regression coverage for the generated site navigation partial."""

from __future__ import annotations

import json
import shutil
import subprocess
from html.parser import HTMLParser
from pathlib import Path

from scripts import gen_site_nav


ROOT = Path(__file__).resolve().parents[2]
PAGES = ("index.html", "npra.html", "health-methodology.html", "learn.html")
LEARN_PAGE = ROOT / "docs/learn.html"
HEALTH_METHODOLOGY_TEMPLATE = ROOT / "scripts/templates/health-methodology.html.tmpl"


class _TagCollector(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.tags: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.tags.append(tag)


def _write_public_surface_fixture(root: Path) -> None:
    config_dir = root / "config"
    config_dir.mkdir(exist_ok=True)
    for name in ("public-surfaces.json", "public-surfaces.schema.json"):
        shutil.copy(ROOT / "config" / name, config_dir / name)


def test_canonical_partial_is_well_formed_and_contains_expected_nav_links() -> None:
    partial = (ROOT / "docs/assets/site-nav.html").read_text(encoding="utf-8")
    parser = _TagCollector()
    parser.feed(partial)
    parser.close()

    assert parser.tags.count("nav") == 1
    assert "div" in parser.tags
    assert 'class="nav-links"' in partial
    # Scoped nav: dark-theme reversed (white) logo; only Register + GitHub in the menu.
    assert 'href="/health-methodology.html"' not in partial
    assert ">Methodology</a>" not in partial
    assert 'href="/learn.html"' not in partial
    assert ">Learn</a>" not in partial
    assert ">NPRA</a>" not in partial
    assert ">MCP</a>" not in partial
    assert ">Catalogue</a>" not in partial
    assert 'href="/"' in partial and ">Register</a>" in partial
    assert 'href="https://github.com/r3dz4r/datapulse-my"' in partial
    assert partial.count("<img") == 1
    assert '<a class="brand" href="/" aria-label="DataPulse home"><img class="brand-logo" src="/assets/brand/datapulse-horizontal-reversed.svg" alt="DataPulse"></a>' in partial
    assert "/assets/brand/datapulse-horizontal-full-color.svg" not in partial
    assert 'href="/#mcp"' not in partial
    assert 'href="/#machine-title"' not in partial
    assert 'href="/landing"' not in partial
    assert 'href="/landing#' not in partial
    assert "[DATA]" not in partial
    assert "DataPulse MY" not in partial


def test_health_methodology_template_uses_canonical_landing_links() -> None:
    template = HEALTH_METHODOLOGY_TEMPLATE.read_text(encoding="utf-8")

    assert 'href="/"' in template
    # Scoped dark nav: no MCP/surfaces anchors, reversed logo, Dashboard + GitHub only.
    assert 'href="/#mcp"' not in template
    assert 'href="/#surfaces"' not in template
    assert "datapulse-horizontal-reversed.svg" in template
    assert ">Dashboard</a>" in template
    assert 'href="https://github.com/r3dz4r/datapulse-my"' in template
    assert 'href="/landing"' not in template
    assert 'href="/landing#' not in template


def test_inject_all_replaces_only_whitelisted_existing_nav_blocks(tmp_path: Path) -> None:
    _write_public_surface_fixture(tmp_path)
    docs = tmp_path / "docs"
    assets = docs / "assets"
    assets.mkdir(parents=True)
    canonical = (ROOT / "docs/assets/site-nav.html").read_text(encoding="utf-8")
    (assets / "site-nav.html").write_text(canonical, encoding="utf-8")
    old_nav = '<nav class="site-nav"><a href="/old">Old</a></nav>'

    for page in PAGES:
        (docs / page).write_text(f"<html><body>{old_nav}</body></html>\n", encoding="utf-8")
    untouched = docs / "404.html"
    untouched.write_text("<html><body>No navigation here.</body></html>\n", encoding="utf-8")
    original_404 = untouched.read_bytes()

    changed = gen_site_nav.inject_all(tmp_path)

    assert changed == [docs / page for page in PAGES]
    for page in PAGES:
        rendered = (docs / page).read_text(encoding="utf-8")
        assert old_nav not in rendered
        assert canonical.rstrip() in rendered
        assert "<!-- BEGIN SITE-NAV (generated from assets/site-nav.html) -->" in rendered
        assert "<!-- END SITE-NAV -->" in rendered
    assert untouched.read_bytes() == original_404
    assert gen_site_nav.inject_all(tmp_path) == []


def test_check_is_clean_for_the_rendered_site_pages() -> None:
    result = subprocess.run(
        ["python3", "scripts/gen_site_nav.py", "--check"],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stdout + result.stderr


def test_learn_page_uses_the_shared_shell_and_verified_builder_surfaces() -> None:
    page = LEARN_PAGE.read_text(encoding="utf-8")
    canonical = (ROOT / "docs/assets/site-nav.html").read_text(encoding="utf-8").rstrip()
    stylesheet = (ROOT / "docs/assets/datapulse.css").read_text(encoding="utf-8")

    assert "<!-- BEGIN SITE-NAV (generated from assets/site-nav.html) -->" in page
    assert canonical in page
    assert '<a class="skip-link" href="#main-content">' in page
    assert '<main id="main-content">' in page
    assert page.count('<h1 id="hero-title">') == 1
    assert 'class="prose"' not in page
    assert "<style" not in page
    assert 'href="https://colab.research.google.com/github/r3dz4r/datapulse-my/blob/main/docs/trust-layer-notebook.ipynb"' in page
    assert 'href="/data/fuelprice.md"' in page
    assert "https://mcp.data-pulse.my/mcp" in page
    assert 'class="code-wrap"' in page
    assert "white-space: pre-wrap" in stylesheet
    assert "overflow-wrap: anywhere" in stylesheet


def test_public_pages_use_plain_same_origin_stylesheet_links() -> None:
    # Same-origin CSS must NOT carry crossorigin="anonymous": forcing a CORS-mode
    # fetch on a same-origin stylesheet causes intermittent styling drops in
    # Chrome (documented Chromium/CSS-engine issue), matching a prior audit.
    for page_name in PAGES:
        page = (ROOT / "docs" / page_name).read_text(encoding="utf-8")
        assert '<link rel="stylesheet" href="/assets/datapulse.css">' in page or '<link rel="stylesheet" href="assets/datapulse.css">' in page
        assert 'crossorigin="anonymous"' not in page


def test_learn_page_is_declared_and_discoverable() -> None:
    config = json.loads((ROOT / "config/public-surfaces.json").read_text(encoding="utf-8"))
    sitemap = (ROOT / "sitemap.xml").read_text(encoding="utf-8")

    assert "/learn.html" in config["pages"]
    assert LEARN_PAGE.is_file()
    assert "https://www.data-pulse.my/learn.html" in sitemap
