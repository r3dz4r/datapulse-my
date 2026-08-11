import json
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from scripts.tests.generator_harness import (
    GeneratorRun,
    run_generator,
    run_generator_twice,
)


ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "scripts/tests/fixtures/generator/shell"
GENERATORS = {
    "badges": ROOT / "scripts/gen_badges.sh",
    "legend": ROOT / "scripts/gen_status_legend.sh",
    "readme": ROOT / "scripts/gen_readme_summary.sh",
    "rss": ROOT / "scripts/gen_rss.sh",
}
BASE_INPUTS = ["datapulse.json", "health/latest.json", "README.md", "badges"]
EXPECTED_OUTPUTS = {
    "badges": [
        "badges/alpha.svg",
        "badges/beta.svg",
        "badges/status-fresh.svg",
        "badges/status-stale.svg",
    ],
    "legend": ["badges/status-fresh.svg", "badges/status-stale.svg"],
    "readme": ["README.md"],
    "rss": ["feed.xml"],
}
STATUSES = (
    "fresh",
    "aging",
    "stale",
    "degraded",
    "browser-dependent",
    "unreachable",
    "unknown",
    "unknown-freshness",
    "reference",
)


def _stage_fixture(tmp_path: Path) -> Path:
    source = tmp_path / "source"
    for relative in ("datapulse.json", "health/latest.json", "README.md"):
        destination = source / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes((FIXTURE / relative).read_bytes())
    (source / "badges").mkdir()
    scripts = source / "scripts"
    scripts.mkdir()
    staged_legend = scripts / "gen_status_legend.sh"
    staged_legend.write_bytes(GENERATORS["legend"].read_bytes())
    staged_legend.chmod(GENERATORS["legend"].stat().st_mode)
    return source


def _run(
    source: Path,
    name: str,
    *,
    expected_outputs: list[str] | None = None,
) -> GeneratorRun:
    inputs = list(BASE_INPUTS)
    if name == "badges":
        inputs.append("scripts/gen_status_legend.sh")
    return run_generator(
        source,
        GENERATORS[name],
        inputs,
        expected_outputs or EXPECTED_OUTPUTS[name],
    )


def _write_json(path: Path, document: dict) -> None:
    path.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")


def test_gen_badges_produces_svg_per_id(tmp_path: Path) -> None:
    result = _run(_stage_fixture(tmp_path), "badges")

    assert result.returncode == 0, result.stderr
    for dataset_id in ("alpha", "beta"):
        relative = f"badges/{dataset_id}.svg"
        badge = result.outputs[relative]
        assert badge is not None
        assert badge.startswith(b"<svg")
        # Dataset identity is encoded in the per-ID output filename; the SVG label
        # itself intentionally displays that dataset's health status.
        assert dataset_id in relative


def test_gen_status_legend_lists_all_configured_statuses(tmp_path: Path) -> None:
    source = _stage_fixture(tmp_path)
    health_path = source / "health/latest.json"
    health = json.loads(health_path.read_text(encoding="utf-8"))
    health["_trust_summary"] = {
        "datasets_total": len(STATUSES),
        "by_status": {status.replace("-", "_"): 1 for status in STATUSES},
    }
    _write_json(health_path, health)
    outputs = [f"badges/status-{status}.svg" for status in STATUSES]

    result = _run(source, "legend", expected_outputs=outputs)

    assert result.returncode == 0, result.stderr
    for status in STATUSES:
        badge = result.outputs[f"badges/status-{status}.svg"]
        assert badge is not None
        assert status.encode() in badge


def test_gen_readme_summary_replaces_marker(tmp_path: Path) -> None:
    result = _run(_stage_fixture(tmp_path), "readme")

    assert result.returncode == 0, result.stderr
    readme = result.outputs["README.md"]
    assert readme is not None
    text = readme.decode()
    assert "placeholder" not in text
    assert "Current distribution (`_trust_summary`):" in text
    assert "[1 fresh]" in text
    assert "[1 stale]" in text
    assert "2 official datasets" in text
    assert "2-dataset catalogue" in text
    assert "42" not in text


def test_gen_rss_produces_valid_xml(tmp_path: Path) -> None:
    result = _run(_stage_fixture(tmp_path), "rss")

    assert result.returncode == 0, result.stderr
    feed = result.outputs["feed.xml"]
    assert feed is not None
    root = ET.fromstring(feed)
    assert root.tag == "rss"
    items = root.findall("./channel/item")
    assert len(items) == 2
    item_text = ET.tostring(root, encoding="unicode")
    assert "alpha" in item_text
    assert "beta" in item_text


def test_zero_count_status_badge_is_refreshed(tmp_path: Path) -> None:
    source = _stage_fixture(tmp_path)
    health_path = source / "health/latest.json"
    health = json.loads(health_path.read_text(encoding="utf-8"))
    health["_trust_summary"]["by_status"] = {
        "fresh": 1,
        "aging": 0,
        "stale": 1,
    }
    _write_json(health_path, health)
    (source / "badges/status-aging.svg").write_text("stale output\n", encoding="utf-8")

    result = _run(
        source,
        "legend",
        expected_outputs=[
            "badges/status-fresh.svg",
            "badges/status-aging.svg",
            "badges/status-stale.svg",
        ],
    )

    assert result.returncode == 0, result.stderr
    aging_badge = result.outputs["badges/status-aging.svg"]
    assert aging_badge is not None
    assert b"aging: 0" in aging_badge
    assert result.outputs["badges/status-fresh.svg"] is not None
    assert result.outputs["badges/status-stale.svg"] is not None


def test_xml_html_escaping_in_rss(tmp_path: Path) -> None:
    source = _stage_fixture(tmp_path)
    manifest_path = source / "datapulse.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    payload = "<script>alert(1)</script> & public data"
    manifest["datasets"][0]["title"] = payload
    manifest["datasets"][0]["name"] = payload
    _write_json(manifest_path, manifest)

    result = _run(source, "rss")

    assert result.returncode == 0, result.stderr
    feed = result.outputs["feed.xml"]
    assert feed is not None
    text = feed.decode()
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in text
    assert "&amp; public data" in text
    assert "<script>" not in text
    ET.fromstring(feed)


def test_badge_output_is_valid_svg(tmp_path: Path) -> None:
    result = _run(_stage_fixture(tmp_path), "badges")

    assert result.returncode == 0, result.stderr
    for dataset_id in ("alpha", "beta"):
        relative = f"badges/{dataset_id}.svg"
        badge = result.outputs[relative]
        assert badge is not None
        root = ET.fromstring(badge)
        assert root.tag == "{http://www.w3.org/2000/svg}svg"
        assert dataset_id in relative


def test_readme_summary_marker_missing_fails(tmp_path: Path) -> None:
    source = _stage_fixture(tmp_path)
    (source / "README.md").write_text(
        "# README without a trust summary marker\n", encoding="utf-8"
    )

    result = _run(source, "readme")

    assert result.returncode != 0
    assert "Could not replace trust summary block" in result.stderr


@pytest.mark.parametrize("name", tuple(GENERATORS))
def test_deterministic_second_run_for_all_generators(
    tmp_path: Path, name: str
) -> None:
    source = _stage_fixture(tmp_path)
    inputs = list(BASE_INPUTS)
    if name == "badges":
        inputs.append("scripts/gen_status_legend.sh")

    first, second, diff = run_generator_twice(
        source,
        GENERATORS[name],
        inputs,
        EXPECTED_OUTPUTS[name],
    )

    assert first.returncode == second.returncode == 0
    assert all(diff[path] is True for path in EXPECTED_OUTPUTS[name])


def test_does_not_touch_tracked_workspace(tmp_path: Path) -> None:
    command = ["git", "status", "--short", "README.md", "feed.xml", "badges/"]
    status_before = subprocess.run(
        command, cwd=ROOT, capture_output=True, text=True, check=True
    ).stdout

    for name in GENERATORS:
        result = _run(_stage_fixture(tmp_path / name), name)
        assert result.returncode == 0, result.stderr

    status_after = subprocess.run(
        command, cwd=ROOT, capture_output=True, text=True, check=True
    ).stdout
    assert status_after == status_before
