"""Onboarding contract for the MECo delimitation mapping and cartogram tables.

The three CSVs are versioned reference tables published by the "Malaysian
Election Corpus: Electoral Maps and Cartograms since 1954" repository
(``Thevesh/paper-meco-maps``) under CC0-1.0. They carry no freshness clock:
the manifest marks them ``reference`` and the probe policy uses the static
structural-hash shape, so no content date is ever invented for them.

The byte sizes, header rows and record counts below were read from the raw
upstream files on 2026-10-04. Record counts are ``csv.reader`` data rows with
the header excluded - never inferred from the filename, the byte size or a
geometry feature count.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from scripts.health_policy import classify_status


ROOT = Path(__file__).resolve().parents[2]
RAW_BASE = "https://raw.githubusercontent.com/Thevesh/paper-meco-maps/main/data/"
REPO = "https://github.com/Thevesh/paper-meco-maps"
LICENCE = "CC0-1.0"
CUSTODIAN = "thevesh"
STEWARD = "Thevesh Theva"
VERIFIED_AT = "2026-10-04"
STATIC_REFERENCE_FRESHNESS = {
    "extraction-mode": "structural-hash",
    "fallback": "unknown-freshness",
}

# dataset id -> (filename, upstream byte size, data-row count, header row)
DATASETS = {
    "meco_delimitation_to_elections": (
        "delims_to_elections.csv",
        6338,
        210,
        ["state", "year", "election", "peninsular", "sabah", "sarawak"],
    ),
    "meco_cartogram_equal_k": (
        "cartogram_equal_k.csv",
        3852,
        208,
        ["state", "election_name", "seat_type", "k"],
    ),
    "meco_cartogram_electorate_k": (
        "cartogram_electorate_k.csv",
        3846,
        207,
        ["state", "election_name", "seat_type", "k"],
    ),
}


def _json(path: str) -> dict:
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def test_manifest_rows_record_the_read_licence_and_url() -> None:
    rows = {row["id"]: row for row in _json("datapulse.json")["datasets"]}
    custodians = _json("custodians.json")["custodians"]
    approved = set(_json("scripts/contract-scope.json")["json_envelope"]["approved_ids"])

    for dataset_id, (filename, _byte_size, record_count, _header) in DATASETS.items():
        url = RAW_BASE + filename
        row = rows[dataset_id]
        assert row["id"] == row["canonical_id"] == dataset_id
        assert row["url"] == row["record_source_url"] == url
        assert row["source"] == REPO
        assert row["licence"] == LICENCE
        assert row["custodian"] == CUSTODIAN
        assert custodians[CUSTODIAN]["name"] == STEWARD
        assert row["steward"] == STEWARD
        assert row["data_type"] == "reference"
        assert row["refresh_frequency"] == "as-required"
        assert row["namespace"] == "government_open_data"
        assert row["geo_coverage"] == "Malaysia"
        assert row["real_status"] == "live"
        assert row["expected_record_count"] == record_count
        assert row["verified_at"] == VERIFIED_AT
        # A reference row must not smuggle in a freshness clock of its own.
        assert "freshness_policy" not in row
        assert "content_freshness_date" not in row
        assert dataset_id in approved


def test_probe_policy_is_the_static_reference_shape() -> None:
    policies = _json("scripts/probe-policy.json")["datasets"]

    for dataset_id, (filename, _byte_size, _record_count, _header) in DATASETS.items():
        policy = policies[dataset_id]
        assert policy == {
            "adapter": "direct",
            "format": "csv",
            "url": RAW_BASE + filename,
            "freshness": STATIC_REFERENCE_FRESHNESS,
        }
        # The structural hash is a change-identity check, not a publisher date:
        # the static-reference shape declares no content date field at all.
        assert "content-date-field" not in policy["freshness"]
        assert "date-source" not in policy["freshness"]


def test_measured_header_rows_are_documented() -> None:
    headers = {
        dataset_id: header
        for dataset_id, (_filename, _byte_size, _record_count, header) in DATASETS.items()
    }
    assert headers["meco_delimitation_to_elections"] == [
        "state", "year", "election", "peninsular", "sabah", "sarawak",
    ]
    assert headers["meco_cartogram_equal_k"] == headers["meco_cartogram_electorate_k"] == [
        "state", "election_name", "seat_type", "k",
    ]


def test_reference_rows_never_invent_a_freshness_date() -> None:
    rows = {row["id"]: row for row in _json("datapulse.json")["datasets"]}

    for dataset_id, (_filename, _byte_size, record_count, _header) in DATASETS.items():
        row = rows[dataset_id]
        status, reason = classify_status(
            {
                "dataset_id": dataset_id,
                "data_type": row["data_type"],
                "refresh_frequency": row["refresh_frequency"],
                "http_status": 200,
                "last_checked": "2026-10-04T00:00:00Z",
                "content_freshness_date": None,
                "expected_record_count": record_count,
            },
            datetime(2026, 10, 4, 1, tzinfo=timezone.utc),
        )
        assert (status, reason) == ("reference", "versioned-reference-data")
