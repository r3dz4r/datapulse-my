from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
TARGETS = (
    "kkmnow_blood",
    "kkmnow_organ",
    "kkmnow_covidnow",
    "kkmnow_covidepid",
    "kkmnow_covidvax",
    "kkmnow_pekab40",
    "kkmnow_bedutil",
    "kkmnow_facilities",
)


def _load_json(relative_path: str) -> dict:
    return json.loads((ROOT / relative_path).read_text(encoding="utf-8"))


def test_kkmnow_datasets_have_complete_contract_records() -> None:
    manifest = _load_json("datapulse.json")
    policies = _load_json("scripts/probe-policy.json")["datasets"]
    approved_ids = _load_json("scripts/contract-scope.json")["json_envelope"]["approved_ids"]
    rows = {row["id"]: row for row in manifest["datasets"]}

    for dataset_id in TARGETS:
        row = rows[dataset_id]
        assert row["canonical_id"] == dataset_id
        assert row["custodian"] == "kkm"
        assert row["methodology_version"] == 1
        assert row["freshness_policy"]["family"] == "github_parquet"
        assert policies[dataset_id]["adapter"] == "direct"
        assert policies[dataset_id]["format"] == "parquet"
        assert policies[dataset_id]["freshness"]["family"] == "github_parquet"
        assert policies[dataset_id]["freshness"]["content-date-field"] == "date"
        assert dataset_id in approved_ids
        assert (ROOT / "data" / f"{dataset_id}.md").is_file()
        assert (ROOT / "data" / "jsonld" / f"{dataset_id}.json").is_file()
        assert (ROOT / "badges" / f"{dataset_id}.svg").is_file()


def test_kkmnow_blood_artifacts_preserve_template_structure() -> None:
    health = _load_json("health/latest.json")
    statuses = {row["dataset_id"]: row["status"] for row in health["datasets"]}

    for dataset_id in TARGETS:
        report = (ROOT / "data" / f"{dataset_id}.md").read_text(encoding="utf-8")
        jsonld = _load_json(f"data/jsonld/{dataset_id}.json")
        badge = (ROOT / "badges" / f"{dataset_id}.svg").read_text(encoding="utf-8")
        status = statuses[dataset_id]

        assert report.startswith(f'---\nid: "{dataset_id}"')
        assert "## Status" in report
        assert jsonld["@type"] == "Dataset"
        assert jsonld["identifier"] == dataset_id
        assert jsonld["distribution"][0]["contentUrl"].endswith(
            f"/{dataset_id}.md"
        )
        assert f'aria-label="health: {status}"' in badge
        assert f"<title>health: {status}</title>" in badge
