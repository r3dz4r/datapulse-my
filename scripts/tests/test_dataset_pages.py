from __future__ import annotations

import json
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

from scripts.gen_dataset_pages import generate


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/gen_dataset_pages.py"


def _stage(root: Path, *, synthetic: bool = False) -> None:
    (root / "config").mkdir()
    for name in ("public-surfaces.json", "public-surfaces.schema.json"):
        shutil.copyfile(ROOT / "config" / name, root / "config" / name)
    if synthetic:
        (root / "health").mkdir()
        (root / "datapulse.json").write_text(json.dumps({"datasets": [
            {"id": "present", "name": "Present data", "url": "https://example.org/present"},
            {"id": "missing", "name": "Missing data", "url": "https://example.org/missing"},
        ]}))
        (root / "health/latest.json").write_text(json.dumps({"checked_at": "2026-10-02T00:00:00Z", "datasets": [
            {"dataset_id": "present", "status": "fresh", "content_freshness_date": "2026-10-01"}
        ]}))
    else:
        shutil.copyfile(ROOT / "datapulse.json", root / "datapulse.json")
        (root / "health").mkdir()
        shutil.copyfile(ROOT / "health/latest.json", root / "health/latest.json")


def test_all_manifest_datasets_have_deterministic_published_pages(tmp_path: Path) -> None:
    _stage(tmp_path)
    count = generate(tmp_path)
    manifest = json.loads((tmp_path / "datapulse.json").read_text())["datasets"]
    health = {row["dataset_id"]: row for row in json.loads((tmp_path / "health/latest.json").read_text())["datasets"]}
    pages = list((tmp_path / "docs/datasets").glob("*.html"))
    sitemap = ET.parse(ROOT / "sitemap.xml")
    locations = {
        node.text
        for node in sitemap.findall("{http://www.sitemaps.org/schemas/sitemap/0.9}url/{http://www.sitemaps.org/schemas/sitemap/0.9}loc")
    }
    assert count == len(manifest) == len(pages)
    first = {path.name: path.read_bytes() for path in pages}
    for row in manifest:
        page = first[f'{row["id"]}.html'].decode()
        assert row["id"] in page
        assert f'>{health[row["id"]]["status"]} <small>' in page
        canonical = f'https://www.data-pulse.my/datasets/{row["id"]}'
        assert f'<link rel="canonical" href="{canonical}">' in page
        assert canonical in locations
        assert ".html" not in canonical
    assert generate(tmp_path) == count
    assert first == {path.name: path.read_bytes() for path in pages}


def test_pages_depend_only_on_their_dataset_facts(tmp_path: Path) -> None:
    _stage(tmp_path, synthetic=True)
    assert generate(tmp_path) == 2
    page_dir = tmp_path / "docs/datasets"
    first = {path.name: path.read_bytes() for path in page_dir.glob("*.html")}

    snapshot_path = tmp_path / "health/latest.json"
    snapshot = json.loads(snapshot_path.read_text())
    snapshot["checked_at"] = "2026-10-03T00:00:00Z"
    snapshot["_trust_summary"] = {"changed": True}
    snapshot_path.write_text(json.dumps(snapshot))
    assert generate(tmp_path) == 2
    after_snapshot = {path.name: path.read_bytes() for path in page_dir.glob("*.html")}
    assert after_snapshot == first

    snapshot["datasets"][0]["status"] = "stale"
    snapshot_path.write_text(json.dumps(snapshot))
    assert generate(tmp_path) == 2
    after_dataset = {path.name: path.read_bytes() for path in page_dir.glob("*.html")}
    assert {name for name in first if after_dataset[name] != first[name]} == {"present.html"}


def test_missing_health_row_and_check_mode(tmp_path: Path) -> None:
    _stage(tmp_path, synthetic=True)
    assert generate(tmp_path) == 2
    missing = tmp_path / "docs/datasets/missing.html"
    text = missing.read_text()
    assert '>unknown <small>(health/latest.json: no row for this dataset)' in text
    assert 'health/latest.json snapshot has no row for this dataset.' in text
    assert 'No content date was published' in text
    clean = subprocess.run([sys.executable, str(SCRIPT), "--root", str(tmp_path), "--check"], capture_output=True, text=True)
    assert clean.returncode == 0, clean.stderr
    missing.write_text(text + "mutated\n")
    stale = subprocess.run([sys.executable, str(SCRIPT), "--root", str(tmp_path), "--check"], capture_output=True, text=True)
    assert stale.returncode != 0
    assert str(missing) in stale.stderr
