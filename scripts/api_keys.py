#!/usr/bin/env python3
"""Operator CLI for buyer API keys."""
from __future__ import annotations
import argparse
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from api.config import Config
from api.keys import add_key, read_keys, revoke_key

def main() -> int:
    parser = argparse.ArgumentParser(); sub = parser.add_subparsers(dest="command", required=True)
    add = sub.add_parser("add"); add.add_argument("--label", required=True); add.add_argument("--scope", required=True)
    sub.add_parser("list"); revoke = sub.add_parser("revoke"); revoke.add_argument("--label", required=True)
    args = parser.parse_args(); config = Config.from_env()
    if args.command == "add":
        token = add_key(config.keys_file, args.label, [x for x in args.scope.split(",") if x], config.key_salt)
        print("API key (shown once): " + token); return 0
    if args.command == "revoke":
        if not revoke_key(config.keys_file, args.label): parser.error("no active key with that label")
        print("revoked " + args.label); return 0
    for section in ("active", "revoked"):
        for item in read_keys(config.keys_file)[section]:
            print(f"{section:7} {item['label']:20} {item.get('hashed_token', '')[:10]}… {','.join(item.get('scopes', []))}")
    return 0
if __name__ == "__main__": raise SystemExit(main())
