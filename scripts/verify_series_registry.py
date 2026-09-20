#!/usr/bin/env python3
"""Verify the curated dataset series registry against the manifest and passports.

The registry in ``config/series-registry.json`` is the authoring path of record
for ``series_code`` / ``schema_id`` identity. A dataset with no series identity
is the expected state for most of the catalogue and is never a failure here;
only a declared identity that is missing, duplicated, version-inconsistent, or
absent from the registry is.
"""

from __future__ import annotations

import argparse
import json
import logging
import re
from pathlib import Path
from typing import Any, Iterator

from jsonschema import Draft202012Validator, FormatChecker


ROOT = Path(__file__).resolve().parents[1]
LOGGER = logging.getLogger(__name__)

REGISTRY_PATH = "config/series-registry.json"
SCHEMA_PATH = "config/series-registry.schema.json"
MANIFEST_PATH = "datapulse.json"
PASSPORTS_DIR = "data/passports"
SCHEMA_CONSTANT = "datapulse/v1/series-registry"
VERSION_SUFFIX = re.compile(r"_v([0-9]+)$")


class SeriesRegistryError(Exception):
    """Base class for series registry failures that block verification."""


class RegistryUnavailableError(SeriesRegistryError):
    """A required registry file or schema is absent or unreadable."""


class RegistryParseError(SeriesRegistryError):
    """The registry is not valid JSON, or the manifest cannot be read."""


class RegistrySchemaError(SeriesRegistryError):
    """The registry does not satisfy its own JSON Schema."""


class _JsonObject(dict):
    """A dict that remembers keys repeated at its own JSON nesting level.

    ``json`` silently keeps the last value for a repeated object key, which
    would hide a duplicated ``series_code``. The pairs hook records both values
    so the verifier can still name the offending series.
    """

    duplicate_values: dict[str, list[Any]]


def _pairs_hook(pairs: list[tuple[str, Any]]) -> _JsonObject:
    obj = _JsonObject()
    duplicates: dict[str, list[Any]] = {}
    for key, value in pairs:
        if key in obj:
            duplicates.setdefault(key, [obj[key]]).append(value)
        obj[key] = value
    obj.duplicate_values = duplicates
    return obj


def _read_text(root: Path, relative_path: str) -> str:
    path = root / relative_path
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise RegistryUnavailableError(f"{relative_path}: required file is missing") from exc
    except OSError as exc:
        raise RegistryUnavailableError(f"{relative_path}: cannot read file: {exc}") from exc


def _load_json(root: Path, relative_path: str) -> Any:
    text = _read_text(root, relative_path)
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise RegistryParseError(
            f"{relative_path}:{exc.lineno}:{exc.colno}: invalid JSON: {exc.msg}"
        ) from exc


def _load_registry(root: Path) -> _JsonObject:
    text = _read_text(root, REGISTRY_PATH)
    try:
        document = json.loads(text, object_pairs_hook=_pairs_hook)
    except json.JSONDecodeError as exc:
        raise RegistryParseError(
            f"{REGISTRY_PATH}:{exc.lineno}:{exc.colno}: invalid JSON: {exc.msg}"
        ) from exc
    if not isinstance(document, _JsonObject):
        raise RegistryParseError(f"{REGISTRY_PATH}: registry must be a JSON object")
    return document


def _schema_errors(document: Any, schema: Any) -> list[str]:
    try:
        Draft202012Validator.check_schema(schema)
    except Exception as exc:  # a broken schema is itself a registry failure
        raise RegistrySchemaError(f"{SCHEMA_PATH}: invalid JSON Schema: {exc}") from exc
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    errors: list[str] = []
    for failure in sorted(validator.iter_errors(document), key=lambda item: list(item.path)):
        location = ".".join(str(part) for part in failure.absolute_path) or "<root>"
        errors.append(f"{REGISTRY_PATH}:{location}: schema violation: {failure.message}")
    return errors


def _duplicate_key_errors(registry: _JsonObject) -> list[str]:
    """Report repeated JSON keys, which schema validation cannot observe."""
    errors: list[str] = []
    for key in sorted(registry.duplicate_values):
        errors.append(f"{REGISTRY_PATH}: top-level key {key!r} is declared more than once")
    series = registry.get("series")
    if isinstance(series, _JsonObject):
        for code, values in sorted(series.duplicate_values.items()):
            dataset_sets = {
                frozenset(value.get("dataset_ids", []))
                for value in values
                if isinstance(value, dict) and isinstance(value.get("dataset_ids"), list)
            }
            detail = " with differing dataset_ids" if len(dataset_sets) > 1 else ""
            errors.append(
                f"{REGISTRY_PATH}:series: series_code {code!r} is declared more than once{detail}; "
                "one series must be a single entry whose dataset_ids list every dataset id"
            )
    return errors


def _series_errors(series: dict[str, Any]) -> list[str]:
    """Check each series entry for version consistency and duplicate dataset ids."""
    errors: list[str] = []
    for code, entry in sorted(series.items()):
        if not isinstance(entry, dict):
            continue
        schema_id = entry.get("schema_id")
        version = entry.get("schema_version")
        match = VERSION_SUFFIX.search(schema_id) if isinstance(schema_id, str) else None
        if match is None or not isinstance(version, int) or int(match.group(1)) != version:
            errors.append(
                f"{REGISTRY_PATH}:series.{code}: schema_id {schema_id!r} does not encode "
                f"schema_version {version!r}; changing schema_id requires incrementing schema_version"
            )
        dataset_ids = entry.get("dataset_ids")
        if isinstance(dataset_ids, list):
            seen: set[str] = set()
            for dataset_id in dataset_ids:
                if isinstance(dataset_id, str) and dataset_id in seen:
                    errors.append(
                        f"{REGISTRY_PATH}:series.{code}.dataset_ids: duplicate dataset id {dataset_id!r}"
                    )
                if isinstance(dataset_id, str):
                    seen.add(dataset_id)
        previous = entry.get("previous_schema_ids")
        if isinstance(previous, list):
            for previous_id in previous:
                if previous_id == schema_id:
                    errors.append(
                        f"{REGISTRY_PATH}:series.{code}.previous_schema_ids: {previous_id!r} is also the current schema_id"
                    )
                    continue
                previous_match = (
                    VERSION_SUFFIX.search(previous_id) if isinstance(previous_id, str) else None
                )
                if (
                    previous_match is not None
                    and isinstance(version, int)
                    and int(previous_match.group(1)) >= version
                ):
                    errors.append(
                        f"{REGISTRY_PATH}:series.{code}.previous_schema_ids: {previous_id!r} is not "
                        f"an earlier version than {schema_id!r} (schema_version {version})"
                    )
    return errors


def _registered_dataset_ids(series: dict[str, Any]) -> dict[str, set[str]]:
    registered: dict[str, set[str]] = {}
    for code, entry in series.items():
        if isinstance(entry, dict) and isinstance(entry.get("dataset_ids"), list):
            registered[code] = {item for item in entry["dataset_ids"] if isinstance(item, str)}
        else:
            registered[code] = set()
    return registered


def _registered_schema_ids(series: dict[str, Any]) -> dict[str, set[str]]:
    registered: dict[str, set[str]] = {}
    for code, entry in series.items():
        if isinstance(entry, dict) and isinstance(entry.get("schema_id"), str):
            registered[code] = {entry["schema_id"]}
        else:
            registered[code] = set()
    return registered


def _manifest_errors(manifest: Any, series: dict[str, Any]) -> list[str]:
    """Require every manifest-declared identity to resolve to a registry entry."""
    if not isinstance(manifest, dict) or not isinstance(manifest.get("datasets"), list):
        raise RegistryParseError(f"{MANIFEST_PATH}: expected an object with a datasets array")
    errors: list[str] = []
    rows = [row for row in manifest["datasets"] if isinstance(row, dict)]
    manifest_ids = {row.get("id") for row in rows if isinstance(row.get("id"), str)}
    registered_ids = _registered_dataset_ids(series)
    registered_schemas = _registered_schema_ids(series)

    for code, dataset_ids in sorted(registered_ids.items()):
        for dataset_id in sorted(dataset_ids):
            if dataset_id not in manifest_ids:
                errors.append(
                    f"{REGISTRY_PATH}:series.{code}.dataset_ids: {dataset_id!r} is not a dataset id in {MANIFEST_PATH}"
                )

    for row in rows:
        dataset_id = row.get("id")
        code = row.get("series_code")
        if code is None:
            continue  # absent identity is the expected state, never a failure
        if not isinstance(code, str) or code not in registered_ids:
            errors.append(
                f"{MANIFEST_PATH}: dataset {dataset_id!r} declares series_code {code!r} that is absent from {REGISTRY_PATH}"
            )
            continue
        if dataset_id not in registered_ids[code]:
            errors.append(
                f"{MANIFEST_PATH}: dataset {dataset_id!r} is not listed in {REGISTRY_PATH}:series.{code}.dataset_ids"
            )
        declared_schema = row.get("schema_id")
        if isinstance(declared_schema, str) and declared_schema not in registered_schemas[code]:
            errors.append(
                f"{MANIFEST_PATH}: dataset {dataset_id!r} declares schema_id {declared_schema!r} "
                f"that disagrees with {REGISTRY_PATH}:series.{code}.schema_id"
            )
    return errors


def _iter_series_codes(node: Any, path: str) -> Iterator[tuple[str, str]]:
    """Yield ``(location, series_code)`` for every declared series_code value."""
    if isinstance(node, dict):
        for key, value in node.items():
            location = f"{path}.{key}" if path else str(key)
            if key == "series_code" and isinstance(value, str):
                yield location, value
            else:
                yield from _iter_series_codes(value, location)
    elif isinstance(node, list):
        for index, value in enumerate(node):
            yield from _iter_series_codes(value, f"{path}[{index}]")


def _passport_errors(root: Path, registered: dict[str, set[str]]) -> list[str]:
    """Require every passport-declared series_code to resolve to the registry."""
    errors: list[str] = []
    passports = root / PASSPORTS_DIR
    if not passports.is_dir():
        return errors
    for path in sorted(passports.glob("*.json")):
        relative = f"{PASSPORTS_DIR}/{path.name}"
        try:
            document = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            errors.append(f"{relative}:{exc.lineno}:{exc.colno}: invalid JSON: {exc.msg}")
            continue
        except (OSError, UnicodeError) as exc:
            errors.append(f"{relative}: cannot read passport: {exc}")
            continue
        identity = document.get("identity") if isinstance(document, dict) else None
        dataset_id = identity.get("dataset_id") if isinstance(identity, dict) else None
        for location, code in _iter_series_codes(document, ""):
            if code not in registered:
                errors.append(f"{relative}:{location}: series_code {code!r} is absent from {REGISTRY_PATH}")
                continue
            if isinstance(dataset_id, str) and dataset_id not in registered[code]:
                errors.append(
                    f"{relative}:{location}: dataset id {dataset_id!r} is not listed in "
                    f"{REGISTRY_PATH}:series.{code}.dataset_ids"
                )
    return errors


def verify(root: Path) -> list[str]:
    """Return every series registry defect for ``root``, raising when unreadable."""
    root = root.resolve()
    registry = _load_registry(root)
    errors: list[str] = []
    if registry.get("schema") != SCHEMA_CONSTANT:
        errors.append(
            f"{REGISTRY_PATH}:schema: expected {SCHEMA_CONSTANT!r}, found {registry.get('schema')!r}"
        )
    schema = _load_json(root, SCHEMA_PATH)
    errors.extend(_schema_errors(registry, schema))
    if errors:
        return errors
    series = registry.get("series")
    if not isinstance(series, dict):
        return [f"{REGISTRY_PATH}:series: expected an object keyed by series_code"]
    errors.extend(_duplicate_key_errors(registry))
    errors.extend(_series_errors(series))
    manifest = _load_json(root, MANIFEST_PATH)
    errors.extend(_manifest_errors(manifest, series))
    errors.extend(_passport_errors(root, _registered_dataset_ids(series)))
    return errors


def _summary(root: Path) -> str:
    registry = _load_registry(root)
    series = registry["series"]
    manifest = _load_json(root, MANIFEST_PATH)
    rows = [row for row in manifest["datasets"] if isinstance(row, dict)]
    with_identity = sum(1 for row in rows if isinstance(row.get("series_code"), str))
    dataset_ids = sum(len(entry["dataset_ids"]) for entry in series.values())
    return (
        f"series registry verified: {len(series)} series, {dataset_ids} registered dataset ids, "
        f"{with_identity} of {len(rows)} manifest datasets carry series identity"
    )


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root",
        type=Path,
        default=ROOT,
        help="Repository root containing config/, datapulse.json, and data/passports/.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    args = parse_args(argv)
    root = args.root.resolve()
    try:
        errors = verify(root)
    except SeriesRegistryError as exc:
        LOGGER.error("series registry verification failed: %s", exc)
        return 1
    if errors:
        for error in errors:
            LOGGER.error("series registry defect: %s", error)
        LOGGER.error("series registry verification failed with %d defect(s)", len(errors))
        return 1
    LOGGER.info(_summary(root))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
