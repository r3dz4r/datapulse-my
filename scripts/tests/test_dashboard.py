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

# The source-owned register adds 389 accessible, server-rendered rows while
# retaining the legacy embedded payload for machine consumers.
# Ceilings were originally temporary headroom ('revise deliberately'); the
# register source-owned row + embedded machine-payload growth (register Slice A)
# legitimately exceeded the initial 1.9MB / ~1.0MB values, so revise upward to
# reflect the deliberately-grown register. Revisit if the page grows further.
MAX_HOMEPAGE_BYTES = 2_000_000
MAX_EMBEDDED_DATA_BYTES = 1_100_000
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


def test_register_search_and_filter_controls_are_present_without_network_fetch() -> None:
    html = (ROOT / "docs/index.html").read_text(encoding="utf-8")
    assert 'for="register-search"' in html
    assert 'data-register-search' in html
    assert 'data-register-filters' in html
    for dimension in ("status", "publisher", "category", "recency"):
        assert f'id="register-filter-{dimension}"' in html
    assert 'data-register-empty' in html
    assert 'data-register-reset' in html
    assert "filters.every" in html
    assert "filter.addEventListener('change', apply)" in html
    assert "reset?.addEventListener('click'" in html
    assert 'fetch(' not in html


def test_register_embedded_payload_precedes_its_reader_and_keeps_shared_shell_contracts() -> None:
    html = (ROOT / "docs/index.html").read_text(encoding="utf-8")
    embedded = html.index('<script id="embedded-data">')
    reader = html.index("window.__DATAPULSE_DATA__")

    assert embedded < reader
    assert html.count('<link rel="stylesheet" href="/assets/datapulse.css">') == 1
    assert html.count("<!-- BEGIN SITE-NAV (generated from assets/site-nav.html) -->") == 1
    assert '<nav class="site-nav"' in html


def test_homepage_renders_the_compact_register_instead_of_dashboard_sections() -> None:
    html = (ROOT / "docs/index.html").read_text(encoding="utf-8")

    assert 'class="register-list"' in html
    assert html.count('class="register-row"') == 389
    assert '<details class="register-evidence">' in html
    assert 'class="dashboard-sections"' not in html


def test_embedded_data_contract_includes_dashboard_sections() -> None:
    html = (ROOT / "docs/index.html").read_text(encoding="utf-8")

    assert "dashboardSections:" in html


def test_homepage_retains_fail_closed_attestation_verification_payload() -> None:
    html = (ROOT / "docs/index.html").read_text(encoding="utf-8")

    assert "attestationVerification" in html
    assert '"artifact_signed":false' in html
    assert '"source_truth_verified":false' in html


def test_register_labels_the_canonical_ten_status_taxonomy() -> None:
    html = (ROOT / "docs/index.html").read_text(encoding="utf-8")
    expected = [
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

    positions = [html.index(f"Status: {status.replace('_', '-')}") for status in expected]
    assert positions == sorted(positions)


def test_release_build_generates_and_embeds_dashboard_data_before_deploy() -> None:
    generate = (ROOT / "scripts/generate.sh").read_text(encoding="utf-8")
    workflow = (ROOT / ".github/workflows/deploy-cloudflare-pages.yml").read_text(encoding="utf-8")

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

    for marker in ("dashboard-summary", "dashboard-trust-facts", "changelog-strip"):
        assert f"<!-- BEGIN {marker} -->" in index
        assert f"<!-- END {marker} -->" in index
    for marker in ("npra-freshness", "npra-connect", "npra-surfaces"):
        assert f"<!-- BEGIN {marker} -->" in npra
        assert f"<!-- END {marker} -->" in npra
    generator = (ROOT / "scripts/embed_dashboard_data.py").read_text(encoding="utf-8")
    assert "DATASET_COUNT_PATTERNS" not in generator
    assert "_replace_dataset_counts" not in generator


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
