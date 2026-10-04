"""Onboarding contract for the deterministic ODIN assessment API surfaces.

The ODIN assessment (Open Data Inventory) is served by an Angular single-page
application at ``https://odin.opendatawatch.com/``. The served HTML carries no
data of its own; the application fetches it from a JSON API declared in the
bundle as ``apiUrl:"https://odin-aim.akroninc.net/api/api/"``. That API is the
real data path this lane looked for, and it is deterministic: a bounded GET on
each endpoint below returned ``HTTP 200 application/json`` with a stable body on
2026-10-04.

This test covers the seven endpoints the API exposes by GET and that are
onboarded as static-reference rows. It deliberately does not cover the scored
assessment: ``client/GetGlobalMapData/{useId}``, ``client/GetRanking/{useId}``,
``client/GetCountryScore/{useId}/{countryId}`` and ``client/DataDownload`` are
``POST``-only (a GET returns HTTP 405), so the static-reference probe shape -
adapter ``direct`` with a single ``url`` - cannot express them. The scored data
and the bulk ``2016-2024 data.zip`` static export are recorded in
``docs/specs/odin-export-path-2026-10-04.md`` and are not onboarded.

Licence: the application's own ``settings.json`` and bundle state "Licensed
under a Creative Commons Attribution 4.0 license", and direct the reader to
"cite any uses of these data as: Open Data Watch -- Open Data Inventory". The
manifest therefore records the SPDX identifier ``CC-BY-4.0`` (not the phrase)
and an attribution naming Open Data Watch on every row. CC BY 4.0 requires that
attribution, so it is asserted here and on the generated public dataset page.

Byte sizes and record counts below were read directly from the live endpoints on
2026-10-04. ``record_count`` is the length of the top-level JSON array (or the
top-level key count for the one configuration object); it is never inferred from
a byte size or a filename.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from jsonschema import Draft202012Validator

from scripts import gen_dataset_pages
from scripts.health_policy import classify_status


ROOT = Path(__file__).resolve().parents[2]
API_BASE = "https://odin-aim.akroninc.net/api/api/"
SITE = "https://odin.opendatawatch.com"
SOURCE = "Open Data Watch -- Open Data Inventory"
LICENCE = "CC-BY-4.0"
CUSTODIAN = "odin"
STEWARD = "Open Data Watch"
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

# dataset id -> (endpoint path, upstream byte size, record count, top-level shape,
#                 first-record keys)
DATASETS = {
    "odin_editions": (
        "client/GetLiveYears",
        1210,
        7,
        "json-array",
        ["useId", "year", "description", "dataCollecting", "isLive",
         "dateAdded", "dateUpdated", "dataUpdatedAt"],
    ),
    "odin_countries": (
        "client/GetCountries",
        79590,
        243,
        "json-array",
        ["countryId", "regionId", "incomeGroupId", "incomeRegionId",
         "developingRegionId", "countryCode", "countryName", "isInMap", "nsoUrl",
         "isSmallCountry", "accentedCountryName", "disseminationSubscriber",
         "preferedLanguage", "region", "continent"],
    ),
    "odin_regions": (
        "client/GetRegions",
        3031,
        21,
        "json-array",
        ["regionId", "continentId", "shortName", "fullName", "centerLatitude",
         "centerLongitude", "continent"],
    ),
    "odin_income_groups": (
        "client/GetIncomeGroups",
        442,
        5,
        "json-array",
        ["incomeGroupId", "incomeCode", "incomeGroup1", "orderNumb"],
    ),
    "odin_continents": (
        "client/GetContinents",
        372,
        6,
        "json-array",
        ["continentId", "continentCode", "continent1"],
    ),
    "odin_categories": (
        "client/GetLatestsCategories",
        8702,
        23,
        "json-array",
        ["categoryId", "categoryGroupId", "category1", "recommendedDisaggregation",
         "representativeIndicators", "orderNum", "prevYearCategoryId", "yearId",
         "projectId", "initial", "categoryGoals", "categoryInputs", "indicators",
         "sdgGategoryGoals"],
    ),
    "odin_default_weights": (
        "client/GetDefaultWeights",
        54676,
        52,
        "json-object",
        None,
    ),
}


def _json(path: str) -> dict:
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def test_manifest_rows_are_schema_valid_and_scoped() -> None:
    schema = _json("datapulse.schema.json")
    rows = {row["id"]: row for row in _json("datapulse.json")["datasets"]}
    odin_rows = {dataset_id: row for dataset_id, row in rows.items() if row["custodian"] == CUSTODIAN}

    assert set(odin_rows) == set(DATASETS)
    Draft202012Validator(schema).validate(
        {"$schema": schema["$id"], "datasets": list(odin_rows.values())}
    )


def test_manifest_rows_record_the_spdx_licence_and_attribution() -> None:
    rows = {row["id"]: row for row in _json("datapulse.json")["datasets"]}
    custodians = _json("custodians.json")["custodians"]
    approved = set(_json("scripts/contract-scope.json")["json_envelope"]["approved_ids"])

    assert custodians[CUSTODIAN]["name"] == STEWARD
    for dataset_id, (path, _byte_size, record_count, _shape, _keys) in DATASETS.items():
        url = API_BASE + path
        row = rows[dataset_id]
        assert row["id"] == row["canonical_id"] == dataset_id
        assert row["url"] == row["record_source_url"] == url
        # The licence must be the SPDX identifier, not the prose phrase the
        # application displays.
        assert row["licence"] == LICENCE
        assert " " not in row["licence"]
        assert "Creative Commons" not in row["licence"]
        # CC BY 4.0 requires attribution, so a bare row is a contract failure.
        attribution = row["attribution"]
        assert attribution.startswith("Open Data Watch")
        assert "Open Data Inventory" in attribution
        assert "CC BY 4.0" in attribution
        assert SITE in attribution
        assert row["source"] == SOURCE
        assert row["steward"] == STEWARD
        assert row["custodian"] == CUSTODIAN
        assert row["data_type"] == "reference"
        assert row["refresh_frequency"] == "as-required"
        assert row["namespace"] == "government_open_data"
        assert row["geo_coverage"] == "Global"
        assert row["real_status"] == "live"
        assert row["expected_record_count"] == record_count
        assert row["verified_at"] == VERIFIED_AT
        for key in FORBIDDEN_FRESHNESS_KEYS:
            assert key not in row, f"{dataset_id} carries invented field {key}"
        assert dataset_id in approved


def test_probe_policy_is_the_static_reference_shape() -> None:
    policies = _json("scripts/probe-policy.json")["datasets"]

    for dataset_id, (path, _byte_size, _record_count, _shape, _keys) in DATASETS.items():
        policy = policies[dataset_id]
        assert policy == {
            "adapter": "direct",
            "format": "json",
            "url": API_BASE + path,
            "freshness": STATIC_REFERENCE_FRESHNESS,
        }
        # The structural hash is a change-identity check, not a publisher date:
        # the static-reference shape declares no content date field at all.
        assert "content-date-field" not in policy["freshness"]
        assert "date-source" not in policy["freshness"]
        assert "family" not in policy


def test_public_dataset_page_carries_licence_and_attribution() -> None:
    rows = {row["id"]: row for row in _json("datapulse.json")["datasets"]}

    for dataset_id in DATASETS:
        page = gen_dataset_pages.render_page(
            rows[dataset_id], None, "https://www.data-pulse.my", "/datasets/{id}"
        )
        assert LICENCE in page
        assert "Open Data Watch" in page
        assert "Open Data Inventory" in page


def test_reference_rows_never_invent_a_freshness_date() -> None:
    rows = {row["id"]: row for row in _json("datapulse.json")["datasets"]}

    for dataset_id, (_path, _byte_size, record_count, _shape, _keys) in DATASETS.items():
        row = rows[dataset_id]
        status, _reason = classify_status(
            {
                "dataset_id": dataset_id,
                "data_type": row["data_type"],
                "refresh_frequency": row["refresh_frequency"],
                "http_status": 200,
                "last_checked": "2026-10-04T00:00:00Z",
                "content_freshness_date": None,
                "expected_record_count": record_count,
            },
            datetime(2026, 10, 4, 12, tzinfo=timezone.utc),
        )
        assert status == "reference"


def test_export_path_spec_records_the_post_only_obstacle() -> None:
    spec = ROOT / "docs" / "specs" / "odin-export-path-2026-10-04.md"
    assert spec.is_file()
    text = spec.read_text(encoding="utf-8")
    # The spec must name the real data path and the scored endpoints it could
    # not onboard because they are POST-only.
    assert "odin-aim.akroninc.net/api/api/" in text
    assert "client/DataDownload" in text
    assert "client/GetGlobalMapData/" in text
    assert "client/GetRanking/" in text
    assert "POST" in text
    assert "405" in text
