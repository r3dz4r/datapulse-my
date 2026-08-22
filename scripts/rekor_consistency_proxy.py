#!/usr/bin/env python3
"""Fail-closed proxy that waits for private Rekor read-after-write consistency."""

from __future__ import annotations

import argparse
import json
import logging
import os
import time
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen


ENTRY_PATH = "/api/v1/log/entries"
HOP_BY_HOP_HEADERS = {"connection", "keep-alive", "proxy-authenticate", "proxy-authorization", "te", "trailer", "transfer-encoding", "upgrade"}
LOG = logging.getLogger("rekor_consistency_proxy")


@dataclass(frozen=True)
class Config:
    upstream_url: str
    poll_interval: float = 0.1
    timeout: float = 5.0
    max_response_size: int = 1_048_576


class UpstreamFailure(Exception):
    """An upstream request could not be completed safely."""


def _read_limited(response: Any, limit: int) -> bytes:
    content_length = response.headers.get("Content-Length")
    if content_length is not None and (not content_length.isdigit() or int(content_length) > limit):
        raise UpstreamFailure("upstream response exceeds configured limit")
    body = response.read(limit + 1)
    if len(body) > limit:
        raise UpstreamFailure("upstream response exceeds configured limit")
    return body


def _json(body: bytes) -> Any:
    try:
        return json.loads(body)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise UpstreamFailure("upstream returned malformed JSON") from exc


def _post_entry(body: bytes) -> tuple[str, dict[str, Any]]:
    document = _json(body)
    if not isinstance(document, dict) or len(document) != 1:
        raise UpstreamFailure("POST response must contain exactly one UUID entry")
    uuid, entry = next(iter(document.items()))
    if not isinstance(uuid, str) or not uuid or not isinstance(entry, dict):
        raise UpstreamFailure("POST response contains an invalid UUID entry")
    return uuid, entry


def _proof_ready(body: bytes, uuid: str, submitted: dict[str, Any]) -> bool:
    document = _json(body)
    # Rekor deployments may return a direct entry or a UUID-keyed entry.  A
    # keyed response must name the submitted UUID; a direct response is bound
    # to it by the GET URL and must still match the immutable log metadata.
    if isinstance(document, dict) and uuid in document:
        if len(document) != 1 or not isinstance(document[uuid], dict):
            return False
        entry = document[uuid]
    elif isinstance(document, dict):
        entry = document
    else:
        return False
    verification = entry.get("verification")
    if not isinstance(verification, dict) or not isinstance(verification.get("inclusionProof"), dict):
        return False
    return entry.get("logID") == submitted.get("logID") and entry.get("logIndex") == submitted.get("logIndex") and "logID" in submitted and "logIndex" in submitted


class RekorProxyHandler(BaseHTTPRequestHandler):
    server: "RekorProxyServer"
    protocol_version = "HTTP/1.1"

    def log_message(self, format: str, *args: Any) -> None:
        # BaseHTTPRequestHandler's default includes neither headers nor body,
        # but keep a controlled format so sensitive request material cannot be
        # accidentally added by a future format change.
        LOG.info("method=%s path=%s outcome=%s", self.command, self.path, args[1] if len(args) > 1 else "response")

    def do_GET(self) -> None:
        self._handle()

    def do_POST(self) -> None:
        self._handle()

    def do_PUT(self) -> None:
        self._handle()

    def do_DELETE(self) -> None:
        self._handle()

    def do_PATCH(self) -> None:
        self._handle()

    def do_HEAD(self) -> None:
        self._handle()

    def _handle(self) -> None:
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length < 0:
                raise ValueError
        except ValueError:
            self._error(400, "invalid Content-Length")
            return
        body = self.rfile.read(length)
        status, headers, upstream_body = self.server.request(self.command, self.path, body, self.headers)
        if self.command == "POST" and urlsplit(self.path).path == ENTRY_PATH and 200 <= status < 300:
            self._consistent_response(status, headers, upstream_body)
            return
        self._send(status, headers, upstream_body)

    def _consistent_response(self, status: int, headers: Any, body: bytes) -> None:
        try:
            uuid, submitted = _post_entry(body)
            attempts = self.server.wait_for_proof(uuid, submitted)
        except TimeoutError:
            LOG.info("method=POST path=%s uuid=%s attempts=%s outcome=timeout", self.path, locals().get("uuid", "unknown"), locals().get("attempts", 0))
            self._error(504, "Rekor inclusion proof did not become readable before timeout")
            return
        except UpstreamFailure as exc:
            LOG.info("method=POST path=%s uuid=%s attempts=%s outcome=failed", self.path, locals().get("uuid", "unknown"), locals().get("attempts", 0))
            self._error(502, str(exc))
            return
        LOG.info("method=POST path=%s uuid=%s attempts=%s outcome=ready", self.path, uuid, attempts)
        self._send(status, headers, body)

    def _error(self, status: int, message: str) -> None:
        encoded = json.dumps({"error": message}).encode()
        self._send(status, {"Content-Type": "application/json"}, encoded)

    def _send(self, status: int, headers: Any, body: bytes) -> None:
        self.send_response(status)
        for name, value in headers.items():
            if name.lower() not in HOP_BY_HOP_HEADERS | {"content-length"}:
                self.send_header(name, value)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)


class RekorProxyServer(ThreadingHTTPServer):
    def __init__(self, address: tuple[str, int], config: Config):
        super().__init__(address, RekorProxyHandler)
        self.config = config
        parsed = urlsplit(config.upstream_url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("upstream URL must be absolute HTTP(S) URL")
        self.upstream_url = config.upstream_url.rstrip("/")

    def request(self, method: str, path: str, body: bytes, headers: Any) -> tuple[int, Any, bytes]:
        request_headers = {name: value for name, value in headers.items() if name.lower() not in HOP_BY_HOP_HEADERS | {"host", "content-length"}}
        request = Request(self.upstream_url + path, data=body if method not in {"GET", "HEAD"} else None, headers=request_headers, method=method)
        try:
            with urlopen(request, timeout=self.config.timeout) as response:
                return response.status, response.headers, _read_limited(response, self.config.max_response_size)
        except HTTPError as exc:
            return exc.code, exc.headers, _read_limited(exc, self.config.max_response_size)
        except (URLError, OSError) as exc:
            raise UpstreamFailure("upstream request failed") from exc

    def wait_for_proof(self, uuid: str, submitted: dict[str, Any]) -> int:
        deadline = time.monotonic() + self.config.timeout
        delay = self.config.poll_interval
        attempts = 0
        while True:
            attempts += 1
            try:
                status, _headers, body = self.request("GET", f"{ENTRY_PATH}/{uuid}", b"", {})
                if status == 200 and _proof_ready(body, uuid, submitted):
                    return attempts
            except UpstreamFailure:
                pass
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError
            time.sleep(min(delay, remaining))
            delay = min(delay * 2, self.config.timeout)


def config_from_args(argv: list[str] | None = None) -> tuple[str, int, Config]:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--upstream-url", default=os.environ.get("REKOR_PROXY_UPSTREAM_URL"))
    parser.add_argument("--listen-host", default=os.environ.get("REKOR_PROXY_LISTEN_HOST", "127.0.0.1"))
    parser.add_argument("--listen-port", type=int, default=int(os.environ.get("REKOR_PROXY_LISTEN_PORT", "9301")))
    parser.add_argument("--poll-interval", type=float, default=float(os.environ.get("REKOR_PROXY_POLL_INTERVAL", "0.1")))
    parser.add_argument("--timeout", type=float, default=float(os.environ.get("REKOR_PROXY_TIMEOUT", "5")))
    parser.add_argument("--max-response-size", type=int, default=int(os.environ.get("REKOR_PROXY_MAX_RESPONSE_SIZE", "1048576")))
    args = parser.parse_args(argv)
    if not args.upstream_url or args.poll_interval <= 0 or args.timeout <= 0 or args.max_response_size <= 0:
        parser.error("upstream URL, timeout, poll interval, and response limit must be positive")
    return args.listen_host, args.listen_port, Config(args.upstream_url, args.poll_interval, args.timeout, args.max_response_size)


def main() -> None:
    logging.basicConfig(level=os.environ.get("REKOR_PROXY_LOG_LEVEL", "INFO"), format="%(message)s")
    host, port, config = config_from_args()
    RekorProxyServer((host, port), config).serve_forever()


if __name__ == "__main__":
    main()
