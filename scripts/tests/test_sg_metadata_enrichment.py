from __future__ import annotations

import json
from unittest.mock import patch

from scripts.gen_attestations import enrich_sg_metadata


class FakeResponse:
    def __init__(self, payload: dict, status: int = 200) -> None:
        self.payload = payload
        self.status = status

    def read(self) -> bytes:
        return json.dumps(self.payload).encode()

    def close(self) -> None:
        pass


def static_policy() -> dict:
    return {
        "sg_static_metadata": {
            "sg_datagov_coe_bidding": {
                "title": "COE",
                "description": "COE description",
                "publisher": "LTA",
                "frequency": "monthly",
            },
            "sg_datagov_taxi_availability": {
                "title": "Taxi",
                "description": "Taxi description",
                "publisher": "LTA",
                "frequency": "realtime",
            },
            "sg_datagov_weather_readings": {
                "title": "Weather",
                "description": "Weather description",
                "publisher": "NEA",
                "frequency": "realtime",
            },
            "sg_datagov_hdb_resale_prices": {
                "title": "HDB Resale Flat Prices (Singapore)",
                "description": "HDB resale description",
                "publisher": "Housing & Development Board (Singapore)",
                "frequency": "monthly",
            },
            "sg_datagov_hdb_metadata": {
                "title": "HDB Resale Flat Prices — Dataset Metadata",
                "description": "HDB metadata description",
                "publisher": "Housing & Development Board (Singapore)",
                "frequency": "static",
            },
        }
    }


def test_enrich_v2_dataset_uses_api_metadata() -> None:
    manifest = [{"id": "sg_datagov_hdb_metadata", "url": "https://api-production.data.gov.sg/v2/public/api/datasets/d_X/metadata"}]
    response = FakeResponse({"code": 0, "data": {"name": "HDB", "description": "HDB data", "managedBy": "HDB", "lastUpdatedAt": "2026-09-07T02:10:24+08:00"}})
    with patch("scripts.gen_attestations.urllib.request.urlopen", return_value=response):
        enrich_sg_metadata(manifest, static_policy())
    assert manifest[0]["title"] == "HDB"
    assert manifest[0]["description"] == "HDB data"
    assert manifest[0]["publisher"] == "HDB"
    assert manifest[0]["last_updated_at"] == "2026-09-07T02:10:24+08:00"


def test_enrich_v2_dataset_falls_back_to_static_when_api_fails() -> None:
    manifest = [{"id": "sg_datagov_hdb_resale_prices", "url": "https://api-production.data.gov.sg/v2/public/api/datasets/d_X/list-rows"}]
    # Simulate an API that returns a non-JSON body (truncated response / 502 HTML error page)
    # _fetch_json catches the JSONDecodeError and returns None, so the static-map fallback fires.
    response = FakeResponse({"code": 0, "data": {"name": "should be overridden"}})  # valid shape so it would be used if not for the static map
    # Force _fetch_json to return None by making urlopen return None via side_effect:
    with patch("scripts.gen_attestations.urllib.request.urlopen", side_effect=TypeError("boom")):
        enrich_sg_metadata(manifest, static_policy())
    assert manifest[0]["title"] == "HDB Resale Flat Prices (Singapore)"
    assert manifest[0]["description"] == "HDB resale description"
    assert manifest[0]["publisher"] == "Housing & Development Board (Singapore)"
    assert manifest[0]["frequency"] == "monthly"


def test_enrich_ckan_dataset_uses_static_map() -> None:
    manifest = [{"id": "sg_datagov_coe_bidding", "url": "https://data.gov.sg/api/action/datastore_search?resource_id=d_X"}]
    with patch("scripts.gen_attestations.urllib.request.urlopen") as urlopen:
        enrich_sg_metadata(manifest, static_policy())
    urlopen.assert_not_called()
    assert manifest[0]["title"] == "COE"
    assert manifest[0]["publisher"] == "LTA"


def test_enrich_realtime_weather_extracts_last_timestamp() -> None:
    manifest = [{"id": "sg_datagov_weather_readings", "url": "https://api.data.gov.sg/v1/environment/air-temperature"}]
    response = FakeResponse({"items": [{"timestamp": "2026-09-07T23:35:00+08:00", "readings": []}]})
    with patch("scripts.gen_attestations.urllib.request.urlopen", return_value=response):
        enrich_sg_metadata(manifest, static_policy())
    assert manifest[0]["last_updated_at"] == "2026-09-07T23:35:00+08:00"
    assert manifest[0]["frequency"] == "realtime"


def test_enrich_preserves_existing_nonempty_fields() -> None:
    manifest = [{"id": "sg_datagov_coe_bidding", "url": "https://data.gov.sg/api/action/datastore_search?resource_id=d_X", "title": "my custom title"}]
    enrich_sg_metadata(manifest, static_policy())
    assert manifest[0]["title"] == "my custom title"
    assert manifest[0]["description"] == "COE description"
