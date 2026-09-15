#!/usr/bin/env python3
"""Publish the dashboard health projection to Cloudflare KV.

Exit codes: 0 means published (and is also used for dry runs and successful
verification); 1 is reserved for usage, setup, or internal errors; 2 means a
normal publication was attempted but failed; 3 means publication was skipped
because the cadence window was active.
"""

from __future__ import annotations

import argparse
import fcntl
import http.client
import json
import math
import os
import signal
import sys
import tempfile
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager, suppress
from pathlib import Path
from typing import Any
from urllib.parse import quote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_HEALTH = ROOT / "health/latest.json"
TOKEN_ENV = "DATAPULSE_KV_WRITE"
ACCOUNT_ID_PREFIX = "525ef763"
NAMESPACE_ID = "043b3f20337f4744a21de947f35c67f0"
DEFAULT_API_BASE = "https://api.cloudflare.com/client/v4"
KEY = "health-index.json"
VERIFY_KEY = "health-index.test.json"
HEALTH_ARTIFACTS = (
    "latest.json",
    "history_daily.json",
    "drift.json",
    "trends.json",
    "reconciliation.json",
    "evidence-coverage.json",
)

def _timeout_from_env(name: str, default: float) -> float:
    """Return a positive environment override, falling back safely on bad input."""
    try:
        value = float(os.environ.get(name, ""))
    except ValueError:
        return default
    return value if value > 0 else default


CONNECT_TIMEOUT_SECONDS = _timeout_from_env("DATAPULSE_KV_CONNECT_TIMEOUT", 10.0)
SOCKET_TIMEOUT_SECONDS = _timeout_from_env("DATAPULSE_KV_SOCKET_TIMEOUT", 45.0)
TOTAL_TIMEOUT_SECONDS = _timeout_from_env("DATAPULSE_KV_TOTAL_TIMEOUT", 90.0)
PUBLISH_INTERVAL_ENV = "DATAPULSE_KV_PUBLISH_INTERVAL_SECONDS"
PUBLISH_STATE_ENV = "DATAPULSE_KV_PUBLICATION_STATE"
DEFAULT_PUBLISH_INTERVAL_SECONDS = 30 * 60.0
SECONDS_PER_DAY = 24 * 60 * 60
MAX_PUBLISH_ATTEMPTS = 2
EXIT_SKIPPED = 3
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

    def __init__(self, message: str, *, retryable: bool = False) -> None:
        super().__init__(message)
        self.retryable = retryable


class RequestDeadlineExceeded(TimeoutError):
    """Raised when an HTTP request exceeds its end-to-end deadline."""


def publication_interval_seconds() -> float:
    """Return the configured positive publication cadence in seconds."""
    raw = os.environ.get(PUBLISH_INTERVAL_ENV)
    if raw is None:
        return DEFAULT_PUBLISH_INTERVAL_SECONDS
    try:
        interval = float(raw)
    except ValueError as exc:
        raise PublishError(f"{PUBLISH_INTERVAL_ENV} must be a positive number") from exc
    if not math.isfinite(interval) or interval <= 0:
        raise PublishError(f"{PUBLISH_INTERVAL_ENV} must be a positive number")
    return interval


def publication_state_path() -> Path:
    """Return the local, user-writable cadence state path."""
    configured = os.environ.get(PUBLISH_STATE_ENV)
    if configured:
        return Path(configured)
    state_home = Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local" / "state"))
    return state_home / "datapulse-my" / "publish_health_index.json"


def _read_last_attempted_at(state_path: Path) -> float | None:
    """Read a valid prior reservation; a missing or corrupt state is unreserved."""
    try:
        state = json.loads(state_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeDecodeError):
        return None
    value = state.get("last_attempted_at") if isinstance(state, dict) else None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    value = float(value)
    return value if math.isfinite(value) and value >= 0 else None


def _write_last_attempted_at(state_path: Path, now: float) -> None:
    """Durably replace the cadence state before a KV publication is attempted."""
    temporary: Path | None = None
    try:
        state_path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps({"last_attempted_at": now}, separators=(",", ":")).encode("utf-8")
        with tempfile.NamedTemporaryFile(dir=state_path.parent, prefix=f".{state_path.name}.", delete=False) as handle:
            temporary = Path(handle.name)
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, state_path)
        directory_fd = os.open(state_path.parent, os.O_RDONLY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    except OSError as exc:
        if temporary is not None:
            with suppress(OSError):
                temporary.unlink(missing_ok=True)
        raise PublishError(f"unable to persist KV publication state: {exc}") from exc


@contextmanager
def _publication_lock(state_path: Path) -> Iterator[None]:
    """Serialize local publishers so a cadence reservation cannot race."""
    try:
        state_path.parent.mkdir(parents=True, exist_ok=True)
        with (state_path.parent / f".{state_path.name}.lock").open("a+") as lock_file:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
            yield
    except OSError as exc:
        raise PublishError(f"unable to lock KV publication state: {exc}") from exc


def publish_with_cadence(
    state_path: Path,
    now: float,
    interval: float,
    publish_operation: Callable[[], tuple[int, int]],
) -> tuple[bool, int, int]:
    """Reserve an eligible window then publish, returning ``(skipped, written, unchanged)``."""
    if not math.isfinite(now) or now < 0 or not math.isfinite(interval) or interval <= 0:
        raise PublishError("publication cadence requires positive finite timestamps and interval")
    with _publication_lock(state_path):
        last_attempted_at = _read_last_attempted_at(state_path)
        if last_attempted_at is not None and now - last_attempted_at < interval:
            return True, 0, 0
        # Reserve before I/O so a crash after a PUT cannot create an unbounded retry loop.
        _write_last_attempted_at(state_path, now)
        written, unchanged = publish_operation()
    return False, written, unchanged


def max_daily_kv_writes(interval: float = DEFAULT_PUBLISH_INTERVAL_SECONDS) -> int:
    """Return the conservative maximum PUT count for one day at this cadence."""
    if not math.isfinite(interval) or interval <= 0:
        raise PublishError("publication interval must be a positive number")
    return math.ceil(SECONDS_PER_DAY / interval) * (len(HEALTH_ARTIFACTS) + 1) * MAX_PUBLISH_ATTEMPTS


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
    """Return the explicitly injected KV credential without logging it."""
    try:
        return os.environ[TOKEN_ENV]
    except KeyError:
        raise PublishError("KV credential unavailable: token is unset") from None


def _deadline_handler(_signum: int, _frame: object) -> None:
    raise RequestDeadlineExceeded("total timeout")


def request_bytes(
    method: str,
    url: str,
    token: str,
    body: bytes | None = None,
    allowed_statuses: tuple[int, ...] = (),
) -> tuple[int, bytes]:
    """Make one bounded HTTP request with separate connect and total limits."""
    parsed = urlsplit(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise PublishError("invalid KV API endpoint")
    connection_type = http.client.HTTPSConnection if parsed.scheme == "https" else http.client.HTTPConnection
    # Construct with the operation timeout: http.client applies this setting to
    # every socket operation.  Connect explicitly under the shorter budget.
    connection = connection_type(parsed.hostname, parsed.port, timeout=SOCKET_TIMEOUT_SECONDS)
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
        connection.timeout = CONNECT_TIMEOUT_SECONDS
        connection.connect()
        if connection.sock is not None:
            connection.sock.settimeout(SOCKET_TIMEOUT_SECONDS)
        connection.request(method, path, body=body, headers=headers)
        response = connection.getresponse()
        payload = response.read()
        if not 200 <= response.status < 300 and response.status not in allowed_statuses:
            raise PublishError(f"HTTP {response.status}")
        return response.status, payload
    except RequestDeadlineExceeded:
        raise PublishError("total timeout", retryable=True) from None
    except (OSError, http.client.HTTPException) as exc:
        raise PublishError(f"{exc.__class__.__name__}: {exc}", retryable=True) from exc
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


def read_value(api_base: str, account_id: str, token: str, key: str) -> bytes | None:
    """Return one KV value, or None when the key has not been published yet."""
    status, payload = request_bytes(
        "GET", key_url(api_base, account_id, key), token, allowed_statuses=(404,)
    )
    return None if status == 404 else payload


def publish_value(api_base: str, account_id: str, token: str, key: str, payload: bytes) -> int:
    """Write one KV value and return its HTTP status."""
    status, _ = request_bytes("PUT", key_url(api_base, account_id, key), token, payload)
    return status


def publish(api_base: str, token: str, key: str, payload: bytes) -> int:
    """Write one KV value and return its HTTP status."""
    account_id = resolve_account_id(api_base, token)
    return publish_value(api_base, account_id, token, key, payload)


def health_payloads(health_path: Path) -> dict[str, bytes]:
    """Return the dashboard projection and every health artifact keyed by URL path."""
    payloads = {KEY: build_projection(health_path)}
    health_dir = health_path.parent
    for name in HEALTH_ARTIFACTS:
        payloads[f"health/{name}"] = (health_dir / name).read_bytes()
    return payloads


def publish_unchanged_aware(api_base: str, token: str, payloads: dict[str, bytes]) -> tuple[int, int]:
    """Publish only changed values, returning (written, unchanged) counts."""
    account_id = resolve_account_id(api_base, token)
    written = unchanged = 0
    for key, payload in payloads.items():
        if read_value(api_base, account_id, token, key) == payload:
            unchanged += 1
            continue
        publish_value(api_base, account_id, token, key, payload)
        written += 1
    return written, unchanged


def _is_retryable_error(exc: BaseException) -> bool:
    """Return whether a failed HTTP attempt may safely be retried once."""
    return (
        isinstance(exc, (TimeoutError, OSError, http.client.HTTPException))
        or isinstance(exc, PublishError) and exc.retryable
    )


def publish_unchanged_aware_with_retry(
    api_base: str, token: str, payloads: dict[str, bytes]
) -> tuple[int, int]:
    """Publish once, retrying a transport failure only inside the total budget."""
    started = time.monotonic()
    for attempt in range(MAX_PUBLISH_ATTEMPTS):
        try:
            return publish_unchanged_aware(api_base, token, payloads)
        except Exception as exc:
            elapsed = time.monotonic() - started
            if (
                attempt + 1 >= MAX_PUBLISH_ATTEMPTS
                or not _is_retryable_error(exc)
                or elapsed >= TOTAL_TIMEOUT_SECONDS / 2
            ):
                raise
    raise AssertionError("unreachable retry loop")


def _failure_line(prefix: str, exc: BaseException, token: str | None = None) -> str:
    """Format one bounded, token-safe failure line for pipeline capture."""
    message = " ".join(str(exc).split())
    if token:
        message = message.replace(token, "[REDACTED]")
    return f"{prefix}: {exc.__class__.__name__}: {message[:200]}"


def verify(
    api_base: str,
    token: str,
    payload: bytes,
    expected_value: bytes | None = None,
    key: str = VERIFY_KEY,
) -> tuple[int, int, int]:
    """Round-trip an isolated verification key and remove it on success or failure."""
    write_status: int | None = None
    try:
        write_status = publish(api_base, token, key, payload)
        account_id = resolve_account_id(api_base, token)
        read_status, received = request_bytes("GET", key_url(api_base, account_id, key), token)
        expected = expected_value if expected_value is not None else payload
        if received != expected:
            raise PublishError("round-trip byte mismatch")
        delete_status, _ = request_bytes("DELETE", key_url(api_base, account_id, key), token)
        return write_status, read_status, delete_status
    except PublishError:
        if write_status is not None:
            try:
                account_id = resolve_account_id(api_base, token)
                request_bytes("DELETE", key_url(api_base, account_id, key), token)
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
    """Run the publisher and return its machine-readable outcome."""
    args = parser().parse_args(argv)
    try:
        payloads = health_payloads(args.health)
    except (OSError, json.JSONDecodeError, PublishError) as exc:
        print(_failure_line("health index publish failed", exc), file=sys.stderr)
        return 1
    if args.dry_run:
        print(f"health index dry-run: {len(payloads)} keys, {sum(map(len, payloads.values()))} bytes", file=sys.stderr)
        return 0
    token: str | None = None
    try:
        token = read_token()
        if not token:
            raise PublishError("KV credential unavailable: token is empty")
        if args.verify:
            expected = args.verify_expected_value.encode("utf-8") if args.verify_expected_value is not None else None
            for key, payload in payloads.items():
                verify_key = VERIFY_KEY if key == KEY else f"{key}.test"
                verify(args.api_base, token, payload, expected if key == KEY else None, verify_key)
            print(f"health index verify succeeded: {len(payloads)} keys", file=sys.stderr)
        else:
            skipped, written, unchanged = publish_with_cadence(
                publication_state_path(),
                time.time(),
                publication_interval_seconds(),
                lambda: publish_unchanged_aware_with_retry(args.api_base, token, payloads),
            )
            if skipped:
                print("health index publish skipped: cadence window active", file=sys.stderr)
                return EXIT_SKIPPED
            else:
                print(f"health index publish succeeded: {written} written, {unchanged} unchanged", file=sys.stderr)
        return 0
    except (PublishError, TimeoutError, OSError, http.client.HTTPException) as exc:
        prefix = "health index verify failed" if args.verify else "health index publish failed"
        print(_failure_line(prefix, exc, token), file=sys.stderr)
        if args.verify or token is None:
            return 1
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
