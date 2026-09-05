from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
TARGETS = {
    "st_current_ipp_licensees": "https://myenergystats.st.gov.my/documents/d/guest/csv-senarai-lesen-ipp",
    "st_current_cogen_licensees": "https://myenergystats.st.gov.my/documents/d/guest/csv-senarai-lesen-cogen",
    "st_current_re_licensees": "https://myenergystats.st.gov.my/documents/d/guest/csv-senarai-lesen-re",
    "st_current_lss_licensees": "https://myenergystats.st.gov.my/documents/d/guest/csv-senarai-lesen-lss",
}


def _load_json(relative_path: str) -> dict:
    return json.loads((ROOT / relative_path).read_text(encoding="utf-8"))


def test_current_st_registers_have_safe_complete_contract_records() -> None:
    manifest = _load_json("datapulse.json")
    policies = _load_json("scripts/probe-policy.json")["datasets"]
    approved_ids = _load_json("scripts/contract-scope.json")["json_envelope"]["approved_ids"]

    for dataset_id, url in TARGETS.items():
        rows = [row for row in manifest["datasets"] if row["id"] == dataset_id]
        assert len(rows) == 1
        row = rows[0]
        assert row["canonical_id"] == dataset_id
        assert row["url"] == url
        assert row["record_source_url"] == url
        assert row["data_type"] == "reference-current"
        assert row["licence"] == "Publisher licence not stated; portal disclaimer applies"
        assert all(term not in row["licence"] for term in ("OGL", "CC-BY", "MIT"))
        assert row["freshness_policy"] == {
            "family": "st_energy_statistics",
            "content_date_field": "last_modified",
            "interpretation": "publication_date",
            "discontinued_on_404": True,
            "reference_table": False,
            "notes": "Current MyEnergyStats licence register has no reliable in-file publication date; freshness uses the HTTP Last-Modified signal.",
        }
        assert policies[dataset_id] == {
            "adapter": "direct",
            "format": "csv",
            "url": url,
            "freshness": {
                "family": "st_energy_statistics",
                "extraction-mode": "structural-hash",
                "fallback": "last-modified",
            },
        }
        assert dataset_id in approved_ids
        assert (ROOT / "data" / f"{dataset_id}.md").is_file()
        assert (ROOT / "data" / "json" / f"{dataset_id}.json").is_file()
        assert (ROOT / "data" / "jsonld" / f"{dataset_id}.json").is_file()
        assert (ROOT / "badges" / f"{dataset_id}.svg").is_file()


def test_current_st_register_raw_csvs_are_not_committed() -> None:
    for dataset_id in TARGETS:
        assert not list(ROOT.rglob(f"{dataset_id}.csv"))
