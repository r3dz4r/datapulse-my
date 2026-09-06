#!/usr/bin/env python3
"""Fail-closed, read-only probe for an allowlisted ArcGIS FeatureServer layer."""

from __future__ import annotations

import argparse
import hashlib
import ipaddress
import json
import socket
from collections import Counter
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any, Protocol
from urllib.parse import urlsplit, urlunsplit

import requests


class ArcGISProbeError(ValueError):
    """A fail-closed source or transport validation error."""


class Response(Protocol):
    status_code: int
    headers: Mapping[str, str]

    def iter_content(self, chunk_size: int) -> Any: ...


class Session(Protocol):
    def get(self, url: str, *, params: dict[str, str], **kwargs: Any) -> Response: ...


def _canonical_url(raw_url: str, allowed_host: str) -> str:
    parsed = urlsplit(raw_url)
    if (
        parsed.scheme != "https"
        or parsed.hostname != allowed_host
        or parsed.username
        or parsed.password
        or parsed.port not in (None, 443)
        or parsed.query
        or parsed.fragment
    ):
        raise ArcGISProbeError("source URL does not match the allowlisted HTTPS host")
    try:
        ipaddress.ip_address(allowed_host)
    except ValueError:
        pass
    else:
        raise ArcGISProbeError("IP literal destinations are not allowed")
    parts = [part for part in parsed.path.split("/") if part]
    if len(parts) < 2 or parts[-2].lower() != "featureserver" or not parts[-1].isdigit():
        raise ArcGISProbeError("source URL must identify one numeric FeatureServer layer")
    forbidden = {"addfeatures", "updatefeatures", "deletefeatures", "applyedits", "append", "upload", "create"}
    if forbidden.intersection(part.lower() for part in parts):
        raise ArcGISProbeError("source URL contains an ArcGIS mutation operation")
    return urlunsplit(("https", allowed_host, parsed.path.rstrip("/"), "", ""))


def _public_resolution(host: str) -> None:
    try:
        addresses = socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
    except OSError as exc:
        raise ArcGISProbeError("allowlisted host did not resolve") from exc
    if not addresses or any(not ipaddress.ip_address(row[4][0]).is_global for row in addresses):
        raise ArcGISProbeError("allowlisted host resolves to a non-public address")


def _read_json(response: Response, max_bytes: int) -> dict[str, Any]:
    if response.status_code != 200:
        raise ArcGISProbeError(f"read-only GET returned HTTP {response.status_code}")
    content_type = response.headers.get("Content-Type", "").lower()
    if "json" not in content_type:
        raise ArcGISProbeError("ArcGIS response was not JSON")
    chunks: list[bytes] = []
    total = 0
    for chunk in response.iter_content(chunk_size=16_384):
        if not chunk:
            continue
        total += len(chunk)
        if total > max_bytes:
            raise ArcGISProbeError("ArcGIS response exceeded the configured byte limit")
        chunks.append(chunk)
    try:
        payload = json.loads(b"".join(chunks).decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ArcGISProbeError("ArcGIS response contained malformed JSON") from exc
    if not isinstance(payload, dict) or "error" in payload:
        raise ArcGISProbeError("ArcGIS response was an error or non-data shell")
    return payload


def _get(session: Session, url: str, params: dict[str, str], *, timeout: int, max_bytes: int) -> dict[str, Any]:
    response = session.get(
        url,
        params=params,
        timeout=timeout,
        allow_redirects=False,
        stream=True,
        headers={"Accept": "application/json", "User-Agent": "DataPulseMY/1.0 (+https://www.data-pulse.my/about)"},
    )
    if 300 <= response.status_code < 400:
        raise ArcGISProbeError("ArcGIS redirects are not permitted")
    return _read_json(response, max_bytes)


def _iso_observation(value: object) -> str | None:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return None
    try:
        return datetime.fromtimestamp(value / 1000, UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    except (OverflowError, OSError, ValueError):
        return None


def _fingerprint(fields: list[dict[str, str]]) -> str:
    payload = json.dumps(fields, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def probe_feature_layer(url: str, config: dict[str, Any], *, session: Session | None = None) -> dict[str, Any]:
    """Probe metadata, count, and a small field-minimised sample using GET only."""
    allowed_host = config["allowed-host"]
    canonical_url = _canonical_url(url, allowed_host)
    _public_resolution(allowed_host)
    required_fields = config["required-fields"]
    allowed_fields = config["allowed-fields"]
    if not required_fields or len(set(required_fields)) != len(required_fields):
        raise ArcGISProbeError("required field allowlist is invalid")
    if not set(required_fields).issubset(allowed_fields):
        raise ArcGISProbeError("required fields must be included in the allowed schema")
    client: Session = session or requests.Session()
    timeout = config["timeout-seconds"]
    max_bytes = config["max-response-bytes"]
    sample_limit = config["sample-limit"]
    metadata = _get(client, canonical_url, {"f": "json"}, timeout=timeout, max_bytes=max_bytes)
    if metadata.get("name") != config["expected-layer-name"] or metadata.get("type") != "Feature Layer":
        raise ArcGISProbeError("ArcGIS layer identity did not match the policy")
    raw_fields = metadata.get("fields")
    if not isinstance(raw_fields, list):
        raise ArcGISProbeError("ArcGIS metadata omitted a field schema")
    field_schema: list[dict[str, str]] = []
    for field in raw_fields:
        if not isinstance(field, dict) or not isinstance(field.get("name"), str) or not isinstance(field.get("type"), str):
            raise ArcGISProbeError("ArcGIS metadata contained a malformed field schema")
        field_schema.append({"name": field["name"], "type": field["type"]})
    names = [field["name"] for field in field_schema]
    unexpected = sorted(set(names) - set(allowed_fields))
    missing = sorted(set(required_fields) - set(names))
    if unexpected:
        raise ArcGISProbeError("ArcGIS schema contains unapproved field(s): " + ", ".join(unexpected))
    if missing:
        raise ArcGISProbeError("ArcGIS schema is missing required field(s): " + ", ".join(missing))
    count_payload = _get(client, canonical_url + "/query", {"f": "json", "where": "1=1", "returnCountOnly": "true"}, timeout=timeout, max_bytes=max_bytes)
    count = count_payload.get("count")
    if not isinstance(count, int) or isinstance(count, bool) or not 0 <= count <= config["max-record-count"]:
        raise ArcGISProbeError("ArcGIS count was invalid or exceeded the configured bound")
    sample = _get(client, canonical_url + "/query", {
        "f": "json", "where": "1=1", "outFields": ",".join(required_fields), "returnGeometry": "false",
        "resultRecordCount": str(sample_limit), "orderByFields": "objectid ASC",
    }, timeout=timeout, max_bytes=max_bytes)
    features = sample.get("features")
    if not isinstance(features, list) or len(features) > sample_limit:
        raise ArcGISProbeError("ArcGIS sample was absent or exceeded the configured bound")
    observations: list[str] = []
    active = Counter({"true": 0, "false": 0, "missing": 0})
    for feature in features:
        attributes = feature.get("attributes") if isinstance(feature, dict) else None
        if not isinstance(attributes, dict) or not set(attributes).issubset(required_fields):
            raise ArcGISProbeError("ArcGIS sample exceeded the field allowlist")
        observation = _iso_observation(attributes.get("last_updated"))
        if observation:
            observations.append(observation)
        active_value = attributes.get("active")
        active[str(active_value).lower() if str(active_value).lower() in {"true", "false"} else "missing"] += 1
    return {
        "request_url": canonical_url,
        "access_method": "ArcGIS FeatureServer read-only GET/query",
        "http_status": 200,
        "record_count": count,
        "column_count": len(field_schema),
        "schema_fingerprint": _fingerprint(field_schema),
        "content_freshness_date": max(observations) if observations else None,
        "active_rows": dict(active),
        "sample_rows": len(features),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", required=True)
    parser.add_argument("--config", required=True, help="ArcGIS policy object encoded as JSON")
    args = parser.parse_args()
    try:
        config = json.loads(args.config)
        if not isinstance(config, dict):
            raise ArcGISProbeError("ArcGIS policy configuration must be an object")
        print(json.dumps(probe_feature_layer(args.url, config), sort_keys=True))
        return 0
    except (ArcGISProbeError, requests.RequestException, json.JSONDecodeError, KeyError, TypeError) as exc:
        print(f"arcgis probe failed closed: {exc}", flush=True)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
