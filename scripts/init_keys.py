#!/usr/bin/env python3
"""Create a protected Ed25519 probe key and append its public registry row."""
from __future__ import annotations
import argparse, base64, hashlib, json, os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, NoEncryption, PrivateFormat, PublicFormat

def iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--private-key", type=Path, required=True)
    parser.add_argument("--registry", type=Path, required=True)
    parser.add_argument("--lifetime-days", type=int, default=365)
    parser.add_argument("--supersedes")
    args = parser.parse_args()
    if args.private_key.exists():
        raise SystemExit(f"refusing to overwrite {args.private_key}")
    now = datetime.now(timezone.utc).replace(microsecond=0)
    private = Ed25519PrivateKey.generate()
    private_raw = private.private_bytes(Encoding.Raw, PrivateFormat.Raw, NoEncryption())
    public_raw = private.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
    key_id = "ed25519-" + hashlib.sha256(public_raw).hexdigest()[:16]
    private_doc = {"schema":"datapulse/v1/private-probe-key", "key_id":key_id, "private_key_base64":base64.b64encode(private_raw).decode(), "public_key_base64":base64.b64encode(public_raw).decode(), "created_at":iso(now)}
    args.private_key.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(args.private_key, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as output:
        json.dump(private_doc, output, indent=2); output.write("\n")
    registry = json.loads(args.registry.read_text()) if args.registry.exists() else {"schema":"datapulse/v1/probe-key-registry", "version":1, "keys":[]}
    registry["keys"].append({"key_id":key_id, "algorithm":"Ed25519", "public_key_base64":private_doc["public_key_base64"], "created_at":iso(now), "not_before":iso(now), "not_after":iso(now + timedelta(days=args.lifetime_days)), "status":"active", "supersedes":args.supersedes, "compromised_at":None})
    registry["updated_at"] = iso(now)
    args.registry.parent.mkdir(parents=True, exist_ok=True)
    args.registry.write_text(json.dumps(registry, indent=2) + "\n", encoding="utf-8")
    print(key_id)
    return 0

if __name__ == "__main__": raise SystemExit(main())
