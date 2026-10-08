"""Catalogue contract for the three tabular MECo electoral-map sources."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
REPO = "https://github.com/Thevesh/paper-meco-maps"
RAW_BASE = "https://raw.githubusercontent.com/Thevesh/paper-meco-maps/main/data/"
DATASETS = {
    "meco_delimitation_to_elections": (
        "delims_to_elections.csv", 6338, 210,
        ["state", "year", "election", "peninsular", "sabah", "sarawak"],
    ),
    "meco_cartogram_equal_k": (
        "cartogram_equal_k.csv", 3852, 208,
        ["state", "election_name", "seat_type", "k"],
    ),
    "meco_cartogram_electorate_k": (
        "cartogram_electorate_k.csv", 3846, 207,
        ["state", "election_name", "seat_type", "k"],
    ),
}


def _json(path: str) -> dict:
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def test_exactly_three_tabular_maps_sources_are_registered() -> None:
    rows = {row["id"]: row for row in _json("datapulse.json")["datasets"]}
    maps_rows = {dataset_id: row for dataset_id, row in rows.items() if row["source"] == REPO}
    assert set(maps_rows) == set(DATASETS)
    assert {row["url"].removeprefix(RAW_BASE) for row in maps_rows.values()} == {
        filename for filename, _size, _count, _header in DATASETS.values()
    }

    approved = set(_json("scripts/contract-scope.json")["json_envelope"]["approved_ids"])
    policies = _json("scripts/probe-policy.json")["datasets"]
    assert _json("custodians.json")["custodians"]["thevesh"]["name"] == "Thevesh Theva"

    for dataset_id, (filename, _size, count, _header) in DATASETS.items():
        row = maps_rows[dataset_id]
        url = RAW_BASE + filename
        assert row["id"] == row["canonical_id"] == dataset_id
        assert row["url"] == row["record_source_url"] == url
        assert row["licence"] == "CC0-1.0"
        assert row["custodian"] == "thevesh"
        assert row["steward"] == "Thevesh Theva"
        assert row["data_type"] == "reference"
        assert row["refresh_frequency"] == "as-required"
        assert row["namespace"] == "government_open_data"
        assert row["geo_coverage"] == "Malaysia"
        assert row["real_status"] == "live"
        assert row["expected_record_count"] == count
        assert row["health_report"] == f"data/{dataset_id}.md"
        assert "content_freshness_date" not in row
        assert "freshness_policy" not in row
        assert dataset_id in approved
        assert policies[dataset_id] == {
            "adapter": "direct",
            "format": "csv",
            "url": url,
            "freshness": {
                "extraction-mode": "structural-hash",
                "fallback": "unknown-freshness",
            },
        }


def test_published_health_is_probe_evidence_for_every_manifest_id() -> None:
    manifest_ids = {row["id"] for row in _json("datapulse.json")["datasets"]}
    snapshot = _json("health/latest.json")
    health_rows = {row["dataset_id"]: row for row in snapshot["datasets"]}
    assert len(health_rows) == len(snapshot["datasets"])
    assert set(health_rows) == manifest_ids
    assert snapshot["_trust_summary"]["datasets_total"] == len(health_rows)
    status_counts = Counter(row["status"].replace("-", "_") for row in health_rows.values())
    assert snapshot["_trust_summary"]["by_status"] == {
        key: status_counts[key] for key in snapshot["_trust_summary"]["by_status"]
    }

    for dataset_id, (_filename, _size, count, _header) in DATASETS.items():
        row = health_rows[dataset_id]
        assert row["url"] == RAW_BASE + DATASETS[dataset_id][0]
        assert row["request_url"] == row["url"]
        assert row["last_checked"] and row["last_checked"].endswith("Z")
        assert row["http_status"] == 200
        assert row["status"] == "reference"
        assert row["record_count"] == count
        assert row["content_length"] == DATASETS[dataset_id][1]
        assert row["shape_basis"] == "csv-headers"
        assert row["first_row_hash"].startswith("shape-v1:")
