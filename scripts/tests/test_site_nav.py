"""Regression coverage for the generated site navigation partial."""

from __future__ import annotations

import subprocess
from html.parser import HTMLParser
from pathlib import Path

from scripts import gen_site_nav


ROOT = Path(__file__).resolve().parents[2]
PAGES = ("index.html", "landing.html", "npra.html", "health-methodology.html")


class _TagCollector(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.tags: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.tags.append(tag)


def test_canonical_partial_is_well_formed_and_contains_expected_nav_links() -> None:
    partial = (ROOT / "docs/assets/site-nav.html").read_text(encoding="utf-8")
    parser = _TagCollector()
    parser.feed(partial)
    parser.close()

    assert parser.tags.count("nav") == 1
    assert "div" in parser.tags
    assert 'class="nav-links"' in partial
    assert 'href="/health-methodology.html"' in partial
    assert ">Methodology</a>" in partial


def test_inject_all_replaces_only_whitelisted_existing_nav_blocks(tmp_path: Path) -> None:
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
