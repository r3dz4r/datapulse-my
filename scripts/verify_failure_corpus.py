#!/usr/bin/env python3
"""Validate structured failure records against immutable local probe history."""

from __future__ import annotations

import argparse
from datetime import datetime
import json
import logging
from pathlib import Path
from typing import Any


LOGGER = logging.getLogger(__name__)
ROOT = Path(__file__).resolve().parents[1]
REQUIRED_FIELDS = {"schema", "failure_id", "family", "failure_type", "severity", "first_observed_at", "most_recent_observed_at", "affected_datasets", "evidence", "impact_on_claim_or_decision", "resolution_or_quarantine", "rule_or_policy_change", "regression_test", "served_verification", "recorded_at", "recorded_by"}
EXPECTED = {
    "bnm-open-api-http-200-stale-content": ("bnm_open_api", "http_200_stale_content"),
    "bnm-open-api-schema-shape-hash-churn": ("bnm_open_api", "schema_shape_hash_churn"),
    "bnm-open-api-row-date-missing-200": ("bnm_open_api", "row_date_missing_200"),
    "gtfs-api-realtime-zero-vehicles-off-peak": ("gtfs_api", "realtime_zero_vehicles_off_peak"),
    "gtfs-api-discontinued-line-404": ("gtfs_api", "discontinued_line_404"),
    "gtfs-api-schema-shape-hash-churn": ("gtfs_api", "schema_shape_hash_churn"),
    "cross-family-http-200-stale-content-broad": ("cross-family", "http_200_stale_content"),
}
FAMILIES = {"bnm_open_api", "gtfs_api", "cross-family"}
FAILURE_TYPES = {"http_200_stale_content", "schema_shape_hash_churn", "row_date_missing_200", "realtime_zero_vehicles_off_peak", "discontinued_line_404"}


def _parse_iso8601(value: Any, field: str) -> None:
    if not isinstance(value, str):
        raise ValueError(f"{field} must be an ISO8601 string")
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"{field} is not ISO8601: {value!r}") from exc


def load_records(corpus_dir: Path) -> list[dict[str, Any]]:
    """Load every JSON record, rejecting malformed or non-object JSON."""
    records: list[dict[str, Any]] = []
    for path in sorted(corpus_dir.rglob("*.json")):
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ValueError(f"{path}: invalid JSON") from exc
        if not isinstance(record, dict):
            raise ValueError(f"{path}: record must be a JSON object")
        record["_path"] = str(path)
        records.append(record)
    return records


def load_history(history_path: Path) -> list[dict[str, Any]]:
    """Load local JSONL history without contacting an upstream service."""
    rows: list[dict[str, Any]] = []
    for line_number, line in enumerate(history_path.read_text(encoding="utf-8").splitlines(), 1):
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"{history_path}:{line_number}: invalid JSONL") from exc
        if not isinstance(row, dict):
            raise ValueError(f"{history_path}:{line_number}: row must be an object")
        rows.append(row)
    return rows


def _signal_matches(failure_type: str, dataset_id: str, history: list[dict[str, Any]]) -> bool:
    rows = [row for row in history if row.get("dataset_id") == dataset_id]
    if failure_type == "http_200_stale_content":
        return any(row.get("status") == "stale" and row.get("http_status") == 200 for row in rows)
    if failure_type == "schema_shape_hash_churn":
        return len({row.get("shape_hash") for row in rows if isinstance(row.get("shape_hash"), str)}) > 1
    if failure_type == "discontinued_line_404":
        return any(row.get("status") == "discontinued" and row.get("http_status") == 404 for row in rows)
    if failure_type == "realtime_zero_vehicles_off_peak":
        return any(row.get("probe_outcome") == "success" and row.get("record_count") == 0 for row in rows)
    return True


def verify_records(records: list[dict[str, Any]], history: list[dict[str, Any]]) -> list[str]:
    """Return deterministic contract and live-history mismatches."""
    errors: list[str] = []
    seen: set[str] = set()
    for record in records:
        path = record.get("_path", "<record>")
        missing = REQUIRED_FIELDS - record.keys()
        if missing:
            errors.append(f"{path}: missing required fields: {sorted(missing)}")
            continue
        failure_id = record["failure_id"]
        if not isinstance(failure_id, str):
            errors.append(f"{path}: failure_id must be a string")
            continue
        seen.add(failure_id)
        if record["schema"] != "datapulse/v1/failure-record": errors.append(f"{path}: invalid schema")
        if record["family"] not in FAMILIES: errors.append(f"{path}: invalid family")
        if record["failure_type"] not in FAILURE_TYPES: errors.append(f"{path}: invalid failure_type")
        if record["severity"] not in {"low", "medium", "high"}: errors.append(f"{path}: invalid severity")
        expected = EXPECTED.get(failure_id)
        if expected is None:
            errors.append(f"{path}: unrecognized failure_id {failure_id!r}")
        elif (record["family"], record["failure_type"]) != expected:
            errors.append(f"{path}: unexpected failure_type or family for {failure_id}")
        for field in ("recorded_at", "first_observed_at", "most_recent_observed_at"):
            try: _parse_iso8601(record[field], field)
            except ValueError as exc: errors.append(f"{path}: {exc}")
        if not isinstance(record["affected_datasets"], list): errors.append(f"{path}: affected_datasets must be a list")
        evidence = record["evidence"]
        if not isinstance(evidence, dict) or not isinstance(evidence.get("example_history_lines"), list): errors.append(f"{path}: evidence.example_history_lines must be a list")
        served = record["served_verification"]
        if not isinstance(served, dict): errors.append(f"{path}: served_verification must be an object")
        else:
            try: _parse_iso8601(served.get("last_verified"), "served_verification.last_verified")
            except ValueError as exc: errors.append(f"{path}: {exc}")
        if isinstance(record["affected_datasets"], list):
            for dataset_id in record["affected_datasets"]:
                if not isinstance(dataset_id, str) or not _signal_matches(record["failure_type"], dataset_id, history):
                    errors.append(f"{path}: {dataset_id!r} has no matching live-history signal for {record['failure_type']}")
        if record["family"] == "cross-family":
            signals = evidence.get("live_signals", {}) if isinstance(evidence, dict) else {}
            latest_at = max((row.get("observed_at", "") for row in history), default="")
            latest = [row for row in history if row.get("observed_at") == latest_at]
            actual = 100 * sum(row.get("status") == "stale" and row.get("http_status") == 200 for row in latest) / len(latest) if latest else 0
            baseline = signals.get("stale_http_200_pct") if isinstance(signals, dict) else None
            if not isinstance(baseline, (int, float)) or abs(actual - baseline) > 5:
                errors.append(f"{path}: stale HTTP-200 percentage {actual:.1f} contradicts baseline {baseline!r}")
    if seen != set(EXPECTED): errors.append(f"required failure records mismatch: missing={sorted(set(EXPECTED) - seen)}, extra={sorted(seen - set(EXPECTED))}")
    return errors


def parse_args() -> argparse.Namespace:
    """Parse read-only local input paths."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus-dir", type=Path, default=ROOT / "notes" / "failure-corpus")
    parser.add_argument("--history-path", type=Path, default=ROOT / "health" / "history.jsonl")
    return parser.parse_args()


def main() -> int:
    """Run the verifier and return a conventional process status."""
    args = parse_args()
    if not args.history_path.exists() or args.history_path.stat().st_size == 0:
        LOGGER.error(
            "INFO: health/history.jsonl unavailable; history-anchored checks skipped. "
            "Local-only checks (format, schema) remain enforced if implemented."
        )
        return 1
    try: errors = verify_records(load_records(args.corpus_dir), load_history(args.history_path))
    except (OSError, ValueError, TypeError) as exc:
        LOGGER.error("failure-corpus verification failed: %s", exc); return 1
    if errors:
        for error in errors: LOGGER.error("%s", error)
        return 1
    LOGGER.info("failure corpus agrees with local probe history")
    return 0


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    raise SystemExit(main())
