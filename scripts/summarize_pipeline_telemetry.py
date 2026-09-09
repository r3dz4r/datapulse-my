#!/usr/bin/env python3
"""Summarize DataPulse stage telemetry into one sanitized run receipt."""

from __future__ import annotations

import argparse
import json
import os
import re
import tempfile
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any


STAGES = frozenset(
    {
        "probe",
        "history",
        "snapshot",
        "deltas",
        "validate",
        "publish",
        "mcp-sync",
        "attestation-score",
        "evidence",
        "sigstore-request",
    }
)
STATUSES = frozenset({"success", "fail", "skipped"})
SAFE_METADATA_KEYS = frozenset(
    {"result", "non_fatal", "exit_code", "lag_ms", "publication_lag_ms", "source"}
)
SECRET_PATTERN = re.compile(r"(?:api[_-]?key|authorization|bearer|password|private[_-]?key|secret|token)", re.IGNORECASE)
SCHEMA = "datapulse/v1/pipeline-run-receipt"
MODES = frozenset({"health-cycle", "release-build", "audit", "shadow-health"})
COMMIT_PATTERN = re.compile(r"[0-9a-f]{7,64}")


class TelemetryError(ValueError):
    """Raised when telemetry cannot safely support a receipt."""


def parse_commit_identifier(value: str) -> str:
    """Validate a lowercase hexadecimal source or health commit identifier."""
    if COMMIT_PATTERN.fullmatch(value) is None:
        raise argparse.ArgumentTypeError("must be 7-64 lowercase hexadecimal characters")
    return value


def parse_timestamp(value: object, line_number: int) -> datetime:
    """Parse an offset-aware telemetry timestamp into UTC."""
    if not isinstance(value, str):
        raise TelemetryError(f"line {line_number}: ts must be a string")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise TelemetryError(f"line {line_number}: invalid timestamp") from exc
    if parsed.tzinfo is None:
        raise TelemetryError(f"line {line_number}: timestamp must include an offset")
    return parsed.astimezone(UTC)


def format_timestamp(value: datetime) -> str:
    """Return a stable UTC timestamp suitable for the public receipt."""
    return value.isoformat().replace("+00:00", "Z")


def sanitize_metadata(value: object, line_number: int) -> dict[str, Any]:
    """Retain only typed, non-secret fields explicitly safe for receipts."""
    if not isinstance(value, dict):
        raise TelemetryError(f"line {line_number}: extra must be an object")
    metadata: dict[str, Any] = {}
    for key in sorted(SAFE_METADATA_KEYS.intersection(value)):
        item = value[key]
        if key in {"result", "source"}:
            if not isinstance(item, str) or not item or len(item) > 256 or SECRET_PATTERN.search(item):
                raise TelemetryError(f"line {line_number}: unsafe {key} metadata")
        elif key == "non_fatal":
            if not isinstance(item, bool):
                raise TelemetryError(f"line {line_number}: non_fatal must be boolean")
        elif not isinstance(item, int) or isinstance(item, bool) or item < 0:
            raise TelemetryError(f"line {line_number}: {key} must be a non-negative integer")
        metadata[key] = item
    return metadata


def parse_event(value: object, line_number: int) -> dict[str, Any]:
    """Validate one telemetry row and discard all non-receipt fields."""
    if not isinstance(value, dict):
        raise TelemetryError(f"line {line_number}: event must be an object")
    stage = value.get("stage")
    status = value.get("status")
    cycle = value.get("cycle")
    duration_ms = value.get("duration_ms")
    if not isinstance(stage, str) or stage not in STAGES:
        raise TelemetryError(f"line {line_number}: unknown stage")
    if not isinstance(status, str) or status not in STATUSES:
        raise TelemetryError(f"line {line_number}: unknown status")
    if not isinstance(cycle, str) or not cycle:
        raise TelemetryError(f"line {line_number}: cycle must be a non-empty string")
    if not isinstance(duration_ms, int) or isinstance(duration_ms, bool) or duration_ms < 0:
        raise TelemetryError(f"line {line_number}: duration_ms must be a non-negative integer")
    return {
        "timestamp": parse_timestamp(value.get("ts"), line_number),
        "stage": stage,
        "status": status,
        "cycle": cycle,
        "duration_ms": duration_ms,
        "metadata": sanitize_metadata(value.get("extra"), line_number),
    }


def read_events(path: Path) -> list[dict[str, Any]]:
    """Read and validate every non-empty JSONL row before selecting a cycle."""
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise TelemetryError(f"cannot read telemetry: {exc}") from exc
    events: list[dict[str, Any]] = []
    for line_number, line in enumerate(lines, start=1):
        if not line.strip():
            raise TelemetryError(f"line {line_number}: empty rows are not allowed")
        try:
            event = json.loads(line)
        except json.JSONDecodeError as exc:
            raise TelemetryError(f"line {line_number}: malformed JSON") from exc
        events.append(parse_event(event, line_number))
    if not events:
        raise TelemetryError("telemetry is empty")
    return events


def select_cycle(events: list[dict[str, Any]], requested_cycle: str | None) -> tuple[str, list[dict[str, Any]]]:
    """Select the requested cycle, or the latest cycle by event timestamp."""
    if requested_cycle is None:
        cycle_last_seen: dict[str, datetime] = {}
        for event in events:
            cycle = event["cycle"]
            cycle_last_seen[cycle] = max(cycle_last_seen.get(cycle, event["timestamp"]), event["timestamp"])
        requested_cycle = max(cycle_last_seen, key=lambda cycle: (cycle_last_seen[cycle], cycle))
    selected = [event for event in events if event["cycle"] == requested_cycle]
    if not selected:
        raise TelemetryError(f"no events for cycle {requested_cycle!r}")
    return requested_cycle, selected


def build_receipt(
    events: list[dict[str, Any]], cycle: str, mode: str, source_commit: str, health_commit: str
) -> dict[str, Any]:
    """Build one deterministic receipt while rejecting contradictory stage records."""
    by_stage: dict[str, dict[str, Any]] = {}
    for event in events:
        stage = event["stage"]
        previous = by_stage.get(stage)
        if previous is not None and previous != event:
            raise TelemetryError(f"contradictory duplicate record for stage {stage}")
        by_stage[stage] = event
    timestamps = [event["timestamp"] for event in events]
    first_timestamp = min(timestamps)
    last_timestamp = max(timestamps)
    stages = {
        stage: {
            "duration_ms": by_stage[stage]["duration_ms"],
            "metadata": by_stage[stage]["metadata"],
            "status": by_stage[stage]["status"],
        }
        for stage in sorted(by_stage)
    }
    return {
        "cycle": cycle,
        "failed_stages": sorted(stage for stage, entry in stages.items() if entry["status"] == "fail"),
        "first_timestamp": format_timestamp(first_timestamp),
        "last_timestamp": format_timestamp(last_timestamp),
        "health_commit": health_commit,
        "mode": mode,
        "schema": SCHEMA,
        "source_commit": source_commit,
        "stages": stages,
        "total_elapsed_ms": (last_timestamp - first_timestamp) // timedelta(milliseconds=1),
        "version": 1,
    }


def write_receipt(path: Path, receipt: dict[str, Any]) -> None:
    """Atomically replace the receipt only after complete serialization succeeds."""
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(receipt, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_name, path)
    except BaseException:
        try:
            os.unlink(temporary_name)
        except FileNotFoundError:
            pass
        raise


def main() -> int:
    """Run the telemetry summarizer CLI."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path, help="telemetry JSONL input")
    parser.add_argument("--output", required=True, type=Path, help="run receipt JSON output")
    parser.add_argument("--cycle", help="cycle to summarize; defaults to the latest cycle")
    parser.add_argument("--mode", required=True, choices=sorted(MODES), help="pipeline execution mode")
    parser.add_argument("--source-commit", required=True, type=parse_commit_identifier, help="source commit")
    parser.add_argument("--health-commit", required=True, type=parse_commit_identifier, help="health commit")
    args = parser.parse_args()
    try:
        events = read_events(args.input)
        cycle, selected = select_cycle(events, args.cycle)
        write_receipt(args.output, build_receipt(selected, cycle, args.mode, args.source_commit, args.health_commit))
    except TelemetryError as exc:
        parser.error(str(exc))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
