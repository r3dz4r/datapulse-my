import json
import re
import subprocess
import sys
from collections import Counter
from html.parser import HTMLParser
from pathlib import Path

import pytest

from scripts.embed_dashboard_data import EmbedError, _dashboard_facts, embed_all


ROOT = Path(__file__).resolve().parents[2]
FIXTURE_MANIFEST = (
    Path(__file__).parent / "fixtures/repository_contract/valid/datapulse.json"
)
CANONICAL_KEYS = [
    "all",
    "economy",
    "environment",
    "government_open_data",
    "healthcare",
    "other",
    "transport",
    "weather",
]

# Measured 2026-08-24 baseline: 1,188,958 homepage bytes and 943,505
# embedded-data bytes. These temporary headroom ceilings should be revised
# deliberately after a later dashboard component-breakdown optimization.
MAX_HOMEPAGE_BYTES = 1_248_406
MAX_EMBEDDED_DATA_BYTES = 1_000_115
EMBEDDED_DATA_BLOCK = re.compile(rb'<script id="embedded-data">.*?</script>', re.DOTALL)


class CategoryFilterParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.in_filter_nav = False
        self.buttons = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        if tag == "nav" and "category-filters" in attributes.get("class", "").split():
            self.in_filter_nav = True
        elif self.in_filter_nav and tag == "button":
            self.buttons.append(attributes)

    def handle_endtag(self, tag: str) -> None:
        if self.in_filter_nav and tag == "nav":
            self.in_filter_nav = False


def generate_filters(manifest: Path, output: Path) -> dict:
    subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts/gen_dashboard_filters.py"),
            "--manifest",
            str(manifest),
            "--output",
            str(output),
        ],
        check=True,
        cwd=ROOT,
    )
    return json.loads(output.read_text(encoding="utf-8"))


def assert_dashboard_payload_within_budget(document: bytes) -> None:
    embedded_data = EMBEDDED_DATA_BLOCK.search(document)
    assert embedded_data is not None, "generated dashboard is missing embedded-data block"

    assert len(document) <= MAX_HOMEPAGE_BYTES, (
        f"homepage HTML is {len(document)} bytes; maximum is {MAX_HOMEPAGE_BYTES} bytes"
    )
    embedded_bytes = len(embedded_data.group(0))
    assert embedded_bytes <= MAX_EMBEDDED_DATA_BYTES, (
        "embedded-data block is "
        f"{embedded_bytes} bytes; maximum is {MAX_EMBEDDED_DATA_BYTES} bytes"
    )


def test_fixture_generates_all_count_and_zero_canonical_counts(tmp_path: Path) -> None:
    result = generate_filters(FIXTURE_MANIFEST, tmp_path / "dashboard-filters.json")

    assert result["namespaces"][0] == {"key": "all", "count": 2}
    assert result["namespaces"][1:] == [
        {"key": key, "count": 0} for key in CANONICAL_KEYS[1:]
    ]


def test_real_manifest_counts_match_dataset_namespaces(tmp_path: Path) -> None:
    manifest_path = ROOT / "datapulse.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    expected_counts = Counter(row["namespace"] for row in manifest["datasets"])

    result = generate_filters(manifest_path, tmp_path / "dashboard-filters.json")
    namespaces = result["namespaces"]

    assert len(namespaces) == 8
    assert namespaces[0]["count"] == len(manifest["datasets"])
    assert {row["key"]: row["count"] for row in namespaces[1:]} == {
        key: expected_counts.get(key, 0) for key in CANONICAL_KEYS[1:]
    }


def test_namespace_order_is_all_then_alphabetical(tmp_path: Path) -> None:
    result = generate_filters(ROOT / "datapulse.json", tmp_path / "dashboard-filters.json")

    assert [row["key"] for row in result["namespaces"]] == CANONICAL_KEYS


def test_generated_dashboard_payload_stays_within_budget() -> None:
    document = (ROOT / "docs/index.html").read_bytes()

    assert_dashboard_payload_within_budget(document)


@pytest.mark.parametrize("budget", ["homepage", "embedded-data"])
def test_dashboard_payload_budget_rejects_synthetic_overage(
    tmp_path: Path, budget: str
) -> None:
    if budget == "homepage":
        fixture = b'<script id="embedded-data"></script>' + b"x" * MAX_HOMEPAGE_BYTES
        maximum = MAX_HOMEPAGE_BYTES
    else:
        prefix = b'<script id="embedded-data">'
        suffix = b"</script>"
        fixture = prefix + b"x" * (MAX_EMBEDDED_DATA_BYTES - len(prefix) - len(suffix) + 1) + suffix
        maximum = MAX_EMBEDDED_DATA_BYTES
    fixture_path = tmp_path / "index.html"
    fixture_path.write_bytes(fixture)

    with pytest.raises(AssertionError, match=rf"actual|maximum|{maximum}"):
        assert_dashboard_payload_within_budget(fixture_path.read_bytes())


def test_dashboard_filter_container_is_populated_only_at_runtime() -> None:
    html = (ROOT / "docs/index.html").read_text(encoding="utf-8")
    parser = CategoryFilterParser()
    parser.feed(html)

    assert parser.buttons == []
    assert "function renderCategoryFilters(dashboardFilters)" in html
    assert "Object.entries" in html
    assert "renderCategoryFilters(DATA.dashboardFilters);" in html
    assert "Dashboard filters are unavailable" in html


def test_dashboard_renders_collapsible_sections_with_global_controls() -> None:
    html = (ROOT / "docs/index.html").read_text(encoding="utf-8")

    assert 'class="dashboard-sections"' in html
    assert 'id="toggle-all-sections"' in html
    assert 'class="category-filters status-filters"' in html
    assert 'class="dataset-grid"' not in html
    assert "function buildSection(section, index" in html
    assert 'make("button", "section-header")' in html
    assert 'body.hidden = index !== 0' in html
    assert "function applyFilters()" in html
    assert "DATA.dashboardSections" in html
    assert "Most-consumed on data.gov.my (views + downloads)" in html


def test_embedded_data_contract_includes_dashboard_sections() -> None:
    html = (ROOT / "docs/index.html").read_text(encoding="utf-8")

    assert "dashboardSections:" in html


def test_dashboard_distinguishes_signature_witness_and_source_truth() -> None:
    html = (ROOT / "docs/index.html").read_text(encoding="utf-8")

    assert 'addFact(facts, "Artifact signature"' in html
    assert 'addFact(facts, "Rekor witness"' in html
    assert 'addFact(facts, "Source truth"' in html
    assert "attestationVerification" in html
    assert 'addFact(facts, "Signed"' not in html
    assert "dataset.attestation_ref === signedRef" not in html


def test_hero_uses_the_canonical_ten_status_taxonomy() -> None:
    html = (ROOT / "docs/index.html").read_text(encoding="utf-8")
    hero_start = html.index('<div class="hero-stats"')
    hero_end = html.index("</div>\n    </section>", hero_start)
    hero = html[hero_start:hero_end]
    expected = [
        "datasets_total",
        "fresh",
        "aging",
        "stale",
        "discontinued",
        "degraded",
        "browser_dependent",
        "unreachable",
        "unknown",
        "unknown_freshness",
        "reference",
    ]

    positions = [hero.index(f'data-stat="{status}"') for status in expected]
    assert positions == sorted(positions)
    assert hero.index('id="hero-last-probed"') > positions[-1]


def test_release_build_generates_and_embeds_dashboard_data_before_deploy() -> None:
    generate = (ROOT / "scripts/generate.sh").read_text(encoding="utf-8")
    workflow = (ROOT / ".github/workflows/deploy-pages.yml").read_text(encoding="utf-8")

    sections = generate.index('"gen_dashboard_sections.py"')
    filters = generate.index('"gen_dashboard_filters.py"')
    injector = generate.index('"embed_dashboard_data.py"')
    assert sections < injector
    assert filters < injector
    assert "bash scripts/generate.sh release-build" in workflow
    assert "Inject embedded data" not in workflow


def test_dashboard_and_npra_facts_are_explicit_marker_owned() -> None:
    index = (ROOT / "docs/index.html").read_text(encoding="utf-8")
    npra = (ROOT / "docs/npra.html").read_text(encoding="utf-8")

    for marker in ("dashboard-summary", "dashboard-trust-facts", "dashboard-browser-facts", "changelog-strip"):
        assert f"<!-- BEGIN {marker} -->" in index
        assert f"<!-- END {marker} -->" in index
    for marker in ("npra-freshness", "npra-connect", "npra-surfaces"):
        assert f"<!-- BEGIN {marker} -->" in npra
        assert f"<!-- END {marker} -->" in npra
    generator = (ROOT / "scripts/embed_dashboard_data.py").read_text(encoding="utf-8")
    assert "DATASET_COUNT_PATTERNS" not in generator
    assert "_replace_dataset_counts" not in generator


def test_browser_fact_uses_canonical_summary_for_hyphenated_record_status() -> None:
    html = (
        "<!-- BEGIN dashboard-summary -->old<!-- END dashboard-summary -->"
        "<!-- BEGIN dashboard-trust-facts -->old<!-- END dashboard-trust-facts -->"
        "<!-- BEGIN dashboard-browser-facts -->old<!-- END dashboard-browser-facts -->"
    )
    manifest = {"datasets": [{"dataset_id": str(index)} for index in range(5)]}
    health = {
        "checked_at": "2026-08-24T00:00:00Z",
        "datasets": [{"dataset_id": "browser", "status": "browser-dependent"}],
        "_trust_summary": {
            "datasets_total": 5,
            "by_status": {"browser_dependent": 1},
        },
    }

    rendered = _dashboard_facts(html, manifest, health, "https://www.data-pulse.my")

    assert "1 of 5 datasets (20.0%)" in rendered


@pytest.mark.parametrize("browser_count", [True, -1, 6, "1"])
def test_browser_fact_rejects_malformed_canonical_summary(browser_count: object) -> None:
    html = (
        "<!-- BEGIN dashboard-summary -->old<!-- END dashboard-summary -->"
        "<!-- BEGIN dashboard-trust-facts -->old<!-- END dashboard-trust-facts -->"
        "<!-- BEGIN dashboard-browser-facts -->old<!-- END dashboard-browser-facts -->"
    )
    manifest = {"datasets": [{"dataset_id": str(index)} for index in range(5)]}
    health = {
        "checked_at": "2026-08-24T00:00:00Z",
        "datasets": [],
        "_trust_summary": {
            "datasets_total": 5,
            "by_status": {"browser_dependent": browser_count},
        },
    }

    with pytest.raises(EmbedError, match="browser_dependent"):
        _dashboard_facts(html, manifest, health, "https://www.data-pulse.my")


def test_marker_failure_preserves_all_dashboard_targets(tmp_path: Path) -> None:
    config = tmp_path / "config"
    config.mkdir()
    (config / "public-surfaces.json").write_text(json.dumps({
        "schema": "datapulse/v1/public-surfaces",
        "origins": {"website": "https://www.data-pulse.my", "mcp": "https://mcp.data-pulse.my", "api": "https://api.data-pulse.my", "repository": "https://github.com/r3dz4r/datapulse-my"},
        "pages": ["/", "/landing.html", "/npra.html", "/health-methodology.html"],
        "artifacts": ["/buyer-api-reference.md"], "featured_dataset_ids": ["alpha"],
    }) + "\n", encoding="utf-8")
    (config / "public-surfaces.schema.json").write_text(json.dumps({
        "properties": {"origins": {"required": ["website", "mcp", "api", "repository"], "properties": {key: {"const": value} for key, value in {"website": "https://www.data-pulse.my", "mcp": "https://mcp.data-pulse.my", "api": "https://api.data-pulse.my", "repository": "https://github.com/r3dz4r/datapulse-my"}.items()}, "additionalProperties": False}}, "additionalProperties": False,
    }) + "\n", encoding="utf-8")
    manifest = tmp_path / "datapulse.json"
    health = tmp_path / "health.json"
    manifest.write_text(json.dumps({"datasets": []}), encoding="utf-8")
    health.write_text(json.dumps({"checked_at": "2026-08-23T10:06:30Z", "datasets": [], "_trust_summary": {"datasets_total": 0}}), encoding="utf-8")
    filters, sections = tmp_path / "filters.json", tmp_path / "sections.json"
    filters.write_text("{}", encoding="utf-8")
    sections.write_text("{}", encoding="utf-8")
    index, npra = tmp_path / "index.html", tmp_path / "npra.html"
    index.write_text("<!-- BEGIN dashboard-summary -->\nold\n<!-- END dashboard-summary -->\n<!-- BEGIN dashboard-trust-facts -->\nold\n<!-- END dashboard-trust-facts -->\n<!-- BEGIN changelog-strip -->\nold\n<!-- END changelog-strip --><body></body>", encoding="utf-8")
    npra.write_text("<body><!-- BEGIN npra-freshness -->\nold\n<!-- END npra-freshness --></body>", encoding="utf-8")
    before = {path: path.read_bytes() for path in (index, npra)}

    with pytest.raises(EmbedError):
        embed_all((index, npra), manifest, health, filters, sections, None, None, tmp_path)

    assert {path: path.read_bytes() for path in (index, npra)} == before


def test_embed_preserves_canonical_jsonld_site_metadata(tmp_path: Path) -> None:
    """Embed regeneration must never rewrite the generator-owned JSON-LD block."""
    config = tmp_path / "config"
    config.mkdir()
    (config / "public-surfaces.json").write_text(json.dumps({
        "schema": "datapulse/v1/public-surfaces",
        "origins": {"website": "https://www.data-pulse.my", "mcp": "https://mcp.data-pulse.my", "api": "https://api.data-pulse.my", "repository": "https://github.com/r3dz4r/datapulse-my"},
        "pages": ["/", "/landing.html", "/npra.html", "/health-methodology.html"],
        "artifacts": ["/buyer-api-reference.md"], "featured_dataset_ids": ["alpha"],
    }) + "\n", encoding="utf-8")
    (config / "public-surfaces.schema.json").write_text(json.dumps({
        "properties": {"origins": {"required": ["website", "mcp", "api", "repository"], "properties": {key: {"const": value} for key, value in {"website": "https://www.data-pulse.my", "mcp": "https://mcp.data-pulse.my", "api": "https://api.data-pulse.my", "repository": "https://github.com/r3dz4r/datapulse-my"}.items()}, "additionalProperties": False}}, "additionalProperties": False,
    }) + "\n", encoding="utf-8")
    manifest = tmp_path / "datapulse.json"
    health = tmp_path / "health.json"
    manifest.write_text(json.dumps({"datasets": [{"id": "alpha"}]}), encoding="utf-8")
    health.write_text(json.dumps({
        "checked_at": "2026-08-23T10:06:30Z",
        "datasets": [{"dataset_id": "alpha", "status": "fresh"}],
        "_trust_summary": {"datasets_total": 1, "by_status": {"fresh": 1, "browser_dependent": 0}},
    }), encoding="utf-8")
    filters, sections = tmp_path / "filters.json", tmp_path / "sections.json"
    filters.write_text("{}", encoding="utf-8")
    sections.write_text("{}", encoding="utf-8")
    jsonld = (
        '  <script type="application/ld+json">\n'
        "{\n"
        '  "@context": "https://schema.org",\n'
        '  "@graph": [\n'
        '    {"@type": "Dataset", "@id": "https://www.data-pulse.my/#catalog", "url": "https://www.data-pulse.my/", "publisher": {"@id": "https://www.data-pulse.my/#org"}},\n'
        '    {"@type": "Organization", "@id": "https://www.data-pulse.my/#org", "url": "https://www.data-pulse.my/"},\n'
        '    {"@type": "WebSite", "@id": "https://www.data-pulse.my/#site", "url": "https://www.data-pulse.my/", "publisher": {"@id": "https://www.data-pulse.my/#org"}},\n'
        '    {"@type": "BreadcrumbList", "itemListElement": [{"@type": "ListItem", "position": 1, "name": "DataPulse MY", "item": "https://www.data-pulse.my/"}]}\n'
        "  ]\n"
        "}\n"
        "  </script>"
    )
    index = tmp_path / "index.html"
    index.write_text(
        "<head>\n"
        + jsonld
        + "\n</head><body>\n"
        "<!-- BEGIN dashboard-summary -->\nold\n<!-- END dashboard-summary -->\n"
        "<!-- BEGIN dashboard-trust-facts -->\nold\n<!-- END dashboard-trust-facts -->\n"
        "<!-- BEGIN dashboard-browser-facts -->\nold\n<!-- END dashboard-browser-facts -->\n"
        "<!-- BEGIN changelog-strip -->\nold\n<!-- END changelog-strip -->\n"
        "</body>",
        encoding="utf-8",
    )
    npra = tmp_path / "npra.html"
    npra.write_text(
        "<body><!-- BEGIN npra-freshness -->\nold\n<!-- END npra-freshness -->\n"
        "<!-- BEGIN npra-connect -->\nold\n<!-- END npra-connect -->\n"
        "<!-- BEGIN npra-surfaces -->\nold\n<!-- END npra-surfaces --></body>",
        encoding="utf-8",
    )

    embed_all((index, npra), manifest, health, filters, sections, None, None, tmp_path)

    rendered = index.read_text(encoding="utf-8")
    assert jsonld in rendered
    assert "https://data-pulse.my/" not in rendered
    assert "r3dz4r.github.io/datapulse-my" not in rendered
