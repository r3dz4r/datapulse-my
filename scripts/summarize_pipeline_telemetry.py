#!/usr/bin/env python3
"""Summarize DataPulse stage telemetry into one sanitized run receipt."""

from __future__ import annotations

import argparse
import json
import re
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

try:  # imported as scripts.summarize_pipeline_telemetry (tests)
    from scripts.artifact_modes import replace_file
except ImportError:  # executed directly: scripts/ is on sys.path
    from artifact_modes import replace_file


STAGES = frozenset(
    {
        "probe",
        "history",
        "snapshot",
        "deltas",
        "validate",
        "publish",
        "kv-index",
        "mcp-sync",
        "attestation-score",
        "passports",
        "evidence",
        "sigstore-request",
        "observation-capture",
    }
)
STATUSES = frozenset({"success", "fail", "skipped"})
SAFE_METADATA_KEYS = frozenset(
    {"result", "non_fatal", "exit_code", "lag_ms", "publication_lag_ms", "source"}
)
SECRET_PATTERN = re.compile(r"(?:api[_-]?key|authorization|bearer|password|private[_-]?key|secret|token)", re.IGNORECASE)
SUBSTAGE_TOKEN = re.compile(r"[a-z0-9][a-z0-9_-]*")
SCHEMA = "datapulse/v1/pipeline-run-receipt"
MODES = frozenset({"health-cycle", "release-build", "audit", "shadow-health"})
COMMIT_PATTERN = re.compile(r"[0-9a-f]{7,64}")


class TelemetryError(ValueError):
    """Raised when telemetry cannot safely support a receipt."""


def is_valid_stage(value: str) -> bool:
    """Return whether a stage uses a known root and optional valid sub-stage."""
    root, separator, token = value.partition(".")
    return root in STAGES and (not separator or SUBSTAGE_TOKEN.fullmatch(token) is not None)


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
    if not isinstance(stage, str) or not is_valid_stage(stage):
        roots = ", ".join(sorted(STAGES))
        raise TelemetryError(f"line {line_number}: unknown stage; accepted roots: {roots}")
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


def distinct_events(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Collapse exact duplicate records while preserving first-seen order."""
    distinct: list[dict[str, Any]] = []
    for event in events:
        if event not in distinct:
            distinct.append(event)
    return distinct


def build_receipt(
    events: list[dict[str, Any]], cycle: str, mode: str, source_commit: str, health_commit: str
) -> dict[str, Any]:
    """Build one deterministic receipt while rejecting contradictory stage records.

    A stage can legitimately be attempted more than once in a cycle: an earlier
    attempt may be coalesced (``skipped``) and a later attempt may actually
    perform the work. That sequence is not contradictory -- the later
    non-skipped record is authoritative, and the coalesced attempt is preserved
    in the receipt rather than dropped. Two differing non-skipped records for
    one stage remain a defect and are refused.
    """
    grouped: dict[str, list[dict[str, Any]]] = {}
    for event in events:
        grouped.setdefault(event["stage"], []).append(event)
    by_stage: dict[str, dict[str, Any]] = {}
    coalesced: dict[str, list[dict[str, Any]]] = {}
    for stage in sorted(grouped):
        records = grouped[stage]
        performed = distinct_events([record for record in records if record["status"] != "skipped"])
        skipped = distinct_events([record for record in records if record["status"] == "skipped"])
        if len(performed) > 1:
            raise TelemetryError(f"contradictory duplicate record for stage {stage}")
        if not performed:
            if len(skipped) > 1:
                raise TelemetryError(f"contradictory duplicate record for stage {stage}")
            by_stage[stage] = skipped[0]
            continue
        # A coalesced attempt is only superseded by work that happened after it.
        if any(attempt["timestamp"] >= performed[0]["timestamp"] for attempt in skipped):
            raise TelemetryError(f"contradictory duplicate record for stage {stage}")
        by_stage[stage] = performed[0]
        if skipped:
            coalesced[stage] = sorted(skipped, key=lambda attempt: attempt["timestamp"])
    timestamps = [event["timestamp"] for event in events]
    first_timestamp = min(timestamps)
    last_timestamp = max(timestamps)
    stages: dict[str, dict[str, Any]] = {}
    for stage in sorted(by_stage):
        entry: dict[str, Any] = {
            "duration_ms": by_stage[stage]["duration_ms"],
            "metadata": by_stage[stage]["metadata"],
            "status": by_stage[stage]["status"],
        }
        if stage in coalesced:
            entry["coalesced"] = [
                {
                    "duration_ms": attempt["duration_ms"],
                    "metadata": attempt["metadata"],
                    "status": attempt["status"],
                    "timestamp": format_timestamp(attempt["timestamp"]),
                }
                for attempt in coalesced[stage]
            ]
        stages[stage] = entry
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
    payload = json.dumps(receipt, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    replace_file(path, payload.encode("utf-8"))


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
