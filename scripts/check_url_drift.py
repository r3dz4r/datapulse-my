#!/usr/bin/env python3
"""Check that published dataset URLs and cadence metadata form one invariant."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

ALLOWED_FREQUENCIES = {
    "30 seconds", "hourly", "daily", "weekly", "monthly", "quarterly",
    "annual", "as-required", "biennial to triennial (survey years)",
    "daily (weekdays)", "daily (weekdays, 0900 MYT)",
    "daily (weekdays, 1130 MYT)", "daily (weekdays, 1200 MYT)",
    "daily (weekdays, 1700 MYT)",
}
EXPECTED_CADENCE_DAYS = {
    "30 seconds": 0.001, "hourly": 1 / 24, "daily": 1, "weekly": 7,
    "monthly": 30, "quarterly": 90, "annual": 365,
}
GTFS_PREFIX = "gtfs_"


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def embedded_manifest(html: str) -> list[dict[str, Any]]:
    match = re.search(r"window\.__DATAPULSE_DATA__\s*=\s*\{.*?manifest:\s*", html, re.S)
    if not match:
        raise ValueError("dashboard has no embedded manifest")
    value, _ = json.JSONDecoder().raw_decode(html, match.end())
    rows = value.get("datasets") if isinstance(value, dict) else None
    if not isinstance(rows, list):
        raise ValueError("embedded dashboard manifest has no datasets array")
    return [row for row in rows if isinstance(row, dict)]


def url(row: Any, *keys: str) -> str | None:
    if not isinstance(row, dict):
        return None
    for key in keys:
        value = row.get(key)
        if isinstance(value, str) and value:
            return value
    return None


def compare_urls(sources: dict[str, dict[str, str | None]]) -> list[str]:
    discrepancies = []
    for dataset_id, values in sources.items():
        present = {name: value for name, value in values.items() if value is not None}
        missing = [name for name in values if values[name] is None]
        distinct = set(present.values())
        if missing:
            discrepancies.append(f"{dataset_id}: missing {', '.join(missing)}")
        if len(distinct) > 1:
            details = ", ".join(f"{name}={value}" for name, value in present.items())
            discrepancies.append(f"{dataset_id}: URL mismatch ({details})")
    return discrepancies


def audit(root: Path) -> tuple[list[str], list[str], list[str]]:
    manifest = read_json(root / "datapulse.json")["datasets"]
    health = {row["dataset_id"]: row for row in read_json(root / "health/latest.json")["datasets"]}
    policy = read_json(root / "scripts/probe-policy.json")["datasets"]
    if not isinstance(policy, dict) or not all(isinstance(settings, dict) for settings in policy.values()):
        raise ValueError("probe policy must contain dataset settings")
    dynamic_ids = {dataset_id for dataset_id, settings in policy.items() if "dynamic-url" in settings}
    # The homepage register is rendered from the canonical manifest; its inline
    # payload is intentionally limited to one dataset and cannot be this audit's
    # catalogue-wide source of truth.
    dashboard = {row["id"]: row for row in manifest}
    envelopes = {}
    for path in (root / "data/json").glob("*.json"):
        row = read_json(path)
        if isinstance(row, dict) and isinstance(row.get("id"), str):
            envelopes[row["id"]] = row
    jsonld = {}
    for path in (root / "data/jsonld").glob("*.json"):
        if path.name == "catalog.json":
            continue
        row = read_json(path)
        if isinstance(row, dict) and isinstance(row.get("identifier"), str):
            jsonld[row["identifier"]] = row

    sources = {}
    cadence = []
    availability = []
    dynamic_count = 0
    for entry in manifest:
        dataset_id = entry["id"]
        sources[dataset_id] = {
            "manifest": url(entry, "url"),
            "health": url(health.get(dataset_id), "url", "request_url"),
            "dashboard": url(dashboard.get(dataset_id), "url"),
            "json envelope": url(envelopes.get(dataset_id, {}).get("reproducibility"), "url"),
            "JSON-LD": url(jsonld.get(dataset_id), "sameAs"),
        }
        if dataset_id.startswith(GTFS_PREFIX):
            sources[dataset_id].pop("json envelope")
        if dataset_id in dynamic_ids:
            dynamic_count += 1
            sources[dataset_id]["observed request"] = url(health.get(dataset_id), "request_url")
            status = health.get(dataset_id, {}).get("http_status")
            if type(status) is not int or not 200 <= status < 300:
                availability.append(f"{dataset_id}: observed URL has no confirmed HTTP 2xx (status={status!r})")
        frequency = entry.get("refresh_frequency")
        if frequency not in ALLOWED_FREQUENCIES:
            cadence.append(f"{dataset_id}: unsupported refresh_frequency={frequency!r}")
        expected = EXPECTED_CADENCE_DAYS.get(frequency)
        observed = health.get(dataset_id, {}).get("staleness_days")
        if expected is not None and isinstance(observed, (int, float)) and observed > 2 * expected:
            cadence.append(f"{dataset_id}: {frequency} cadence, staleness {observed:g}d")

    html = (root / "docs/index.html").read_text(encoding="utf-8")
    if 'dataset.refresh_frequency ? `On its ${dataset.refresh_frequency} cadence`' not in html:
        cadence.append("dashboard: Next expected update is not derived from dataset.refresh_frequency")
    discrepancies = compare_urls(sources)
    if dynamic_count and len(availability) == dynamic_count:
        discrepancies.append(
            "probe found no confirmed HTTP 2xx anywhere across dynamic datasets; "
            "our probe or our network is broken"
        )
    return discrepancies, cadence, availability


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    try:
        discrepancies, cadence, availability = audit(args.root.resolve())
    except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
        print(f"URL drift audit error: {error}", file=sys.stderr)
        return 2
    print(f"Availability: {len(availability)} upstream findings", file=sys.stderr)
    for item in availability:
        print(f"  AVAILABILITY {item}", file=sys.stderr)
    print(f"URL drift: {len(discrepancies)} discrepancies")
    for item in discrepancies:
        print(f"  ERROR {item}")
    print(f"Cadence: {len(cadence)} informational findings")
    for item in cadence[:20]:
        print(f"  INFO {item}")
    if len(cadence) > 20:
        print(f"  INFO ... {len(cadence) - 20} more")
    return 1 if discrepancies else 0


if __name__ == "__main__":
    raise SystemExit(main())
