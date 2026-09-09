#!/usr/bin/env python3
"""Aggregate captured pipeline evidence into a deterministic offline report."""

from __future__ import annotations

import argparse
import json
import os
import re
import tempfile
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


SCHEMA = "datapulse/v1/pipeline-observation-report"
VERSION = 1
STAGES = frozenset({"probe", "history", "snapshot", "deltas", "validate", "publish", "mcp-sync", "attestation-score", "evidence", "sigstore-request"})
STATUSES = frozenset({"success", "fail", "skipped"})
WORKFLOW_STATUSES = frozenset({"queued", "in_progress", "completed", "waiting", "requested", "pending"})
CONCLUSIONS = frozenset({"action_required", "cancelled", "failure", "neutral", "skipped", "stale", "success", "timed_out", "startup_failure"})
ENVELOPE_KEYS = frozenset({"schema", "version", "source_commit", "health_commit", "checked_at", "dataset_count", "health_sha256", "semantic_sha256"})
COMMIT_RE = re.compile(r"^[0-9a-f]{7,64}$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
SAFE_WORKFLOW_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 ._:/()\-]{0,127}$")
SECRET_RE = re.compile(r"(?:api[_-]?key|authorization|bearer|password|private[_-]?key|secret|token|credential)", re.IGNORECASE)
REASON_CODES = frozenset({"missing_input", "malformed_input", "out_of_window", "invalid_identity", "invalid_digest", "unsupported_value", "no_matching_evidence"})
ISO_TIMESTAMP_PATTERN = r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})"
MAX_INPUT_BYTES = 8 * 1024 * 1024
MAX_REASONS = 8


class ObservationError(Exception):
    """Base exception containing only a fixed safe error code."""


class InputError(ObservationError):
    """Raised when a supplied input cannot be safely read."""


def parse_timestamp(value: object) -> datetime:
    """Return an offset-aware ISO-8601 timestamp in UTC."""
    if not isinstance(value, str):
        raise InputError("malformed_input")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise InputError("malformed_input") from exc
    if parsed.tzinfo is None:
        raise InputError("malformed_input")
    return parsed.astimezone(UTC)


def timestamp_text(value: datetime) -> str:
    """Render a UTC timestamp in a stable public form."""
    return value.isoformat(timespec="seconds").replace("+00:00", "Z")


def read_text(path: Path) -> str:
    """Read a bounded regular input file without exposing its path on error."""
    try:
        if path.is_symlink() or not path.is_file() or path.stat().st_size > MAX_INPUT_BYTES:
            raise OSError
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise InputError("missing_input") from exc


def empty_coverage(reason: str) -> dict[str, object]:
    """Build a coverage record with only fixed reason codes."""
    return {"status": "unknown", "reasons": [reason]}


def coverage(reasons: set[str]) -> dict[str, object]:
    """Return deterministic coverage state from bounded reason codes."""
    safe_reasons = sorted(reason for reason in reasons if reason in REASON_CODES)[:MAX_REASONS]
    return {"status": "verifiable" if not safe_reasons else "unknown", "reasons": safe_reasons}


def in_window(value: datetime, start: datetime, end: datetime) -> bool:
    """Use a half-open reporting interval to avoid double-counting boundaries."""
    return start <= value < end


def parse_telemetry(path: Path | None, start: datetime, end: datetime) -> tuple[dict[str, object], dict[str, object], dict[str, object]]:
    """Aggregate strict heartbeat events while retaining no event payloads."""
    if path is None:
        return {"cycles": 0, "stage_events": 0, "stages": {}}, {"first": None, "last": None}, empty_coverage("missing_input")
    try:
        lines = read_text(path).splitlines()
    except InputError as exc:
        return {"cycles": 0, "stage_events": 0, "stages": {}}, {"first": None, "last": None}, empty_coverage(str(exc))
    reasons: set[str] = set()
    cycles: set[str] = set()
    stage_counts: dict[str, Counter[str]] = defaultdict(Counter)
    observed: list[datetime] = []
    for line in lines:
        if not line.strip():
            reasons.add("malformed_input")
            continue
        try:
            row = json.loads(line)
            if not isinstance(row, dict) or set(row) != {"ts", "stage", "duration_ms", "status", "cycle", "extra"}:
                raise InputError("malformed_input")
            event_time = parse_timestamp(row["ts"])
            if not isinstance(row["stage"], str) or row["stage"] not in STAGES:
                raise InputError("unsupported_value")
            if not isinstance(row["status"], str) or row["status"] not in STATUSES:
                raise InputError("unsupported_value")
            if type(row["duration_ms"]) is not int or row["duration_ms"] < 0 or not isinstance(row["cycle"], str) or not row["cycle"] or not isinstance(row["extra"], dict):
                raise InputError("malformed_input")
        except InputError as exc:
            reasons.add(str(exc))
            continue
        except (json.JSONDecodeError, KeyError, TypeError):
            reasons.add("malformed_input")
            continue
        if not in_window(event_time, start, end):
            reasons.add("out_of_window")
            continue
        cycles.add(row["cycle"])
        stage_counts[row["stage"]][row["status"]] += 1
        observed.append(event_time)
    if not observed and not reasons:
        reasons.add("no_matching_evidence")
    stages = {stage: dict(sorted(counts.items())) for stage, counts in sorted(stage_counts.items())}
    bounds = {"first": timestamp_text(min(observed)) if observed else None, "last": timestamp_text(max(observed)) if observed else None}
    return {"cycles": len(cycles), "stage_events": sum(sum(counts.values()) for counts in stage_counts.values()), "stages": stages}, bounds, coverage(reasons)


def parse_producer(path: Path | None, start: datetime, end: datetime) -> tuple[dict[str, object], dict[str, object]]:
    """Count timestamped producer messages in the reporting window only."""
    if path is None:
        return {"failure_count": 0, "signals": {}}, empty_coverage("missing_input")
    try:
        lines = read_text(path).splitlines()
    except InputError as exc:
        return {"failure_count": 0, "signals": {}}, empty_coverage(str(exc))
    patterns = (
        ("probe_started", re.compile(rf"^(?:(?P<leading>{ISO_TIMESTAMP_PATTERN}) )?datapulse-health: probe started(?: at (?P<event>{ISO_TIMESTAMP_PATTERN}))?$")),
        ("probe_finished", re.compile(rf"^(?:(?P<leading>{ISO_TIMESTAMP_PATTERN}) )?datapulse-health: probe finished(?: at (?P<event>{ISO_TIMESTAMP_PATTERN}))?$")),
        ("publish_pushed", re.compile(rf"^(?:(?P<leading>{ISO_TIMESTAMP_PATTERN}) )?datapulse-health: publish pushed(?: at (?P<event>{ISO_TIMESTAMP_PATTERN}))?$")),
        ("shadow_equivalent", re.compile(rf"^(?:(?P<leading>{ISO_TIMESTAMP_PATTERN}) )?datapulse-health: shadow health equivalent; equivalent=true(?: at (?P<event>{ISO_TIMESTAMP_PATTERN}))?$")),
        ("shadow_comparison_failed", re.compile(rf"^(?:(?P<leading>{ISO_TIMESTAMP_PATTERN}) )?datapulse-health: shadow comparison failed(?: at (?P<event>{ISO_TIMESTAMP_PATTERN}))?$")),
        ("pipeline_receipt_written", re.compile(rf"^(?:(?P<leading>{ISO_TIMESTAMP_PATTERN}) )?datapulse-health: pipeline receipt written(?: at (?P<event>{ISO_TIMESTAMP_PATTERN}))?$")),
        ("failed", re.compile(rf"^(?:(?P<leading>{ISO_TIMESTAMP_PATTERN}) )?datapulse-health: failed \(exit [1-9][0-9]*\)$")),
    )
    counts: Counter[str] = Counter()
    reasons: set[str] = set()
    for line in lines:
        for name, pattern in patterns:
            match = pattern.fullmatch(line)
            if match is None:
                continue
            timestamp_value = match.groupdict().get("event") or match.groupdict().get("leading")
            if timestamp_value is None:
                reasons.add("no_matching_evidence")
                break
            try:
                event_time = parse_timestamp(timestamp_value)
            except InputError as exc:
                reasons.add(str(exc))
                break
            if not in_window(event_time, start, end):
                reasons.add("out_of_window")
                break
            counts[name] += 1
            break
    if not counts and not reasons:
        reasons.add("no_matching_evidence")
    return {"failure_count": counts["failed"], "signals": dict(sorted(counts.items()))}, coverage(reasons)


def validate_receipt(row: object) -> tuple[dict[str, object], datetime]:
    """Validate a local shadow envelope without returning any identifier values."""
    if not isinstance(row, dict) or set(row) != ENVELOPE_KEYS:
        raise InputError("malformed_input")
    if row["schema"] != "datapulse/v1/shadow-health-publication-envelope" or row["version"] != 1:
        raise InputError("unsupported_value")
    if not all(isinstance(row[key], str) and COMMIT_RE.fullmatch(row[key]) for key in ("source_commit", "health_commit")):
        raise InputError("invalid_identity")
    if not all(isinstance(row[key], str) and SHA256_RE.fullmatch(row[key]) for key in ("health_sha256", "semantic_sha256")):
        raise InputError("invalid_digest")
    if type(row["dataset_count"]) is not int or row["dataset_count"] < 1:
        raise InputError("malformed_input")
    return row, parse_timestamp(row["checked_at"])


def parse_shadow(path: Path | None, start: datetime, end: datetime) -> tuple[dict[str, int], dict[str, object], dict[str, object]]:
    """Aggregate valid local shadow envelopes and detect conflicting same-time receipts."""
    result = {"equivalent": 0, "mismatch": 0, "unknown": 0}
    if path is None:
        return result, {"first": None, "last": None}, empty_coverage("missing_input")
    try:
        lines = read_text(path).splitlines()
    except InputError as exc:
        return result, {"first": None, "last": None}, empty_coverage(str(exc))
    reasons: set[str] = set()
    candidates: list[tuple[dict[str, object], datetime]] = []
    for line in lines:
        try:
            row = json.loads(line)
            valid, checked_at = validate_receipt(row)
        except InputError as exc:
            result["unknown"] += 1
            reasons.add(str(exc))
            continue
        except (json.JSONDecodeError, TypeError):
            result["unknown"] += 1
            reasons.add("malformed_input")
            continue
        if not in_window(checked_at, start, end):
            reasons.add("out_of_window")
            continue
        candidates.append((valid, checked_at))
    groups: dict[str, list[dict[str, object]]] = defaultdict(list)
    for row, checked_at in candidates:
        groups[timestamp_text(checked_at)].append(row)
    for rows in groups.values():
        fingerprints = {(row["source_commit"], row["health_commit"], row["dataset_count"], row["health_sha256"], row["semantic_sha256"]) for row in rows}
        if len(fingerprints) == 1:
            result["equivalent"] += len(rows)
        else:
            result["mismatch"] += len(rows)
            if len({(row["source_commit"], row["health_commit"]) for row in rows}) > 1:
                reasons.add("invalid_identity")
            if len({(row["dataset_count"], row["health_sha256"], row["semantic_sha256"]) for row in rows}) > 1:
                reasons.add("invalid_digest")
    if not candidates and not reasons:
        reasons.add("no_matching_evidence")
    bounds = {"first": timestamp_text(min(time for _, time in candidates)) if candidates else None, "last": timestamp_text(max(time for _, time in candidates)) if candidates else None}
    return result, bounds, coverage(reasons)


def parse_workflows(path: Path | None, start: datetime, end: datetime) -> tuple[list[dict[str, object]], dict[str, object], dict[str, object], dict[str, int] | None]:
    """Count only typed sanitized workflow fields and discard every other field."""
    if path is None:
        return [], {"first": None, "last": None}, empty_coverage("missing_input"), None
    try:
        value = json.loads(read_text(path))
    except InputError as exc:
        return [], {"first": None, "last": None}, empty_coverage(str(exc)), None
    except json.JSONDecodeError:
        return [], {"first": None, "last": None}, empty_coverage("malformed_input"), None
    if not isinstance(value, list):
        return [], {"first": None, "last": None}, empty_coverage("malformed_input"), None
    counts: dict[str, Counter[str]] = defaultdict(Counter)
    observed: list[datetime] = []
    reasons: set[str] = set()
    health_only: Counter[str] = Counter()
    for row in value:
        if not isinstance(row, dict) or not {"workflowName", "status", "conclusion", "headSha"}.issubset(row) or set(row) - {"workflowName", "status", "conclusion", "headSha", "createdAt"}:
            reasons.add("unsupported_value")
            continue
        name, status, conclusion, head = row["workflowName"], row["status"], row["conclusion"], row["headSha"]
        if not isinstance(name, str) or not SAFE_WORKFLOW_RE.fullmatch(name) or SECRET_RE.search(name) or not isinstance(status, str) or status not in WORKFLOW_STATUSES or not isinstance(conclusion, str) or conclusion not in CONCLUSIONS or not isinstance(head, str) or not COMMIT_RE.fullmatch(head):
            reasons.add("unsupported_value")
            continue
        if "createdAt" in row:
            try:
                created = parse_timestamp(row["createdAt"])
            except InputError:
                reasons.add("malformed_input")
                continue
            if not in_window(created, start, end):
                reasons.add("out_of_window")
                continue
            observed.append(created)
        counts[name][conclusion] += 1
        health_only["health_only" if "health-only" in name.casefold() else "unknown"] += 1
    if not counts and not reasons:
        reasons.add("no_matching_evidence")
    workflows = [{"workflow": name, "conclusions": dict(sorted(conclusions.items()))} for name, conclusions in sorted(counts.items())]
    bounds = {"first": timestamp_text(min(observed)) if observed else None, "last": timestamp_text(max(observed)) if observed else None}
    return workflows, bounds, coverage(reasons), dict(sorted(health_only.items())) if health_only else None


def build_report(start: datetime, end: datetime, telemetry: Path | None, producer: Path | None, shadow: Path | None, workflows: Path | None) -> dict[str, object]:
    """Build the full report using only aggregate and allowlisted evidence fields."""
    cycle_counts, telemetry_bounds, telemetry_coverage = parse_telemetry(telemetry, start, end)
    producer_counts, producer_coverage = parse_producer(producer, start, end)
    shadow_counts, shadow_bounds, shadow_coverage = parse_shadow(shadow, start, end)
    workflow_counts, workflow_bounds, workflow_coverage, health_only_counts = parse_workflows(workflows, start, end)
    report: dict[str, object] = {
        "coverage": {"producer_log": producer_coverage, "shadow_receipts": shadow_coverage, "telemetry": telemetry_coverage, "workflow_runs": workflow_coverage},
        "cycle_counts": cycle_counts,
        "evidence_bounds": {"shadow_receipts": shadow_bounds, "telemetry": telemetry_bounds, "workflow_runs": workflow_bounds},
        "producer": producer_counts,
        "requested_window": {"end": timestamp_text(end), "start": timestamp_text(start)},
        "schema": SCHEMA,
        "shadow": shadow_counts,
        "version": VERSION,
        "workflows": workflow_counts,
    }
    if health_only_counts is not None:
        report["health_only_classification_counts"] = health_only_counts
    return report


def write_report(path: Path, report: dict[str, object]) -> None:
    """Atomically replace the report only after fully serializing its safe content."""
    payload = json.dumps(report, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8") + b"\n"
    descriptor = -1
    temporary = ""
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
        with os.fdopen(descriptor, "wb") as stream:
            descriptor = -1
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    except OSError as exc:
        raise ObservationError("write_failed") from exc
    finally:
        if descriptor != -1:
            os.close(descriptor)
        if temporary:
            try:
                os.unlink(temporary)
            except FileNotFoundError:
                pass


def parser() -> argparse.ArgumentParser:
    """Construct the explicit offline observation command line."""
    command = argparse.ArgumentParser(description=__doc__)
    command.add_argument("--start", required=True)
    command.add_argument("--end", required=True)
    command.add_argument("--telemetry", type=Path)
    command.add_argument("--producer-log", type=Path)
    command.add_argument("--shadow-receipts", type=Path)
    command.add_argument("--workflow-runs", type=Path)
    command.add_argument("--output", required=True, type=Path)
    return command


def main(argv: list[str] | None = None) -> int:
    """Run the offline aggregation without revealing supplied input values."""
    args = parser().parse_args(argv)
    try:
        start, end = parse_timestamp(args.start), parse_timestamp(args.end)
        if start >= end:
            raise InputError("malformed_input")
        write_report(args.output, build_report(start, end, args.telemetry, args.producer_log, args.shadow_receipts, args.workflow_runs))
    except ObservationError as exc:
        print(str(exc), file=os.sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
