#!/usr/bin/env python3
"""Upsert per-dataset health observations and compact expired raw history."""

from __future__ import annotations

import argparse
import json
import os
import re
import tempfile
from collections import Counter
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SNAPSHOT = ROOT / "health/latest.json"
DEFAULT_MANIFEST = ROOT / "datapulse.json"
DEFAULT_HISTORY = ROOT / "health/history.jsonl"
DEFAULT_DAILY = ROOT / "health/history_daily.json"
DEFAULT_RETENTION_DAYS = 90
DAILY_SCHEMA = "datapulse/v1/health-history-daily"
STATUSES = (
    "fresh",
    "aging",
    "stale",
    "discontinued",
    "degraded",
    "browser-dependent",
    "unreachable",
    "unknown",
    "unknown-freshness",
    "reference",
)
PROBE_OUTCOMES = ("success", "error", "timeout")
HISTORY_FIELDS = (
    "dataset_id",
    "observed_at",
    "cycle",
    "status",
    "freshness_signal",
    "last_modified",
    "content_date",
    "record_count",
    "record_count_estimated",
    "http_status",
    "latency_ms",
    "probe_outcome",
    "message",
)
TIMEOUT_PATTERN = re.compile(r"timed?\s*out|timeout", re.IGNORECASE)
CYCLE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}$")


def is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def parse_datetime(value: str, *, field: str) -> datetime:
    if not isinstance(value, str):
        raise ValueError(f"{field} must be an ISO 8601 string")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"{field} is not a valid ISO 8601 timestamp: {value}") from exc
    if parsed.tzinfo is None:
        raise ValueError(f"{field} must include a UTC offset")
    return parsed


def read_snapshot(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read valid health snapshot {path}: {exc}") from exc
    if not isinstance(payload, dict) or not isinstance(payload.get("datasets"), list):
        raise ValueError("health snapshot must contain a datasets array")
    parse_datetime(payload.get("checked_at"), field="checked_at")
    return payload


def infer_probe_outcome(row: dict[str, Any]) -> str:
    explicit = row.get("probe_outcome")
    if explicit in PROBE_OUTCOMES:
        return explicit
    message = row.get("message")
    if isinstance(message, str) and TIMEOUT_PATTERN.search(message):
        return "timeout"
    http_status = row.get("http_status")
    if (
        isinstance(http_status, int)
        and not isinstance(http_status, bool)
        and 200 <= http_status < 300
    ):
        return "success"
    return "error"


def observation(
    row: dict[str, Any],
    *,
    observed_at: str,
    cycle: str,
    catalog_entry: dict[str, Any] | None = None,
) -> dict[str, Any]:
    dataset_id = row.get("dataset_id")
    if not isinstance(dataset_id, str) or not dataset_id:
        raise ValueError("every health row must have a non-empty dataset_id")
    status = row.get("status", "unknown")
    if status not in STATUSES:
        raise ValueError(f"{dataset_id}: unsupported status {status!r}")

    record_count = row.get("record_count")
    if not isinstance(record_count, (int, float)) or isinstance(record_count, bool):
        record_count = None
    http_status = row.get("http_status")
    if not isinstance(http_status, int) or isinstance(http_status, bool):
        http_status = None
    latency_ms = row.get("latency_ms")
    if not isinstance(latency_ms, (int, float)) or isinstance(latency_ms, bool):
        latency_ms = None
    message = row.get("message")
    if not isinstance(message, str) or not message:
        message = None

    values = {
        "dataset_id": dataset_id,
        "observed_at": observed_at,
        "cycle": cycle,
        "status": status,
        "freshness_signal": row.get("freshness_signal"),
        "last_modified": row.get("last_modified"),
        "content_date": row.get("content_freshness_date"),
        "record_count": record_count,
        "record_count_estimated": row.get("record_count_estimated") is True,
        "http_status": http_status,
        "latency_ms": latency_ms,
        "probe_outcome": infer_probe_outcome(row),
        "message": message,
    }
    result = {field: values[field] for field in HISTORY_FIELDS}
    entry = catalog_entry or {}
    optional = {
        "name": entry.get("name") or row.get("name"),
        "url": entry.get("url") or row.get("url"),
        "shape_hash": row.get("first_row_hash"),
        "column_count": (
            row.get("column_count") if is_number(row.get("column_count")) else None
        ),
    }
    if "anomaly_detected" in row:
        optional["anomaly_detected"] = row.get("anomaly_detected") is True
    result.update({key: value for key, value in optional.items() if value is not None})
    return result


def snapshot_observations(
    snapshot: dict[str, Any],
    cycle: str,
    catalog_by_id: dict[str, dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    if not CYCLE_PATTERN.fullmatch(cycle):
        raise ValueError("cycle must use YYYY-MM-DDTHH:MM")
    observed_at = snapshot["checked_at"]
    rows = [
        observation(
            row,
            observed_at=observed_at,
            cycle=cycle,
            catalog_entry=(catalog_by_id or {}).get(row.get("dataset_id")),
        )
        for row in snapshot["datasets"]
        if isinstance(row, dict)
    ]
    keys = [(row["dataset_id"], row["cycle"]) for row in rows]
    if len(rows) != len(snapshot["datasets"]):
        raise ValueError("every datasets entry must be an object")
    if len(set(keys)) != len(keys):
        raise ValueError("health snapshot contains duplicate dataset IDs")
    return rows


def read_history(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    line_number = 0
    try:
        with path.open(encoding="utf-8") as history_file:
            for line_number, line in enumerate(history_file, start=1):
                if not line.strip():
                    continue
                row = json.loads(line)
                if not isinstance(row, dict):
                    raise ValueError("line is not a JSON object")
                if not isinstance(row.get("dataset_id"), str) or not isinstance(
                    row.get("cycle"), str
                ):
                    raise ValueError("line has no dataset_id/cycle key")
                parse_datetime(row.get("observed_at"), field="observed_at")
                rows.append(row)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        raise ValueError(f"invalid history {path} at line {line_number}: {exc}") from exc
    return rows


def upsert_history(
    prior: list[dict[str, Any]], current: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    by_key = {(row["dataset_id"], row["cycle"]): row for row in prior}
    by_key.update({(row["dataset_id"], row["cycle"]): row for row in current})
    return sorted(
        by_key.values(),
        key=lambda row: (
            parse_datetime(row["observed_at"], field="observed_at").astimezone(UTC),
            row["cycle"],
            row["dataset_id"],
        ),
    )


def empty_distribution(names: tuple[str, ...]) -> dict[str, int]:
    return dict.fromkeys(names, 0)


def read_daily(
    path: Path,
) -> tuple[dict[tuple[str, str], dict[str, Any]], set[str]]:
    if not path.exists():
        return {}, set()
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read valid daily history {path}: {exc}") from exc
    if not isinstance(payload, dict) or payload.get("schema") != DAILY_SCHEMA:
        raise ValueError(f"daily history {path} has an unsupported schema")
    aggregates = payload.get("aggregates")
    if not isinstance(aggregates, list):
        raise ValueError(f"daily history {path} must contain an aggregates array")
    compacted_cycles = payload.get("compacted_cycles", [])
    if not isinstance(compacted_cycles, list) or not all(
        isinstance(cycle, str) for cycle in compacted_cycles
    ):
        raise ValueError(f"daily history {path} has an invalid compacted_cycles index")
    indexed: dict[tuple[str, str], dict[str, Any]] = {}
    for aggregate in aggregates:
        if not isinstance(aggregate, dict):
            raise ValueError("daily aggregate must be an object")
        dataset_id, day = aggregate.get("dataset_id"), aggregate.get("date")
        if not isinstance(dataset_id, str) or not isinstance(day, str):
            raise ValueError("daily aggregate must have dataset_id and date")
        indexed[(dataset_id, day)] = aggregate
    return indexed, set(compacted_cycles)


def _numeric_summary(values: list[int | float]) -> dict[str, Any]:
    if not values:
        return {"min": None, "mean": None, "max": None, "samples": 0, "sum": 0}
    total = sum(values)
    return {
        "min": min(values),
        "mean": round(total / len(values), 3),
        "max": max(values),
        "samples": len(values),
        "sum": total,
    }


def _mean_summary(values: list[int | float]) -> dict[str, Any]:
    summary = _numeric_summary(values)
    return {key: summary[key] for key in ("mean", "samples", "sum")}


def aggregate_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    first = min(rows, key=lambda row: row["observed_at"])
    last = max(rows, key=lambda row: row["observed_at"])
    statuses = Counter(row["status"] for row in rows)
    outcomes = Counter(row["probe_outcome"] for row in rows)
    counts = [
        row["record_count"]
        for row in rows
        if isinstance(row.get("record_count"), (int, float))
        and not isinstance(row.get("record_count"), bool)
    ]
    latencies = [
        row["latency_ms"]
        for row in rows
        if isinstance(row.get("latency_ms"), (int, float))
        and not isinstance(row.get("latency_ms"), bool)
    ]
    return {
        "dataset_id": first["dataset_id"],
        "date": parse_datetime(first["observed_at"], field="observed_at").date().isoformat(),
        "first_observed_at": first["observed_at"],
        "last_observed_at": last["observed_at"],
        "observations": len(rows),
        "status_distribution": {name: statuses[name] for name in STATUSES},
        "probe_outcome_distribution": {
            name: outcomes[name] for name in PROBE_OUTCOMES
        },
        "availability_percent": round(100 * outcomes["success"] / len(rows), 3),
        "record_count": _numeric_summary(counts),
        "latency_ms": _mean_summary(latencies),
    }


def merge_aggregates(old: dict[str, Any], new: dict[str, Any]) -> dict[str, Any]:
    observations = old["observations"] + new["observations"]
    outcomes = {
        name: old["probe_outcome_distribution"].get(name, 0)
        + new["probe_outcome_distribution"].get(name, 0)
        for name in PROBE_OUTCOMES
    }
    statuses = {
        name: old["status_distribution"].get(name, 0)
        + new["status_distribution"].get(name, 0)
        for name in STATUSES
    }

    old_count, new_count = old["record_count"], new["record_count"]
    count_samples = old_count["samples"] + new_count["samples"]
    count_sum = old_count["sum"] + new_count["sum"]
    count_min_values = [
        value for value in (old_count["min"], new_count["min"]) if value is not None
    ]
    count_max_values = [
        value for value in (old_count["max"], new_count["max"]) if value is not None
    ]
    old_latency, new_latency = old["latency_ms"], new["latency_ms"]
    latency_samples = old_latency["samples"] + new_latency["samples"]
    latency_sum = old_latency["sum"] + new_latency["sum"]

    return {
        "dataset_id": old["dataset_id"],
        "date": old["date"],
        "first_observed_at": min(old["first_observed_at"], new["first_observed_at"]),
        "last_observed_at": max(old["last_observed_at"], new["last_observed_at"]),
        "observations": observations,
        "status_distribution": statuses,
        "probe_outcome_distribution": outcomes,
        "availability_percent": round(100 * outcomes["success"] / observations, 3),
        "record_count": {
            "min": min(count_min_values) if count_min_values else None,
            "mean": round(count_sum / count_samples, 3) if count_samples else None,
            "max": max(count_max_values) if count_max_values else None,
            "samples": count_samples,
            "sum": count_sum,
        },
        "latency_ms": {
            "mean": round(latency_sum / latency_samples, 3) if latency_samples else None,
            "samples": latency_samples,
            "sum": latency_sum,
        },
    }


def compact_history(
    rows: list[dict[str, Any]],
    daily_path: Path,
    *,
    retention_days: int,
    now: datetime,
) -> tuple[list[dict[str, Any]], dict[str, Any], int]:
    cutoff = now - timedelta(days=retention_days)
    retained: list[dict[str, Any]] = []
    expired: list[dict[str, Any]] = []
    for row in rows:
        observed = parse_datetime(row["observed_at"], field="observed_at")
        (expired if observed < cutoff else retained).append(row)

    daily, compacted_cycles = read_daily(daily_path)
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for row in expired:
        if row["cycle"] in compacted_cycles:
            continue
        day = parse_datetime(row["observed_at"], field="observed_at").date().isoformat()
        grouped.setdefault((row["dataset_id"], day), []).append(row)
    for key, group in grouped.items():
        aggregate = aggregate_rows(group)
        daily[key] = merge_aggregates(daily[key], aggregate) if key in daily else aggregate
    compacted_cycles.update(row["cycle"] for row in expired)

    document = {
        "schema": DAILY_SCHEMA,
        "retention_days": retention_days,
        "compacted_cycles": sorted(compacted_cycles),
        "aggregates": [daily[key] for key in sorted(daily)],
    }
    return retained, document, len(expired)


def atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        mode = path.stat().st_mode & 0o777 if path.exists() else 0o644
        os.fchmod(descriptor, mode)
        with os.fdopen(descriptor, "w", encoding="utf-8") as temporary_file:
            temporary_file.write(content)
            temporary_file.flush()
            os.fsync(temporary_file.fileno())
        os.replace(temporary_name, path)
    except BaseException:
        try:
            os.unlink(temporary_name)
        except FileNotFoundError:
            pass
        raise


def write_history(path: Path, rows: list[dict[str, Any]]) -> None:
    content = "".join(
        json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n" for row in rows
    )
    atomic_write(path, content)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot", type=Path, default=DEFAULT_SNAPSHOT)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--history", type=Path, default=DEFAULT_HISTORY)
    parser.add_argument("--daily", type=Path, default=DEFAULT_DAILY)
    parser.add_argument("--cycle", help="probe-cycle start as YYYY-MM-DDTHH:MM")
    parser.add_argument("--retention-days", type=int, default=DEFAULT_RETENTION_DAYS)
    parser.add_argument("--compact", action="store_true")
    parser.add_argument("--now", help=argparse.SUPPRESS)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.retention_days < 1:
        raise SystemExit("--retention-days must be at least 1")
    try:
        snapshot = read_snapshot(args.snapshot)
        manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
        catalog_by_id = {
            row["id"]: row
            for row in manifest.get("datasets", [])
            if isinstance(row, dict) and isinstance(row.get("id"), str)
        }
        cycle = args.cycle or snapshot["checked_at"][:16]
        current = snapshot_observations(snapshot, cycle, catalog_by_id)
        rows = upsert_history(read_history(args.history), current)
        expired_count = 0
        if args.compact:
            now = (
                parse_datetime(args.now, field="now")
                if args.now
                else datetime.now(UTC)
            )
            rows, daily, expired_count = compact_history(
                rows,
                args.daily,
                retention_days=args.retention_days,
                now=now,
            )
            atomic_write(
                args.daily,
                json.dumps(daily, ensure_ascii=False, indent=2) + "\n",
            )
        write_history(args.history, rows)
    except ValueError as exc:
        raise SystemExit(f"health history generation failed: {exc}") from exc

    print(
        f"Health history upserted {len(current)} observations for {cycle}; "
        f"{len(rows)} raw retained, {expired_count} compacted"
    )


if __name__ == "__main__":
    main()
