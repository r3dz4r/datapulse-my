"""Authenticated, versioned HTTP API for DataPulse buyers.

This deliberately does not import the public FastMCP server: buyer policy
(keys, rate limits and audit records) is isolated from public discovery.
"""
from __future__ import annotations

import argparse
import json
import time
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

from api.config import Config
from api.entitlements import Entitlements
from api.keys import read_keys, token_hash, write_keys
from api.paddle import PaddleError, parse_approved_event, verify_signature
from api.pharma_proxy import fetch as pharma_fetch


def _utcnow() -> datetime: return datetime.now(timezone.utc)
def _iso() -> str: return _utcnow().isoformat().replace("+00:00", "Z")
def _json(path: Path) -> Any: return json.loads(path.read_text(encoding="utf-8"))

class RateLimiter:
    """A per-key token bucket backed by an atomically replaced JSON file."""
    def __init__(self, path: Path, per_minute: int):
        self.path, self.per_minute = path, per_minute
        self.cache = self._load()
    def _load(self) -> dict[str, dict[str, float]]:
        try: return _json(self.path)
        except (FileNotFoundError, json.JSONDecodeError): return {}
    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True); temp = self.path.with_suffix(".tmp")
        temp.write_text(json.dumps(self.cache), encoding="utf-8"); temp.replace(self.path)
    def allow(self, key_hash: str) -> tuple[bool, int]:
        now = time.time(); bucket = self.cache.get(key_hash, {"count": 0, "window_started_at": now})
        started = float(bucket.get("window_started_at", now))
        if now - started >= 60: bucket, started = {"count": 0, "window_started_at": now}, now
        if int(bucket.get("count", 0)) >= self.per_minute:
            retry = max(1, int(60 - (now - started)) + 1); self.cache[key_hash] = bucket; self._save(); return False, retry
        bucket["count"] = int(bucket.get("count", 0)) + 1; self.cache[key_hash] = bucket; self._save(); return True, 0

class BuyerApplication:
    def __init__(self, config: Config):
        self.config, self.rate_limiter, self._json_cache = config, RateLimiter(config.rate_state_file, config.rate_limit), {}
        self.entitlements = Entitlements(config.entitlement_file or config.root / "var/entitlements.json", config.key_salt)
    def load_json(self, path: Path) -> Any:
        """Cache parsed generated artifacts until their atomic replacement changes mtime."""
        stamp = path.stat().st_mtime_ns
        cached = self._json_cache.get(path)
        if cached and cached[0] == stamp: return cached[1]
        value = _json(path); self._json_cache[path] = (stamp, value); return value
    def authenticate(self, token: str | None) -> tuple[dict | None, str | None]:
        if not token: return None, None
        hashed = token_hash(token, self.config.key_salt)
        data = read_keys(self.config.keys_file)
        for item in data["active"]:
            if item.get("hashed_token") == hashed:
                item["last_used_at"] = _iso(); write_keys(self.config.keys_file, data); return item, hashed
        return None, hashed
    def audit(self, **entry: Any) -> None:
        self.config.audit_log.parent.mkdir(parents=True, exist_ok=True)
        with self.config.audit_log.open("a", encoding="utf-8") as output: output.write(json.dumps({"ts": _iso(), **entry}, sort_keys=True) + "\n")
    def health(self) -> dict: return self.load_json(self.config.root / "health/latest.json")
    def history(self) -> list[dict]:
        path = self.config.root / "health/history.jsonl"
        if not path.exists(): return []
        return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]

class Handler(BaseHTTPRequestHandler):
    server_version = "DataPulseBuyerAPI/1"
    def log_message(self, *args: Any) -> None: pass
    @property
    def app(self) -> BuyerApplication: return self.server.app  # type: ignore[attr-defined]
    def response(self, status: int, body: Any, headers: dict[str, str] | None = None) -> None:
        encoded = json.dumps(body, separators=(",", ":")).encode(); self.send_response(status); self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(encoded)))
        origin = self.headers.get("Origin")
        if origin in {"https://data-pulse.my", "https://www.data-pulse.my"}:
            self.send_header("Access-Control-Allow-Origin", origin); self.send_header("Vary", "Origin")
        for key, value in (headers or {}).items(): self.send_header(key, value)
        self.end_headers(); self.wfile.write(encoded)
    def error(self, status: int, code: str, message: str, retry: int | None = None) -> None:
        details: dict[str, Any] = {"code": code, "message": message}
        if retry is not None: details["retry_after_s"] = retry
        headers = {"Retry-After": str(retry)} if retry is not None else None
        self.response(status, {"error": details}, headers)
    def page(self, values: list[Any], query: dict[str, list[str]]) -> dict:
        try: size = min(max(1, int(query.get("limit", ["50"])[0])), self.app.config.pagination_max); start = max(0, int(query.get("cursor", ["0"])[0]))
        except ValueError: size, start = 50, 0
        end = start + size
        return {"data": values[start:end], "pagination": {"limit": size, "next_cursor": str(end) if end < len(values) else None, "total": len(values)}}
    def do_OPTIONS(self) -> None:
        if self.headers.get("Origin") not in {"https://data-pulse.my", "https://www.data-pulse.my"}: self.send_response(403); self.end_headers(); return
        self.send_response(204); self.send_header("Access-Control-Allow-Origin", self.headers["Origin"]); self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS"); self.send_header("Access-Control-Allow-Headers", "X-API-Key, Content-Type"); self.send_header("Vary", "Origin"); self.end_headers()
    def _body(self) -> bytes:
        try: length = int(self.headers.get("Content-Length", "0"))
        except ValueError: raise ValueError("invalid body") from None
        if length < 1 or length > 256 * 1024: raise ValueError("invalid body")
        return self.rfile.read(length)
    def do_POST(self) -> None:
        path = urlparse(self.path).path
        try:
            raw = self._body()
            if path == "/api/v1/paddle/webhook":
                verify_signature(raw, self.headers.get("Paddle-Signature"), self.app.config.paddle_webhook_secret)
                event_id, event_type, data, payload_hash = parse_approved_event(raw)
                outcome = self.app.entitlements.apply_event(event_id, event_type, payload_hash, data)
                if outcome == "security_failure":
                    self.app.audit(
                        event="webhook_replay_payload_conflict",
                        event_id=event_id,
                        status=409,
                    )
                    self.error(409, "webhook_replay_conflict", "Conflicting replay was rejected")
                    return
                # The browser already holds the nonce; its hash is stored server-side only.
                # Webhook responses never return the nonce or a redemption token.
                self.response(200, {"data": {"outcome": outcome}}); return
            if path == "/api/v1/paddle/redeem":
                payload = json.loads(raw)
                if not isinstance(payload, dict) or not isinstance(payload.get("redemption_token"), str): raise ValueError("invalid redemption")
                outcome, key = self.app.entitlements.redeem(payload["redemption_token"])
                if outcome == "pending":
                    self.error(409, "redemption_pending", "Payment confirmation is pending", 2)
                    return
                if outcome == "invalid":
                    self.error(409, "redemption_invalid", "Redemption token is invalid or unavailable")
                    return
                self.response(201, {"data": {"api_key": key, "tier": "pro", "scopes": ["npra.read"]}}); return
            self.error(404, "not_found", "Resource not found")
        except (PaddleError, ValueError, json.JSONDecodeError): self.error(400, "invalid_request", "Request could not be accepted")
    def do_GET(self) -> None:
        started = time.monotonic(); status = 500; key, key_hash = None, None
        try:
            key, key_hash = self.app.authenticate(self.headers.get("X-API-Key"))
            pro = self.app.entitlements.by_key(self.headers.get("X-API-Key", ""))
            if not key and not pro: status = 401; self.error(401, "unauthorized", "A valid X-API-Key is required"); return
            if key:
                permitted, retry = self.app.rate_limiter.allow(key_hash or "")
                if not permitted: status = 429; self.error(429, "rate_limited", "Rate limit exceeded", retry); return
            parsed = urlparse(self.path); path, query = parsed.path, parse_qs(parsed.query)
            if not path.startswith("/api/v1/"): status = 404; self.error(404, "not_found", "Resource not found"); return
            if path == "/api/v1/keys/me":
                if not pro: status = 403; self.error(403, "forbidden", "Pro entitlement required"); return
                status = 200; self.response(200, {"data": {"tier": "pro", "status": pro.get("status"), "scopes": pro.get("scopes"), "quota_remaining": max(0, int(pro.get("quota", 100000)) - int(pro.get("used", 0))), "reset_at": pro.get("reset_at")}}); return
            if path.startswith("/api/v1/npra/"):
                if not pro or pro.get("status") != "active" or "npra.read" not in pro.get("scopes", []): status = 403; self.error(403, "forbidden", "Active Pro entitlement required"); return
                parts = path.split("/"); resource = parts[4] if len(parts) == 5 else ""; identifier = parts[5] if len(parts) == 6 else None
                collections = {"health", "changes"}; lookups = {"product", "manufacturer", "importer"}
                if (
                    (resource in collections and len(parts) != 5)
                    or (resource in lookups and (len(parts) != 6 or not identifier))
                    or resource not in collections | lookups
                ): status = 404; self.error(404, "not_found", "Resource not found"); return
                charge, _current = self.app.entitlements.charge(self.headers.get("X-API-Key", ""))
                if charge == "quota_exhausted": status = 403; self.error(403, "quota_exhausted", "Billing-period quota exhausted"); return
                if charge != "charged": status = 403; self.error(403, "forbidden", "Active Pro entitlement required"); return
                try:
                    upstream_status, payload = pharma_fetch(self.app.config.pharma_engine_url, self.app.config.pharma_api_key, resource, identifier)
                    if upstream_status >= 500:
                        self.app.entitlements.refund(self.headers.get("X-API-Key", "")); status = upstream_status; self.response(upstream_status, {"data": payload}); return
                except Exception:
                    self.app.entitlements.refund(self.headers.get("X-API-Key", "")); status = 503; self.error(503, "upstream_unavailable", "NPRA engine temporarily unavailable", 5); return
                status = upstream_status; self.response(upstream_status, {"data": payload}); return
            if path == "/api/v1/health": status = 200; self.response(200, {"status": "ok", "service": "buyer-api", "checked_at": self.app.health().get("checked_at")}); return
            if path == "/api/v1/datasets": status = 200; self.response(200, self.page(self.app.health().get("datasets", []), query)); return
            if path.startswith("/api/v1/datasets/"):
                parts = path.split("/"); dataset_id = parts[4] if len(parts) > 4 else ""
                if len(parts) == 6 and parts[5] == "history":
                    days = min(3650, max(1, int(query.get("days", ["30"])[0]))); cutoff = _utcnow() - timedelta(days=days)
                    rows = [r for r in self.app.history() if r.get("dataset_id") == dataset_id and _parse_time(r.get("observed_at")) >= cutoff]
                    status = 200; self.response(200, self.page(rows, query)); return
                row = next((r for r in self.app.health().get("datasets", []) if r.get("dataset_id") == dataset_id), None)
                if row is None: status = 404; self.error(404, "not_found", "Dataset not found"); return
                status = 200; self.response(200, {"data": row}); return
            if path == "/api/v1/deltas":
                after, before = query.get("from", [None])[0], query.get("to", [None])[0]
                records = []
                for file in sorted((self.app.config.root / "deltas").glob("*.json")):
                    cycle = file.stem
                    if (after and cycle < after) or (before and cycle > before): continue
                    records.append({"cycle": cycle, "observed_at": self.app.load_json(file).get("observed_at")})
                status = 200; self.response(200, self.page(records, query)); return
            if path.startswith("/api/v1/deltas/"):
                cycle = path.rsplit("/", 1)[1]; file = self.app.config.root / "deltas" / (cycle + ".json")
                if not file.is_file(): status = 404; self.error(404, "not_found", "Delta not found"); return
                status = 200; self.response(200, {"data": self.app.load_json(file)}); return
            if path == "/api/v1/snapshot": status = 200; self.response(200, {"data": self.app.load_json(self.app.config.root / "catalog-snapshot.json")}); return
            status = 404; self.error(404, "not_found", "Resource not found")
        except (OSError, json.JSONDecodeError, ValueError):
            status = 503; self.error(503, "artifact_unavailable", "Service data is temporarily unavailable", 5)
        finally:
            self.app.audit(key_label=key.get("label") if key else None, key_hash=key_hash, method="GET", path=urlparse(self.path).path, status=status, latency_ms=round((time.monotonic()-started)*1000), ip=self.client_address[0], ua=self.headers.get("User-Agent", ""))

def _parse_time(value: str | None) -> datetime:
    try: return datetime.fromisoformat((value or "").replace("Z", "+00:00"))
    except ValueError: return datetime.min.replace(tzinfo=timezone.utc)
def make_server(config: Config) -> ThreadingHTTPServer:
    server = ThreadingHTTPServer((config.bind_host, config.bind_port), Handler); server.app = BuyerApplication(config)  # type: ignore[attr-defined]
    return server
def main() -> None:
    parser = argparse.ArgumentParser(); parser.add_argument("--bind", default=None); args = parser.parse_args(); config = Config.from_env()
    if args.bind:
        host, port = args.bind.rsplit(":", 1); config = Config(**{**config.__dict__, "bind_host": host, "bind_port": int(port)})
    server = make_server(config); print(f"buyer API listening on {config.bind_host}:{config.bind_port}", flush=True); server.serve_forever()
if __name__ == "__main__": main()
