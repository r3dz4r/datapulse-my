#!/usr/bin/env python3
"""Verify the checked-in DataPulse repository contract without network access."""

from __future__ import annotations

import argparse
import fnmatch
import json
import re
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


def _verify_scoped_contract(
    root: Path,
    scope: dict[str, Any],
    manifest_id_set: set[str],
    errors: list[str],
) -> None:
    envelope = scope.get("json_envelope", {})
    approved_ids = envelope.get("approved_ids", [])
    excluded_ids = envelope.get("excluded_ids", [])
    if not isinstance(approved_ids, list) or not all(isinstance(item, str) for item in approved_ids):
        errors.append("scripts/contract-scope.json:json_envelope.approved_ids: expected string array")
        approved_ids = []
    if not isinstance(excluded_ids, list) or not all(isinstance(item, str) for item in excluded_ids):
        errors.append("scripts/contract-scope.json:json_envelope.excluded_ids: expected string array")
        excluded_ids = []
    approved_set = set(approved_ids)
    excluded_set = set(excluded_ids)
    if len(approved_ids) != len(approved_set):
        errors.append("scripts/contract-scope.json:json_envelope.approved_ids: duplicate IDs")
    if len(excluded_ids) != len(excluded_set):
        errors.append("scripts/contract-scope.json:json_envelope.excluded_ids: duplicate IDs")
    if approved_set & excluded_set:
        errors.append(
            "scripts/contract-scope.json: JSON-envelope approved/excluded overlap: "
            + _format_ids(approved_set & excluded_set)
        )
    scoped_ids = approved_set | excluded_set
    if scoped_ids != manifest_id_set:
        missing = manifest_id_set - scoped_ids
        extra = scoped_ids - manifest_id_set
        if missing:
            errors.append(
                "scripts/contract-scope.json: JSON-envelope scope omits manifest IDs: "
                + _format_ids(missing)
            )
        if extra:
            errors.append(
                "scripts/contract-scope.json: JSON-envelope scope has unknown IDs: "
                + _format_ids(extra)
            )
    actual_envelopes = {path.stem for path in (root / "data/json").glob("*.json")}
    missing_envelopes = approved_set - actual_envelopes
    extra_envelopes = actual_envelopes - approved_set
    if missing_envelopes:
        errors.append(
            "data/json: approved JSON-envelope paths are missing: "
            + ", ".join(f"data/json/{item}.json" for item in sorted(missing_envelopes))
        )
    if extra_envelopes:
        errors.append(
            "data/json: files are outside the approved legacy subset: "
            + ", ".join(f"data/json/{item}.json" for item in sorted(extra_envelopes))
        )

    report_exclusions = scope.get("report_exclusions", [])
    if not isinstance(report_exclusions, list):
        errors.append("scripts/contract-scope.json:report_exclusions: expected array")
        report_exclusions = []
    excluded_report_ids: set[str] = set()
    for index, exclusion in enumerate(report_exclusions):
        if not isinstance(exclusion, dict) or not isinstance(exclusion.get("id"), str):
            errors.append(
                f"scripts/contract-scope.json:report_exclusions.{index}: expected object with string id"
            )
            continue
        if not isinstance(exclusion.get("reason"), str) or not exclusion["reason"].strip():
            errors.append(
                f"scripts/contract-scope.json:report_exclusions.{index}: non-empty reason is required"
            )
        excluded_report_ids.add(exclusion["id"])
    actual_reports = {path.stem for path in (root / "data").glob("*.md")}
    expected_reports = manifest_id_set | excluded_report_ids
    for report_id in sorted(actual_reports - expected_reports):
        errors.append(f"data/{report_id}.md: orphan report is not approved by contract scope")
    for report_id in sorted(excluded_report_ids - actual_reports):
        errors.append(f"data/{report_id}.md: approved private report is missing")

    literal_scope = scope.get("literal_detection", {})
    literal_paths = literal_scope.get("paths", [])
    literal_pattern = literal_scope.get("pattern", "")
    literal_exclusions = literal_scope.get("exclusions", [])
    try:
        compiled_literal = re.compile(literal_pattern)
    except (TypeError, re.error) as exc:
        errors.append(f"scripts/contract-scope.json:literal_detection.pattern: invalid regex: {exc}")
        compiled_literal = re.compile(r"(?!x)x")
    if not isinstance(literal_paths, list) or not all(isinstance(item, str) for item in literal_paths):
        errors.append("scripts/contract-scope.json:literal_detection.paths: expected string array")
        literal_paths = []
    if not isinstance(literal_exclusions, list):
        errors.append("scripts/contract-scope.json:literal_detection.exclusions: expected array")
        literal_exclusions = []
    for relative_path in literal_paths:
        path = root / relative_path
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except FileNotFoundError:
            errors.append(f"{relative_path}: literal-detection target is missing")
            continue
        for line_number, line in enumerate(lines, start=1):
            match = compiled_literal.search(line)
            if not match:
                continue
            excluded = False
            for exclusion in literal_exclusions:
                if not isinstance(exclusion, dict) or exclusion.get("path") != relative_path:
                    continue
                try:
                    excluded = bool(re.search(exclusion.get("line_pattern", "(?!x)x"), line))
                except (TypeError, re.error):
                    excluded = False
                if excluded:
                    break
            if not excluded:
                errors.append(
                    f"{relative_path}:{line_number}: hardcoded portfolio total: {match.group(0)!r}"
                )

    generated_artifacts = scope.get("generated_artifacts", [])
    if not isinstance(generated_artifacts, list):
        errors.append("scripts/contract-scope.json:generated_artifacts: expected array")
        return
    for index, ownership in enumerate(generated_artifacts):
        if not isinstance(ownership, dict):
            errors.append(f"scripts/contract-scope.json:generated_artifacts.{index}: expected object")
            continue
        directory = ownership.get("directory")
        artifact_glob = ownership.get("glob")
        generator = ownership.get("generator")
        if ownership.get("editing") != "generator-only":
            errors.append(
                f"scripts/contract-scope.json:generated_artifacts.{index}.editing: must be generator-only"
            )
        if not all(isinstance(item, str) for item in (directory, artifact_glob, generator)):
            errors.append(
                f"scripts/contract-scope.json:generated_artifacts.{index}: directory, glob, and generator are required"
            )
            continue
        if not (root / generator).is_file():
            errors.append(f"{generator}: declared owner for {directory} is missing")
            continue
        auxiliary_globs = ownership.get("allowed_auxiliary_globs", [])
        if not isinstance(auxiliary_globs, list) or not all(
            isinstance(item, str) for item in auxiliary_globs
        ):
            errors.append(
                f"scripts/contract-scope.json:generated_artifacts.{index}.allowed_auxiliary_globs: expected string array"
            )
            auxiliary_globs = []
        expected_names = {
            f"{dataset_id}{Path(artifact_glob).suffix}" for dataset_id in manifest_id_set
        }
        actual_names = {path.name for path in (root / directory).glob(artifact_glob)}
        unexpected = {
            name
            for name in actual_names - expected_names
            if not any(fnmatch.fnmatch(name, pattern) for pattern in auxiliary_globs)
        }
        for name in sorted(unexpected):
            errors.append(f"{directory}/{name}: unowned generated artifact")


def verify_repository_contract(root: Path) -> list[str]:
    """Return actionable invariant failures for ``root``; never mutate it."""
    root = root.resolve()
    errors: list[str] = []
    schema = _load_json(root, "datapulse.schema.json", errors)
    manifest = _load_json(root, "datapulse.json", errors)
    custodians = _load_json(root, "custodians.json", errors)
    health = _load_json(root, "health/latest.json", errors)
    scope = _load_json(root, "scripts/contract-scope.json", errors)
    probe_policy = _load_json(root, "scripts/probe-policy.json", errors)
    probe_policy_schema = _load_json(root, "scripts/probe-policy.schema.json", errors)
    if any(
        document is None
        for document in (schema, manifest, custodians, health, scope, probe_policy, probe_policy_schema)
    ):
        return errors

    try:
        validator = Draft202012Validator(schema, format_checker=FormatChecker())
        for failure in sorted(validator.iter_errors(manifest), key=lambda item: list(item.path)):
            location = ".".join(str(part) for part in failure.absolute_path) or "<root>"
            errors.append(f"datapulse.json:{location}: schema violation: {failure.message}")
    except Exception as exc:  # invalid schemas should be reported as contract failures
        errors.append(f"datapulse.schema.json: invalid schema: {exc}")

    manifest_rows = manifest.get("datasets", []) if isinstance(manifest, dict) else []
    registry = custodians.get("custodians", {}) if isinstance(custodians, dict) else {}
    if custodians.get("schema") != "datapulse/v1/custodians":
        errors.append("custodians.json:schema: expected datapulse/v1/custodians")
    if not isinstance(registry, dict):
        errors.append("custodians.json:custodians: expected object")
        registry = {}
    referenced_custodians = {
        row.get("custodian") for row in manifest_rows
        if isinstance(row, dict) and isinstance(row.get("custodian"), str)
    }
    missing_custodians = referenced_custodians - set(registry)
    if missing_custodians:
        errors.append("datapulse.json: unresolved custodian IDs: " + _format_ids(missing_custodians))
    unused_custodians = set(registry) - referenced_custodians
    if unused_custodians:
        errors.append("custodians.json: unreferenced custodian IDs: " + _format_ids(unused_custodians))
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

    try:
        policy_validator = Draft202012Validator(
            probe_policy_schema, format_checker=FormatChecker()
        )
        for failure in sorted(
            policy_validator.iter_errors(probe_policy), key=lambda item: list(item.path)
        ):
            location = ".".join(str(part) for part in failure.absolute_path) or "<root>"
            errors.append(
                f"scripts/probe-policy.json:{location}: schema violation: {failure.message}"
            )
    except Exception as exc:
        errors.append(f"scripts/probe-policy.schema.json: invalid schema: {exc}")

    private_npra_ids = {
        "npra_products_registered",
        "npra_cosmetic_notifications",
        "npra_drug_registration_guidance",
    }
    policy_rows = probe_policy.get("datasets", {}) if isinstance(probe_policy, dict) else {}
    policy_ids = set(policy_rows) if isinstance(policy_rows, dict) else set()
    missing_private_manifests = {
        dataset_id
        for dataset_id in policy_ids & private_npra_ids
        if not (root / "data" / f"{dataset_id}.md").is_file()
    }
    if missing_private_manifests:
        errors.append(
            "scripts/probe-policy.json: approved private NPRA manifests are missing: "
            + _format_ids(missing_private_manifests)
        )
    unknown_policy_ids = policy_ids - manifest_id_set - private_npra_ids
    if unknown_policy_ids:
        errors.append(
            "scripts/probe-policy.json: dataset keys absent from canonical manifests: "
            + _format_ids(unknown_policy_ids)
        )

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

    if isinstance(scope, dict):
        _verify_scoped_contract(root, scope, manifest_id_set, errors)
    else:
        errors.append("scripts/contract-scope.json:<root>: expected object")

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
