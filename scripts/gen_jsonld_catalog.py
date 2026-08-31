#!/usr/bin/env python3
"""Regenerate the JSON-LD catalog and dashboard catalog graph."""

from __future__ import annotations

import json
from pathlib import Path

try:
    from scripts.public_surface_generation import load_public_surfaces
except ModuleNotFoundError:  # Direct script execution puts scripts/ on sys.path.
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


def script_safe_json(document: object) -> str:
    """Serialize JSON-LD safely for text inside an HTML script element."""
    return json.dumps(document, ensure_ascii=False, indent=2).replace("<", "\\u003c")


def publisher_reference(base_url: str) -> dict:
    return {
        "@type": "Organization",
        "@id": f"{base_url}/#org",
        "name": "DataPulse",
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
                "name": f"DataPulse health record for {entry['name']}",
            }
        ],
        "measurementTechnique": "Continuous HTTP + content-shape probing by DataPulse",
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
            "name": "DataPulse",
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
            "name": "DataPulse",
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
                    "name": "DataPulse",
                    "item": f"{base_url}/",
                }
            ],
        },
    ]


def homepage_graph(manifest: dict, origins: dict[str, str]) -> dict:
    """Build the canonical, deterministic homepage JSON-LD graph."""
    datasets = manifest.get("datasets")
    if not isinstance(datasets, list):
        raise ValueError("manifest datasets must be an array")
    base_url = origins["website"]
    catalog = {
        "@type": "Dataset",
        "@id": f"{base_url}/#catalog",
        "name": "DataPulse Dataset Catalog",
        "description": f"Open trust layer for Malaysian public data. {len(datasets)} official datasets with continuous health monitoring and licence/attribution metadata.",
        "url": f"{base_url}/",
        "sameAs": origins["repository"],
        "identifier": "datapulse-my-catalog-v1",
        "spatialCoverage": {"@type": "Place", "name": "Malaysia"},
        "publisher": publisher_reference(base_url),
        "creator": {"@type": "Organization", "name": "Multiple Malaysian government agencies", "url": "https://data.gov.my"},
        "license": f"{origins['repository']}/blob/main/LICENSE",
        "isAccessibleForFree": True,
        "distribution": [
            {"@type": "DataDownload", "encodingFormat": "application/json", "contentUrl": f"{base_url}/datapulse.json", "name": "Machine-readable dataset manifest"},
            {"@type": "DataDownload", "encodingFormat": "application/json", "contentUrl": f"{base_url}/health/latest.json", "name": "Current health signals for all tracked datasets"},
            {"@type": "DataDownload", "encodingFormat": "text/markdown", "contentUrl": f"{base_url}/llms.txt", "name": "LLM agent index"},
        ],
        "hasPart": [dashboard_part(dataset_object(entry, {}, base_url=base_url)) for entry in datasets],
    }
    return {"@context": "https://schema.org", "@graph": [catalog, *site_metadata_graph(base_url, origins["mcp"], origins["repository"])]}


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
        "name": "DataPulse — All Datasets (JSON-LD)",
        "url": f"{base_url}/data/jsonld/catalog.json",
        "dataset": datasets,
    }
    CATALOG_PATH.write_text(
        json.dumps(catalog, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    dashboard = DASHBOARD_PATH.read_text(encoding="utf-8")
    try:
        start = dashboard.index(SCRIPT_OPEN) + len(SCRIPT_OPEN)
        end = dashboard.index(SCRIPT_CLOSE, start)
    except ValueError as error:
        raise ValueError("docs/index.html is missing the canonical JSON-LD slot") from error
    replacement = script_safe_json(homepage_graph(manifest, origins))
    DASHBOARD_PATH.write_text(
        dashboard[:start] + replacement + dashboard[end:], encoding="utf-8"
    )

    print(
        f"Generated {len(datasets)} per-dataset, catalog, and dashboard JSON-LD objects"
    )


if __name__ == "__main__":
    main()
