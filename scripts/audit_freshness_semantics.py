#!/usr/bin/env python3
"""Read-only audit of manifest freshness semantics against health evidence."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SCHEMA = "datapulse/freshness-semantics-audit/v1"
NO_CLOCK_DATA_TYPES = {"reference", "policy-reference"}
SOURCE_AWARE_FAMILIES = {
    "data_gov_my_openapi",
    "data_gov_my_storage",
    "data_gov_my",
    "dosm_via_data_gov_my",
    "opendosm_storage",
    "opendosm_data_gov_my_storage",
    "data_gov_my_archive",
    "data_gov_my_storage_dosm_gov_my",
}
PUBLISHER_RETIRED_FAMILIES = {"data_gov_my_openapi", "data_gov_my_storage"}
RETIRED_AGE_DAYS = 365


class AuditInputError(ValueError):
    """Raised when an audit input cannot be safely joined by dataset ID."""


def _load_object(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise AuditInputError(f"cannot read valid {label} JSON: {path}") from error
    if not isinstance(value, dict):
        raise AuditInputError(f"{label} must be a JSON object")
    return value


def _rows_by_id(document: dict[str, Any], key: str, label: str) -> dict[str, dict[str, Any]]:
    rows = document.get("datasets")
    if not isinstance(rows, list):
        raise AuditInputError(f"{label}.datasets must be an array")
    indexed: dict[str, dict[str, Any]] = {}
    for row in rows:
        if not isinstance(row, dict):
            raise AuditInputError(f"{label}.datasets must contain only objects")
        dataset_id = row.get(key)
        if not isinstance(dataset_id, str) or not dataset_id:
            raise AuditInputError(f"{label} row has invalid {key}")
        if dataset_id in indexed:
            raise AuditInputError(f"duplicate dataset ID {dataset_id!r} in {label}")
        indexed[dataset_id] = row
    return indexed


def _checked_datetime(health: dict[str, Any]) -> datetime | None:
    checked_at = health.get("checked_at")
    if not isinstance(checked_at, str):
        return None
    try:
        parsed = datetime.fromisoformat(checked_at.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed.replace(tzinfo=None)


def _content_date(row: dict[str, Any]) -> datetime | None:
    value = row.get("content_freshness_date")
    if not isinstance(value, str) or not value:
        return None
    try:
        return datetime.fromisoformat(value[:10])
    except ValueError:
        return None


def _is_no_clock(row: dict[str, Any]) -> bool:
    data_type = row.get("data_type")
    if isinstance(data_type, str) and data_type in NO_CLOCK_DATA_TYPES:
        return True
    policy = row.get("freshness_policy")
    if isinstance(policy, dict) and policy.get("reference_table") is True:
        return True
    return False


def _has_freshness_signal(row: dict[str, Any]) -> bool:
    return any(
        isinstance(row.get(key), str) and bool(row[key].strip())
        for key in ("content_freshness_date", "last_modified")
    )


def _source_aware_reason(
    policy: dict[str, Any],
    health_row: dict[str, Any],
    checked_at: datetime | None,
) -> str | None:
    family = policy.get("family")
    if not isinstance(family, str) or family not in SOURCE_AWARE_FAMILIES:
        return None
    http_status = health_row.get("http_status")
    if (
        policy.get("discontinued_on_404") is True
        and isinstance(http_status, int)
        and http_status in {404, 410}
    ):
        return "discontinued-on-404"
    if family in PUBLISHER_RETIRED_FAMILIES:
        content_date = _content_date(health_row)
        if checked_at is not None and content_date is not None:
            if (checked_at - content_date).days > RETIRED_AGE_DAYS:
                return "publisher-likely-retired"
    if policy.get("interpretation") == "observation_period":
        return "observation-period-staleness"
    return None


def build_report(manifest: dict[str, Any], health: dict[str, Any]) -> dict[str, Any]:
    """Return a deterministic semantic audit without mutating its inputs."""
    manifest_by_id = _rows_by_id(manifest, "id", "manifest")
    health_by_id = _rows_by_id(health, "dataset_id", "health")
    manifest_ids = set(manifest_by_id)
    health_ids = set(health_by_id)
    if manifest_ids != health_ids:
        missing_health = sorted(manifest_ids - health_ids)
        missing_manifest = sorted(health_ids - manifest_ids)
        raise AuditInputError(
            "dataset ID mismatch: "
            f"missing health={missing_health!r}; missing manifest={missing_manifest!r}"
        )

    typed_ids = sorted(dataset_id for dataset_id, row in manifest_by_id.items() if _is_no_clock(row))
    untyped_stale_ids: list[str] = []
    source_aware_entries: list[dict[str, str]] = []
    no_signal_ids: list[str] = []
    checked_at = _checked_datetime(health)

    for dataset_id in sorted(manifest_ids):
        manifest_row = manifest_by_id[dataset_id]
        health_row = health_by_id[dataset_id]
        if not _has_freshness_signal(health_row):
            no_signal_ids.append(dataset_id)
        if dataset_id in set(typed_ids):
            continue
        if manifest_row.get("refresh_frequency") == "as-required":
            continue
        if health_row.get("status") != "stale":
            continue
        untyped_stale_ids.append(dataset_id)
        policy = manifest_row.get("freshness_policy")
        policy = policy if isinstance(policy, dict) else {}
        reason = _source_aware_reason(policy, health_row, checked_at)
        if reason is not None:
            source_aware_entries.append({
                "dataset_id": dataset_id,
                "family": str(policy.get("family")),
                "reason": reason,
            })

    source_aware_ids = {entry["dataset_id"] for entry in source_aware_entries}
    remaining_ids = [dataset_id for dataset_id in untyped_stale_ids if dataset_id not in source_aware_ids]

    return {
        "schema": SCHEMA,
        "datasets_total": len(manifest_by_id),
        "typed_datasets": len(typed_ids),
        "untyped_datasets": len(manifest_by_id) - len(typed_ids),
        "health_status_counts": dict(sorted(Counter(
            str(row.get("status")) for row in health_by_id.values()
        ).items())),
        "untyped_stale_candidates": {
            "count": len(untyped_stale_ids),
            "dataset_ids": untyped_stale_ids,
        },
        "source_policy_aware_candidates": {
            "count": len(source_aware_entries),
            "entries": source_aware_entries,
        },
        "remaining_unambiguous_candidates": {
            "count": len(remaining_ids),
            "dataset_ids": remaining_ids,
        },
        "no_freshness_signal": {
            "count": len(no_signal_ids),
            "dataset_ids": no_signal_ids,
        },
        "recommendation": "Audit candidates by source semantics; do not rewrite automatically.",
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=ROOT / "datapulse.json")
    parser.add_argument("--health", type=Path, default=ROOT / "health/latest.json")
    parser.add_argument("--json", action="store_true", dest="as_json")
    return parser


def main() -> int:
    """Run the audit and return a shell-friendly exit status."""
    args = _parser().parse_args()
    try:
        report = build_report(
            _load_object(args.manifest, "manifest"),
            _load_object(args.health, "health"),
        )
    except AuditInputError as error:
        print(f"audit error: {error}", file=sys.stderr)
        return 1

    if args.as_json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(
            f"datasets: {report['datasets_total']} "
            f"({report['typed_datasets']} typed, {report['untyped_datasets']} untyped)"
        )
        print(f"untyped stale candidates: {report['untyped_stale_candidates']['count']}")
        print(f"source-policy-aware candidates: {report['source_policy_aware_candidates']['count']}")
        print(f"remaining unambiguous candidates: {report['remaining_unambiguous_candidates']['count']}")
        print(f"no freshness signal: {report['no_freshness_signal']['count']}")
        print(f"recommendation: {report['recommendation']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
