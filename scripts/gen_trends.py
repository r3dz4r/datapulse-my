#!/usr/bin/env python3
"""Generate explainable per-dataset freshness trends from health history."""

from __future__ import annotations

import argparse
import json
import os
import tempfile
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from gen_anomaly import cadence_days, historical_delta, parse_time


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_HISTORY = ROOT / "health/history.jsonl"
DEFAULT_MANIFEST = ROOT / "datapulse.json"
DEFAULT_OUTPUT = ROOT / "health/trends.json"
SCHEMA = "datapulse/v1/dataset-trends"
WINDOW_DAYS = 14
MIN_SAMPLE_DAYS = 3
MIN_HISTORY_SPAN_DAYS = 2.0
SLOPE_THRESHOLD = 0.25
ON_TIME_CADENCE_MULTIPLIER = 1.5
INELIGIBLE_STATUSES = {"reference", "discontinued"}
TREND_NAMES = ("deteriorating", "recovering", "stable", "insufficient_data")
GRADE_NAMES = ("A", "B", "C", "D", "F", "insufficient_data")


def linear_slope(points: list[tuple[datetime, float]]) -> float | None:
    """Return OLS staleness-days per elapsed day for time-ordered points."""
    if len(points) < 2:
        return None
    origin = points[0][0]
    xs = [(observed - origin).total_seconds() / 86400 for observed, _ in points]
    ys = [value for _, value in points]
    mean_x = sum(xs) / len(xs)
    mean_y = sum(ys) / len(ys)
    denominator = sum((value - mean_x) ** 2 for value in xs)
    if denominator == 0:
        return None
    return sum(
        (x_value - mean_x) * (y_value - mean_y)
        for x_value, y_value in zip(xs, ys, strict=True)
    ) / denominator


def reliability_grade(percent: float | None) -> str:
    if percent is None:
        return "insufficient_data"
    if percent >= 95:
        return "A"
    if percent >= 85:
        return "B"
    if percent >= 70:
        return "C"
    if percent >= 50:
        return "D"
    return "F"


def latest_daily_rows(
    history: Path, *, generated_at: datetime
) -> dict[str, list[dict[str, Any]]]:
    """Keep the latest successful freshness-evaluable row on each UTC day."""
    cutoff = generated_at.date() - timedelta(days=WINDOW_DAYS - 1)
    latest: dict[str, dict[object, tuple[datetime, dict[str, Any]]]] = {}
    try:
        source = history.open(encoding="utf-8")
    except FileNotFoundError:
        return {}
    with source:
        for line in source:
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(row, dict) or not isinstance(row.get("dataset_id"), str):
                continue
            observed = parse_time(row.get("observed_at"))
            if observed is None or not (cutoff <= observed.date() <= generated_at.date()):
                continue
            delta = historical_delta(row)
            if delta is None:
                continue
            daily = latest.setdefault(row["dataset_id"], {})
            previous = daily.get(observed.date())
            if previous is None or observed > previous[0]:
                daily[observed.date()] = (observed, row | {"_staleness_days": delta})
    return {
        dataset_id: [daily[day][1] for day in sorted(daily)]
        for dataset_id, daily in latest.items()
    }


def history_end(history: Path) -> datetime:
    """Find the latest valid observation timestamp without trusting file order."""
    latest: datetime | None = None
    try:
        source = history.open(encoding="utf-8")
    except FileNotFoundError as exc:
        raise ValueError(f"history file does not exist: {history}") from exc
    with source:
        for line in source:
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(row, dict):
                continue
            observed = parse_time(row.get("observed_at"))
            if observed is not None and (latest is None or observed > latest):
                latest = observed
    if latest is None:
        raise ValueError("history contains no valid observed_at timestamps")
    return latest


def classify(
    points: list[tuple[datetime, float]],
    *,
    cadence: float | None,
    latest_status: Any,
) -> tuple[str, float | None, float, str]:
    span = (
        (points[-1][0] - points[0][0]).total_seconds() / 86400
        if len(points) >= 2
        else 0.0
    )
    if latest_status in INELIGIBLE_STATUSES:
        return "insufficient_data", None, span, f"status {latest_status} is not freshness-evaluable"
    if cadence is None:
        return "insufficient_data", None, span, "refresh cadence is not mapped"
    if len(points) < MIN_SAMPLE_DAYS or span < MIN_HISTORY_SPAN_DAYS:
        return (
            "insufficient_data",
            None,
            span,
            f"requires {MIN_SAMPLE_DAYS} daily samples spanning at least {MIN_HISTORY_SPAN_DAYS:g} days",
        )
    slope = linear_slope(points)
    if slope is None:
        return "insufficient_data", None, span, "observation times have no measurable span"
    if slope < -SLOPE_THRESHOLD:
        return "recovering", slope, span, "staleness is decreasing faster than the recovery threshold"
    latest_staleness = points[-1][1]
    if slope > SLOPE_THRESHOLD and latest_staleness > cadence * ON_TIME_CADENCE_MULTIPLIER:
        return (
            "deteriorating",
            slope,
            span,
            "staleness is increasing and latest freshness is beyond the on-time cadence boundary",
        )
    return "stable", slope, span, "slope is within the stable band or latest freshness remains on time"


def dataset_trend(entry: dict[str, Any], rows: list[dict[str, Any]]) -> dict[str, Any]:
    cadence = cadence_days(entry.get("refresh_frequency"))
    points = [
        (parse_time(row["observed_at"]), row["_staleness_days"])
        for row in rows
    ]
    typed_points = [(observed, value) for observed, value in points if observed is not None]
    latest_status = rows[-1].get("status") if rows else None
    trend, slope, span, reason = classify(
        typed_points, cadence=cadence, latest_status=latest_status
    )

    evaluable = (
        cadence is not None
        and latest_status not in INELIGIBLE_STATUSES
        and len(typed_points) >= MIN_SAMPLE_DAYS
        and span >= MIN_HISTORY_SPAN_DAYS
    )
    on_time_pct: float | None = None
    if evaluable:
        on_time = sum(value <= cadence * ON_TIME_CADENCE_MULTIPLIER for _, value in typed_points)
        on_time_pct = round(100 * on_time / len(typed_points), 1)

    anomaly_values = [
        row["anomaly_detected"]
        for row in rows
        if isinstance(row.get("anomaly_detected"), bool)
    ]
    anomaly_rate = (
        round(100 * sum(anomaly_values) / len(anomaly_values), 1)
        if anomaly_values
        else None
    )
    latest_staleness = typed_points[-1][1] if typed_points else None
    return {
        "dataset_id": entry["id"],
        "name": entry["name"],
        "latest_status": latest_status,
        "cadence_days": round(cadence, 6) if cadence is not None else None,
        "trend": trend,
        "reason": reason,
        "trend_sample_days": len(typed_points),
        "history_span_days": round(span, 3),
        "latest_staleness_days": round(latest_staleness, 3) if latest_staleness is not None else None,
        "slope_days_per_day": round(slope, 3) if slope is not None else None,
        "slope_days_per_week": round(slope * 7, 3) if slope is not None else None,
        "publish_on_time_pct": on_time_pct,
        "reliability_grade": reliability_grade(on_time_pct),
        "reliability_sample_days": len(typed_points) if evaluable else 0,
        "anomaly_rate_pct": anomaly_rate,
        "anomaly_sample_days": len(anomaly_values),
    }


def generate(manifest: dict[str, Any], history: Path, now: datetime | None = None) -> dict[str, Any]:
    generated_at = now or history_end(history)
    daily = latest_daily_rows(history, generated_at=generated_at)
    datasets = [
        dataset_trend(entry, daily.get(entry["id"], []))
        for entry in manifest.get("datasets", [])
        if isinstance(entry, dict) and isinstance(entry.get("id"), str)
    ]
    trend_counts = Counter(row["trend"] for row in datasets)
    grade_counts = Counter(row["reliability_grade"] for row in datasets)
    return {
        "schema": SCHEMA,
        "generated_at": generated_at.isoformat().replace("+00:00", "Z"),
        "window_days": WINDOW_DAYS,
        "methodology": {
            "metric": "freshness_delta_days",
            "daily_sample": "latest_successful_evaluable_observation_utc",
            "regression": "ordinary_least_squares",
            "minimum_sample_days": MIN_SAMPLE_DAYS,
            "minimum_history_span_days": MIN_HISTORY_SPAN_DAYS,
            "slope_threshold_days_per_day": SLOPE_THRESHOLD,
            "deteriorating_requires_latest_above_cadence_multiplier": ON_TIME_CADENCE_MULTIPLIER,
            "publish_on_time_cadence_multiplier": ON_TIME_CADENCE_MULTIPLIER,
        },
        "summary": {
            "datasets_total": len(datasets),
            "by_trend": {name: trend_counts[name] for name in TREND_NAMES},
            "by_reliability_grade": {name: grade_counts[name] for name in GRADE_NAMES},
        },
        "datasets": datasets,
    }


def write_atomic(path: Path, document: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as output:
            json.dump(document, output, ensure_ascii=False, indent=2)
            output.write("\n")
        os.replace(temporary_name, path)
    except BaseException:
        try:
            os.unlink(temporary_name)
        except FileNotFoundError:
            pass
        raise


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--history", type=Path, default=DEFAULT_HISTORY)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--now", help="Explicit UTC timestamp for deterministic tests.")
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    now = parse_time(args.now) if args.now else None
    if args.now and now is None:
        raise SystemExit("--now must be an ISO 8601 timestamp")
    write_atomic(args.output, generate(manifest, args.history, now))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
