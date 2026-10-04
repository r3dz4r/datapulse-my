"""Onboarding contract for the MECo election-results tables.

The twelve CSVs under ``data/`` in the "Malaysian Election Corpus: Federal and
State-Level Election Results since 1955" repository (``Thevesh/paper-meco-results``)
are publication-grade historical reference tables released under CC0-1.0. They
describe named candidates, parties and coalitions, so the catalogue reports only
what the source published and never upgrades a source claim into a verified fact.

A historical record carries no freshness clock. The manifest marks every row
``reference`` and the probe policy uses the static structural-hash shape the DOSM
boundary layers and the MECo maps onboarding used, so no content date, cadence or
recency field is ever invented for them.

The byte sizes, header rows and record counts below were read directly from each
raw upstream CSV on 2026-10-04. Every byte size matched the size reported by the
GitHub contents API for ``data/``. Record counts are ``csv.reader`` data rows with
the header excluded - never inferred from a filename, a byte size or a schema
guess. ``data/lookup_dates`` also ships a ``.json`` and most of the tables ship a
``.parquet`` mirror; only the ``.csv`` of each dataset is onboarded.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from scripts.health_policy import classify_status


ROOT = Path(__file__).resolve().parents[2]
RAW_BASE = "https://raw.githubusercontent.com/Thevesh/paper-meco-results/main/data/"
REPO = "https://github.com/Thevesh/paper-meco-results"
LICENCE = "CC0-1.0"
CUSTODIAN = "thevesh"
STEWARD = "Thevesh Theva"
VERIFIED_AT = "2026-10-04"
STATIC_REFERENCE_FRESHNESS = {
    "extraction-mode": "structural-hash",
    "fallback": "unknown-freshness",
}
FORBIDDEN_FRESHNESS_KEYS = (
    "freshness_policy",
    "content_freshness_date",
    "cadence",
    "probe_cadence",
    "last_modified",
)

# dataset id -> (filename, upstream byte size, data-row count, header row)
DATASETS = {
    "meco_consol_ballots": (
        "consol_ballots.csv",
        4_464_471,
        26_965,
        [
            "date", "election", "state", "seat", "ballot_order", "candidate_uid",
            "name_on_ballot", "name", "sex", "ethnicity", "age", "party_on_ballot",
            "party_uid", "party", "coalition_uid", "coalition", "votes",
            "votes_perc", "rank", "result",
        ],
    ),
    "meco_consol_stats": (
        "consol_stats.csv",
        1_377_490,
        10_092,
        [
            "date", "election", "state", "seat", "voters_total", "ballots_issued",
            "ballots_not_returned", "votes_rejected", "votes_valid", "majority",
            "n_candidates", "voter_turnout", "majority_perc", "votes_rejected_perc",
            "ballots_not_returned_perc",
        ],
    ),
    "meco_lookup_candidate": (
        "lookup_candidate.csv",
        778_859,
        14_742,
        ["candidate_uid", "candidate_rn", "name", "sex", "ethnicity", "dob"],
    ),
    "meco_lookup_coalition": (
        "lookup_coalition.csv",
        2_300,
        20,
        [
            "coalition_uid", "coalition", "coalition_name_en", "coalition_name_bm",
            "year_start", "year_end", "notes",
        ],
    ),
    "meco_lookup_coalition_succession": (
        "lookup_coalition_succession.csv",
        267,
        3,
        ["predecessor_uid", "successor_uid", "type", "year", "notes"],
    ),
    "meco_lookup_dates": (
        "lookup_dates.csv",
        4_647,
        210,
        ["state", "election_number", "date"],
    ),
    "meco_lookup_dun_parlimen": (
        "lookup_dun_parlimen.csv",
        177_517,
        7_009,
        ["state", "election", "code_parlimen", "code_dun"],
    ),
    "meco_lookup_party": (
        "lookup_party.csv",
        15_676,
        132,
        [
            "party_uid", "party", "party_name_en", "party_name_bm", "year_formed",
            "year_end", "notes",
        ],
    ),
    "meco_lookup_party_succession": (
        "lookup_party_succession.csv",
        3_455,
        55,
        ["predecessor_uid", "successor_uid", "type", "year", "notes"],
    ),
    "meco_lookup_prk": (
        "lookup_prk.csv",
        13_883,
        276,
        ["date", "state", "seat", "trigger", "notes"],
    ),
    "meco_raw_ballots": (
        "raw_ballots.csv",
        2_842_535,
        26_965,
        [
            "date", "election", "state", "seat", "ballot_order", "candidate_rn",
            "name_on_ballot", "party_on_ballot", "party_uid", "party",
            "coalition_uid", "coalition", "votes",
        ],
    ),
    "meco_raw_stats": (
        "raw_stats.csv",
        591_905,
        10_092,
        [
            "date", "election", "state", "seat", "voters_total", "ballots_issued",
            "ballots_not_returned", "votes_rejected",
        ],
    ),
}

# The full CSV set the GitHub contents API reported under data/ on 2026-10-04.
ENUMERATED_CSVS = frozenset(filename for filename, _size, _rows, _header in DATASETS.values())
NON_CSV_MIRRORS = frozenset(
    {
        "consol_ballots.parquet",
        "consol_stats.parquet",
        "lookup_candidate.parquet",
        "lookup_coalition.parquet",
        "lookup_coalition_succession.parquet",
        "lookup_dates.json",
        "lookup_dates.parquet",
        "lookup_party.parquet",
        "lookup_party_succession.parquet",
        "lookup_prk.parquet",
    }
)


def _json(path: str) -> dict:
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def test_one_manifest_row_per_enumerated_csv() -> None:
    rows = {row["id"]: row for row in _json("datapulse.json")["datasets"]}
    # Scope by originating repository, not a name prefix: the sibling MECo maps
    # onboarding shares the meco_ namespace and may land alongside this one.
    meco_rows = {dataset_id: row for dataset_id, row in rows.items() if row["source"] == REPO}

    # Exactly the twelve CSVs under data/ become rows: no parquet mirror, no
    # lookup_dates.json, and nothing from outside data/.
    assert set(meco_rows) == set(DATASETS)
    onboarded_files = set()
    for dataset_id, row in meco_rows.items():
        assert row["url"] == row["record_source_url"]
        onboarded_files.add(row["url"].rsplit("/", 1)[-1])
    assert onboarded_files == set(ENUMERATED_CSVS)
    assert onboarded_files.isdisjoint(NON_CSV_MIRRORS)


def test_manifest_rows_record_the_read_licence_and_url() -> None:
    rows = {row["id"]: row for row in _json("datapulse.json")["datasets"]}
    custodians = _json("custodians.json")["custodians"]
    approved = set(_json("scripts/contract-scope.json")["json_envelope"]["approved_ids"])

    assert custodians[CUSTODIAN]["name"] == STEWARD
    for dataset_id, (filename, _byte_size, record_count, _header) in DATASETS.items():
        url = RAW_BASE + filename
        row = rows[dataset_id]
        assert row["id"] == row["canonical_id"] == dataset_id
        assert row["url"] == row["record_source_url"] == url
        assert row["source"] == REPO
        assert row["licence"] == LICENCE
        assert row["custodian"] == CUSTODIAN
        assert row["steward"] == STEWARD
        assert row["data_type"] == "reference"
        assert row["refresh_frequency"] == "as-required"
        assert row["namespace"] == "government_open_data"
        assert row["geo_coverage"] == "Malaysia"
        assert row["real_status"] == "live"
        assert row["expected_record_count"] == record_count
        assert row["verified_at"] == VERIFIED_AT
        # A reference row must not smuggle in a freshness clock of its own.
        for key in FORBIDDEN_FRESHNESS_KEYS:
            assert key not in row, f"{dataset_id} carries invented field {key}"
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
        assert "family" not in policy


def test_measured_header_rows_are_documented() -> None:
    headers = {
        dataset_id: header
        for dataset_id, (_filename, _byte_size, _record_count, header) in DATASETS.items()
    }
    assert headers["meco_consol_ballots"][:3] == ["date", "election", "state"]
    assert headers["meco_consol_ballots"][-1] == "result"
    assert headers["meco_lookup_dates"] == ["state", "election_number", "date"]
    assert headers["meco_lookup_coalition_succession"][:2] == [
        "predecessor_uid", "successor_uid",
    ]
    assert headers["meco_raw_stats"] == [
        "date", "election", "state", "seat", "voters_total", "ballots_issued",
        "ballots_not_returned", "votes_rejected",
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
