#!/usr/bin/env python3
"""Regenerate the JSON-LD catalog and dashboard catalog graph."""

from __future__ import annotations

import json
from pathlib import Path

from public_surface_generation import load_public_surfaces


ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = ROOT / "datapulse.json"
HEALTH_PATH = ROOT / "health/latest.json"
CATALOG_PATH = ROOT / "data/jsonld/catalog.json"
DASHBOARD_PATH = ROOT / "docs/index.html"
SCRIPT_OPEN = '  <script type="application/ld+json">\n'
SCRIPT_CLOSE = "\n  </script>"


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def publisher_reference(base_url: str) -> dict:
    return {
        "@type": "Organization",
        "@id": f"{base_url}/#org",
        "name": "DataPulse MY",
    }


def dataset_object(entry: dict, health: dict, *, base_url: str) -> dict:
    report_url = f"{base_url}/{entry['health_report']}"
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
        "publisher": publisher_reference(base_url),
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


def site_metadata_graph(base_url: str, mcp_url: str, repository_url: str) -> list[dict]:
    """Rebuild the dashboard Organization/WebSite/BreadcrumbList nodes on every run.

    Owning these nodes outright (instead of editing static bytes in
    docs/index.html) is what stops a later deterministic regeneration from
    republishing a stale apex or GitHub Pages host as the site identity.
    """
    return [
        {
            "@type": "Organization",
            "@id": f"{base_url}/#org",
            "name": "DataPulse MY",
            "alternateName": "DataPulse Malaysia",
            "url": f"{base_url}/",
            "logo": "https://raw.githubusercontent.com/r3dz4r/datapulse-my/main/docs/images/ce/logo_dark.svg",
            "description": "Open-source trust layer for Malaysian public data.",
            "foundingDate": "2026",
            "areaServed": {"@type": "Country", "name": "Malaysia"},
            "knowsAbout": [
                "Malaysian public data",
                "data.gov.my",
                "Open Government Licence (Malaysia)",
                "DOSM",
                "BNM",
                "DOE",
                "KKM",
                "KPDN",
                "MET Malaysia",
                "data quality monitoring",
            ],
            "sameAs": [repository_url],
        },
        {
            "@type": "WebSite",
            "@id": f"{base_url}/#site",
            "name": "DataPulse MY",
            "url": f"{base_url}/",
            "inLanguage": ["en", "ms"],
            "publisher": {"@id": f"{base_url}/#org"},
            "potentialAction": {
                "@type": "SearchAction",
                "target": {"@type": "EntryPoint", "urlTemplate": f"{mcp_url}/mcp"},
                "query-input": "required name=query",
            },
        },
        {
            "@type": "BreadcrumbList",
            "itemListElement": [
                {
                    "@type": "ListItem",
                    "position": 1,
                    "name": "DataPulse MY",
                    "item": f"{base_url}/",
                }
            ],
        },
    ]


def main() -> None:
    manifest = read_json(MANIFEST_PATH)
    origins = load_public_surfaces(ROOT)["origins"]
    base_url = origins["website"]
    health = read_json(HEALTH_PATH)
    health_by_id = {row["dataset_id"]: row for row in health["datasets"]}
    datasets = [
        dataset_object(entry, health_by_id.get(entry["id"], {}), base_url=base_url)
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
        "@id": f"{base_url}/data/jsonld/catalog.json",
        "name": "DataPulse MY — All Datasets (JSON-LD)",
        "url": f"{base_url}/data/jsonld/catalog.json",
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
    catalog_node["@id"] = f"{base_url}/#catalog"
    catalog_node["url"] = f"{base_url}/"
    catalog_node["sameAs"] = origins["repository"]
    catalog_node["license"] = f"{origins['repository']}/blob/main/LICENSE"
    catalog_node["publisher"] = publisher_reference(base_url)
    distributions = catalog_node.get("distribution")
    if distributions is not None:
        paths = ("/datapulse.json", "/health/latest.json", "/llms.txt")
        if (
            not isinstance(distributions, list)
            or len(distributions) != len(paths)
            or not all(isinstance(item, dict) for item in distributions)
        ):
            raise ValueError("dashboard catalog graph must contain the three canonical distributions")
        for distribution, path in zip(distributions, paths, strict=True):
            distribution["contentUrl"] = f"{base_url}{path}"
    catalog_node["hasPart"] = [dashboard_part(dataset) for dataset in datasets]
    graph["@graph"] = [
        catalog_node,
        *site_metadata_graph(base_url, origins["mcp"], origins["repository"]),
    ]
    replacement = json.dumps(graph, ensure_ascii=False, indent=2)
    DASHBOARD_PATH.write_text(
        dashboard[:start] + replacement + dashboard[end:], encoding="utf-8"
    )

    print(
        f"Generated {len(datasets)} per-dataset, catalog, and dashboard JSON-LD objects"
    )


if __name__ == "__main__":
    main()
