import json
import subprocess
import sys
from collections import Counter
from html.parser import HTMLParser
from pathlib import Path


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
