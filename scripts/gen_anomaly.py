#!/usr/bin/env python3
"""Annotate a health snapshot with deterministic freshness anomaly evidence."""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

WINDOW_DAYS = 14
METRIC = "freshness_delta_days"
INELIGIBLE_STATUSES = {"reference", "discontinued"}


def parse_time(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        # Content freshness is often published as a date-only UTC calendar date.
        if len(value) == 10:
            return parsed.replace(tzinfo=UTC)
        return None
    return parsed.astimezone(UTC)


def cadence_days(frequency: Any) -> float | None:
    value = frequency.lower() if isinstance(frequency, str) else ""
    if value.startswith("daily"):
        return 1
    if value == "weekly":
        return 7
    if value == "monthly":
        return 30
    if value == "quarterly":
        return 90
    if value == "annual":
        return 365
    if value.startswith("survey-year") or value.startswith("biennial"):
        return 730
    if value == "hourly":
        return 1 / 24
    if value == "30 seconds":
        return 30 / 86400
    return None


def number(value: Any) -> float | None:
    if isinstance(value, (int, float)) and not isinstance(value, bool) and value >= 0:
        return float(value)
    return None


def historical_delta(row: dict[str, Any]) -> float | None:
    observed = parse_time(row.get("observed_at"))
    if observed is None or row.get("probe_outcome") != "success":
        return None
    ages: list[float] = []
    for field in ("last_modified", "content_date"):
        timestamp = parse_time(row.get(field))
        if timestamp is not None and timestamp <= observed:
            ages.append((observed - timestamp).total_seconds() / 86400)
    return max(ages) if ages else None


def prior_daily_values(history: Path, dataset_ids: set[str], now: datetime) -> dict[str, list[float]]:
    latest: dict[str, dict[object, tuple[datetime, float]]] = {dataset_id: {} for dataset_id in dataset_ids}
    try:
        source = history.open(encoding="utf-8")
    except FileNotFoundError:
        return {dataset_id: [] for dataset_id in dataset_ids}
    with source:
        for line in source:
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(row, dict) or row.get("dataset_id") not in latest:
                continue
            observed = parse_time(row.get("observed_at"))
            if observed is None or not (now.date() - timedelta(days=WINDOW_DAYS) <= observed.date() < now.date()):
                continue
            delta = historical_delta(row)
            daily = latest[row["dataset_id"]]
            previous = daily.get(observed.date())
            if delta is not None and (previous is None or observed > previous[0]):
                daily[observed.date()] = (observed, delta)
    return {dataset_id: [daily[day][1] for day in sorted(daily)] for dataset_id, daily in latest.items()}


def evidence(*, latest: float | None, values: list[float], cadence: float | None, eligible: bool) -> tuple[bool, dict[str, Any]]:
    base = {"metric": METRIC, "window_days": WINDOW_DAYS, "sample_days": len(values), "mean_days": None, "stdev_days": None, "threshold_days": None, "latest_days": latest}
    if not eligible or latest is None:
        return False, base | {"mode": "not_evaluated"}
    if len(values) == WINDOW_DAYS:
        mean = statistics.fmean(values)
        stdev = statistics.pstdev(values)
        threshold = mean + 2 * stdev
        return latest > threshold, base | {"mode": "rolling_14d", "mean_days": round(mean, 3), "stdev_days": round(stdev, 3), "threshold_days": round(threshold, 3)}
    if cadence is None:
        return False, base | {"mode": "not_evaluated"}
    threshold = 2 * cadence
    return latest > threshold, base | {"mode": "cadence_fallback", "threshold_days": threshold}


def annotate(snapshot: dict[str, Any], manifest: dict[str, Any], history: Path, now: datetime | None = None) -> dict[str, Any]:
    checked = now or parse_time(snapshot.get("checked_at"))
    if checked is None:
        raise ValueError("snapshot checked_at must be a UTC timestamp")
    manifest_by_id = {row.get("id"): row for row in manifest.get("datasets", []) if isinstance(row, dict)}
    dataset_ids = {row.get("dataset_id") for row in snapshot.get("datasets", []) if isinstance(row, dict) and isinstance(row.get("dataset_id"), str)}
    daily_values = prior_daily_values(history, dataset_ids, checked)
    for row in snapshot.get("datasets", []):
        if not isinstance(row, dict):
            continue
        entry = manifest_by_id.get(row.get("dataset_id"), {})
        latest = number(row.get("staleness_days"))
        values = daily_values.get(row.get("dataset_id"), [])
        detected, details = evidence(latest=latest, values=values, cadence=cadence_days(entry.get("refresh_frequency")), eligible=row.get("status") not in INELIGIBLE_STATUSES)
        row["anomaly_detected"] = detected
        row["anomaly_detection"] = details
    return snapshot


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--history", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--now", help="Explicit UTC timestamp for deterministic tests.")
    args = parser.parse_args()
    snapshot = json.load(sys.stdin)
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    now = parse_time(args.now) if args.now else None
    if args.now and now is None:
        raise SystemExit("--now must be an ISO 8601 timestamp")
    json.dump(annotate(snapshot, manifest, args.history, now), sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
