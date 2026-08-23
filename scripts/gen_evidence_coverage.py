#!/usr/bin/env python3
"""Generate conservative coverage metrics for retained DataPulse evidence."""

from __future__ import annotations

import argparse
import json
import os
import tempfile
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

from gen_anomaly import parse_time
from gen_drift import (
    MIN_RECORD_SAMPLE_DAYS,
    MIN_RECORD_SPAN_DAYS,
    SCHEMA as DRIFT_SCHEMA,
    WINDOW_DAYS as DRIFT_WINDOW_DAYS,
)
from gen_record_evidence import SCHEMA_NAME as RECORD_EVIDENCE_SCHEMA, validate_record_evidence
from gen_trends import (
    MIN_HISTORY_SPAN_DAYS,
    MIN_SAMPLE_DAYS,
    SCHEMA as TRENDS_SCHEMA,
    WINDOW_DAYS as TREND_WINDOW_DAYS,
)


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = ROOT / "datapulse.json"
DEFAULT_TRENDS = ROOT / "health/trends.json"
DEFAULT_DRIFT = ROOT / "health/drift.json"
DEFAULT_HISTORY = ROOT / "health/history.jsonl"
DEFAULT_DAILY = ROOT / "health/history_daily.json"
DEFAULT_RECEIPTS = ROOT / "record-evidence"
DEFAULT_OUTPUT = ROOT / "health/evidence-coverage.json"
SCHEMA = "datapulse/v1/evidence-coverage"
DAILY_SCHEMA = "datapulse/v1/health-history-daily"


def _read_json(path: Path) -> dict[str, Any] | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


def _artifact_rows(path: Path, schema: str, field: str) -> dict[str, dict[str, Any]]:
    payload = _read_json(path)
    if payload is None or payload.get("schema") != schema or not isinstance(payload.get("datasets"), list):
        return {}
    rows: dict[str, dict[str, Any]] = {}
    for row in payload["datasets"]:
        if isinstance(row, dict) and isinstance(row.get("dataset_id"), str):
            rows[row["dataset_id"]] = row
    return rows


def _history_coverage(path: Path, manifest_ids: set[str]) -> dict[str, int]:
    observations = 0
    days: set[tuple[str, object]] = set()
    try:
        source = path.open(encoding="utf-8")
    except (FileNotFoundError, OSError, UnicodeDecodeError):
        return _observation_counts(observations, days)
    with source:
        for line in source:
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(row, dict) or row.get("dataset_id") not in manifest_ids:
                continue
            observed = parse_time(row.get("observed_at"))
            if observed is None:
                continue
            observations += 1
            days.add((row["dataset_id"], observed.date()))
    return _observation_counts(observations, days)


def _observation_counts(
    observations: int, days: set[tuple[str, object]]
) -> dict[str, int]:
    return {
        "datasets_with_observations": len({dataset_id for dataset_id, _ in days}),
        "observation_count": observations,
        "dataset_day_count": len(days),
    }


def _compacted_coverage(path: Path, manifest_ids: set[str]) -> tuple[dict[str, int], dict[str, Any]]:
    payload = _read_json(path)
    retention_days: int | float | None = None
    compacted_cycles = 0
    if payload is None or payload.get("schema") != DAILY_SCHEMA:
        return _observation_counts(0, set()), {
            "input_available": False,
            "retention_days": None,
            "compacted_cycles": 0,
        }
    if isinstance(payload.get("retention_days"), (int, float)) and not isinstance(payload["retention_days"], bool):
        retention_days = payload["retention_days"]
    if isinstance(payload.get("compacted_cycles"), list):
        compacted_cycles = len(payload["compacted_cycles"])
    aggregates = payload.get("aggregates")
    if not isinstance(aggregates, list):
        return _observation_counts(0, set()), {
            "input_available": True,
            "retention_days": retention_days,
            "compacted_cycles": compacted_cycles,
        }
    days: set[tuple[str, object]] = set()
    for aggregate in aggregates:
        if not isinstance(aggregate, dict) or aggregate.get("dataset_id") not in manifest_ids:
            continue
        evidence = aggregate.get("latest_observation")
        if not isinstance(evidence, dict):
            continue
        observed = parse_time(evidence.get("observed_at"))
        if observed is not None:
            days.add((aggregate["dataset_id"], observed.date()))
    return _observation_counts(len(days), days), {
        "input_available": True,
        "retention_days": retention_days,
        "compacted_cycles": compacted_cycles,
    }


def _valid_receipt(path: Path, dataset_id: str, *, full: bool) -> bool:
    payload = _read_json(path)
    if payload is None or payload.get("dataset_id") != dataset_id:
        return False
    try:
        return not validate_record_evidence(payload, full=full)
    except (KeyError, TypeError, ValueError):
        return False


def _record_coverage(receipts_root: Path, eligible_ids: set[str]) -> dict[str, int | float | None]:
    valid_latest = 0
    receipt_count = 0
    for dataset_id in sorted(eligible_ids):
        directory = receipts_root / dataset_id
        if _valid_receipt(directory / "latest.json", dataset_id, full=False):
            valid_latest += 1
        try:
            receipt_paths = sorted(path for path in directory.glob("*.json") if path.name != "latest.json")
        except OSError:
            receipt_paths = []
        receipt_count += sum(_valid_receipt(path, dataset_id, full=True) for path in receipt_paths)
    denominator = len(eligible_ids)
    return {
        "eligible_manifest_datasets": denominator,
        "datasets_with_valid_latest_receipts": valid_latest,
        "receipt_count": receipt_count,
        "coverage_pct": round(100 * valid_latest / denominator, 1) if denominator else None,
    }


def _history_latest(path: Path) -> datetime | None:
    latest: datetime | None = None
    try:
        source = path.open(encoding="utf-8")
    except (FileNotFoundError, OSError, UnicodeDecodeError):
        return None
    with source:
        for line in source:
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(row, dict):
                observed = parse_time(row.get("observed_at"))
                if observed is not None and (latest is None or observed > latest):
                    latest = observed
    return latest


def _generated_at(paths: tuple[Path, ...], history_path: Path, now: datetime | None) -> datetime:
    if now is not None:
        return now
    candidates: list[datetime] = []
    for path in paths:
        payload = _read_json(path)
        if payload is not None:
            parsed = parse_time(payload.get("generated_at"))
            if parsed is not None:
                candidates.append(parsed)
    history_latest = _history_latest(history_path)
    if history_latest is not None:
        candidates.append(history_latest)
    if not candidates:
        raise ValueError("--now is required when inputs have no valid generated_at timestamp")
    return max(candidates)


def _checks(document: dict[str, Any]) -> dict[str, Any]:
    total = document["dataset_denominator"]
    checks = [
        document["trend_evidence"]["evaluable_datasets"] + document["trend_evidence"]["insufficient_datasets"] == total,
        document["drift_evidence"]["evaluable_datasets"] + document["drift_evidence"]["insufficient_datasets"] == total,
        all(0 <= document["record_evidence"][key] <= document["record_evidence"]["eligible_manifest_datasets"] for key in ("datasets_with_valid_latest_receipts",)),
        all(0 <= section[key] <= total for section in (document["retained_history"]["raw"], document["retained_history"]["compacted"]) for key in ("datasets_with_observations",)),
    ]
    return {"valid": all(checks), "failed_checks": [index for index, check in enumerate(checks) if not check]}


def generate(
    manifest: dict[str, Any], *, trends_path: Path, drift_path: Path,
    history_path: Path, daily_path: Path, receipts_root: Path, now: datetime | None = None,
) -> dict[str, Any]:
    """Build coverage counts without treating absent optional evidence as positive."""
    entries = manifest.get("datasets")
    if not isinstance(entries, list):
        raise ValueError("manifest datasets must be a list")
    datasets = [entry for entry in entries if isinstance(entry, dict) and isinstance(entry.get("id"), str) and entry["id"]]
    ids = [entry["id"] for entry in datasets]
    if len(ids) != len(entries) or len(set(ids)) != len(ids):
        raise ValueError("manifest datasets must have unique non-empty ids")
    manifest_ids = set(ids)
    trend_rows = _artifact_rows(trends_path, TRENDS_SCHEMA, "trend")
    drift_rows = _artifact_rows(drift_path, DRIFT_SCHEMA, "verdict")
    trend_samples = Counter()
    trend_evaluable = 0
    drift_evaluable = 0
    for dataset_id in ids:
        trend = trend_rows.get(dataset_id, {})
        samples = trend.get("trend_sample_days")
        if isinstance(samples, int) and not isinstance(samples, bool) and samples >= 0:
            trend_samples[str(samples)] += 1
        else:
            trend_samples["unavailable"] += 1
        trend_evaluable += trend.get("trend") in {"deteriorating", "recovering", "stable"}
        drift_evaluable += drift_rows.get(dataset_id, {}).get("verdict") in {"drift_detected", "record_count_drift", "stable"}
    raw = _history_coverage(history_path, manifest_ids)
    compacted, retention = _compacted_coverage(daily_path, manifest_ids)
    record = _record_coverage(receipts_root, {entry["id"] for entry in datasets if entry.get("record_evidence_schema") == RECORD_EVIDENCE_SCHEMA})
    generated_at = _generated_at((trends_path, drift_path, daily_path), history_path, now)
    document: dict[str, Any] = {
        "schema": SCHEMA,
        "generated_at": generated_at.isoformat().replace("+00:00", "Z"),
        "dataset_denominator": len(datasets),
        "source_window": {
            "trend_window_days": TREND_WINDOW_DAYS,
            "drift_window_days": DRIFT_WINDOW_DAYS,
            "daily_retention": retention,
        },
        "trend_evidence": {
            "evaluable_datasets": trend_evaluable,
            "insufficient_datasets": len(datasets) - trend_evaluable,
            "sample_day_distribution": dict(sorted(trend_samples.items(), key=lambda item: item[0])),
            "requirements": {"minimum_sample_days": MIN_SAMPLE_DAYS, "minimum_history_span_days": MIN_HISTORY_SPAN_DAYS},
        },
        "drift_evidence": {
            "evaluable_datasets": drift_evaluable,
            "insufficient_datasets": len(datasets) - drift_evaluable,
            "requirements": {"minimum_record_sample_days": MIN_RECORD_SAMPLE_DAYS, "minimum_record_span_days": MIN_RECORD_SPAN_DAYS, "comparison_requirement": "existing drift verdict must not be insufficient_data"},
        },
        "retained_history": {"raw": raw, "compacted": compacted},
        "record_evidence": record,
    }
    document["consistency_checks"] = _checks(document)
    return document


def write_atomic(path: Path, document: dict[str, Any]) -> None:
    """Write canonical JSON atomically so partial reports never appear."""
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
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--trends", type=Path, default=DEFAULT_TRENDS)
    parser.add_argument("--drift", type=Path, default=DEFAULT_DRIFT)
    parser.add_argument("--history", type=Path, default=DEFAULT_HISTORY)
    parser.add_argument("--daily", type=Path, default=DEFAULT_DAILY)
    parser.add_argument("--record-evidence", type=Path, default=DEFAULT_RECEIPTS)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--now", help="Explicit UTC timestamp for deterministic fixtures.")
    args = parser.parse_args()
    now = parse_time(args.now) if args.now else None
    if args.now and now is None:
        raise SystemExit("--now must be an ISO 8601 timestamp")
    manifest = _read_json(args.manifest)
    if manifest is None:
        raise SystemExit(f"manifest is not valid JSON: {args.manifest}")
    write_atomic(args.output, generate(manifest, trends_path=args.trends, drift_path=args.drift, history_path=args.history, daily_path=args.daily, receipts_root=args.record_evidence, now=now))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
