#!/usr/bin/env python3
"""Value-insensitive structural fingerprints for JSON and CSV text.

Untyped and binary formats do not expose defensible field/type evidence and
therefore return ``None`` through :func:`fingerprint_untyped`.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import sys


FINGERPRINT_VERSION = "shape-v1"


def _shape(value: object) -> dict:
    if value is None:
        return {"type": "null"}
    if isinstance(value, bool):
        return {"type": "boolean"}
    if isinstance(value, int):
        return {"type": "integer"}
    if isinstance(value, float):
        return {"type": "number"}
    if isinstance(value, str):
        return {"type": "string"}
    if isinstance(value, dict):
        return {
            "type": "object",
            "fields": [[key, _shape(value[key])] for key in sorted(value)],
        }
    if isinstance(value, list):
        unique_items = {
            json.dumps(_shape(item), sort_keys=True, separators=(",", ":"))
            for item in value
        }
        return {
            "type": "array",
            "items": [json.loads(item) for item in sorted(unique_items)],
        }
    raise TypeError(f"unsupported JSON value type {type(value).__name__}")


def _fingerprint(signature: dict) -> str:
    normalized = json.dumps(signature, sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
    return f"{FINGERPRINT_VERSION}:{digest}"


def fingerprint_json(text: str) -> str:
    """Fingerprint recursive JSON keys and types while ignoring all values."""
    return _fingerprint(_shape(json.loads(text)))


def fingerprint_csv_headers(text: str) -> str:
    """Fingerprint normalized CSV column names in their declared order."""
    reader = csv.reader(io.StringIO(text), strict=True)
    try:
        headers = next(reader)
    except StopIteration as exc:
        raise ValueError("CSV text has no header row") from exc
    normalized_headers = [header.strip() for header in headers]
    if normalized_headers:
        normalized_headers[0] = normalized_headers[0].lstrip("\ufeff")
    return _fingerprint({"type": "csv", "headers": normalized_headers})


def fingerprint_untyped(_: str | bytes) -> None:
    """Return no fingerprint for binary or otherwise untyped formats."""
    return None


def main() -> int:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--json", action="store_true", help="fingerprint JSON input")
    mode.add_argument(
        "--csv-headers", action="store_true", help="fingerprint the CSV header row"
    )
    args = parser.parse_args()
    try:
        if args.json:
            fingerprint = fingerprint_json(sys.stdin.read())
        else:
            fingerprint = fingerprint_csv_headers(sys.stdin.readline())
    except (csv.Error, json.JSONDecodeError, TypeError, ValueError) as exc:
        print(f"Shape fingerprint failed: {exc}", file=sys.stderr)
        return 1
    print(fingerprint)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
