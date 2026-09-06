"""Bounded, read-only probes for selected Singapore data.gov.sg source families."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import time
from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol

import httpx

TIMEOUT_SECONDS = 20.0
SAMPLE_LIMIT = 3
FAMILY_DELAY_SECONDS = 2.0
HDB_DATASET_ID = "d_8b84c4ee58e3cfc0ece0d773c8ca6abc"
COE_RESOURCE_ID = "d_69b3380ad7e51aff3a7dcc84eba52b8a"

COE_URL = "https://data.gov.sg/api/action/datastore_search?resource_id=" + COE_RESOURCE_ID + "&limit=3&sort=month%20desc"
HDB_ROWS_URL = "https://api-production.data.gov.sg/v2/public/api/datasets/" + HDB_DATASET_ID + "/list-rows?limit=3"
HDB_METADATA_URL = "https://api-production.data.gov.sg/v2/public/api/datasets/" + HDB_DATASET_ID + "/metadata"
TAXI_URL = "https://api.data.gov.sg/v1/transport/taxi-availability"
WEATHER_URL = "https://api.data.gov.sg/v1/environment/air-temperature"

RESULT_FIELDS = {
    "source_id", "request_url", "http_status", "probe_outcome", "observed_at",
    "record_count", "content_freshness_date", "schema_fingerprint", "sample_rows", "error_message",
}


class JsonResponse(Protocol):
    status_code: int

    def json(self) -> Any: ...


class Transport(Protocol):
    def get(self, url: str, *, headers: Mapping[str, str], timeout: float) -> JsonResponse: ...


def _now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def schema_fingerprint(columns: list[str]) -> str:
    """Return the stable SHA-256 fingerprint of a tabular column-name set."""
    canonical = json.dumps(sorted(set(columns)), separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def _headers() -> dict[str, str]:
    headers = {"Accept": "application/json", "User-Agent": "DataPulseMY-SGProbe/1.0"}
    if api_key := os.getenv("SG_DATAGOV_API_KEY"):
        headers["x-api-key"] = api_key
    return headers


def _redacted_message(exc: BaseException) -> str:
    message = str(exc) or exc.__class__.__name__
    for secret in (os.getenv("SG_DATAGOV_API_KEY"),):
        if secret:
            message = message.replace(secret, "[REDACTED]")
    return message[:500]


def _result(source_id: str, request_url: str, *, status: int = 0, outcome: str = "error",
            record_count: int | None = None, freshness: str | None = None,
            fingerprint: str | None = None, samples: list[dict[str, Any]] | None = None,
            error: str | None = None) -> dict[str, Any]:
    return {
        "source_id": source_id, "request_url": request_url, "http_status": status,
        "probe_outcome": outcome, "observed_at": _now(), "record_count": record_count,
        "content_freshness_date": freshness, "schema_fingerprint": fingerprint,
        "sample_rows": (samples or [])[:SAMPLE_LIMIT], "error_message": error,
    }


def _as_rows(value: object) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)][:SAMPLE_LIMIT]


def _first_string(payload: object, names: tuple[str, ...]) -> str | None:
    if isinstance(payload, dict):
        for name in names:
            value = payload.get(name)
            if isinstance(value, str) and value:
                return value
        for value in payload.values():
            found = _first_string(value, names)
            if found:
                return found
    if isinstance(payload, list):
        for value in payload:
            found = _first_string(value, names)
            if found:
                return found
    return None


def _iso_datetime(value: str | None) -> str | None:
    """Convert source dates to the full ISO-8601 timestamps required by output."""
    if value is None:
        return None
    if re.fullmatch(r"\d{4}-\d{2}", value):
        return value + "-01T00:00:00Z"
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        return value + "T00:00:00Z"
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return value


def _fetch(source_id: str, url: str, parser: Callable[[dict[str, Any]], tuple[int | None, str | None, str | None, list[dict[str, Any]]]],
           *, transport: Transport | None = None) -> dict[str, Any]:
    client: Transport = transport or httpx.Client(follow_redirects=False)
    try:
        response = client.get(url, headers=_headers(), timeout=TIMEOUT_SECONDS)
        status = int(response.status_code)
        if status != 200:
            return _result(source_id, url, status=status, error=f"GET returned HTTP {status}")
        try:
            payload = response.json()
        except (json.JSONDecodeError, ValueError) as exc:
            return _result(source_id, url, status=status, error=f"malformed JSON: {_redacted_message(exc)}")
        if not isinstance(payload, dict):
            return _result(source_id, url, status=status, error="malformed JSON: expected object")
        count, freshness, fingerprint, samples = parser(payload)
        return _result(source_id, url, status=status, outcome="success", record_count=count,
                       freshness=freshness, fingerprint=fingerprint, samples=samples)
    except (httpx.TimeoutException, TimeoutError) as exc:
        return _result(source_id, url, outcome="timeout", error=_redacted_message(exc))
    except (httpx.HTTPError, OSError, TypeError, KeyError, ValueError) as exc:
        return _result(source_id, url, error=_redacted_message(exc))
    finally:
        if transport is None and isinstance(client, httpx.Client):
            client.close()


def probe_coe_bidding(*, transport: Transport | None = None) -> dict[str, Any]:
    def parse(payload: dict[str, Any]) -> tuple[int | None, str | None, str | None, list[dict[str, Any]]]:
        result = payload.get("result")
        if not isinstance(result, dict):
            raise ValueError("COE response omitted result")
        rows = _as_rows(result.get("records"))
        fields = result.get("fields")
        columns = [field["id"] for field in fields if isinstance(field, dict) and isinstance(field.get("id"), str)] if isinstance(fields, list) else []
        count = result.get("total")
        if not isinstance(count, int) or isinstance(count, bool):
            count = None
        return count, _iso_datetime(_first_string(rows, ("month",))), schema_fingerprint(columns) if columns else None, rows
    return _fetch("sg_datagov_coe_bidding", COE_URL, parse, transport=transport)


def probe_hdb_resale_prices(*, transport: Transport | None = None) -> dict[str, Any]:
    def parse(payload: dict[str, Any]) -> tuple[int | None, str | None, str | None, list[dict[str, Any]]]:
        data = payload.get("data", payload)
        if not isinstance(data, dict):
            raise ValueError("HDB response omitted data")
        rows = _as_rows(data.get("rows") or data.get("records"))
        count = data.get("total") or data.get("totalNumRows")
        if not isinstance(count, int) or isinstance(count, bool):
            count = None
        columns = sorted({key for row in rows for key in row})
        return count, None, schema_fingerprint(columns) if columns else None, rows
    return _fetch("sg_datagov_hdb_resale_prices", HDB_ROWS_URL, parse, transport=transport)


def probe_hdb_metadata(*, transport: Transport | None = None) -> dict[str, Any]:
    def parse(payload: dict[str, Any]) -> tuple[int | None, str | None, str | None, list[dict[str, Any]]]:
        return None, _iso_datetime(_first_string(payload, ("lastUpdated", "last_updated", "updatedAt", "updated_at"))), None, []
    return _fetch("sg_datagov_hdb_metadata", HDB_METADATA_URL, parse, transport=transport)


def probe_taxi_availability(*, transport: Transport | None = None) -> dict[str, Any]:
    def parse(payload: dict[str, Any]) -> tuple[int | None, str | None, str | None, list[dict[str, Any]]]:
        return None, _iso_datetime(_first_string(payload, ("timestamp", "updated_at", "updatedAt"))), None, []
    return _fetch("sg_datagov_taxi_availability", TAXI_URL, parse, transport=transport)


def probe_weather_readings(endpoint: str = "air-temperature", *, transport: Transport | None = None) -> dict[str, Any]:
    if endpoint not in {"air-temperature", "rainfall", "relative-humidity"}:
        return _result("sg_datagov_weather_readings", f"https://api.data.gov.sg/v1/environment/{endpoint}", error="unsupported weather endpoint")
    url = f"https://api.data.gov.sg/v1/environment/{endpoint}"
    def parse(payload: dict[str, Any]) -> tuple[int | None, str | None, str | None, list[dict[str, Any]]]:
        return None, _iso_datetime(_first_string(payload, ("timestamp", "updated_at", "updatedAt"))), None, []
    return _fetch("sg_datagov_weather_readings", url, parse, transport=transport)


def run_all(*, transport: Transport | None = None, sleep: Callable[[float], None] = time.sleep) -> dict[str, Any]:
    probes = (probe_coe_bidding, probe_hdb_resale_prices, probe_hdb_metadata, probe_taxi_availability, probe_weather_readings)
    families: list[dict[str, Any]] = []
    for index, probe in enumerate(probes):
        families.append(probe(transport=transport))
        if index < len(probes) - 1:
            sleep(FAMILY_DELAY_SECONDS)
    return {"schema": "datapulse/v1/sg-probe", "probe_run_at": _now(), "families": families}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True, help="write probe-run JSON to this path")
    args = parser.parse_args()
    result = run_all()
    args.out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
