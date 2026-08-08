#!/usr/bin/env python3
"""Regenerate the JSON-LD catalog and dashboard catalog graph."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = ROOT / "datapulse.json"
HEALTH_PATH = ROOT / "health/latest.json"
CATALOG_PATH = ROOT / "data/jsonld/catalog.json"
DASHBOARD_PATH = ROOT / "docs/index.html"
SCRIPT_OPEN = '  <script type="application/ld+json">\n'
SCRIPT_CLOSE = "\n  </script>"
BASE_URL = "https://data-pulse.my"


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def dataset_object(entry: dict, health: dict) -> dict:
    report_url = f"{BASE_URL}/{entry['health_report']}"
    record_count = health.get("record_count")
    return {
        "@context": "https://schema.org",
        "@type": "Dataset",
        "@id": report_url,
        "name": entry["name"],
        "description": (
            f"Malaysian public dataset: {entry['name']}. "
            f"Steward: {entry['steward']}. Source: {entry['source']}."
        ),
        "url": report_url,
        "sameAs": entry["url"],
        "identifier": entry["id"],
        "keywords": [entry["source"], entry["steward"], "Malaysia", "open data"],
        "creator": {"@type": "Organization", "name": entry["steward"]},
        "publisher": {
            "@type": "Organization",
            "@id": f"{BASE_URL}/#org",
            "name": "DataPulse MY",
        },
        "spatialCoverage": {"@type": "Place", "name": entry["geo_coverage"]},
        "license": entry["licence"],
        "isAccessibleForFree": True,
        "distribution": [
            {
                "@type": "DataDownload",
                "encodingFormat": "text/markdown",
                "contentUrl": report_url,
                "name": f"DataPulse MY health record for {entry['name']}",
            }
        ],
        "measurementTechnique": "Continuous HTTP + content-shape probing by DataPulse MY",
        "dateModified": entry.get("verified_at") or health.get("checked_at", "")[:10],
        "variableMeasured": [
            {
                "@type": "PropertyValue",
                "name": "freshness",
                "value": health.get("status", "unknown"),
            },
            {
                "@type": "PropertyValue",
                "name": "record_count",
                "value": record_count,
            },
        ],
    }


def dashboard_part(dataset: dict) -> dict:
    return {
        "@type": "Dataset",
        "@id": dataset["@id"],
        "name": dataset["name"],
        "url": dataset["url"],
        "creator": dataset["creator"],
        "license": dataset["license"],
        "identifier": dataset["identifier"],
    }


def main() -> None:
    manifest = read_json(MANIFEST_PATH)
    health = read_json(HEALTH_PATH)
    health_by_id = {row["dataset_id"]: row for row in health["datasets"]}
    datasets = [
        dataset_object(entry, health_by_id.get(entry["id"], {}))
        for entry in manifest["datasets"]
    ]

    CATALOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    for dataset in datasets:
        dataset_path = CATALOG_PATH.parent / f"{dataset['identifier']}.json"
        dataset_path.write_text(
            json.dumps(dataset, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    catalog = {
        "@context": "https://schema.org",
        "@type": "DatasetCatalog",
        "@id": f"{BASE_URL}/data/jsonld/catalog.json",
        "name": "DataPulse MY — All Datasets (JSON-LD)",
        "url": f"{BASE_URL}/data/jsonld/catalog.json",
        "dataset": datasets,
    }
    CATALOG_PATH.write_text(
        json.dumps(catalog, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    dashboard = DASHBOARD_PATH.read_text(encoding="utf-8")
    start = dashboard.index(SCRIPT_OPEN) + len(SCRIPT_OPEN)
    end = dashboard.index(SCRIPT_CLOSE, start)
    graph = json.loads(dashboard[start:end])
    catalog_node = graph["@graph"][0]
    catalog_node["hasPart"] = [dashboard_part(dataset) for dataset in datasets]
    replacement = json.dumps(graph, ensure_ascii=False, indent=2)
    DASHBOARD_PATH.write_text(
        dashboard[:start] + replacement + dashboard[end:], encoding="utf-8"
    )

    print(
        f"Generated {len(datasets)} per-dataset, catalog, and dashboard JSON-LD objects"
    )


if __name__ == "__main__":
    main()
