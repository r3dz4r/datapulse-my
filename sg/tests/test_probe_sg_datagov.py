from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import httpx
import pytest
from jsonschema import Draft202012Validator, FormatChecker

from sg import probe_sg_datagov as probe


class FakeResponse:
    def __init__(self, payload: Any, status: int = 200) -> None:
        self.payload = payload
        self.status_code = status

    def json(self) -> Any:
        if isinstance(self.payload, BaseException):
            raise self.payload
        return self.payload


class FakeTransport:
    def __init__(self, responses: list[FakeResponse | BaseException]) -> None:
        self.responses = responses
        self.calls: list[tuple[str, dict[str, str], float]] = []

    def get(self, url: str, *, headers: dict[str, str], timeout: float) -> FakeResponse:
        self.calls.append((url, headers, timeout))
        item = self.responses.pop(0)
        if isinstance(item, BaseException):
            raise item
        return item


def coe_payload(records: int = 4) -> dict[str, Any]:
    return {"result": {"total": 1970, "fields": [{"id": "month"}, {"id": "quota"}], "records": [{"month": "2026-09", "quota": number} for number in range(records)]}}


def hdb_payload(rows: int = 4) -> dict[str, Any]:
    return {"data": {"totalNumRows": 100, "rows": [{"month": "2026-09", "resale_price": number} for number in range(rows)]}}


def metadata_payload() -> dict[str, Any]:
    return {"data": {"lastUpdated": "2026-09-07T02:15:00+08:00"}}


def realtime_payload() -> dict[str, Any]:
    return {"items": [{"timestamp": "2026-09-07T02:15:00+08:00", "readings": []}]}


@pytest.mark.parametrize(("function", "payload", "source_id"), [
    (probe.probe_coe_bidding, coe_payload(), "sg_datagov_coe_bidding"),
    (probe.probe_hdb_resale_prices, hdb_payload(), "sg_datagov_hdb_resale_prices"),
    (probe.probe_hdb_metadata, metadata_payload(), "sg_datagov_hdb_metadata"),
    (probe.probe_taxi_availability, realtime_payload(), "sg_datagov_taxi_availability"),
    (probe.probe_weather_readings, realtime_payload(), "sg_datagov_weather_readings"),
])
def test_each_family_returns_the_documented_success_shape(function: Any, payload: dict[str, Any], source_id: str) -> None:
    result = function(transport=FakeTransport([FakeResponse(payload)]))
    assert set(result) == probe.RESULT_FIELDS
    assert result["source_id"] == source_id
    assert result["probe_outcome"] == "success"
    assert result["http_status"] == 200
    assert result["error_message"] is None


@pytest.mark.parametrize("function", [probe.probe_coe_bidding, probe.probe_hdb_resale_prices, probe.probe_hdb_metadata, probe.probe_taxi_availability, probe.probe_weather_readings])
def test_http_failure_is_an_error(function: Any) -> None:
    result = function(transport=FakeTransport([FakeResponse({}, 500)]))
    assert result["probe_outcome"] == "error"
    assert result["http_status"] == 500
    assert "500" in result["error_message"]


@pytest.mark.parametrize("function", [probe.probe_coe_bidding, probe.probe_hdb_resale_prices, probe.probe_hdb_metadata, probe.probe_taxi_availability, probe.probe_weather_readings])
def test_timeout_is_distinct_from_other_transport_errors(function: Any) -> None:
    result = function(transport=FakeTransport([httpx.ReadTimeout("late")]))
    assert result["probe_outcome"] == "timeout"
    assert result["http_status"] == 0


@pytest.mark.parametrize("function", [probe.probe_coe_bidding, probe.probe_hdb_resale_prices, probe.probe_hdb_metadata, probe.probe_taxi_availability, probe.probe_weather_readings])
def test_malformed_json_is_an_error(function: Any) -> None:
    result = function(transport=FakeTransport([FakeResponse(json.JSONDecodeError("bad", "x", 0))]))
    assert result["probe_outcome"] == "error"
    assert result["http_status"] == 200
    assert result["error_message"].startswith("malformed JSON")


def test_schema_fingerprint_is_deterministic_and_order_independent() -> None:
    assert probe.schema_fingerprint(["month", "quota"]) == probe.schema_fingerprint(["quota", "month", "month"])


def test_schema_fingerprint_changes_when_columns_change() -> None:
    assert probe.schema_fingerprint(["month"]) != probe.schema_fingerprint(["month", "quota"])


@pytest.mark.parametrize(("source", "expected"), [("2026-09", "2026-09-01T00:00:00Z"), ("2026-09-07", "2026-09-07T00:00:00Z"), ("2026-09-07T02:15:00+08:00", "2026-09-07T02:15:00+08:00"), ("not-a-date", None)])
def test_source_freshness_is_normalized_to_iso_datetime(source: str, expected: str | None) -> None:
    assert probe._iso_datetime(source) == expected


@pytest.mark.parametrize(("function", "payload"), [(probe.probe_coe_bidding, coe_payload(9)), (probe.probe_hdb_resale_prices, hdb_payload(9))])
def test_tabular_samples_are_capped_at_three(function: Any, payload: dict[str, Any]) -> None:
    result = function(transport=FakeTransport([FakeResponse(payload)]))
    assert len(result["sample_rows"]) == 3


def test_coe_uses_a_bounded_query_url() -> None:
    transport = FakeTransport([FakeResponse(coe_payload())])
    probe.probe_coe_bidding(transport=transport)
    assert transport.calls[0][0] == probe.COE_URL
    assert "limit=3" in transport.calls[0][0]


def test_hdb_uses_a_bounded_query_url() -> None:
    transport = FakeTransport([FakeResponse(hdb_payload())])
    probe.probe_hdb_resale_prices(transport=transport)
    assert transport.calls[0][0] == probe.HDB_ROWS_URL
    assert "limit=3" in transport.calls[0][0]


def test_api_key_is_sent_as_header_only(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SG_DATAGOV_API_KEY", "not-in-output")
    transport = FakeTransport([FakeResponse(coe_payload())])
    result = probe.probe_coe_bidding(transport=transport)
    assert transport.calls[0][1]["x-api-key"] == "not-in-output"
    assert "not-in-output" not in json.dumps(result)


def test_transport_error_redacts_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SG_DATAGOV_API_KEY", "secret-value")
    result = probe.probe_coe_bidding(transport=FakeTransport([httpx.ConnectError("secret-value")]))
    assert result["error_message"] == "[REDACTED]"


@pytest.mark.parametrize("endpoint", ["air-temperature", "rainfall", "relative-humidity"])
def test_weather_adapter_supports_all_documented_endpoints(endpoint: str) -> None:
    result = probe.probe_weather_readings(endpoint, transport=FakeTransport([FakeResponse(realtime_payload())]))
    assert result["probe_outcome"] == "success"
    assert result["request_url"].endswith(endpoint)


def test_unsupported_weather_endpoint_fails_closed_without_network() -> None:
    result = probe.probe_weather_readings("wind-speed")
    assert result["probe_outcome"] == "error"
    assert result["http_status"] == 0


def test_run_all_waits_between_each_family() -> None:
    sleeps: list[float] = []
    transport = FakeTransport([FakeResponse(coe_payload()), FakeResponse(hdb_payload()), FakeResponse(metadata_payload()), FakeResponse(realtime_payload()), FakeResponse(realtime_payload())])
    output = probe.run_all(transport=transport, sleep=sleeps.append)
    assert len(output["families"]) == 5
    assert sleeps == [2.0, 2.0, 2.0, 2.0]


def test_full_run_validates_against_its_json_schema() -> None:
    transport = FakeTransport([FakeResponse(coe_payload()), FakeResponse(hdb_payload()), FakeResponse(metadata_payload()), FakeResponse(realtime_payload()), FakeResponse(realtime_payload())])
    result = probe.run_all(transport=transport, sleep=lambda _: None)
    schema = json.loads((Path(__file__).parents[1] / "schema" / "sg_probe.schema.json").read_text())
    Draft202012Validator(schema, format_checker=FormatChecker()).validate(result)


def test_main_writes_the_documented_shape(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    output = {"schema": "datapulse/v1/sg-probe", "probe_run_at": "2026-09-07T00:00:00Z", "families": []}
    destination = tmp_path / "result.json"
    monkeypatch.setattr(probe, "run_all", lambda: output)
    monkeypatch.setattr(sys, "argv", ["probe", "--out", str(destination)])
    assert probe.main() == 0
    assert json.loads(destination.read_text()) == output


def test_realtime_families_do_not_claim_tabular_schema() -> None:
    result = probe.probe_taxi_availability(transport=FakeTransport([FakeResponse(realtime_payload())]))
    assert result["record_count"] is None
    assert result["schema_fingerprint"] is None
    assert result["sample_rows"] == []
