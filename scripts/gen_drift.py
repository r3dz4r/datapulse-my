#!/usr/bin/env python3
"""Generate explainable per-dataset schema and record-count drift signals."""

from __future__ import annotations

import argparse
import json
import os
import tempfile
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from gen_anomaly import parse_time

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_HISTORY = ROOT / "health/history.jsonl"
DEFAULT_DAILY = ROOT / "health/history_daily.json"
DEFAULT_MANIFEST = ROOT / "datapulse.json"
DEFAULT_LATEST = ROOT / "health/latest.json"
DEFAULT_OUTPUT = ROOT / "health/drift.json"
SCHEMA = "datapulse/v1/dataset-drift"
WINDOW_DAYS = 30
MIN_RECORD_SAMPLE_DAYS = 2
MIN_RECORD_SPAN_DAYS = 1.0
RECORD_TREND_THRESHOLD_PCT = 5.0
RECORD_COUNT_TOLERANCE_RATIO = 0.5
VERDICTS = ("drift_detected", "record_count_drift", "stable", "insufficient_data")


def is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _daily_observations(path: Path, *, generated_at: datetime) -> list[dict[str, Any]]:
    """Return retained daily evidence; legacy aggregates supply no observations."""
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, OSError, UnicodeDecodeError, json.JSONDecodeError):
        return []
    if (
        not isinstance(payload, dict)
        or payload.get("schema") != "datapulse/v1/health-history-daily"
        or not isinstance(payload.get("aggregates"), list)
    ):
        return []

    rows: list[dict[str, Any]] = []
    for aggregate in payload["aggregates"]:
        if not isinstance(aggregate, dict):
            continue
        dataset_id = aggregate.get("dataset_id")
        evidence = aggregate.get("latest_observation")
        if not isinstance(dataset_id, str) or not isinstance(evidence, dict):
            continue
        observed = parse_time(evidence.get("observed_at"))
        if observed is None or observed > generated_at:
            continue
        rows.append(evidence | {"dataset_id": dataset_id})
    return rows


def read_history(
    path: Path, *, generated_at: datetime, daily: Path | None = None
) -> dict[str, list[dict[str, Any]]]:
    cutoff = generated_at - timedelta(days=WINDOW_DAYS)
    current: dict[str, dict[tuple[str, str], dict[str, Any]]] = {}
    baseline: dict[str, tuple[datetime, dict[str, Any]]] = {}
    raw_days: set[tuple[str, object]] = set()

    def add(row: dict[str, Any]) -> None:
        observed = parse_time(row.get("observed_at"))
        if observed is None or observed > generated_at:
            return
        prepared = row | {"_observed": observed, "_in_window": observed >= cutoff}
        dataset_id = row["dataset_id"]
        if observed < cutoff:
            previous = baseline.get(dataset_id)
            if previous is None or observed > previous[0]:
                baseline[dataset_id] = (observed, prepared)
            return
        key = (row.get("observed_at", ""), row.get("cycle", ""))
        current.setdefault(dataset_id, {})[key] = prepared

    try:
        source = path.open(encoding="utf-8")
    except FileNotFoundError:
        source = None
    if source is not None:
        with source:
            for line in source:
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if not isinstance(row, dict) or not isinstance(row.get("dataset_id"), str):
                    continue
                observed = parse_time(row.get("observed_at"))
                if observed is None:
                    continue
                raw_days.add((row["dataset_id"], observed.date()))
                add(row)
    for row in _daily_observations(
        daily or path.with_name("history_daily.json"), generated_at=generated_at
    ):
        observed = parse_time(row.get("observed_at"))
        if observed is not None and (row["dataset_id"], observed.date()) not in raw_days:
            add(row)
    result: dict[str, list[dict[str, Any]]] = {}
    for dataset_id in set(current) | set(baseline):
        rows = list(current.get(dataset_id, {}).values())
        if dataset_id in baseline:
            rows.append(baseline[dataset_id][1])
        result[dataset_id] = sorted(rows, key=lambda row: (row["_observed"], row.get("cycle", "")))
    return result


def transition_summary(rows: list[dict[str, Any]], field: str) -> tuple[int, str | None, int, int]:
    values: list[tuple[Any, datetime, bool]] = []
    for row in rows:
        value = row.get(field)
        valid = (isinstance(value, str) and value.startswith("shape-v1:")) if field == "shape_hash" else is_number(value)
        if valid:
            values.append((value, row["_observed"], row["_in_window"]))
    changes = 0
    last_change: datetime | None = None
    previous: Any = None
    have_previous = False
    for value, observed, in_window in values:
        if have_previous and value != previous and in_window:
            changes += 1
            last_change = observed
        previous, have_previous = value, True
    samples = sum(in_window for _, _, in_window in values)
    return changes, last_change.isoformat().replace("+00:00", "Z") if last_change else None, samples, len({value for value, _, _ in values})


def record_points(rows: list[dict[str, Any]]) -> list[tuple[datetime, float]]:
    daily: dict[object, tuple[datetime, float]] = {}
    for row in rows:
        observed, count = row["_observed"], row.get("record_count")
        if not row["_in_window"] or row.get("probe_outcome") != "success" or not is_number(count):
            continue
        previous = daily.get(observed.date())
        if previous is None or observed > previous[0]:
            daily[observed.date()] = (observed, float(count))
    return [daily[day] for day in sorted(daily)]


def classify_record_trend(points: list[tuple[datetime, float]]) -> tuple[str, float | None, float]:
    span = (points[-1][0] - points[0][0]).total_seconds() / 86400 if len(points) >= 2 else 0.0
    if len(points) < MIN_RECORD_SAMPLE_DAYS or span < MIN_RECORD_SPAN_DAYS:
        return "insufficient_data", None, span
    first, last = points[0][1], points[-1][1]
    if first == 0:
        return ("growing" if last > 0 else "stable"), None, span
    change_pct = 100 * (last - first) / abs(first)
    trend = "growing" if change_pct > RECORD_TREND_THRESHOLD_PCT else "shrinking" if change_pct < -RECORD_TREND_THRESHOLD_PCT else "stable"
    return trend, round(change_pct, 1), span


def normalized_tolerance(record_count: Any, expected: Any) -> bool | None:
    if not is_number(record_count) or not is_number(expected):
        return None
    return record_count >= expected * RECORD_COUNT_TOLERANCE_RATIO


def dataset_drift(entry: dict[str, Any], latest: dict[str, Any], rows: list[dict[str, Any]]) -> dict[str, Any]:
    shape_changes, last_shape_change, shape_samples, distinct_shapes = transition_summary(rows, "shape_hash")
    column_changes, last_column_change, column_samples, _ = transition_summary(rows, "column_count")
    points = record_points(rows)
    record_trend, record_change_pct, record_span = classify_record_trend(points)
    record_count = latest.get("record_count")
    column_count = latest.get("column_count")
    expected = entry.get("expected_record_count")
    if not is_number(expected):
        expected = latest.get("expected_record_count")
    tolerance = normalized_tolerance(record_count, expected)
    latest_shape_flag = latest.get("content_shape_changed") is True
    shape_changed = shape_changes > 0 or latest_shape_flag
    column_changed = True if column_changes > 0 else False if column_samples >= 2 else None
    if shape_changed or column_changed is True:
        verdict = "drift_detected"
        reason = (f"{shape_changes} structural fingerprint change(s) detected in the {WINDOW_DAYS}-day window" if shape_changes else f"{column_changes} column-count change(s) detected in the {WINDOW_DAYS}-day window" if column_changes else "latest health snapshot reports a structural comparison change")
    elif tolerance is False:
        verdict = "record_count_drift"
        reason = f"record count {record_count} is below {RECORD_COUNT_TOLERANCE_RATIO:.0%} of expected count {expected}"
    elif shape_samples >= 2 or column_samples >= 2 or tolerance is not None or record_trend != "insufficient_data":
        verdict, reason = "stable", "no structural transition or record-count tolerance failure was detected"
    else:
        verdict, reason = "insufficient_data", "requires two comparable structural or record-count observations, or an evaluable expected count"
    return {
        "dataset_id": entry["id"], "name": entry["name"], "verdict": verdict,
        "shape_changed_recently": shape_changed, "shape_change_count": shape_changes,
        "last_shape_change_at": last_shape_change, "shape_sample_count": shape_samples,
        "distinct_shape_count": distinct_shapes, "column_count_changed": column_changed,
        "column_change_count": column_changes, "last_column_change_at": last_column_change,
        "column_sample_count": column_samples, "record_trend": record_trend,
        "record_change_pct": record_change_pct, "record_sample_days": len(points),
        "record_history_span_days": round(record_span, 3),
        "record_count": record_count if is_number(record_count) else None,
        "column_count": column_count if is_number(column_count) else None,
        "expected_record_count": expected if is_number(expected) else None,
        "record_count_within_tolerance": tolerance, "content_shape_changed_latest": latest_shape_flag,
        "reason": reason,
    }


def generate(
    manifest: dict[str, Any], history: Path, latest: dict[str, Any], daily: Path | None = None
) -> dict[str, Any]:
    generated_at = parse_time(latest.get("checked_at"))
    if generated_at is None:
        raise ValueError("health snapshot has no valid checked_at timestamp")
    health_by_id = {row["dataset_id"]: row for row in latest.get("datasets", []) if isinstance(row, dict) and isinstance(row.get("dataset_id"), str)}
    history_by_id = read_history(history, generated_at=generated_at, daily=daily)
    datasets = [dataset_drift(entry, health_by_id.get(entry["id"], {}), history_by_id.get(entry["id"], [])) for entry in manifest.get("datasets", []) if isinstance(entry, dict) and isinstance(entry.get("id"), str) and isinstance(entry.get("name"), str)]
    counts = Counter(row["verdict"] for row in datasets)
    return {"schema": SCHEMA, "generated_at": generated_at.isoformat().replace("+00:00", "Z"), "window_days": WINDOW_DAYS, "methodology": {"shape_signal": "adjacent versioned shape_hash transitions", "column_signal": "adjacent numeric column_count transitions", "window_baseline": "latest valid observation before the window", "daily_compaction_evidence": "latest retained observation per compacted UTC day; raw history takes precedence on overlap", "record_daily_sample": "latest successful numeric observation per UTC day", "minimum_record_sample_days": MIN_RECORD_SAMPLE_DAYS, "minimum_record_span_days": MIN_RECORD_SPAN_DAYS, "record_trend_threshold_pct": RECORD_TREND_THRESHOLD_PCT, "record_count_tolerance_ratio": RECORD_COUNT_TOLERANCE_RATIO, "verdict_precedence": list(VERDICTS)}, "summary": {"datasets_total": len(datasets), "by_verdict": {name: counts[name] for name in VERDICTS}}, "datasets": datasets}


def write_atomic(path: Path, document: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as output:
            json.dump(document, output, ensure_ascii=False, indent=2)
            output.write("\n")
        os.replace(temporary_name, path)
    except BaseException:
        try: os.unlink(temporary_name)
        except FileNotFoundError: pass
        raise


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--history", type=Path, default=DEFAULT_HISTORY)
    parser.add_argument("--daily", type=Path, default=DEFAULT_DAILY)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--latest", type=Path, default=DEFAULT_LATEST)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    write_atomic(args.output, generate(json.loads(args.manifest.read_text()), args.history, json.loads(args.latest.read_text()), args.daily))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
