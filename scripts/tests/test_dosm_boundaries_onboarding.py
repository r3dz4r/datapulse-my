from __future__ import annotations

import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import pytest

from scripts.health_policy import classify_status
from scripts import gen_json_envelope


ROOT = Path(__file__).resolve().parents[2]
BASE_URL = "https://raw.githubusercontent.com/dosm-malaysia/data-open/main/datasets/geodata/"
BOUNDARIES = {
    "dosm_boundary_parlimen": ("electoral_0_parlimen.geojson", 1_370_546, 222),
    "dosm_boundary_dun": ("electoral_1_dun.geojson", 2_238_573, 600),
    "dosm_boundary_malaysia": ("administrative_0_malaysia.geojson", 306_328, 1),
    "dosm_boundary_state": ("administrative_1_state.geojson", 391_521, 16),
    "dosm_boundary_district": ("administrative_2_district.geojson", 947_755, 160),
}


def _json(path: str) -> dict:
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def test_boundary_contract_and_artifacts_are_source_honest() -> None:
    rows = {row["id"]: row for row in _json("datapulse.json")["datasets"]}
    policies = _json("scripts/probe-policy.json")["datasets"]
    approved = set(_json("scripts/contract-scope.json")["json_envelope"]["approved_ids"])

    for dataset_id, (filename, byte_size, feature_count) in BOUNDARIES.items():
        url = BASE_URL + filename
        row = rows[dataset_id]
        assert row["canonical_id"] == dataset_id
        assert row["url"] == row["record_source_url"] == url
        assert row["custodian"] == "dosm"
        assert row["licence"] == "Open Data License"
        assert row["source"] == "https://github.com/dosm-malaysia/data-open"
        assert row["data_type"] == "reference"
        assert row["refresh_frequency"] == "as-required"
        assert row["namespace"] == "government_open_data"
        assert row["expected_record_count"] == feature_count
        assert row["verified_at"] == "2026-10-03"
        assert "freshness_policy" not in row
        assert policies[dataset_id] == {
            "adapter": "direct",
            "format": "geojson",
            "url": url,
            "freshness": {"extraction-mode": "structural-hash", "fallback": "unknown-freshness"},
        }
        assert dataset_id in approved
        assert (ROOT / "data" / f"{dataset_id}.md").is_file()
        assert (ROOT / "data" / "jsonld" / f"{dataset_id}.json").is_file()
        assert (ROOT / "badges" / f"{dataset_id}.svg").is_file()

        report = (ROOT / "data" / f"{dataset_id}.md").read_text(encoding="utf-8")
        jsonld = _json(f"data/jsonld/{dataset_id}.json")
        badge = (ROOT / "badges" / f"{dataset_id}.svg").read_text(encoding="utf-8")
        assert f"dataset_id: {dataset_id}" in report
        assert jsonld["identifier"] == dataset_id
        assert jsonld["sameAs"] == url
        assert jsonld["license"] == "Open Data License"
        assert "dateModified" not in jsonld
        assert jsonld["variableMeasured"][0]["value"] in {"unknown", "reference", "unreachable", "degraded"}
        assert any(f'aria-label="health: {status}"' in badge for status in ("unknown", "reference", "unreachable", "degraded"))
        assert f"{byte_size:,}" in report
        assert byte_size < gen_json_envelope.MAX_GEOJSON_SOURCE_BYTES


def test_geojson_probe_counts_features_without_inventing_content_date(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    body = tmp_path / "boundary.geojson"
    body.write_text(
        json.dumps({
            "type": "FeatureCollection",
            "features": [
                {"type": "Feature", "properties": {"code_parlimen": "P001"},
                 "geometry": {"type": "Polygon", "coordinates": [[[0, 0], [1, 0], [0, 0]]]}},
                {"type": "Feature", "properties": {"code_parlimen": "P002"},
                 "geometry": {"type": "Polygon", "coordinates": [[[0, 0], [1, 0], [0, 0]]]}},
                {"type": "Feature", "properties": {"code_parlimen": "P003"},
                 "geometry": {"type": "Polygon", "coordinates": [[[0, 0], [1, 0], [0, 0]]]}},
            ],
        }),
        encoding="utf-8",
    )
    command = (
        'export DATAPULSE_CHECK_SOURCE_ONLY=true; '
        'source scripts/check.sh; extract_json_metrics "$GEOJSON_FIXTURE"'
    )
    result = subprocess.run(
        ["bash", "-c", command], cwd=ROOT,
        env={**os.environ, "GEOJSON_FIXTURE": str(body)},
        capture_output=True, text=True, check=True,
    )
    metrics = json.loads(result.stdout)
    assert metrics["record_count"] == 3
    assert metrics["column_count"] == 1
    assert metrics["first_record_timestamp"] is None
    monkeypatch.setattr(gen_json_envelope, "fetch_source", lambda _url: (body.read_bytes(), "text/plain"))
    assert gen_json_envelope.infer_fields(BASE_URL + "electoral_0_parlimen.geojson") == [
        {"name": "code_parlimen", "type": "string"}
    ]
    status = classify_status({
        "dataset_id": "dosm_boundary_parlimen", "data_type": "reference",
        "refresh_frequency": "as-required", "http_status": 200,
        "last_checked": "2026-10-03T02:21:01Z", "content_freshness_date": None,
    }, datetime(2026, 10, 3, 3, tzinfo=timezone.utc))
    assert status[0] == "reference"
