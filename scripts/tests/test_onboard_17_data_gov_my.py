"""Lock the measured data.gov.my fisheries, ICT and organ donation onboarding."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
VERIFIED_AT = "2026-10-11"
DATASETS = {
    "aquaculture_production": (
        "Annual Aquaculture Production by State & Culture System",
        "agriculture/aquaculture_production.csv", 5090, "annual", "dof",
        "Department of Fisheries Malaysia", "government_open_data",
    ),
    "aquaculture_production_species": (
        "Annual Aquaculture Production by Species",
        "agriculture/aquaculture_production_species.csv", 1216, "annual", "dof",
        "Department of Fisheries Malaysia", "government_open_data",
    ),
    "fish_landings_gear": (
        "Annual Landings Marine Fish by State & Fishing Gear",
        "agriculture/fish_landings_gear.csv", 6004, "annual", "dof",
        "Department of Fisheries Malaysia", "government_open_data",
    ),
    "fish_landings_inland": (
        "Annual Landings & Value Freshwater Fish from Inland Fisheries by State & Waterbody",
        "agriculture/fish_landings_inland.csv", 4230, "annual", "dof",
        "Department of Fisheries Malaysia", "government_open_data",
    ),
    "fish_landings_species": (
        "Annual Landings Marine Fish by State & Species",
        "agriculture/fish_landings_species.csv", 64581, "annual", "dof",
        "Department of Fisheries Malaysia", "government_open_data",
    ),
    "fish_landings_value": (
        "Annual Value of Marine Fish Landings by State & Grade",
        "agriculture/fish_landings_value.csv", 3971, "annual", "dof",
        "Department of Fisheries Malaysia", "government_open_data",
    ),
    "fish_prices": (
        "Monthly Prices of Marine Fish by Market Level & Species",
        "agriculture/fish_prices.csv", 98952, "monthly", "dof",
        "Department of Fisheries Malaysia", "government_open_data",
    ),
    "fishers": (
        "Annual Number of Fishers by State & Fishing Gear",
        "agriculture/fishers.csv", 7866, "annual", "dof",
        "Department of Fisheries Malaysia", "government_open_data",
    ),
    "fishing_vessels": (
        "Annual Number of Licensed Fishing Vessels by State, Engine Type & Horsepower",
        "agriculture/fishing_vessels.csv", 8512, "annual", "dof",
        "Department of Fisheries Malaysia", "government_open_data",
    ),
    "seaweed_production": (
        "Monthly Seaweed Production by State",
        "agriculture/seaweed_production.csv", 3792, "monthly", "dof",
        "Department of Fisheries Malaysia", "government_open_data",
    ),
    "hh_access_internet": (
        "Household Access to Internet by State & Strata",
        "https://storage.dosm.gov.my/icths/hh_access_internet.csv", 343, "annual", "dosm",
        "Department of Statistics Malaysia", "other",
    ),
    "icths_internet_device": (
        "Internet Use by Type of Portable Device",
        "https://storage.dosm.gov.my/icths/icths_internet_device.csv", 1372, "annual", "dosm",
        "Department of Statistics Malaysia", "other",
    ),
    "icths_internet_sex": (
        "Internet Use by State & Sex",
        "https://storage.dosm.gov.my/icths/icths_internet_sex.csv", 216, "annual", "dosm",
        "Department of Statistics Malaysia", "other",
    ),
    "icths_internet_strata": (
        "Internet Use by State & Strata",
        "https://storage.dosm.gov.my/icths/icths_internet_strata.csv", 392, "annual", "dosm",
        "Department of Statistics Malaysia", "other",
    ),
    "icths_mobile_sex": (
        "Mobile Phone Ownership by State & Sex",
        "https://storage.dosm.gov.my/icths/icths_mobile_sex.csv", 219, "annual", "dosm",
        "Department of Statistics Malaysia", "other",
    ),
    "organ_pledge_demog": (
        "Organ Donation Pledges by Sex, Ethnicity and Age Group",
        "healthcare/organ_pledge_demog.csv", 1620, "daily", "kkm",
        "Ministry of Health Malaysia", "healthcare",
    ),
    "organ_pledge_demog_state": (
        "Organ Donation Pledges by State, Sex, Ethnicity and Age Group",
        "healthcare/organ_pledge_demog_state.csv", 25920, "daily", "kkm",
        "Ministry of Health Malaysia", "healthcare",
    ),
}


def _json(path: str) -> dict:
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def test_all_seventeen_data_gov_my_sources_are_registered_end_to_end() -> None:
    manifest = {row["id"]: row for row in _json("datapulse.json")["datasets"]}
    policies = _json("scripts/probe-policy.json")["datasets"]
    approved = set(_json("scripts/contract-scope.json")["json_envelope"]["approved_ids"])
    custodians = _json("custodians.json")["custodians"]
    health = {row["dataset_id"]: row for row in _json("health/latest.json")["datasets"]}

    for custodian, steward in {
        "dof": "Department of Fisheries Malaysia",
        "dosm": "Department of Statistics Malaysia",
        "kkm": "Ministry of Health Malaysia",
    }.items():
        assert custodians[custodian]["name"] == steward

    for dataset_id, (name, path_or_url, count, cadence, custodian, steward, namespace) in DATASETS.items():
        url = path_or_url if path_or_url.startswith("https://") else f"https://storage.data.gov.my/{path_or_url}"
        row = manifest[dataset_id]
        assert row["id"] == row["canonical_id"] == dataset_id
        assert row["name"] == name
        assert row["url"] == row["record_source_url"] == url
        assert row["source"] == "data.gov.my"
        assert row["licence"] == "Creative Commons Attribution 4.0"
        attribution = {
            "dof": "Department of Fisheries",
            "dosm": "Department of Statistics Malaysia",
            "kkm": "National Transplant Resource Centre, Ministry of Health Malaysia",
        }[custodian]
        assert row["attribution"] == attribution
        assert row["custodian"] == custodian
        assert row["steward"] == steward
        assert row["data_type"] == "reference-current"
        assert row["refresh_frequency"] == cadence
        assert row["namespace"] == namespace
        assert row["geo_coverage"] == "Malaysia"
        assert row["real_status"] == "live"
        assert row["expected_record_count"] == count
        assert row["health_report"] == f"data/{dataset_id}.md"
        assert row["verified_at"] == VERIFIED_AT
        assert "freshness_policy" not in row
        assert policies[dataset_id] == {
            "adapter": "direct",
            "format": "csv",
            "url": url,
            "freshness": {
                "content-date-field": "date",
                "extraction-mode": "max",
                "family": "data_gov_my",
                "fallback": "last-modified",
            },
        }
        assert dataset_id in approved
        assert health[dataset_id] == {
            "dataset_id": dataset_id,
            "url": url,
            "last_checked": None,
            "status": "unknown-freshness",
            "message": "Not probed; provisional onboarding status.",
        }
