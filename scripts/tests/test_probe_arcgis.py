from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.probe_arcgis import ArcGISProbeError, probe_feature_layer


ROOT = Path(__file__).resolve().parents[2]
CHECK_SCRIPT = ROOT / "scripts/check.sh"


class Response:
    def __init__(self, payload: dict, *, status_code: int = 200) -> None:
        self.payload = payload
        self.status_code = status_code
        self.headers = {"Content-Type": "application/json"}

    def iter_content(self, chunk_size: int):  # type: ignore[no-untyped-def]
        yield json.dumps(self.payload).encode("utf-8")


class Session:
    def __init__(self, responses: list[Response]) -> None:
        self.responses = responses
        self.calls: list[tuple[str, dict[str, str]]] = []

    def get(self, url: str, *, params: dict[str, str], **_: object) -> Response:
        self.calls.append((url, params))
        return self.responses.pop(0)


def mbpp_config() -> dict:
    return json.loads((ROOT / "scripts/probe-policy.json").read_text())["datasets"][
        "mbpp_weather_stations"
    ]["arcgis-feature"]


def metadata(*, extra_field: str | None = None) -> dict:
    fields = [
        {"name": name, "type": "esriFieldTypeString"}
        for name in mbpp_config()["allowed-fields"]
    ]
    if extra_field:
        fields.append({"name": extra_field, "type": "esriFieldTypeString"})
    return {"name": "Weather Station", "type": "Feature Layer", "fields": fields}


def test_mbpp_feature_probe_uses_only_bounded_read_only_get_queries(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("scripts.probe_arcgis._public_resolution", lambda _: None)
    config = mbpp_config()
    session = Session(
        [
            Response(metadata()),
            Response({"count": 28}),
            Response(
                {
                    "features": [
                        {"attributes": {
                            "station_id": 1,
                            "station_name": "MBPP test station",
                            "city": "George Town",
                            "region": "Pulau Pinang",
                            "country": "Malaysia",
                            "latitude": 5.4,
                            "longitude": 100.3,
                            "rainrate_mm": 0,
                            "wind_speed_last": 0,
                            "active": "false",
                            "last_updated": 1788692846000,
                            "temperature_out_last_c": 30,
                            "humidity_out_last": 70,
                            "rainfall_day": 0,
                        }}
                    ]
                }
            ),
        ]
    )

    result = probe_feature_layer(
        "https://vip.mbpp.gov.my/vipserver/rest/services/Weather_Station/FeatureServer/50",
        config,
        session=session,
    )

    assert result["record_count"] == 28
    assert result["content_freshness_date"] == "2026-09-06T11:07:26Z"
    assert result["active_rows"] == {"true": 0, "false": 1, "missing": 0}
    assert result["schema_fingerprint"]
    assert len(session.calls) == 3
    assert all(url.startswith("https://vip.mbpp.gov.my/") for url, _ in session.calls)
    assert session.calls[1][1] == {"f": "json", "where": "1=1", "returnCountOnly": "true"}
    assert session.calls[2][1]["returnGeometry"] == "false"
    assert session.calls[2][1]["resultRecordCount"] == "3"
    assert set(session.calls[2][1]["outFields"].split(",")) == set(config["required-fields"])


def test_mbpp_feature_probe_fails_closed_when_an_unapproved_field_appears(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("scripts.probe_arcgis._public_resolution", lambda _: None)
    config = mbpp_config()
    session = Session([Response(metadata(extra_field="email_address"))])

    with pytest.raises(ArcGISProbeError, match="unapproved field"):
        probe_feature_layer(
            "https://vip.mbpp.gov.my/vipserver/rest/services/Weather_Station/FeatureServer/50",
            config,
            session=session,
        )


def test_health_projection_preserves_arcgis_evidence_and_timestamp_freshness() -> None:
    source = CHECK_SCRIPT.read_text(encoding="utf-8")

    assert "def content_epoch($value):" in source
    assert "schema_fingerprint: ($probe.schema_fingerprint // null)" in source
    assert "sample_rows: ($probe.sample_rows // null)" in source
    assert "active_rows: ($probe.active_rows // null)" in source


def test_data_report_generator_seeds_newly_promoted_dataset_reports() -> None:
    source = (ROOT / "scripts/gen_data_reports.sh").read_text(encoding="utf-8")

    assert "every public derivative is generator-owned" in source
