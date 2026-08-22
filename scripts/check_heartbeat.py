#!/usr/bin/env python3
"""Append structured DataPulse cycle-stage telemetry."""

from __future__ import annotations

import argparse
import json
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_LOG = ROOT / "var/log/stages.jsonl"
STAGES = {
    "probe",
    "history",
    "snapshot",
    "deltas",
    "validate",
    "publish",
    "mcp-sync",
    "attestation-score",
    "evidence",
}
STATUSES = {"success", "fail", "skipped"}


def parse_ts(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC)


def log_path() -> Path:
    return Path(os.environ.get("DATAPULSE_TELEMETRY_FILE", str(DEFAULT_LOG)))


def append_event(event: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    now = parse_ts(event["ts"])
    cutoff = now - timedelta(days=1)
    retained: list[str] = []
    old_events: dict[str, list[str]] = {}
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            try:
                previous = json.loads(line)
                previous_ts = parse_ts(previous["ts"])
            except (json.JSONDecodeError, KeyError, TypeError, ValueError):
                retained.append(line)
                continue
            if previous_ts < cutoff:
                old_events.setdefault(previous_ts.date().isoformat(), []).append(line)
            else:
                retained.append(line)
    retained.append(json.dumps(event, separators=(",", ":"), sort_keys=True))
    path.write_text("\n".join(retained) + "\n", encoding="utf-8")
    for date, lines in old_events.items():
        rotated = path.with_name(f"{path.stem}.{date}{path.suffix}")
        with rotated.open("a", encoding="utf-8") as handle:
            handle.write("\n".join(lines) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    append = subparsers.add_parser("append", help="append one stage completion event")
    append.add_argument("--stage", required=True, choices=sorted(STAGES))
    append.add_argument("--duration", required=True, type=int)
    append.add_argument("--status", required=True, choices=sorted(STATUSES))
    append.add_argument("--cycle", default=os.environ.get("DATAPULSE_CYCLE"))
    append.add_argument("--extra-json", default="{}", help="JSON object merged into extra")
    append.add_argument("--lag-ms", type=int, help="publication lag, for publish events")
    args = parser.parse_args()
    try:
        extra = json.loads(args.extra_json)
        if not isinstance(extra, dict):
            raise ValueError("--extra-json must be a JSON object")
    except (json.JSONDecodeError, ValueError) as exc:
        parser.error(str(exc))
    if args.lag_ms is not None:
        extra["lag_ms"] = args.lag_ms
        extra["publication_lag_ms"] = args.lag_ms
    now = datetime.now(UTC)
    event = {
        "ts": now.isoformat(timespec="seconds").replace("+00:00", "Z"),
        "stage": args.stage,
        "duration_ms": args.duration,
        "status": args.status,
        "cycle": args.cycle or now.strftime("%Y-%m-%dT%H:%M"),
        "extra": extra,
    }
    append_event(event, log_path())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
