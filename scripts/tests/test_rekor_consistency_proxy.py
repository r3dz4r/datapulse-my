from __future__ import annotations

import json
import logging
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest

from scripts.rekor_consistency_proxy import Config, RekorProxyServer


UUID = "a" * 64
ENTRY = {"logID": "log-1", "logIndex": 7, "verification": {"inclusionProof": {"rootHash": "ok"}}}
POST_ENTRY = {"logID": "log-1", "logIndex": 7}


class FakeRekor(ThreadingHTTPServer):
    def __init__(self, responses: list[tuple[int, Any]]):
        self.responses = responses
        self.posts = 0
        self.gets = 0
        self.received: list[tuple[str, str, bytes, dict[str, str]]] = []
        super().__init__(("127.0.0.1", 0), FakeHandler)


class FakeHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None: self.server.handle(self)  # type: ignore[attr-defined]
    def do_POST(self) -> None: self.server.handle(self)  # type: ignore[attr-defined]
    def log_message(self, format: str, *args: Any) -> None: pass


def fake_handle(server: FakeRekor, handler: FakeHandler) -> None:
    length = int(handler.headers.get("Content-Length", "0"))
    body = handler.rfile.read(length)
    server.received.append((handler.command, handler.path, body, dict(handler.headers)))
    if handler.command == "POST" and handler.path == "/api/v1/log/entries":
        server.posts += 1
        status, payload = 201, {UUID: POST_ENTRY}
    elif handler.command == "GET" and handler.path == f"/api/v1/log/entries/{UUID}":
        server.gets += 1
        status, payload = server.responses.pop(0) if server.responses else (200, ENTRY)
    else:
        status, payload = 202, {"path": handler.path, "method": handler.command}
    encoded = json.dumps(payload).encode()
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json")
    if handler.command == "POST" and handler.path == "/api/v1/log/entries":
        handler.send_header("ETag", UUID)
    elif handler.command == "GET" and handler.path == f"/api/v1/log/entries/{UUID}":
        handler.send_header("ETag", "wrong-get-header")
    handler.send_header("Content-Length", str(len(encoded)))
    handler.end_headers()
    handler.wfile.write(encoded)


@pytest.fixture
def servers():
    upstream = FakeRekor([])
    upstream.handle = lambda handler: fake_handle(upstream, handler)  # type: ignore[method-assign]
    proxy = RekorProxyServer(("127.0.0.1", 0), Config(f"http://127.0.0.1:{upstream.server_port}", 0.005, 0.08))
    threads = [threading.Thread(target=s.serve_forever, daemon=True) for s in (upstream, proxy)]
    for thread in threads: thread.start()
    yield upstream, proxy
    for server in (proxy, upstream): server.shutdown(); server.server_close()


def call(proxy: RekorProxyServer, method: str, path: str, body: bytes = b"", headers: dict[str, str] | None = None):
    request = Request(f"http://127.0.0.1:{proxy.server_port}{path}", data=body if method != "GET" else None, method=method, headers=headers or {})
    try:
        with urlopen(request, timeout=2) as response: return response.status, response.headers, response.read()
    except HTTPError as exc:
        return exc.code, exc.headers, exc.read()


def test_post_returns_proof_enriched_get_representation_after_delayed_inclusion(servers):
    upstream, proxy = servers
    upstream.responses = [(404, {"error": "pending"}), (200, {**ENTRY, "verification": {}}), (200, ENTRY)]
    status, headers, body = call(proxy, "POST", "/api/v1/log/entries", b'{"signedEntryTimestamp":"secret"}')
    assert status == 201
    assert json.loads(body) == {UUID: ENTRY}
    assert json.loads(body) != {UUID: POST_ENTRY}
    assert "inclusionProof" in json.loads(body)[UUID]["verification"]
    assert headers["Content-Type"] == "application/json"
    assert headers["ETag"] == UUID
    assert int(headers["Content-Length"]) == len(body)
    assert upstream.posts == 1 and upstream.gets == 3


@pytest.mark.parametrize("proof_response", [ENTRY, {UUID: ENTRY}])
def test_post_normalizes_direct_and_uuid_keyed_proof_responses(servers, proof_response):
    upstream, proxy = servers
    upstream.responses = [(200, proof_response)]
    status, _, body = call(proxy, "POST", "/api/v1/log/entries")
    assert status == 201
    assert json.loads(body) == {UUID: ENTRY}
    assert upstream.posts == 1 and upstream.gets == 1


def test_bounded_backoff_has_multiple_delayed_attempts(servers):
    upstream, proxy = servers
    upstream.responses = [(200, {**ENTRY, "verification": {}})] * 20
    start = time.monotonic(); status, _, _ = call(proxy, "POST", "/api/v1/log/entries"); elapsed = time.monotonic() - start
    assert status == 504 and upstream.posts == 1 and upstream.gets >= 3 and elapsed >= 0.06


@pytest.mark.parametrize("response", ["not-an-entry", {"b" * 64: ENTRY}])
def test_malformed_or_uuid_mismatched_proof_response_fails_closed(servers, response):
    upstream, proxy = servers
    upstream.responses = [(200, response)] * 20
    status, _, _ = call(proxy, "POST", "/api/v1/log/entries")
    assert status == 504
    assert upstream.posts == 1 and upstream.gets >= 3


@pytest.mark.parametrize("payload", [b"not-json", json.dumps({}).encode(), json.dumps({UUID: ENTRY, "b" * 64: ENTRY}).encode()])
def test_malformed_or_multiple_post_uuid_response_fails_closed(servers, payload):
    upstream, proxy = servers
    original = upstream.handle
    def malformed(handler):
        if handler.command == "POST":
            handler.send_response(201); handler.send_header("Content-Length", str(len(payload))); handler.end_headers(); handler.wfile.write(payload)
        else: original(handler)
    upstream.handle = malformed
    status, _, _ = call(proxy, "POST", "/api/v1/log/entries")
    assert status == 502 and upstream.gets == 0


def test_non_2xx_post_passes_through_without_polling(servers):
    upstream, proxy = servers
    def rejected(handler):
        encoded = b'{"error":"no"}'; handler.send_response(409); handler.send_header("Content-Type", "application/json"); handler.send_header("Content-Length", str(len(encoded))); handler.end_headers(); handler.wfile.write(encoded)
    upstream.handle = rejected
    status, _, body = call(proxy, "POST", "/api/v1/log/entries")
    assert status == 409 and body == b'{"error":"no"}' and upstream.gets == 0


def test_non_entry_paths_forward_unchanged(servers):
    upstream, proxy = servers
    for method, path, body in [("GET", "/api/v1/log", b""), ("POST", "/other", b"payload")]:
        status, _, received = call(proxy, method, path, body)
        assert status == 202 and json.loads(received) == {"path": path, "method": method}
    assert upstream.gets == 0 and upstream.posts == 0


def test_logs_exclude_body_and_sensitive_headers(servers, caplog):
    upstream, proxy = servers
    caplog.set_level(logging.INFO, logger="rekor_consistency_proxy")
    call(proxy, "POST", "/api/v1/log/entries", b"artifact-payload-secret", {"Authorization": "Bearer token-secret"})
    text = caplog.text
    assert "artifact-payload-secret" not in text and "token-secret" not in text and UUID in text
    assert upstream.posts == 1
