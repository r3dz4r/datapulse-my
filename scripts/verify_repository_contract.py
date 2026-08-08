#!/usr/bin/env python3
"""Verify the checked-in DataPulse repository contract without network access."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker


def _load_json(root: Path, relative_path: str, errors: list[str]) -> Any | None:
    path = root / relative_path
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        errors.append(f"{relative_path}: required file is missing")
    except json.JSONDecodeError as exc:
        errors.append(f"{relative_path}:{exc.lineno}:{exc.colno}: invalid JSON: {exc.msg}")
    return None


def _duplicates(values: list[str]) -> list[str]:
    counts = Counter(values)
    return sorted(value for value, count in counts.items() if count > 1)


def _format_ids(values: set[str] | list[str]) -> str:
    return ", ".join(sorted(values))


def verify_repository_contract(root: Path) -> list[str]:
    """Return actionable invariant failures for ``root``; never mutate it."""
    root = root.resolve()
    errors: list[str] = []
    schema = _load_json(root, "datapulse.schema.json", errors)
    manifest = _load_json(root, "datapulse.json", errors)
    health = _load_json(root, "health/latest.json", errors)
    if schema is None or manifest is None or health is None:
        return errors

    try:
        validator = Draft202012Validator(schema, format_checker=FormatChecker())
        for failure in sorted(validator.iter_errors(manifest), key=lambda item: list(item.path)):
            location = ".".join(str(part) for part in failure.absolute_path) or "<root>"
            errors.append(f"datapulse.json:{location}: schema violation: {failure.message}")
    except Exception as exc:  # invalid schemas should be reported as contract failures
        errors.append(f"datapulse.schema.json: invalid schema: {exc}")

    manifest_rows = manifest.get("datasets", []) if isinstance(manifest, dict) else []
    health_rows = health.get("datasets", []) if isinstance(health, dict) else []
    manifest_ids = [row.get("id") for row in manifest_rows if isinstance(row, dict)]
    health_ids = [row.get("dataset_id") for row in health_rows if isinstance(row, dict)]
    manifest_ids = [value for value in manifest_ids if isinstance(value, str)]
    health_ids = [value for value in health_ids if isinstance(value, str)]

    duplicate_manifest_ids = _duplicates(manifest_ids)
    if duplicate_manifest_ids:
        errors.append(
            "datapulse.json: duplicate dataset IDs: " + _format_ids(duplicate_manifest_ids)
        )
    duplicate_health_ids = _duplicates(health_ids)
    if duplicate_health_ids:
        errors.append(
            "health/latest.json: duplicate dataset IDs: " + _format_ids(duplicate_health_ids)
        )

    manifest_id_set = set(manifest_ids)
    health_id_set = set(health_ids)
    missing_health_ids = manifest_id_set - health_id_set
    extra_health_ids = health_id_set - manifest_id_set
    if missing_health_ids:
        errors.append(
            "health/latest.json: missing IDs present in datapulse.json: "
            + _format_ids(missing_health_ids)
        )
    if extra_health_ids:
        errors.append(
            "health/latest.json: extra IDs absent from datapulse.json: "
            + _format_ids(extra_health_ids)
        )

    summary = health.get("_trust_summary", {}) if isinstance(health, dict) else {}
    dataset_total = summary.get("datasets_total") if isinstance(summary, dict) else None
    if dataset_total != len(health_rows):
        errors.append(
            "health/latest.json:_trust_summary.datasets_total: "
            f"expected {len(health_rows)} from datasets rows, found {dataset_total!r}"
        )
    by_status = summary.get("by_status", {}) if isinstance(summary, dict) else {}
    if not isinstance(by_status, dict) or not all(
        isinstance(value, int) and not isinstance(value, bool) and value >= 0
        for value in by_status.values()
    ):
        errors.append("health/latest.json:_trust_summary.by_status: expected non-negative integer counts")
    else:
        status_total = sum(by_status.values())
        if status_total != len(health_rows):
            errors.append(
                "health/latest.json:_trust_summary.by_status: "
                f"counts sum to {status_total}; expected {len(health_rows)} dataset rows"
            )
        actual_statuses = Counter(
            row.get("status") for row in health_rows if isinstance(row, dict)
        )
        normalized_summary = {key.replace("_", "-"): value for key, value in by_status.items()}
        all_statuses = set(actual_statuses) | set(normalized_summary)
        mismatches = [
            f"{status}: summary={normalized_summary.get(status, 0)}, rows={actual_statuses.get(status, 0)}"
            for status in sorted(all_statuses)
            if normalized_summary.get(status, 0) != actual_statuses.get(status, 0)
        ]
        if mismatches:
            errors.append(
                "health/latest.json:_trust_summary.by_status: status counts disagree: "
                + "; ".join(mismatches)
            )

    required_artifacts = (
        ("data", ".md", "dataset report"),
        ("data/jsonld", ".json", "JSON-LD artifact"),
        ("badges", ".svg", "dataset badge"),
    )
    for directory, suffix, label in required_artifacts:
        missing = [
            f"{directory}/{dataset_id}{suffix}"
            for dataset_id in sorted(manifest_id_set)
            if not (root / directory / f"{dataset_id}{suffix}").is_file()
        ]
        if missing:
            errors.append(f"{label}: missing required paths: " + ", ".join(missing))

    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
        help="repository root (defaults to the parent of scripts/)",
    )
    args = parser.parse_args()
    errors = verify_repository_contract(args.root)
    if errors:
        print(f"Repository contract verification failed ({len(errors)} invariant(s)):")
        for error in errors:
            print(f"- {error}")
        return 1

    manifest = json.loads((args.root / "datapulse.json").read_text(encoding="utf-8"))
    print(f"Repository contract verification passed ({len(manifest['datasets'])} datasets).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
