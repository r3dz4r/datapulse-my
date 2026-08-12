"""Shared key-file handling; plaintext API tokens never reach disk."""
from __future__ import annotations
import hashlib, json, secrets
from datetime import datetime, timezone
from pathlib import Path

def now() -> str: return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
def token_hash(token: str, salt: str) -> str:
    return hashlib.sha256((salt + ":" + token).encode()).hexdigest()
def read_keys(path: Path) -> dict:
    if not path.exists(): return {"active": [], "revoked": []}
    data = json.loads(path.read_text(encoding="utf-8"))
    return {"active": data.get("active", []), "revoked": data.get("revoked", [])}
def write_keys(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    temp.replace(path)
def add_key(path: Path, label: str, scopes: list[str], salt: str) -> str:
    data = read_keys(path); token = "dp_" + secrets.token_urlsafe(32)
    data["active"].append({"label": label, "hashed_token": token_hash(token, salt), "scopes": scopes,
                           "created_at": now(), "last_used_at": None})
    write_keys(path, data); return token
def revoke_key(path: Path, label: str) -> bool:
    data = read_keys(path); retained = [k for k in data["active"] if k.get("label") != label]
    moved = [k for k in data["active"] if k.get("label") == label]
    if not moved: return False
    for key in moved: key["revoked_at"] = now()
    data["active"], data["revoked"] = retained, data["revoked"] + moved; write_keys(path, data); return True
