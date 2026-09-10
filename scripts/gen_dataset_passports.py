#!/usr/bin/env python3
"""Generate deterministic, evidence-bounded DataPulse Dataset Passport v1 files."""

from __future__ import annotations

import argparse
import json
import logging
import os
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker


ROOT = Path(__file__).resolve().parents[1]
PASSPORT_SCHEMA = "datapulse/v1/dataset-passport"
logger = logging.getLogger(__name__)
LICENCE_URLS = {
    "Creative Commons Attribution 4.0": "https://creativecommons.org/licenses/by/4.0/",
    "Open Government Licence (Malaysia)": "https://www.data.gov.my/pages/terms-of-use",
}
LIMITATIONS = [
    "This passport is evidence about observed metadata and state, not semantic truth, completeness, certification, legal permission, safety, or AI admission.",
    "Unavailable evidence is explicit and must not be read as a neutral or favourable result.",
]


class PassportError(ValueError):
    """Raised when a canonical input cannot produce a safe passport."""


def _load(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise PassportError(f"cannot load {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise PassportError(f"{path} must contain a JSON object")
    return value


def _validate(value: Mapping[str, Any], schema_path: Path, label: str) -> None:
    schema = _load(schema_path)
    errors = sorted(Draft202012Validator(schema, format_checker=FormatChecker()).iter_errors(value), key=lambda error: list(error.absolute_path))
    if errors:
        raise PassportError(f"{label} schema validation failed: {errors[0].message}")


def _unavailable(reason: str, *, state: str = "not_evaluated") -> dict[str, str]:
    return {"state": state, "reason": reason}


def _nullable_string(value: object) -> str | None:
    return value if isinstance(value, str) and value else None


def _index(rows: object, field: str, label: str) -> dict[str, dict[str, Any]]:
    if not isinstance(rows, list):
        raise PassportError(f"{label} must be an array")
    result: dict[str, dict[str, Any]] = {}
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get(field), str) or not row[field]:
            raise PassportError(f"{label} rows must have a non-empty {field}")
        if row[field] in result:
            raise PassportError(f"{label} contains duplicate {field}: {row[field]}")
        result[row[field]] = row
    return result


def _record_evidence(root: Path, dataset_id: str) -> dict[str, Any]:
    path = root / "record-evidence" / dataset_id / "latest.json"
    if not path.is_file():
        return _unavailable("record_evidence_not_enabled_for_dataset")
    value = _load(path)
    if value.get("schema") != "record-evidence/v1" or value.get("dataset_id") != dataset_id:
        raise PassportError(f"{path}: expected record-evidence/v1 for {dataset_id}")
    return {"schema": "record-evidence/v1", "reference": path.relative_to(root).as_posix(), "dataset_id": dataset_id}


def build_passport(root: Path, entry: dict[str, Any], health: dict[str, Any], graph: dict[str, Any], attestations: dict[str, Any]) -> dict[str, Any]:
    """Build one passport using only current local canonical evidence."""
    dataset_id = entry["id"]
    profile = health.get("quality_profile")
    if not isinstance(profile, dict):
        raise PassportError(f"{dataset_id}: health row is missing quality_profile")
    envelope = root / "data" / "json" / f"{dataset_id}.json"
    edges = [edge for edge in graph.get("edges", []) if isinstance(edge, dict) and dataset_id in {edge.get("from"), edge.get("to")}]
    attestation_ref = attestations.get("attestations", {}).get(dataset_id)
    if attestation_ref is not None and not isinstance(attestation_ref, str):
        raise PassportError(f"attestation index has invalid reference for {dataset_id}")
    geography = _nullable_string(entry.get("geo_coverage"))
    expected_record_count = health.get("expected_record_count", entry.get("expected_record_count"))
    return {
        "schema": PASSPORT_SCHEMA,
        "identity": {
            "dataset_id": dataset_id, "name": entry["name"], "source": _nullable_string(entry.get("source")),
            "steward": _nullable_string(entry.get("steward")), "custodian": _nullable_string(entry.get("custodian")),
            "canonical_url": entry["url"], "namespace": _nullable_string(entry.get("namespace")), "geography": geography,
            "declared_verified_at": _nullable_string(entry.get("verified_at")), "observed_verified_at": _nullable_string(health.get("last_checked")),
        },
        "intended_use": {
            "declared_purpose": _unavailable("declared_purpose_not_present_in_canonical_manifest"),
            "declared_coverage": {"geography": geography} if geography else _unavailable("declared_coverage_not_present_in_canonical_manifest"),
        },
        "licence_and_attribution": {
            "declared_licence": _nullable_string(entry.get("licence")), "licence_url": LICENCE_URLS.get(entry.get("licence")),
            "attribution": _nullable_string(entry.get("attribution")),
            "limitation": "Declared metadata and evidence only; not legal advice or legal permission.",
        },
        "health_evidence": {
            "status": health["status"], "last_checked": _nullable_string(health.get("last_checked")),
            "freshness_signal": _nullable_string(health.get("freshness_signal")), "freshness_signal_source": _nullable_string(health.get("freshness_signal_source")),
            "record_count": health.get("record_count"), "expected_record_count": expected_record_count,
            "record_count_within_tolerance": health.get("record_count_within_tolerance") if type(expected_record_count) is int else None,
            "record_count_estimated": health.get("record_count_estimated"), "incomplete": health.get("incomplete"),
            "http_status": health.get("http_status"), "access_method": _nullable_string(health.get("access_method")), "access_dependency": _nullable_string(health.get("access_dependency")),
            "schema_shape": {"column_count": health.get("column_count"), "first_row_hash": _nullable_string(health.get("first_row_hash")), "content_shape_changed": health.get("content_shape_changed")},
            "anomaly_reliability": {"anomaly_detected": health.get("anomaly_detected"), "anomaly_detection": health.get("anomaly_detection")},
        },
        "quality_profile": profile,
        "reproducibility_and_evidence": {
            "verification_method": "deterministic_local_projection_of_current_canonical_inputs",
            "source_envelope": envelope.relative_to(root).as_posix() if envelope.is_file() else _unavailable("json_envelope_not_available_for_dataset"),
            "source_digest": _unavailable("canonical_source_digest_not_available"),
            "attestation": attestation_ref if attestation_ref else _unavailable("attestation_reference_not_available"),
            "chain_reference": attestations.get("chain_head_ref") if isinstance(attestations.get("chain_head_ref"), str) else _unavailable("attestation_chain_reference_not_available"),
            "witness_reference": _unavailable("witness_reference_not_available"),
        },
        "lineage": {
            "catalogue_relationships": {"graph_reference": "catalog-graph.json", "relationship_edges": sorted(edges, key=lambda edge: (str(edge.get("kind")), str(edge.get("from")), str(edge.get("to")))), "limitation": "Catalogue relationships are literal metadata context, not full transformation lineage."},
            "transformation_lineage": _unavailable("full_transformation_lineage_not_published"),
        },
        "record_evidence": _record_evidence(root, dataset_id),
        "sensitivity_and_pii": _unavailable("sensitivity_or_pii_classification_not_evaluated"),
        "limitations": LIMITATIONS,
    }


def _write_atomic(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def generate(root: Path, output: Path, *, quick_test: bool = False) -> int:
    manifest = _load(root / "datapulse.json")
    snapshot = _load(root / "health/latest.json")
    _validate(manifest, root / "datapulse.schema.json", "manifest")
    _validate(snapshot, root / "health.schema.json", "health")
    datasets = _index(manifest.get("datasets"), "id", "manifest.datasets")
    health_rows = _index(snapshot.get("datasets"), "dataset_id", "health.datasets")
    if set(datasets) != set(health_rows):
        raise PassportError("manifest and health dataset IDs differ")
    graph = _load(root / "catalog-graph.json")
    if graph.get("node_count") != len(datasets):
        raise PassportError("catalogue graph node count does not match manifest")
    attestations = _load(root / "attestations/latest/index.json")
    selected = sorted(datasets)[:2] if quick_test else sorted(datasets)
    schema = _load(root / "passport.schema.json")
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    for dataset_id in selected:
        passport = build_passport(root, datasets[dataset_id], health_rows[dataset_id], graph, attestations)
        errors = sorted(validator.iter_errors(passport), key=lambda error: list(error.absolute_path))
        if errors:
            raise PassportError(f"{dataset_id}: passport schema validation failed: {errors[0].message}")
        _write_atomic(output / f"{dataset_id}.json", passport)
    _write_atomic(output / "index.json", {"schema": "datapulse/v1/dataset-passport-index", "dataset_count": len(selected), "dataset_ids": selected})
    return len(selected)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--quick-test", action="store_true")
    args = parser.parse_args(argv)
    try:
        output = args.out or args.root / "data" / "passports"
        count = generate(args.root, output, quick_test=args.quick_test)
    except PassportError as exc:
        parser.error(str(exc))
    logger.info("Generated %d dataset passport(s) -> %s", count, output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
