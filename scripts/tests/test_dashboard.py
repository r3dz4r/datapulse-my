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


def test_deploy_workflow_generates_and_embeds_dashboard_filters() -> None:
    workflow = (ROOT / ".github/workflows/deploy-pages.yml").read_text(encoding="utf-8")

    generator = workflow.index("python3 scripts/gen_dashboard_filters.py")
    injector = workflow.index("python3 - <<'PY'", generator)
    assert generator < injector
    assert "dashboardFilters" in workflow
    assert 'open("docs/.dashboard_filters.json"' in workflow
