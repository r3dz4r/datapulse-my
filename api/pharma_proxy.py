"""Narrow NPRA proxy: fixed internal target, isolated headers and bounded reads."""
from __future__ import annotations

import json
from http.client import HTTPConnection, HTTPSConnection
from urllib.parse import quote, urlsplit

ALLOWED = {"health", "changes", "product", "manufacturer", "importer"}
MAX_RESPONSE_BYTES = 1024 * 1024


def fetch(base_url: str, internal_key: str, resource: str, identifier: str | None = None) -> tuple[int, object]:
    """Fetch one whitelisted resource using only the engine's credential."""
    if resource not in ALLOWED or (resource in {"product", "manufacturer", "importer"} and not identifier):
        raise ValueError("not found")
    if not internal_key:
        raise RuntimeError("engine unavailable")
    parsed = urlsplit(base_url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise RuntimeError("invalid engine URL")
    connection_class = HTTPSConnection if parsed.scheme == "https" else HTTPConnection
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    prefix = parsed.path.rstrip("/")
    path = prefix + "/" + resource + ("/" + quote(identifier, safe="") if identifier else "")
    connection = connection_class(parsed.hostname, port, timeout=5)
    try:
        connection.request("GET", path, headers={"Accept": "application/json", "X-API-Key": internal_key})
        response = connection.getresponse()
        raw = response.read(MAX_RESPONSE_BYTES + 1)
        if len(raw) > MAX_RESPONSE_BYTES:
            raise RuntimeError("upstream response too large")
        if response.status >= 500:
            raise RuntimeError("upstream failure")
        if "application/json" not in response.getheader("Content-Type", ""):
            raise RuntimeError("invalid upstream response")
        return response.status, json.loads(raw)
    finally:
        connection.close()
