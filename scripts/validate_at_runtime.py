#!/usr/bin/env python3
"""Validate probe-boundary documents against the repository's CI schemas."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

try:
    from jsonschema import Draft202012Validator, FormatChecker
except ImportError:  # pragma: no cover - exercised in deployment environments
    Draft202012Validator = None  # type: ignore[assignment,misc]
    FormatChecker = None  # type: ignore[assignment,misc]


def _load_json(path: Path, errors: list[str]) -> Any | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        errors.append(f"{path}: required JSON document is missing")
    except OSError as exc:
        errors.append(f"{path}: cannot read JSON document: {exc}")
    except json.JSONDecodeError as exc:
        errors.append(f"{path}:{exc.lineno}:{exc.colno}: invalid JSON: {exc.msg}")
    return None


def _schema_path(schemas_dir: Path, filename: str) -> Path:
    candidates = [schemas_dir / filename]
    if schemas_dir.is_dir():
        candidates.extend(schemas_dir.rglob(filename))
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    raise FileNotFoundError(f"schema {filename!r} was not found below {schemas_dir}")


def _repo_schema_path(document: Path, filename: str) -> Path:
    for parent in (document.parent, *document.parents):
        try:
            candidate = parent / filename
            if candidate.is_file():
                return candidate
        except FileNotFoundError:
            continue
    # This also keeps the public single-document API useful for temporary test files.
    return _schema_path(Path(__file__).resolve().parents[1], filename)


def _schema_errors(document: Path, schema: Path) -> list[str]:
    errors: list[str] = []
    value = _load_json(document, errors)
    schema_value = _load_json(schema, errors)
    if errors or value is None or schema_value is None:
        return errors
    if Draft202012Validator is None:
        return [
            "jsonschema is required for full runtime schema validation; "
            "install it with `python3 -m pip install -r requirements-dev.txt`"
        ]
    try:
        validator = Draft202012Validator(schema_value, format_checker=FormatChecker())
        failures = sorted(validator.iter_errors(value), key=lambda item: list(item.absolute_path))
    except Exception as exc:
        return [f"{schema}: invalid schema: {exc}"]
    for failure in failures:
        location = ".".join(str(part) for part in failure.absolute_path) or "<root>"
        errors.append(f"{document}:{location}: schema violation: {failure.message}")
    return errors


def validate_manifest(path: str | Path) -> tuple[bool, list[str]]:
    """Validate a manifest using ``datapulse.schema.json``."""
    document = Path(path)
    try:
        errors = _schema_errors(document, _repo_schema_path(document, "datapulse.schema.json"))
    except FileNotFoundError as exc:
        errors = [str(exc)]
    return not errors, errors


def validate_probe_policy(path: str | Path) -> tuple[bool, list[str]]:
    """Validate a probe policy using ``probe-policy.schema.json``."""
    document = Path(path)
    try:
        errors = _schema_errors(
            document, _repo_schema_path(document, "probe-policy.schema.json")
        )
    except FileNotFoundError as exc:
        errors = [str(exc)]
    return not errors, errors


def _document_root(input_dir: Path) -> Path:
    input_dir = input_dir.resolve()
    return input_dir if (input_dir / "datapulse.json").is_file() else input_dir.parent


def _cross_reference_errors(health: Path, manifest: Path) -> list[str]:
    errors: list[str] = []
    health_value = _load_json(health, errors)
    manifest_value = _load_json(manifest, errors)
    if errors or not isinstance(health_value, dict) or not isinstance(manifest_value, dict):
        return errors
    manifest_ids = {
        row.get("id") for row in manifest_value.get("datasets", []) if isinstance(row, dict)
    }
    health_ids = [
        row.get("dataset_id") for row in health_value.get("datasets", []) if isinstance(row, dict)
    ]
    for dataset_id in health_ids:
        if dataset_id not in manifest_ids:
            errors.append(
                f"{health}: dataset_id {dataset_id!r} has no matching manifest entry"
            )
    missing = sorted(manifest_ids - set(health_ids))
    for dataset_id in missing:
        errors.append(f"{manifest}: dataset {dataset_id!r} has no health row in {health}")
    duplicates = sorted({item for item in health_ids if health_ids.count(item) > 1})
    for dataset_id in duplicates:
        errors.append(f"{health}: duplicate health row for dataset_id {dataset_id!r}")
    return errors


def validate_health(
    path: str | Path, manifest: str | Path | None = None
) -> tuple[bool, list[str]]:
    """Validate health and, when supplied, its manifest dataset cross-references."""
    document = Path(path)
    try:
        errors = _schema_errors(document, _repo_schema_path(document, "health.schema.json"))
    except FileNotFoundError as exc:
        errors = [str(exc)]
    if manifest is not None and not errors:
        errors.extend(_cross_reference_errors(document, Path(manifest)))
    return not errors, errors


def validate_all(input_dir: str | Path, schemas_dir: str | Path) -> tuple[bool, list[str]]:
    """Validate manifest, probe policy, health, and health/manifest cross-references."""
    input_path = Path(input_dir).resolve()
    root = _document_root(input_path)
    schema_root = Path(schemas_dir).resolve()
    if not schema_root.is_dir() or not any(
        (schema_root / filename).is_file()
        for filename in ("datapulse.schema.json", "health.schema.json", "probe-policy.schema.json")
    ):
        schema_root = root
    if not any(
        (schema_root / filename).is_file()
        for filename in ("datapulse.schema.json", "health.schema.json", "probe-policy.schema.json")
    ):
        schema_root = Path(__file__).resolve().parents[1]
    manifest = root / "datapulse.json"
    health = root / "health/latest.json"
    policy_candidates = (root / "scripts/probe-policy.json", root / "probe-policy.json")
    policy = next((candidate for candidate in policy_candidates if candidate.is_file()), policy_candidates[0])
    errors: list[str] = []
    for document, schema_name in (
        (manifest, "datapulse.schema.json"),
        (policy, "probe-policy.schema.json"),
        (health, "health.schema.json"),
    ):
        try:
            errors.extend(_schema_errors(document, _schema_path(schema_root, schema_name)))
        except FileNotFoundError as exc:
            errors.append(str(exc))
    if not errors:
        errors.extend(_cross_reference_errors(health, manifest))
    return not errors, errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path, help="probe staging directory or health directory")
    parser.add_argument("--schemas", required=True, type=Path, help="directory containing the CI schemas")
    args = parser.parse_args(argv)
    ok, errors = validate_all(args.input, args.schemas)
    if ok:
        print("runtime schema validation: PASS")
        return 0
    for error in errors:
        print(f"runtime schema validation: {error}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
