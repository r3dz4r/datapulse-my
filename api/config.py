"""Configuration for the authenticated DataPulse buyer API."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _bounded_int(name: str, default: int, maximum: int) -> int:
    try:
        value = int(os.getenv(name, str(default)))
    except ValueError:
        value = default
    return max(1, min(value, maximum))


@dataclass(frozen=True)
class Config:
    root: Path
    keys_file: Path
    rate_state_file: Path
    rate_limit: int
    bind_host: str
    bind_port: int
    audit_log: Path
    pagination_max: int
    key_salt: str
    entitlement_file: Path | None = None
    paddle_webhook_secret: str = ""
    pharma_api_key: str = ""
    pharma_engine_url: str = "http://127.0.0.1:8001"

    @classmethod
    def from_env(cls, root: Path | None = None) -> Config:
        root = root or Path(os.getenv("DATAPULSE_API_ROOT", Path(__file__).resolve().parents[1]))
        def path(name: str, default: str) -> Path:
            item = Path(os.getenv(name, default))
            return item if item.is_absolute() else root / item
        host = os.getenv("DATAPULSE_API_BIND_HOST", "127.0.0.1")
        port = _bounded_int("DATAPULSE_API_BIND_PORT", 8791, 65535)
        return cls(root, path("DATAPULSE_API_KEYS_FILE", "var/api_keys.json"),
                   path("DATAPULSE_API_RATE_STATE", "var/rate_limit.json"),
                   _bounded_int("DATAPULSE_API_RATE_LIMIT", 100, 1000), host, port,
                   path("DATAPULSE_API_AUDIT_LOG", "var/log/buyer-api-audit.jsonl"),
                   _bounded_int("DATAPULSE_API_PAGINATION_MAX", 200, 1000),
                   os.getenv("DATAPULSE_API_KEY_SALT", "datapulse-api-v1"),
                   path("DATAPULSE_API_ENTITLEMENTS_FILE", "var/entitlements.json"),
                   os.getenv("PADDLE_SANDBOX_WEBHOOK_SECRET", ""),
                   os.getenv("PHARMA_API_KEY", ""),
                   os.getenv("PHARMA_ENGINE_URL", "http://127.0.0.1:8001"))
