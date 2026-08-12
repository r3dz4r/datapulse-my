"""Authenticated, versioned HTTP API for DataPulse buyers.

This deliberately does not import the public FastMCP server: buyer policy
(keys, rate limits and audit records) is isolated from public discovery.
"""
from __future__ import annotations
import argparse, json, os, time
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse
from typing import Any
from api.config import Config
from api.keys import read_keys, token_hash, write_keys

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
    def do_GET(self) -> None:
        started = time.monotonic(); status = 500; key, key_hash = None, None
        try:
            key, key_hash = self.app.authenticate(self.headers.get("X-API-Key"))
            if not key: status = 401; self.error(401, "unauthorized", "A valid X-API-Key is required"); return
            permitted, retry = self.app.rate_limiter.allow(key_hash or "")
            if not permitted: status = 429; self.error(429, "rate_limited", "Rate limit exceeded", retry); return
            parsed = urlparse(self.path); path, query = parsed.path, parse_qs(parsed.query)
            if not path.startswith("/api/v1/"): status = 404; self.error(404, "not_found", "Resource not found"); return
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
        except (OSError, json.JSONDecodeError, ValueError) as exc:
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
