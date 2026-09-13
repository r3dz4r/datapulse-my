#!/usr/bin/env python3
"""Publish the dashboard health projection to Cloudflare KV."""

from __future__ import annotations

import argparse
import http.client
import json
import os
import shlex
import signal
import sys
from pathlib import Path
from typing import Any
from urllib.parse import quote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_HEALTH = ROOT / "health/latest.json"
TOKEN_ENV = "DATAPULSE_KV_WRITE"
TOKEN_FALLBACK = Path("/home/redza/.hermes/.env")
ACCOUNT_ID_PREFIX = "525ef763"
NAMESPACE_ID = "043b3f20337f4744a21de947f35c67f0"
DEFAULT_API_BASE = "https://api.cloudflare.com/client/v4"
KEY = "health-index.json"
VERIFY_KEY = "health-index.test.json"
CONNECT_TIMEOUT_SECONDS = 5.0
TOTAL_TIMEOUT_SECONDS = 15.0
DATASET_KEYS = (
    "dataset_id",
    "status",
    "content_freshness_date",
    "last_checked",
    "access_method",
    "record_count",
    "staleness_status",
)


class PublishError(RuntimeError):
    """An expected publication error whose text is safe to log."""


class RequestDeadlineExceeded(TimeoutError):
    """Raised when an HTTP request exceeds its end-to-end deadline."""


def build_projection(health_path: Path) -> bytes:
    """Return the stable, allowlisted dashboard projection for one health document."""
    document = json.loads(health_path.read_text(encoding="utf-8"))
    if not isinstance(document, dict):
        raise PublishError("health document is not an object")
    datasets = document.get("datasets")
    if not isinstance(datasets, list):
        raise PublishError("health document datasets is not a list")
    try:
        projection: dict[str, Any] = {
            "schema": document["schema"],
            "checked_at": document["checked_at"],
            "_trust_summary": document["_trust_summary"],
            "datasets": [],
        }
    except KeyError as exc:
        raise PublishError(f"health document is missing top-level {exc.args[0]!r}") from exc
    for row in datasets:
        if not isinstance(row, dict):
            raise PublishError("health document contains a non-object dataset row")
        projection["datasets"].append({key: row.get(key) for key in DATASET_KEYS})
    return json.dumps(
        projection, ensure_ascii=False, separators=(",", ":"), sort_keys=True
    ).encode("utf-8")


def read_token() -> str:
    """Read the KV credential without ever returning it to output."""
    if TOKEN_ENV in os.environ:
        return os.environ[TOKEN_ENV]
    try:
        lines = TOKEN_FALLBACK.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise PublishError(f"KV credential unavailable: cannot read fallback env file ({exc.__class__.__name__})") from exc
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("export "):
            stripped = stripped[7:].lstrip()
        name, separator, value = stripped.partition("=")
        if name.strip() != TOKEN_ENV or not separator:
            continue
        try:
            values = shlex.split(value, comments=True)
        except ValueError as exc:
            raise PublishError("KV credential unavailable: fallback env file has invalid quoting") from exc
        if len(values) == 1 and values[0]:
            return values[0]
        raise PublishError("KV credential unavailable: fallback env file has an empty token")
    raise PublishError("KV credential unavailable: token is unset")


def _deadline_handler(_signum: int, _frame: object) -> None:
    raise RequestDeadlineExceeded("total timeout")


def request_bytes(method: str, url: str, token: str, body: bytes | None = None) -> tuple[int, bytes]:
    """Make one bounded HTTP request with separate connect and total limits."""
    parsed = urlsplit(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise PublishError("invalid KV API endpoint")
    connection_type = http.client.HTTPSConnection if parsed.scheme == "https" else http.client.HTTPConnection
    connection = connection_type(parsed.hostname, parsed.port, timeout=CONNECT_TIMEOUT_SECONDS)
    old_handler = signal.signal(signal.SIGALRM, _deadline_handler)
    signal.setitimer(signal.ITIMER_REAL, TOTAL_TIMEOUT_SECONDS)
    try:
        path = parsed.path or "/"
        if parsed.query:
            path += f"?{parsed.query}"
        headers = {"Authorization": f"Bearer {token}"}
        if body is not None:
            headers["Content-Type"] = "application/json"
            headers["Content-Length"] = str(len(body))
        connection.request(method, path, body=body, headers=headers)
        response = connection.getresponse()
        payload = response.read()
        if not 200 <= response.status < 300:
            raise PublishError(f"HTTP {response.status}")
        return response.status, payload
    except RequestDeadlineExceeded:
        raise PublishError("total timeout") from None
    except (OSError, http.client.HTTPException) as exc:
        raise PublishError(f"{exc.__class__.__name__}: {exc}") from exc
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, old_handler)
        connection.close()


def _json_response(method: str, url: str, token: str) -> object:
    """Request and parse a Cloudflare JSON envelope without exposing its body."""
    status, body = request_bytes(method, url, token)
    try:
        envelope = json.loads(body)
    except json.JSONDecodeError as exc:
        raise PublishError(f"HTTP {status}: invalid JSON response") from exc
    if not isinstance(envelope, dict) or envelope.get("success") is not True:
        raise PublishError(f"HTTP {status}: Cloudflare API rejected request")
    return envelope.get("result")


def resolve_account_id(api_base: str, token: str) -> str:
    """Resolve the documented account-ID prefix to Cloudflare's complete account ID."""
    accounts = _json_response("GET", f"{api_base.rstrip('/')}/accounts", token)
    if not isinstance(accounts, list):
        raise PublishError("Cloudflare accounts response is not a list")
    matches = [
        account.get("id")
        for account in accounts
        if isinstance(account, dict)
        and isinstance(account.get("id"), str)
        and account["id"].startswith(ACCOUNT_ID_PREFIX)
    ]
    if len(matches) != 1:
        raise PublishError("Cloudflare account matching configured prefix was not found uniquely")
    return matches[0]


def key_url(api_base: str, account_id: str, key: str) -> str:
    """Return the verified Cloudflare KV value endpoint for one key."""
    return f"{api_base.rstrip('/')}/accounts/{account_id}/storage/kv/namespaces/{NAMESPACE_ID}/values/{quote(key, safe='')}"


def publish(api_base: str, token: str, key: str, payload: bytes) -> int:
    """Write one KV value and return its HTTP status."""
    account_id = resolve_account_id(api_base, token)
    status, _ = request_bytes("PUT", key_url(api_base, account_id, key), token, payload)
    return status


def verify(api_base: str, token: str, payload: bytes, expected_value: bytes | None = None) -> tuple[int, int, int]:
    """Round-trip an isolated verification key and remove it on success or failure."""
    write_status: int | None = None
    try:
        write_status = publish(api_base, token, VERIFY_KEY, payload)
        account_id = resolve_account_id(api_base, token)
        read_status, received = request_bytes("GET", key_url(api_base, account_id, VERIFY_KEY), token)
        expected = expected_value if expected_value is not None else payload
        if received != expected:
            raise PublishError("round-trip byte mismatch")
        delete_status, _ = request_bytes("DELETE", key_url(api_base, account_id, VERIFY_KEY), token)
        return write_status, read_status, delete_status
    except PublishError:
        if write_status is not None:
            try:
                account_id = resolve_account_id(api_base, token)
                request_bytes("DELETE", key_url(api_base, account_id, VERIFY_KEY), token)
            except PublishError:
                pass
        raise


def parser() -> argparse.ArgumentParser:
    """Build the command-line parser."""
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--health", type=Path, default=DEFAULT_HEALTH, help="health document to project")
    result.add_argument("--api-base", default=DEFAULT_API_BASE, help="Cloudflare API base URL")
    modes = result.add_mutually_exclusive_group()
    modes.add_argument("--dry-run", action="store_true", help="build but do not publish")
    modes.add_argument("--verify", action="store_true", help="round-trip a separate verification key")
    result.add_argument("--verify-expected-value", help=argparse.SUPPRESS)
    return result


def main(argv: list[str] | None = None) -> int:
    """Run the publisher; normal publication intentionally remains non-fatal."""
    args = parser().parse_args(argv)
    try:
        payload = build_projection(args.health)
    except (OSError, json.JSONDecodeError, PublishError) as exc:
        print(f"health index publish failed: {exc}", file=sys.stderr)
        return 1 if args.verify else 0
    if args.dry_run:
        print(f"health index dry-run: {len(payload)} bytes", file=sys.stderr)
        return 0
    try:
        token = read_token()
        if not token:
            raise PublishError("KV credential unavailable: token is empty")
        if args.verify:
            expected = args.verify_expected_value.encode("utf-8") if args.verify_expected_value is not None else None
            write_status, read_status, delete_status = verify(args.api_base, token, payload, expected)
            print(f"health index verify succeeded: {len(payload)} bytes (write HTTP {write_status}, read HTTP {read_status}, delete HTTP {delete_status})", file=sys.stderr)
        else:
            status = publish(args.api_base, token, KEY, payload)
            print(f"health index publish succeeded: {len(payload)} bytes (HTTP {status})", file=sys.stderr)
        return 0
    except PublishError as exc:
        prefix = "health index verify failed" if args.verify else "health index publish failed"
        print(f"{prefix}: {exc}", file=sys.stderr)
        return 1 if args.verify else 0


if __name__ == "__main__":
    raise SystemExit(main())
