#!/usr/bin/env python3
"""Opt-in signed-health operational integration.

This module is the operational seam above :mod:`scripts.signed_health_publication`:
an explicitly injected Cloudflare-KV-REST-shaped transport, destination-bound
cooperating-writer serialization, independently delivered trusted-registry
artifacts, and an isolated local Pages/workerd runtime rehearsal.

Nothing here is a default. Running the CLI with no mode performs no signing and
no network write. There is no destination default, no dotenv/process-environment
credential, no key discovery, no timer or workflow hook, and no remote provider
is contacted outside the operator-supplied endpoint (loopback in every test).
"""
from __future__ import annotations

import argparse
import fcntl
import hashlib
import http.client
import http.server
import json
import os
import re
import shutil
import socket
import subprocess
import tempfile
import threading
import time
import urllib.parse
from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

try:
    from scripts import signed_health_publication as shp
except ImportError:  # direct invocation places scripts/ on sys.path
    import signed_health_publication as shp

ROOT = Path(__file__).resolve().parents[1]
STAGING_RELATIVE = "health/staging-signed-health"
WRANGLER_RELATIVE = "health/staging-tooling/node_modules/.bin/wrangler"
LOCAL_KV_BINDING = "DATAPULSE_HEALTH_INDEX"
REGISTRY_ASSET_PATH = "/.well-known/datapulse-probe-keys.json"
REGISTRY_SCHEMA = "datapulse/v2/probe-key-registry"
ARTIFACT_SCHEMA = "datapulse/v1/signed-health-pages-artifact"
FIXTURE_SOURCE_COMMIT = "0" * 40
COMPATIBILITY_DATE = "2026-01-01"
DESTINATION_RE = re.compile(r"[A-Za-z0-9_-]{1,128}")
SEGMENT_RE = re.compile(r"[A-Za-z0-9_.-]{1,128}")
LOOPBACK_HOSTS = {"127.0.0.1", "::1", "localhost"}
MAX_KV_RESPONSE_BYTES = shp.MAX_PACKAGE_BYTES + 64 * 1024
MAX_SECRET_BYTES = 8192
SCOPED_FUNCTIONS = (
    "functions/_lib/signed-health.js",
    "functions/_lib/signed-health-trust.js",
    "functions/health/verified/[[path]].js",
)
REHEARSAL_ROUTES = {
    "latest": "/health/verified/latest.json",
    "digest": "/health/verified/{identity}.json",
}


class IntegrationError(RuntimeError):
    """A bounded reason token safe for operator or consumer reporting."""


class TransportError(IntegrationError):
    """A bounded transport failure carrying an honest acknowledgement outcome.

    ``outcome`` is one of ``acknowledged``, ``failed`` or ``unknown``. A remote
    write may succeed before the response is lost, so ``unknown`` never claims a
    rollback or a no-write.
    """

    def __init__(self, reason: str, *, outcome: str = "failed", phase: str = "", evidence: dict[str, Any] | None = None) -> None:
        super().__init__(reason)
        self.reason = reason
        self.outcome = outcome
        self.phase = phase
        self.evidence = evidence or {}


class LockUnavailable(IntegrationError):
    """The destination-bound writer lock was already held elsewhere."""


class RehearsalError(IntegrationError):
    """The isolated local runtime rehearsal could not complete."""


def _require(condition: bool, reason: str) -> None:
    if not condition:
        raise IntegrationError(reason)


def _token(value: object, pattern: re.Pattern[str], reason: str) -> str:
    _require(isinstance(value, str) and pattern.fullmatch(value) is not None, reason)
    return value  # type: ignore[return-value]


def _validate_destination(destination: object) -> str:
    _require(isinstance(destination, str) and DESTINATION_RE.fullmatch(destination) is not None, "explicit_destination_required")
    return destination  # type: ignore[return-value]


def _validate_key(key: object) -> str:
    _require(isinstance(key, str) and 0 < len(key) <= 512, "invalid_storage_key")
    _require(not key.startswith("/") and all(ord(char) >= 0x20 for char in key), "invalid_storage_key")
    _require(all(segment not in {"", ".", ".."} for segment in key.split("/")), "invalid_storage_key")
    return key  # type: ignore[return-value]


def digest_bytes(raw: bytes) -> str:
    """Content identity helper (kept local so evidence never needs the payload)."""
    return hashlib.sha256(raw).hexdigest()


def writer_lock_path(lock_dir: str | os.PathLike[str], destination: str) -> Path:
    """One explicit lock file per destination so a lock cannot leak across targets."""
    return Path(lock_dir) / f"writer-{_validate_destination(destination)}.lock"


# --------------------------------------------------------------------------- #
# Cloudflare-KV-REST-shaped transport
# --------------------------------------------------------------------------- #


def validate_api_base(api_base: object) -> tuple[str, str, int | None, str]:
    """Require an explicit endpoint; plaintext HTTP is loopback-only.

    Credentials embedded in the URL are rejected, and non-loopback hosts must be
    reached over TLS. The return value is (scheme, host, port, path-prefix).
    """
    _require(isinstance(api_base, str) and bool(api_base), "invalid_api_base")
    parsed = urllib.parse.urlsplit(api_base)
    _require(parsed.scheme in {"http", "https"} and bool(parsed.hostname), "invalid_api_base")
    _require(parsed.username is None and parsed.password is None, "api_base_must_not_carry_credentials")
    _require(not parsed.query and not parsed.fragment, "invalid_api_base")
    host = parsed.hostname.lower()
    if host not in LOOPBACK_HOSTS:
        _require(parsed.scheme == "https", "non_loopback_requires_https")
    prefix = parsed.path.rstrip("/")
    _require(".." not in prefix.split("/"), "invalid_api_base")
    return parsed.scheme, host, parsed.port, prefix


def _json_object(payload: bytes) -> dict[str, Any] | None:
    if not payload.startswith(b"{"):
        return None
    try:
        value = json.loads(payload.decode("utf-8"))
    except (ValueError, UnicodeError):
        return None
    return value if isinstance(value, dict) else None


def _looks_like_api_error(payload: bytes) -> bool:
    """Detect an explicit Cloudflare-style error envelope on a write response."""
    value = _json_object(payload)
    return value is not None and value.get("success") is False


def _looks_like_envelope(payload: bytes) -> bool:
    """Detect any API envelope where raw stored bytes were expected.

    Cloudflare returns ``{"result":..,"success":..,"errors":..,"messages":..}``;
    a signed-health object never carries that shape, so a 200 body with it must
    never be accepted as stored value bytes.
    """
    value = _json_object(payload)
    return value is not None and {"success", "result", "errors", "messages"}.issubset(value)


class KVRestTransport:
    """Destination-bound Cloudflare KV REST values transport.

    The endpoint, account, namespace and credential are all explicit. Redirects
    are never followed, so the credential can only travel to the configured host.
    Responses are bounded, timeouts are surfaced, and no retry is attempted after
    an ambiguous acknowledgement.
    """

    def __init__(
        self,
        *,
        api_base: str,
        account_id: str,
        namespace_id: str,
        credential: str,
        destination: str,
        timeout: float = 15.0,
        max_response_bytes: int = MAX_KV_RESPONSE_BYTES,
    ) -> None:
        scheme, host, port, prefix = validate_api_base(api_base)
        _require(isinstance(account_id, str) and SEGMENT_RE.fullmatch(account_id) is not None, "invalid_account_id")
        _require(isinstance(namespace_id, str) and SEGMENT_RE.fullmatch(namespace_id) is not None, "invalid_namespace_id")
        _require(isinstance(credential, str) and 0 < len(credential) <= MAX_SECRET_BYTES, "invalid_credential")
        _require(isinstance(timeout, (int, float)) and not isinstance(timeout, bool) and timeout > 0, "invalid_timeout")
        self.destination = _validate_destination(destination)
        self.scheme = scheme
        self.host = host
        self.port = port
        self.path_prefix = prefix
        self.account_id = account_id
        self.namespace_id = namespace_id
        self.timeout = float(timeout)
        self.max_response_bytes = int(max_response_bytes)
        self.calls: list[dict[str, Any]] = []
        self._credential = credential

    # -- internals -------------------------------------------------------- #

    def _check_destination(self, destination: object) -> str:
        value = _validate_destination(destination)
        _require(value == self.destination, "transport_destination_mismatch")
        return value

    def _path(self, key: str) -> str:
        return (
            self.path_prefix
            + "/accounts/"
            + urllib.parse.quote(self.account_id, safe="")
            + "/storage/kv/namespaces/"
            + urllib.parse.quote(self.namespace_id, safe="")
            + "/values/"
            + urllib.parse.quote(key, safe="/")
        )

    def _connection(self) -> http.client.HTTPConnection:
        if self.scheme == "https":
            return http.client.HTTPSConnection(self.host, self.port, timeout=self.timeout)
        return http.client.HTTPConnection(self.host, self.port, timeout=self.timeout)

    def _read_bounded(self, response: http.client.HTTPResponse, evidence: dict[str, Any]) -> bytes:
        chunks: list[bytes] = []
        total = 0
        phase = str(evidence.get("phase", ""))
        while True:
            chunk = response.read(65536)
            if not chunk:
                break
            total += len(chunk)
            if total > self.max_response_bytes:
                # An over-budget acknowledgement to a pointer write is ambiguous:
                # the write may have landed before the body became unreadable.
                outcome = "unknown" if phase == "put_pointer" else "failed"
                raise TransportError(
                    "response_too_large",
                    outcome=outcome,
                    phase=phase,
                    evidence=evidence,
                )
            chunks.append(chunk)
        return b"".join(chunks)

    def _status_error(self, phase: str, status: int, *, method: str) -> TransportError:
        if 300 <= status < 400:
            reason, outcome = "redirect_not_followed", "failed"
        elif method == "PUT" and status >= 500:
            reason, outcome = "storage_server_error", "unknown"
        elif method == "PUT":
            reason, outcome = "storage_client_error", "failed"
        else:
            reason, outcome = "storage_error", "failed"
        return TransportError(reason, outcome=outcome, phase=phase, evidence={"phase": phase, "method": method, "status": status})

    def _request(self, phase: str, method: str, key: str, body: bytes | None = None) -> tuple[int, bytes]:
        path = self._path(key)
        evidence: dict[str, Any] = {
            "phase": phase,
            "method": method,
            "key": key,
            "key_sha256": digest_bytes(key.encode("utf-8")),
            "request_sha256": digest_bytes(body) if body is not None else None,
            "request_bytes": len(body) if body is not None else 0,
        }
        connection = self._connection()
        try:
            headers = {"Authorization": f"Bearer {self._credential}", "Accept": "application/octet-stream"}
            if body is not None:
                headers["Content-Type"] = "application/octet-stream"
                headers["Content-Length"] = str(len(body))
            connection.request(method, path, body=body, headers=headers)
            response = connection.getresponse()
            payload = self._read_bounded(response, evidence)
            evidence.update(
                {
                    "status": response.status,
                    "response_sha256": digest_bytes(payload) if payload else None,
                    "response_bytes": len(payload),
                }
            )
            self.calls.append(evidence)
            return response.status, payload
        except TransportError as error:
            self.calls.append({**evidence, "outcome": error.outcome, "reason": error.reason})
            raise
        except (socket.timeout, TimeoutError):
            outcome = "unknown" if method == "PUT" else "failed"
            self.calls.append({**evidence, "outcome": outcome, "reason": "transport_timeout"})
            raise TransportError("transport_timeout", outcome=outcome, phase=phase, evidence=evidence) from None
        except (ConnectionRefusedError, socket.gaierror):
            self.calls.append({**evidence, "outcome": "failed", "reason": "transport_unreachable"})
            raise TransportError("transport_unreachable", outcome="failed", phase=phase, evidence=evidence) from None
        except (BrokenPipeError, ConnectionResetError, http.client.HTTPException):
            outcome = "unknown" if method == "PUT" else "failed"
            self.calls.append({**evidence, "outcome": outcome, "reason": "transport_interrupted"})
            raise TransportError("transport_interrupted", outcome=outcome, phase=phase, evidence=evidence) from None
        except OSError:
            outcome = "unknown" if method == "PUT" else "failed"
            self.calls.append({**evidence, "outcome": outcome, "reason": "transport_error"})
            raise TransportError("transport_error", outcome=outcome, phase=phase, evidence=evidence) from None
        finally:
            connection.close()

    # -- PublicationTransport contract ------------------------------------ #

    def get(self, destination: str, key: str) -> bytes | None:
        """Read one value; 404 is a definite absence, error envelopes are not bytes."""
        self._check_destination(destination)
        self._validate_key(key)
        status, payload = self._request("get", "GET", key)
        if status == 200:
            if _looks_like_envelope(payload):
                raise TransportError(
                    "api_error_envelope",
                    outcome="failed",
                    phase="get",
                    evidence={"phase": "get", "method": "GET", "key": key, "status": status, "response_sha256": digest_bytes(payload)},
                )
            return payload
        if status == 404:
            return None
        raise self._status_error("get", status, method="GET")

    def create(self, destination: str, key: str, value: bytes) -> None:
        """Write an immutable object; serialization is enforced by the caller's lock."""
        self._check_destination(destination)
        self._validate_key(key)
        _require(type(value) is bytes and 0 < len(value) <= shp.MAX_PACKAGE_BYTES, "invalid_value")
        _require(key.startswith(shp.PREFIX + "objects/") and key.endswith(".json"), "invalid_object_key")
        status, payload = self._request("create", "PUT", key, value)
        if not 200 <= status < 300:
            raise self._status_error("create", status, method="PUT")
        if _looks_like_api_error(payload):
            raise TransportError("api_error_envelope", outcome="unknown", phase="create", evidence={"phase": "create", "status": status})

    def put_pointer(self, destination: str, key: str, value: bytes) -> None:
        """Advance only the latest pointer; an ambiguous ack stays unknown."""
        self._check_destination(destination)
        self._validate_key(key)
        _require(key == shp.LATEST_KEY, "invalid_pointer_key")
        _require(type(value) is bytes and 0 < len(value) <= 1024, "invalid_pointer")
        status, payload = self._request("put_pointer", "PUT", key, value)
        if not 200 <= status < 300:
            raise self._status_error("put_pointer", status, method="PUT")
        if _looks_like_api_error(payload):
            raise TransportError("api_error_envelope", outcome="unknown", phase="put_pointer", evidence={"phase": "put_pointer", "status": status})

    @staticmethod
    def _validate_key(key: object) -> str:
        return _validate_key(key)


# --------------------------------------------------------------------------- #
# Destination-bound writer lock
# --------------------------------------------------------------------------- #


class WriterLock:
    """One explicit same-host cooperating-writer lock bound to a destination.

    This proves serialization only between cooperating publishers on one host.
    It is not globally exclusive writer authority; that remains an external
    operator promotion gate documented alongside the module.
    """

    def __init__(self, path: str | os.PathLike[str], destination: str, *, timeout: float = 0.0) -> None:
        self.destination = _validate_destination(destination)
        self.path = Path(path)
        self.timeout = float(timeout)
        self._fd: int | None = None
        self._identity: tuple[int, int] | None = None

    def acquire(self) -> "WriterLock":
        _require(self._fd is None, "writer_lock_already_held")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(self.path, os.O_CREAT | os.O_RDWR, 0o600)
        deadline = time.monotonic() + self.timeout
        while True:
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                stat = os.fstat(fd)
                self._fd = fd
                self._identity = (stat.st_dev, stat.st_ino)
                return self
            except OSError:
                if time.monotonic() >= deadline:
                    os.close(fd)
                    raise LockUnavailable("writer_lock_unavailable") from None
                time.sleep(0.05)

    def release(self) -> None:
        if self._fd is not None:
            try:
                fcntl.flock(self._fd, fcntl.LOCK_UN)
            finally:
                os.close(self._fd)
                self._fd = None
                self._identity = None

    def assert_held(self, destination: object) -> None:
        _require(self._fd is not None, "writer_lock_not_held")
        value = _validate_destination(destination)
        _require(value == self.destination, "writer_lock_destination_mismatch")
        # The convention is one lock file per destination: the held descriptor
        # must be the canonical lock for this destination, compared by file
        # identity rather than the caller-supplied label alone.
        canonical = writer_lock_path(self.path.parent, value)
        try:
            expected = os.stat(canonical)
        except OSError:
            raise IntegrationError("writer_lock_identity_mismatch") from None
        _require(self._identity == (expected.st_dev, expected.st_ino), "writer_lock_identity_mismatch")

    def __enter__(self) -> "WriterLock":
        return self.acquire()

    def __exit__(self, *_exc: object) -> None:
        self.release()


def _write_count(transport: object) -> int:
    return sum(1 for call in getattr(transport, "calls", []) if call.get("method") == "PUT")


# --------------------------------------------------------------------------- #
# Signer capability (operator-only explicit path; never discovery)
# --------------------------------------------------------------------------- #


def signer_from_key_document(document: bytes) -> tuple[str, Callable[[bytes], bytes]]:
    """Parse the existing attestation key JSON shape into an injected signer.

    This is an explicit operator seam. Tests build the document in memory from a
    disposable key; no real key file is read anywhere in this task.
    """
    try:
        value = shp.strict_json(document, MAX_SECRET_BYTES)
    except shp.PublicationError:
        raise IntegrationError("invalid_key_document") from None
    _require(isinstance(value, dict) and set(value) == {"key_id", "public_key_base64", "private_key_base64"}, "invalid_key_document")
    try:
        key_id = _token(value["key_id"], shp.KEY_ID, "invalid_key_identity")
        public = shp.unb64(value["public_key_base64"], 32)
        private = shp.unb64(value["private_key_base64"], 32)
    except shp.PublicationError as error:
        raise IntegrationError(str(error)) from None
    _require(len(public) == 32 and len(private) == 32, "invalid_key_material")
    private_key = Ed25519PrivateKey.from_private_bytes(private)
    derived = private_key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
    _require(derived == public, "key_material_mismatch")
    _require("ed25519-" + shp.digest(public)[:16] == key_id, "key_identity_mismatch")
    return key_id, private_key.sign


def _read_explicit_secret(*, path: str | None, fd: int | None, label: str) -> bytes:
    _require((path is None) != (fd is None), f"explicit_{label}_required")
    if fd is not None:
        raw = os.read(fd, MAX_SECRET_BYTES)
    else:
        with open(str(path), "rb") as handle:
            raw = handle.read(MAX_SECRET_BYTES)
    return raw.rstrip(b"\r\n")


# --------------------------------------------------------------------------- #
# Trusted-registry validation and independent Pages artifact delivery
# --------------------------------------------------------------------------- #


def validate_registry_bytes(raw: bytes) -> dict[str, Any]:
    """Validate explicitly prepared same-deployment public registry input."""
    _require(type(raw) is bytes and 0 < len(raw) <= shp.MAX_REGISTRY_BYTES, "invalid_registry_size")
    try:
        registry = shp.strict_json(raw, shp.MAX_REGISTRY_BYTES)
    except shp.PublicationError:
        raise IntegrationError("invalid_registry_json") from None
    try:
        _require(registry.get("schema") == REGISTRY_SCHEMA and type(registry.get("version")) is int and registry["version"] == 2, "invalid_registry")
        rows = registry.get("keys")
        _require(isinstance(rows, list) and bool(rows) and all(isinstance(row, dict) for row in rows), "invalid_registry")
        identities = [_token(row.get("key_id"), shp.KEY_ID, "invalid_key_identity") for row in rows]
        _require(len(set(identities)) == len(identities), "ambiguous_key")
        active = [row for row in rows if row.get("purpose") == shp.ATTESTATION_KEY_PURPOSE and row.get("status") == "active"]
        _require(len(active) == 1 and active[0]["key_id"] == registry.get("current_key_id"), "inactive_or_ambiguous_key")
        row = active[0]
        _require(row.get("algorithm") == "Ed25519", "wrong_algorithm")
        _require(row.get("compromised_at") is None and row.get("revoked_at") is None, "revoked_or_compromised_key")
        start, end = shp.timestamp(row.get("not_before")), shp.timestamp(row.get("not_after"))
        _require(start <= end, "invalid_key_window")
        public = shp.unb64(row.get("public_key_base64"), 32)
        _require(len(public) == 32 and "ed25519-" + shp.digest(public)[:16] == row["key_id"], "key_identity_mismatch")
    except shp.PublicationError as error:
        raise IntegrationError(str(error)) from None
    return registry


def build_pages_artifact(
    registry_bytes: bytes,
    *,
    root: str | os.PathLike[str] = ROOT,
    out_dir: str | os.PathLike[str],
    source_commit: str,
) -> dict[str, Any]:
    """Build a reproducible isolated Pages project from explicit registry input.

    The manifest records the registry digest and source commit and is explicitly
    not a signature authority; it is written outside the served directory.
    """
    registry = validate_registry_bytes(registry_bytes)
    artifact_bytes = shp.canonical(registry)
    _require(isinstance(source_commit, str) and shp.COMMIT.fullmatch(source_commit) is not None, "invalid_source_commit")
    out = Path(out_dir)
    _require(not out.exists(), "artifact_dir_exists")
    project = out / "project"
    public = project / "public"
    (public / ".well-known").mkdir(parents=True)
    functions: list[dict[str, Any]] = []
    for relative in SCOPED_FUNCTIONS:
        source = Path(root) / relative
        if not source.is_file():
            continue
        target = project / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        raw = source.read_bytes()
        target.write_bytes(raw)
        functions.append({"path": relative, "sha256": digest_bytes(raw)})
    _require(any(item["path"] == "functions/_lib/signed-health.js" for item in functions), "scoped_functions_missing")
    (public / REGISTRY_ASSET_PATH.lstrip("/")).write_bytes(artifact_bytes)
    manifest = {
        "schema": ARTIFACT_SCHEMA,
        "source_commit": source_commit,
        "registry_sha256": digest_bytes(artifact_bytes),
        "registry_bytes": len(artifact_bytes),
        "functions": functions,
        "signature_authority": False,
        "scope": "static same-deployment trust delivery; not a signer or signature",
    }
    (out / "manifest.json").write_bytes(shp.canonical(manifest))
    return {"project": project, "public": public, "manifest": manifest, "registry_sha256": manifest["registry_sha256"]}


# --------------------------------------------------------------------------- #
# Serialized publication
# --------------------------------------------------------------------------- #


def authoritative_observed_at(
    transport: object,
    destination: str,
    registry: dict[str, Any],
    now: str,
) -> str | None:
    """Observed time of the complete authoritative pointer, when available.

    A genuinely absent or malformed pointer/package is reported as unavailable.
    A transient read failure is not: it propagates so publication fails closed
    instead of being silently downgraded to "state unavailable".
    """
    raw = transport.get(destination, shp.LATEST_KEY)  # type: ignore[attr-defined]
    if raw is None:
        return None
    try:
        pointer = shp.strict_json(raw, 1024)
        _require(set(pointer) == {"schema", "publication_sha256"} and pointer["schema"] == shp.POINTER_SCHEMA, "invalid_pointer")
        identity = _token(pointer["publication_sha256"], shp.DIGEST, "invalid_publication")
    except (shp.PublicationError, IntegrationError):
        return None
    package = transport.get(destination, shp.object_key(identity))  # type: ignore[attr-defined]
    if package is None:
        return None
    try:
        verdict = shp.verify_package(package, registry=registry, now=now, expected_publication=identity)
    except (shp.PublicationError, IntegrationError):
        return None
    return str(verdict["observed_at"])


def serialized_publish(
    health_bytes: bytes,
    *,
    registry: dict[str, Any],
    key_id: str,
    signer: Callable[[bytes], bytes],
    assembled_at: str,
    signed_at: str,
    source_commit: str,
    destination: str,
    transport: object,
    lock: WriterLock,
    now: str,
    guard_pointer_regression: bool = True,
) -> dict[str, Any]:
    """Freeze, sign, object, exact read-back and pointer under one held lock."""
    lock.assert_held(destination)
    _require(getattr(transport, "destination", None) == destination, "transport_destination_mismatch")
    try:
        health = shp.strict_json(health_bytes, shp.MAX_HEALTH_BYTES)
        candidate_observed = shp.timestamp(health.get("checked_at"))
    except shp.PublicationError as error:
        return {"ok": False, "reason": str(error), "phase": "freeze", "outcome": "failed", "pointer_outcome": "not_attempted", "writes": _write_count(transport)}
    regression = "not_checked"
    if guard_pointer_regression:
        current = authoritative_observed_at(transport, destination, registry, now)
        if current is None:
            regression = "authoritative_state_unavailable"
        else:
            current_observed = shp.timestamp(current)
            _require(current_observed <= candidate_observed, "pointer_regression")
            regression = "equal_observation_time_no_total_order" if current_observed == candidate_observed else "newer_observation"
    try:
        package = shp.build_package(
            health_bytes,
            registry=registry,
            key_id=key_id,
            signer=signer,
            assembled_at=assembled_at,
            signed_at=signed_at,
            source_commit=source_commit,
        )
    except shp.PublicationError as error:
        return {"ok": False, "reason": str(error), "phase": "freeze_sign", "outcome": "failed", "pointer_outcome": "not_attempted", "pointer_regression": regression, "writes": _write_count(transport)}
    identity = shp.digest(package)
    try:
        shp.publish_package(package, destination=destination, transport=transport, registry=registry, now=now)  # type: ignore[arg-type]
    except TransportError as error:
        pointer_outcome = "unknown" if error.phase == "put_pointer" and error.outcome == "unknown" else "not_advanced"
        return {
            "ok": False,
            "reason": error.reason,
            "phase": error.phase,
            "outcome": error.outcome,
            "pointer_outcome": pointer_outcome,
            "pointer_regression": regression,
            "publication_sha256": identity,
            "evidence": error.evidence,
            "writes": _write_count(transport),
            "claim": "no_rollback_claim",
        }
    except shp.PublicationError as error:
        return {"ok": False, "reason": str(error), "phase": "publish", "outcome": "failed", "pointer_outcome": "not_advanced", "pointer_regression": regression, "publication_sha256": identity, "writes": _write_count(transport)}
    return {
        "ok": True,
        "phase": "pointer",
        "outcome": "acknowledged",
        "pointer_outcome": "acknowledged",
        "pointer_regression": regression,
        "publication_sha256": identity,
        "object_key": shp.object_key(identity),
        "pointer_key": shp.LATEST_KEY,
        "writes": _write_count(transport),
    }


# --------------------------------------------------------------------------- #
# Loopback fixture KV REST server
# --------------------------------------------------------------------------- #


class MockKVRestServer:
    """Loopback-only KV REST fixture; records exact paths and never logs secrets."""

    def __init__(self, *, credential: str = "fixture-credential", account: str = "fixture-account", namespace: str = "fixture-namespace") -> None:
        self.credential = credential
        self.account = account
        self.namespace = namespace
        self.storage: dict[str, bytes] = {}
        self.calls: list[dict[str, Any]] = []
        self.behaviour: dict[str, Any] = {}
        outer = self

        class Handler(http.server.BaseHTTPRequestHandler):
            def log_message(self, *_args: Any) -> None:
                return

            def do_GET(self) -> None:
                outer._handle(self, "GET")

            def do_PUT(self) -> None:
                outer._handle(self, "PUT")

        self._server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self._server.daemon_threads = True
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)

    @property
    def api_base(self) -> str:
        host, port = self._server.server_address[:2]
        return f"http://{host}:{port}"

    def start(self) -> "MockKVRestServer":
        self._thread.start()
        return self

    def shutdown(self) -> None:
        self._server.shutdown()
        self._server.server_close()
        self._thread.join(timeout=5)

    # -- request handling -------------------------------------------------- #

    def _respond(self, handler: http.server.BaseHTTPRequestHandler, status: int, body: bytes, content_type: str | None, extra: dict[str, str] | None = None) -> None:
        try:
            handler.send_response(status)
            if content_type:
                handler.send_header("Content-Type", content_type)
            handler.send_header("Content-Length", str(len(body)))
            for name, value in (extra or {}).items():
                handler.send_header(name, value)
            handler.end_headers()
            if body:
                handler.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError, OSError):
            # A client that already timed out is not a fixture failure.
            handler.close_connection = True

    def _handle(self, handler: http.server.BaseHTTPRequestHandler, method: str) -> None:
        parsed = urllib.parse.urlsplit(handler.path)
        prefix = f"/accounts/{self.account}/storage/kv/namespaces/{self.namespace}/values/"
        authenticated = handler.headers.get("Authorization") == f"Bearer {self.credential}"
        record: dict[str, Any] = {"method": method, "path": parsed.path, "had_authorization": authenticated, "phase": "unknown"}
        if not parsed.path.startswith(prefix) or not authenticated:
            record["status"] = 404 if not parsed.path.startswith(prefix) else 401
            self.calls.append(record)
            self._respond(handler, record["status"], b"", None)
            return
        key = urllib.parse.unquote(parsed.path[len(prefix):])
        record["key"] = key
        record["phase"] = "get" if method == "GET" else ("put_pointer" if key == shp.LATEST_KEY else "create")
        if method == "PUT":
            length = int(handler.headers.get("Content-Length") or 0)
            body = handler.rfile.read(length) if length else b""
            record["body_sha256"] = digest_bytes(body)
            record["body_bytes"] = len(body)
            if self.behaviour.get("redirect"):
                record["status"] = 302
                self.calls.append(record)
                self._respond(handler, 302, b"", None, {"Location": str(self.behaviour["redirect"])})
                return
            self.storage[key] = body
            record["status"] = 200
            self.calls.append(record)
            if self.behaviour.get("drop_write") or (self.behaviour.get("drop_pointer_ack") and key == shp.LATEST_KEY):
                handler.close_connection = True
                return
            if self.behaviour.get("write_timeout"):
                time.sleep(float(self.behaviour["write_timeout"]))
            if self.behaviour.get("oversized_pointer_ack") and key == shp.LATEST_KEY:
                # Injected over-budget acknowledgement for a pointer write only.
                payload = b'{"result":{},"success":true,"errors":[],"messages":[]}' + b"x" * int(self.behaviour["oversized_pointer_ack"])
                self._respond(handler, 200, payload, "application/json")
                return
            self._respond(handler, 200, b'{"result":{},"success":true,"errors":[],"messages":[]}', "application/json")
            return
        if self.behaviour.get("redirect"):
            record["status"] = 302
            self.calls.append(record)
            self._respond(handler, 302, b"", None, {"Location": str(self.behaviour["redirect"])})
            return
        if self.behaviour.get("read_timeout"):
            time.sleep(float(self.behaviour["read_timeout"]))
        if self.behaviour.get("error_envelope"):
            payload = b'{"result":null,"success":false,"errors":[{"code":1000,"message":"boom"}],"messages":[]}'
            record["status"] = 200
            self.calls.append(record)
            self._respond(handler, 200, payload, "application/json")
            return
        if self.behaviour.get("fail_object_key") == key:
            # Injected transient read failure for exactly one stored key.
            record["status"] = 503
            self.calls.append(record)
            self._respond(handler, 503, b'{"result":null,"success":false,"errors":[{"code":1000,"message":"temporary"}],"messages":[]}', "application/json")
            return
        if key not in self.storage:
            record["status"] = 404
            self.calls.append(record)
            self._respond(handler, 404, b'{"result":null,"success":false,"errors":[{"code":1009,"message":"not found"}],"messages":[]}', "application/json")
            return
        value = self.storage[key]
        if self.behaviour.get("oversized"):
            value = value + b"x" * int(self.behaviour["oversized"])
        if self.behaviour.get("mutate_readback") and key.startswith(shp.PREFIX + "objects/"):
            value = value + b" "
        record["status"] = 200
        record["response_sha256"] = digest_bytes(value)
        record["response_bytes"] = len(value)
        self.calls.append(record)
        if self.behaviour.get("drop_read"):
            handler.close_connection = True
            return
        self._respond(handler, 200, value, "application/octet-stream")


# --------------------------------------------------------------------------- #
# Fixtures
# --------------------------------------------------------------------------- #


def health_fixture(observed_at: str, *, marker: str = "signed") -> bytes:
    """Build disposable health bytes with an explicit observation clock."""
    return shp.canonical(
        {
            "schema": "datapulse/v0.4/dataset-health",
            "checked_at": observed_at,
            "_trust_summary": {"pipeline_heartbeat_at": observed_at},
            "datasets": [{"dataset_id": "fixture", "status": "fresh", "marker": marker, "extra": ["preserved", 123]}],
        }
    ) + b"\n"


def registry_fixture(
    private: Ed25519PrivateKey,
    *,
    key_id: str,
    not_before: str,
    not_after: str,
    status: str = "active",
    purpose: str | None = None,
    revoked_at: str | None = None,
) -> dict[str, Any]:
    """Disposable registry matching the existing probe-key-registry shape."""
    public = private.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
    return {
        "schema": REGISTRY_SCHEMA,
        "version": 2,
        "current_key_id": key_id,
        "keys": [
            {
                "key_id": key_id,
                "algorithm": "Ed25519",
                "purpose": shp.ATTESTATION_KEY_PURPOSE if purpose is None else purpose,
                "status": status,
                "public_key_base64": shp.b64(public),
                "not_before": not_before,
                "not_after": not_after,
                "compromised_at": None,
                "revoked_at": revoked_at,
            }
        ],
    }


def disposable_key() -> tuple[Ed25519PrivateKey, str]:
    """Generate a disposable in-memory key without touching any key store."""
    private = Ed25519PrivateKey.generate()
    public = private.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
    return private, "ed25519-" + shp.digest(public)[:16]


def _staging_root(root: Path) -> Path:
    staging = root / STAGING_RELATIVE
    staging.mkdir(parents=True, exist_ok=True)
    return staging


def _kv_values(transport: MockKVRestServer) -> dict[str, bytes]:
    return {key: value for key, value in transport.storage.items()}


def _fixture_clock() -> str:
    return "2026-10-01T00:01:00Z"


def quick_test() -> dict[str, Any]:
    """Isolated signer, real REST transport, verified read-back, consumer path."""
    raw, registry, private, key_id = shp.fixture()
    now = _fixture_clock()
    server = MockKVRestServer().start()
    staging = _staging_root(ROOT)
    work = Path(tempfile.mkdtemp(prefix="quick-test-", dir=staging))
    lock = WriterLock(writer_lock_path(work, "fixture"), "fixture")
    try:
        with lock:
            transport = KVRestTransport(
                api_base=server.api_base,
                account_id="fixture-account",
                namespace_id="fixture-namespace",
                credential=server.credential,
                destination="fixture",
            )
            result = serialized_publish(
                raw,
                registry=registry,
                key_id=key_id,
                signer=private.sign,
                assembled_at=now,
                signed_at=now,
                source_commit="eaf56e5fc910ac380b270ff0f655adc9bd0d658e",
                destination="fixture",
                transport=transport,
                lock=lock,
                now=now,
            )
            _require(result["ok"] is True, str(result.get("reason", "publish_failed")))
            identity = str(result["publication_sha256"])
            status, body = shp.exercise_handler(_kv_values(server), registry, now=now, path=f"/health/verified/{identity}.json")
            _require(status == 200, "fixture_handler_unavailable")
            verdict = shp.verify_response(body, registry=registry, now=now, expected_publication=identity)
        return {
            "ok": True,
            "fixture_only": True,
            "publisher": "serialized_kv_rest_verified_readback_before_pointer",
            "handler_status": status,
            "consumer_verified": verdict["verified"],
            "age_seconds": verdict["age_seconds"],
            "pointer_outcome": result["pointer_outcome"],
            "writes": result["writes"],
            "source_truth_verified": False,
        }
    finally:
        lock.release()
        server.shutdown()
        shutil.rmtree(work, ignore_errors=True)


# --------------------------------------------------------------------------- #
# Isolated local Pages/workerd runtime rehearsal
# --------------------------------------------------------------------------- #


def _wrangler_env(work: Path) -> dict[str, str]:
    """Minimal allowlisted environment; no ambient credentials or dotenv."""
    home = work / "wrangler-home"
    (home / ".config").mkdir(parents=True, exist_ok=True)
    (home / ".cache").mkdir(parents=True, exist_ok=True)
    (home / ".local" / "share").mkdir(parents=True, exist_ok=True)
    temporary = work / "tmp"
    temporary.mkdir(parents=True, exist_ok=True)
    return {
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "HOME": str(home),
        "TMPDIR": str(temporary),
        "XDG_CONFIG_HOME": str(home / ".config"),
        "XDG_CACHE_HOME": str(home / ".cache"),
        "XDG_DATA_HOME": str(home / ".local" / "share"),
        "CLOUDFLARE_TELEMETRY_DISABLED": "1",
        "CLOUDFLARE_LOAD_DEV_VARS_FROM_DOT_ENV": "false",
        "WRANGLER_SEND_METRICS": "false",
        "WRANGLER_SEND_ERROR_REPORTS": "false",
        "WRANGLER_WRITE_LOGS": "false",
        "WRANGLER_LOG_SANITIZE": "true",
        "CI": "1",
        "NO_COLOR": "1",
        "FORCE_COLOR": "0",
    }


def _wrangler_binary(root: Path) -> Path:
    binary = root / WRANGLER_RELATIVE
    _require(binary.is_file(), "wrangler_missing")
    return binary


def _free_loopback_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])


def _seed_local_kv(*, root: Path, work: Path, state_dir: Path, values: dict[str, bytes]) -> None:
    binary = _wrangler_binary(root)
    environment = _wrangler_env(work)
    for index, (key, value) in enumerate(sorted(values.items())):
        value_path = work / f"seed-{index}.bin"
        value_path.write_bytes(value)
        command = [
            str(binary),
            "kv",
            "key",
            "put",
            "--local",
            "--namespace-id",
            LOCAL_KV_BINDING,
            "--persist-to",
            str(state_dir),
            "--path",
            str(value_path),
            key,
        ]
        try:
            result = subprocess.run(command, capture_output=True, timeout=60, env=environment, cwd=str(work))
        except subprocess.SubprocessError:
            raise RehearsalError("local_kv_seed_failed") from None
        _require(result.returncode == 0, "local_kv_seed_failed")


def _start_pages_dev(*, root: Path, project: Path, port: int, state_dir: Path, work: Path) -> tuple[subprocess.Popen[bytes], Any, Path]:
    binary = _wrangler_binary(root)
    environment = _wrangler_env(work)
    log_path = work / "pages-dev.log"
    log = open(log_path, "wb")
    command = [
        str(binary),
        "pages",
        "dev",
        "public",
        "--cwd",
        str(project),
        "--ip",
        "127.0.0.1",
        "--port",
        str(port),
        "--kv",
        LOCAL_KV_BINDING,
        "--persist-to",
        str(state_dir),
        "--compatibility-date",
        COMPATIBILITY_DATE,
        "--log-level",
        "warn",
    ]
    process = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT, env=environment, cwd=str(project), start_new_session=True)
    return process, log, log_path


def _stop_process(process: subprocess.Popen[bytes]) -> None:
    """Shut down only the child process group this rehearsal started."""
    if process.poll() is not None:
        return
    try:
        os.killpg(os.getpgid(process.pid), 15)
    except (ProcessLookupError, PermissionError):
        process.terminate()
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(os.getpgid(process.pid), 9)
        except (ProcessLookupError, PermissionError):
            process.kill()
        process.wait(timeout=5)


def _loopback_request(port: int, path: str, *, method: str = "GET", timeout: float = 5.0) -> tuple[int, dict[str, str], bytes]:
    connection = http.client.HTTPConnection("127.0.0.1", port, timeout=timeout)
    try:
        connection.request(method, path)
        response = connection.getresponse()
        body = response.read(16 * 1024 * 1024)
        headers = {name.lower(): value for name, value in response.getheaders()}
        return response.status, headers, body
    finally:
        connection.close()


def _poll_verified(port: int, path: str, *, deadline: float, registry: dict[str, Any], now: str, identity: str | None) -> tuple[int, bytes]:
    last_status = 0
    last_body = b""
    while time.monotonic() < deadline:
        try:
            status, _headers, body = _loopback_request(port, path, timeout=3.0)
        except (OSError, http.client.HTTPException):
            time.sleep(0.3)
            continue
        last_status, last_body = status, body
        if status == 200:
            try:
                shp.verify_response(body, registry=registry, now=now, expected_publication=identity)
                return status, body
            except shp.PublicationError:
                pass
        time.sleep(0.3)
    return last_status, last_body


def _poll_status(port: int, path: str, expected: int, *, deadline: float) -> int:
    last = 0
    while time.monotonic() < deadline:
        try:
            status, _headers, _body = _loopback_request(port, path, timeout=3.0)
        except (OSError, http.client.HTTPException):
            time.sleep(0.2)
            continue
        last = status
        if status == expected:
            return status
        time.sleep(0.2)
    return last


def _write_registry_asset(public: Path, registry: dict[str, Any]) -> None:
    (public / REGISTRY_ASSET_PATH.lstrip("/")).write_bytes(shp.canonical(registry))


def runtime_rehearsal(*, root: str | os.PathLike[str] = ROOT, timeout: float = 110.0, source_commit: str = FIXTURE_SOURCE_COMMIT) -> dict[str, Any]:
    """Build and serve the isolated Pages Functions with local Wrangler/workerd.

    Binds only a local DATAPULSE_HEALTH_INDEX namespace, exercises real HTTP
    routing plus the ASSETS trust lookup and Ed25519 verification, and verifies
    returned bytes independently in Python. This is a local runtime rehearsal,
    never a deployed Cloudflare preview.
    """
    root_path = Path(root)
    _require(isinstance(timeout, (int, float)) and not isinstance(timeout, bool) and timeout > 0, "invalid_timeout")
    started = time.monotonic()
    deadline = started + float(timeout)
    _wrangler_binary(root_path)  # fail fast before creating any state
    staging = _staging_root(root_path)
    work = Path(tempfile.mkdtemp(prefix="rehearsal-", dir=staging))
    process: subprocess.Popen[bytes] | None = None
    log_handle: Any = None
    try:
        now_dt = datetime.now(timezone.utc)
        now = now_dt.strftime("%Y-%m-%dT%H:%M:%SZ")
        observed = (now_dt - timedelta(seconds=300)).strftime("%Y-%m-%dT%H:%M:%SZ")
        assembled = (now_dt - timedelta(seconds=60)).strftime("%Y-%m-%dT%H:%M:%SZ")
        private, key_id = disposable_key()
        registry = registry_fixture(
            private,
            key_id=key_id,
            not_before=(now_dt - timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%SZ"),
            not_after=(now_dt + timedelta(days=30)).strftime("%Y-%m-%dT%H:%M:%SZ"),
        )
        registry_bytes = shp.canonical(registry)
        artifact = build_pages_artifact(registry_bytes, root=root_path, out_dir=work / "artifact", source_commit=source_commit)

        health_bytes = health_fixture(observed)
        package = shp.build_package(
            health_bytes,
            registry=registry,
            key_id=key_id,
            signer=private.sign,
            assembled_at=assembled,
            signed_at=now,
            source_commit=source_commit,
        )
        identity = shp.digest(package)
        pointer = shp.canonical({"schema": shp.POINTER_SCHEMA, "publication_sha256": identity})
        unsigned = health_fixture(observed, marker="unsigned")
        state_dir = work / "state"
        state_dir.mkdir(parents=True, exist_ok=True)
        _seed_local_kv(
            root=root_path,
            work=work,
            state_dir=state_dir,
            values={shp.object_key(identity): package, shp.LATEST_KEY: pointer, "health/latest.json": unsigned},
        )

        port = _free_loopback_port()
        process, log_handle, log_path = _start_pages_dev(root=root_path, project=artifact["project"], port=port, state_dir=state_dir, work=work)
        _require(process.poll() is None, "pages_dev_start_failed")
        status, body = _poll_verified(port, REHEARSAL_ROUTES["latest"], deadline=min(deadline, time.monotonic() + 45), registry=registry, now=now, identity=identity)
        _require(status == 200, f"rehearsal_readiness_failed:{status}")
        latest = shp.verify_response(body, registry=registry, now=now, expected_publication=identity)

        digest_status, _dh, digest_body = _loopback_request(port, f"/health/verified/{identity}.json", timeout=5.0)
        _require(digest_status == 200, "digest_route_unavailable")
        digest = shp.verify_response(digest_body, registry=registry, now=now, expected_publication=identity)
        _require(digest["publication_sha256"] == latest["publication_sha256"], "route_identity_mismatch")
        # The signed bytes must be exactly the signed health, never the unsigned KV copy.
        served = shp.strict_json(shp.unb64(shp.strict_json(digest_body, 12 * 1024 * 1024)["package_base64"], shp.MAX_PACKAGE_BYTES), shp.MAX_PACKAGE_BYTES)
        _require(shp.unb64(served["health_base64"], shp.MAX_HEALTH_BYTES) == health_bytes, "unsigned_fallback_served")

        missing_status, _mh, _mb = _loopback_request(port, "/health/verified/" + "0" * 64 + ".json", timeout=5.0)
        unknown_status, _uh, _ub = _loopback_request(port, "/health/verified/nope.json", timeout=5.0)
        method_status, _xh, _xb = _loopback_request(port, REHEARSAL_ROUTES["latest"], method="POST", timeout=5.0)
        floor_status, _fh, _fb = _loopback_request(port, REHEARSAL_ROUTES["latest"] + "?minimum_observed_at=" + now, timeout=5.0)
        _require(missing_status == 503, "missing_object_not_fail_closed")
        _require(unknown_status == 404, "unknown_path_not_404")
        _require(method_status == 405, "non_get_not_405")
        _require(floor_status == 503, "floor_not_enforced")

        content_type = _headers_content_type(port, REHEARSAL_ROUTES["latest"]).lower()
        _require("application/json" in content_type, "json_content_type_missing")

        revoked = registry_fixture(
            private,
            key_id=key_id,
            not_before=registry["keys"][0]["not_before"],
            not_after=registry["keys"][0]["not_after"],
            status="revoked",
            revoked_at=now,
        )
        wrong_purpose = registry_fixture(
            private,
            key_id=key_id,
            not_before=registry["keys"][0]["not_before"],
            not_after=registry["keys"][0]["not_after"],
            purpose="observation-receipt-signing",
        )
        _write_registry_asset(artifact["public"], revoked)
        revoked_status = _poll_status(port, REHEARSAL_ROUTES["latest"], 503, deadline=min(deadline, time.monotonic() + 10))
        _require(revoked_status == 503, "revocation_not_observed")
        _write_registry_asset(artifact["public"], registry)
        restored_status = _poll_status(port, REHEARSAL_ROUTES["latest"], 200, deadline=min(deadline, time.monotonic() + 10))
        _require(restored_status == 200, "registry_refresh_not_observed")
        _write_registry_asset(artifact["public"], wrong_purpose)
        purpose_status = _poll_status(port, REHEARSAL_ROUTES["latest"], 503, deadline=min(deadline, time.monotonic() + 10))
        _require(purpose_status == 503, "wrong_purpose_not_rejected")
        _write_registry_asset(artifact["public"], registry)
        final_status = _poll_status(port, REHEARSAL_ROUTES["latest"], 200, deadline=min(deadline, time.monotonic() + 10))
        _require(final_status == 200, "registry_restore_not_observed")

        return {
            "ok": True,
            "fixture_only": True,
            "runtime": "local_wrangler_workerd_pages",
            "deployed": False,
            "publication_sha256": identity,
            "registry_sha256": artifact["registry_sha256"],
            "source_commit": source_commit,
            "consumer_verified": latest["verified"] and digest["verified"],
            "routes": {
                "latest": "200_verified",
                "digest": "200_verified",
                "missing_object": str(missing_status),
                "floor": str(floor_status),
                "unknown_path": str(unknown_status),
                "non_get": str(method_status),
                "content_type": content_type,
            },
            "trust": {
                "revoked": str(revoked_status),
                "wrong_purpose": str(purpose_status),
                "refresh_forward": str(restored_status),
                "revocation_is_live_asset_swap": True,
                "old_deployment_gap": "asset rebuild proves delivery to the refreshed runtime only",
            },
            "unsigned_fallback": "not_served",
            "elapsed_seconds": round(time.monotonic() - started, 1),
            "source_truth_verified": False,
        }
    except RehearsalError:
        raise
    except IntegrationError:
        raise
    except (OSError, subprocess.SubprocessError, shp.PublicationError) as error:
        raise RehearsalError("rehearsal_io_failure") from error
    finally:
        if process is not None:
            _stop_process(process)
        if log_handle is not None:
            log_handle.close()
        shutil.rmtree(work, ignore_errors=True)


def _headers_content_type(port: int, path: str) -> str:
    connection = http.client.HTTPConnection("127.0.0.1", port, timeout=5.0)
    try:
        connection.request("GET", path)
        response = connection.getresponse()
        value = response.getheader("Content-Type") or ""
        response.read()
        return value
    finally:
        connection.close()


# --------------------------------------------------------------------------- #
# CLI (opt-in; no arguments means no signing and no network)
# --------------------------------------------------------------------------- #


def _load_signer(args: argparse.Namespace) -> tuple[str, Callable[[bytes], bytes]]:
    document = _read_explicit_secret(path=args.signer_key_file, fd=args.signer_key_fd, label="signer_key")
    return signer_from_key_document(document)


def _read_registry(path: str) -> dict[str, Any]:
    # Read at most one byte past the bound so an oversized trust input is
    # rejected without loading the remainder into memory.
    with open(str(path), "rb") as handle:
        raw = handle.read(shp.MAX_REGISTRY_BYTES + 1)
    if len(raw) > shp.MAX_REGISTRY_BYTES:
        raise IntegrationError("invalid_registry_size")
    return validate_registry_bytes(raw)


def plan_mode(args: argparse.Namespace) -> dict[str, Any]:
    destination = args.destination
    if destination is not None:
        _validate_destination(destination)
    lock = None
    if destination is not None and args.lock_dir:
        lock = str(writer_lock_path(args.lock_dir, destination))
    return {
        "ok": True,
        "mode": "plan",
        "signed": False,
        "network_writes": 0,
        "phases": [
            "single_read_frozen_health",
            "registry_purpose_window_check",
            "compatible_signing",
            "independent_verification",
            "immutable_object_create",
            "exact_verified_readback",
            "pointer_advance",
        ],
        "object_key_prefix": shp.PREFIX + "objects/",
        "pointer_key": shp.LATEST_KEY,
        "destination": destination,
        "writer_lock": lock,
        "note": "plan only: no health read, no signing, no network",
    }


def dry_run_mode(args: argparse.Namespace) -> dict[str, Any]:
    _require(all((args.health, args.registry, args.source_commit, args.assembled_at, args.signed_at)), "explicit_dry_run_inputs_required")
    _require(args.signer_key_file is not None or args.signer_key_fd is not None, "explicit_signer_key_required")
    key_id, signer = _load_signer(args)
    registry = _read_registry(args.registry)
    package = shp.build_package(
        Path(args.health).read_bytes(),
        registry=registry,
        key_id=key_id,
        signer=signer,
        assembled_at=args.assembled_at,
        signed_at=args.signed_at,
        source_commit=args.source_commit,
    )
    identity = shp.digest(package)
    verdict = shp.verify_package(package, registry=registry, now=args.signed_at)
    return {
        "ok": True,
        "mode": "dry_run",
        "signed": True,
        "network_writes": 0,
        "publication_sha256": identity,
        "object_key": shp.object_key(identity),
        "pointer_key": shp.LATEST_KEY,
        "verified": verdict["verified"],
        "source_truth_verified": False,
    }


def publish_mode(args: argparse.Namespace) -> dict[str, Any]:
    required = {
        "health": args.health,
        "registry": args.registry,
        "source_commit": args.source_commit,
        "assembled_at": args.assembled_at,
        "signed_at": args.signed_at,
        "destination": args.destination,
        "api_base": args.api_base,
        "account_id": args.account_id,
        "namespace_id": args.namespace_id,
        "lock_dir": args.lock_dir,
        "now": args.now,
    }
    missing = sorted(name for name, value in required.items() if not value)
    _require(not missing, "explicit_publish_inputs_required")
    credential = _read_explicit_secret(path=args.credential_file, fd=args.credential_fd, label="credential")
    key_id, signer = _load_signer(args)
    registry = _read_registry(args.registry)
    transport = KVRestTransport(
        api_base=args.api_base,
        account_id=args.account_id,
        namespace_id=args.namespace_id,
        credential=credential.decode("utf-8", "strict"),
        destination=args.destination,
        timeout=args.timeout,
    )
    lock = WriterLock(writer_lock_path(args.lock_dir, args.destination), args.destination, timeout=args.lock_timeout)
    with lock:
        return serialized_publish(
            Path(args.health).read_bytes(),
            registry=registry,
            key_id=key_id,
            signer=signer,
            assembled_at=args.assembled_at,
            signed_at=args.signed_at,
            source_commit=args.source_commit,
            destination=args.destination,
            transport=transport,
            lock=lock,
            now=args.now,
        )


def verify_mode(args: argparse.Namespace) -> dict[str, Any]:
    _require(all((args.registry, args.now)), "explicit_verifier_inputs_required")
    registry = _read_registry(args.registry)
    verdict = shp.verify_response(
        Path(args.verify_response).read_bytes(),
        registry=registry,
        now=args.now,
        expected_publication=args.expected_publication,
        minimum_observed_at=args.minimum_observed_at,
    )
    return {
        "ok": True,
        "mode": "verify",
        "verified": verdict["verified"],
        "publication_sha256": verdict["publication_sha256"],
        "observed_at": verdict["observed_at"],
        "age_seconds": verdict["age_seconds"],
        "source_truth_verified": False,
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Opt-in signed-health operational integration")
    parser.add_argument("--quick-test", action="store_true")
    parser.add_argument("--runtime-rehearsal", action="store_true")
    parser.add_argument("--plan", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--publish", action="store_true")
    parser.add_argument("--verify-response", type=Path)
    parser.add_argument("--health", type=Path)
    parser.add_argument("--registry", type=Path)
    parser.add_argument("--source-commit")
    parser.add_argument("--assembled-at")
    parser.add_argument("--signed-at")
    parser.add_argument("--now")
    parser.add_argument("--minimum-observed-at")
    parser.add_argument("--expected-publication")
    parser.add_argument("--destination")
    parser.add_argument("--api-base")
    parser.add_argument("--account-id")
    parser.add_argument("--namespace-id")
    parser.add_argument("--credential-file")
    parser.add_argument("--credential-fd", type=int)
    parser.add_argument("--signer-key-file")
    parser.add_argument("--signer-key-fd", type=int)
    parser.add_argument("--lock-dir")
    parser.add_argument("--lock-timeout", type=float, default=0.0)
    parser.add_argument("--timeout", type=float, default=15.0)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    try:
        modes = [
            name
            for name, selected in (
                ("quick_test", args.quick_test),
                ("runtime_rehearsal", args.runtime_rehearsal),
                ("plan", args.plan),
                ("dry_run", args.dry_run),
                ("publish", args.publish),
                ("verify", args.verify_response is not None),
            )
            if selected
        ]
        _require(len(modes) <= 1, "ambiguous_cli_mode")
        if not modes:
            print(json.dumps({"ok": True, "mode": "noop", "signed": False, "network_writes": 0, "note": "opt_in_mode_required"}))
            return 0
        mode = modes[0]
        if mode == "quick_test":
            result = quick_test()
        elif mode == "runtime_rehearsal":
            result = runtime_rehearsal()
        elif mode == "plan":
            result = plan_mode(args)
        elif mode == "dry_run":
            result = dry_run_mode(args)
        elif mode == "publish":
            result = publish_mode(args)
        else:
            result = verify_mode(args)
        print(json.dumps(result, sort_keys=True, separators=(",", ":")))
        return 0 if result.get("ok") else 1
    except (IntegrationError, shp.PublicationError) as error:
        print(json.dumps({"ok": False, "error": str(error)}, separators=(",", ":")))
        return 1
    except (OSError, subprocess.SubprocessError, UnicodeError):
        print(json.dumps({"ok": False, "error": "local_io_failure"}, separators=(",", ":")))
        return 1
    except ValueError:
        # The HTTP layer raises an argument error for an illegal header value
        # (for example a credential with an embedded newline). Its message can
        # contain that value, so emit a fixed bounded token instead.
        print(json.dumps({"ok": False, "error": "invalid_request"}, separators=(",", ":")))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
