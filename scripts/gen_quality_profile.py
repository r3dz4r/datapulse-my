#!/usr/bin/env python3
"""Attach deterministic, evidence-bounded quality profiles to a health snapshot."""

from __future__ import annotations

import argparse
import json
import os
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker


ROOT = Path(__file__).resolve().parents[1]
PROFILE_VERSION = "datapulse-quality-profile/v1"
POLICY_ID = "datapulse-quality-readiness/v1"
DIMENSIONS = (
    "fair",
    "licensing",
    "provenance",
    "governance",
    "reproducibility",
    "catalogue_readiness",
)


class QualityProfileError(ValueError):
    """Raised when source inputs cannot support a safe additive profile."""


def _ref(source: str, dataset_id: str, field: str) -> dict[str, str]:
    return {"source": source, "path": f"datasets[{dataset_id!r}].{field}"}


def _present(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip()) or isinstance(value, (int, float)) and not isinstance(value, bool)


def _check(
    check_id: str,
    state: str,
    reason: str,
    refs: Sequence[dict[str, str]],
    limitation: str,
) -> dict[str, Any]:
    return {
        "check_id": check_id,
        "state": state,
        "reason_codes": [reason],
        "evidence_refs": list(refs),
        "limitations": [limitation],
    }


def _dimension_state(states: Sequence[str]) -> str:
    """Aggregate check states without treating an inapplicable check as a pass."""
    if "fail" in states:
        return "fail"
    if "unknown" in states:
        return "unknown"
    if states and all(item == "not_applicable" for item in states):
        return "not_applicable"
    if states and all(item in {"pass", "not_applicable"} for item in states):
        return "pass"
    return "unknown"


def _overall_state(states: Sequence[str]) -> str:
    """Aggregate dimension states according to the public readiness policy."""
    if "fail" in states:
        return "not_ready"
    if "unknown" in states:
        return "indeterminate"
    if states and all(item in {"pass", "not_applicable"} for item in states):
        return "ready"
    return "indeterminate"


def _dimension(checks: Sequence[dict[str, Any]], limitation: str) -> dict[str, Any]:
    states = [str(check["state"]) for check in checks]
    state = _dimension_state(states)
    coverage = {
        "applicable": sum(item != "not_applicable" for item in states),
        "evaluated": sum(item in {"pass", "fail"} for item in states),
        "passed": states.count("pass"),
        "failed": states.count("fail"),
        "unknown": states.count("unknown"),
        "not_applicable": states.count("not_applicable"),
    }
    refs = [ref for check in checks for ref in check["evidence_refs"]]
    return {
        "state": state,
        "checks": list(checks),
        "coverage": coverage,
        "reason_codes": [reason for check in checks for reason in check["reason_codes"]],
        "evidence_refs": refs,
        "limitations": [limitation],
        "policy_basis": POLICY_ID,
    }


def _field_check(
    check_id: str,
    source: str,
    row: Mapping[str, Any],
    dataset_id: str,
    field: str,
    limitation: str,
) -> dict[str, Any]:
    state = "pass" if _present(row.get(field)) else "unknown"
    reason = f"{field}_declared" if state == "pass" else f"{field}_missing"
    return _check(check_id, state, reason, [_ref(source, dataset_id, field)], limitation)


def derive_profile(
    manifest: Mapping[str, Any], health: Mapping[str, Any], *, schema_valid: bool = True
) -> dict[str, Any]:
    """Derive one six-dimension profile only from supplied manifest and health rows."""
    dataset_id = manifest.get("id")
    if not isinstance(dataset_id, str) or not dataset_id:
        raise QualityProfileError("manifest row has no stable id")
    if health.get("dataset_id") != dataset_id:
        raise QualityProfileError(f"health row has no matching manifest row for {dataset_id!r}")

    manifest_ref = lambda field: _ref("manifest", dataset_id, field)
    health_ref = lambda field: _ref("health", dataset_id, field)
    status = health.get("status")
    direct_access_state = (
        "unknown" if not _present(health.get("request_url") or health.get("url"))
        else "fail" if status in {"unreachable", "discontinued"}
        else "pass"
    )
    direct_access_reason = {
        "pass": "observed_access_signal_present",
        "fail": f"observed_access_{status}",
        "unknown": "observed_access_signal_missing",
    }[direct_access_state]
    shape_present = _present(health.get("schema_fingerprint")) or _present(health.get("first_row_hash")) or _present(health.get("column_count"))
    reuse_present = _present(manifest.get("licence")) and _present(manifest.get("attribution"))
    urls_recorded = _present(manifest.get("url")) and _present(health.get("request_url") or health.get("url"))
    url_conflict = urls_recorded and manifest.get("url") != (health.get("request_url") or health.get("url"))
    record_count = health.get("record_count")

    dimensions = {
        "fair": _dimension([
            _check("fair.catalogue_metadata", "pass" if _present(manifest.get("id")) and _present(manifest.get("name")) and _present(manifest.get("url")) else "unknown", "catalogue_metadata_declared" if _present(manifest.get("id")) and _present(manifest.get("name")) and _present(manifest.get("url")) else "catalogue_metadata_missing", [manifest_ref("id"), manifest_ref("name"), manifest_ref("url")], "Checks declared catalogue fields, not FAIR compliance."),
            _check("fair.observed_access", direct_access_state, direct_access_reason, [health_ref("request_url"), health_ref("status")], "Records one observed access signal; it does not promise continuing access."),
            _check("fair.shape_metadata", "pass" if shape_present else "unknown", "shape_metadata_observed" if shape_present else "shape_metadata_missing", [health_ref("schema_fingerprint"), health_ref("first_row_hash"), health_ref("column_count")], "Shape metadata is not a semantic interoperability assessment."),
            _check("fair.reuse_metadata", "pass" if reuse_present else "unknown", "reuse_metadata_declared" if reuse_present else "reuse_metadata_missing", [manifest_ref("licence"), manifest_ref("attribution")], "Declared reuse metadata is not legal or FAIR certification."),
        ], "FAIR-relevant metadata is recorded without inferring FAIR compliance."),
        "licensing": _dimension([
            _field_check("licensing.declared_licence", "manifest", manifest, dataset_id, "licence", "A declared licence is not a legal interpretation or validation."),
            _field_check("licensing.declared_attribution", "manifest", manifest, dataset_id, "attribution", "A declared attribution is not a legal interpretation or validation."),
        ], "Missing or ambiguous licensing evidence remains unknown; no legal conclusion is made."),
        "provenance": _dimension([
            _field_check("provenance.source_url", "manifest", manifest, dataset_id, "url", "A source URL identifies a declared source, not its truth."),
            _check("provenance.steward_or_custodian", "pass" if _present(manifest.get("steward")) or _present(manifest.get("custodian")) else "unknown", "publisher_metadata_declared" if _present(manifest.get("steward")) or _present(manifest.get("custodian")) else "publisher_metadata_missing", [manifest_ref("steward"), manifest_ref("custodian")], "Declared publisher metadata is not independent attribution verification."),
            _check("provenance.observation", "pass" if _present(health.get("last_checked")) and _present(health.get("request_url") or health.get("url")) else "unknown", "observation_reference_present" if _present(health.get("last_checked")) and _present(health.get("request_url") or health.get("url")) else "observation_reference_missing", [health_ref("last_checked"), health_ref("request_url")], "The observation records a probe boundary, not upstream content truth."),
            _check("provenance.source_observed_boundary", "unknown" if not urls_recorded or url_conflict else "pass", "source_observed_url_conflict" if url_conflict else "source_observed_boundary_recorded" if urls_recorded else "source_observed_boundary_missing", [manifest_ref("url"), health_ref("request_url")], "Different declared and observed URLs are preserved rather than resolved automatically."),
        ], "Provenance records declared and observed boundaries; it does not certify source authority or truth."),
        "governance": _dimension([
            _field_check("governance.methodology_version", "manifest", manifest, dataset_id, "methodology_version", "Version metadata identifies a declared method, not its adequacy."),
            _check("governance.status_reason_slot", "pass" if "status_reason" in health else "unknown", "status_reason_slot_present" if "status_reason" in health else "status_reason_slot_missing", [health_ref("status"), health_ref("status_reason")], "A present reason slot may be null for a given health observation."),
            _check("governance.declared_cadence", "not_applicable" if manifest.get("data_type") in {"reference", "policy-reference"} else "pass" if _present(manifest.get("refresh_frequency")) else "unknown", "cadence_not_applicable_reference_dataset" if manifest.get("data_type") in {"reference", "policy-reference"} else "refresh_frequency_declared" if _present(manifest.get("refresh_frequency")) else "refresh_frequency_missing", [manifest_ref("data_type"), manifest_ref("refresh_frequency")], "Cadence is explicitly not applicable only to manifest-declared reference data; otherwise it is not evidence that the publisher followed it."),
        ], "Governance checks declaration and observation fields, not institutional governance compliance."),
        "reproducibility": _dimension([
            _check("reproducibility.shape_fingerprint", "pass" if shape_present else "unknown", "shape_fingerprint_observed" if shape_present else "shape_fingerprint_missing", [health_ref("schema_fingerprint"), health_ref("first_row_hash"), health_ref("column_count")], "Shape signals are bounded structural observations, not a complete reproducibility proof."),
            _field_check("reproducibility.retrieval_timestamp", "health", health, dataset_id, "last_checked", "A retrieval timestamp does not reproduce the remote response by itself."),
            _check("reproducibility.record_count", "pass" if isinstance(record_count, int) and record_count >= 0 else "unknown", "record_count_estimated" if health.get("record_count_estimated") is True and isinstance(record_count, int) else "record_count_observed" if isinstance(record_count, int) and record_count >= 0 else "record_count_missing", [health_ref("record_count"), health_ref("record_count_estimated"), health_ref("record_count_within_tolerance")], "A count is an observed or estimated measurement, not a completeness guarantee."),
            _field_check("reproducibility.attestation_reference", "manifest", manifest, dataset_id, "attestation_ref", "A declared reference is not verified here; missing evidence remains unknown."),
        ], "Reproducibility evidence is limited to recorded probe metadata and references; no replay guarantee is made."),
        "catalogue_readiness": _dimension([
            _field_check("catalogue_readiness.stable_id", "manifest", manifest, dataset_id, "id", "A stable local ID does not establish external catalogue identity."),
            _check("catalogue_readiness.identity_metadata", "pass" if all(_present(manifest.get(field)) for field in ("name", "steward", "source")) else "unknown", "identity_metadata_declared" if all(_present(manifest.get(field)) for field in ("name", "steward", "source")) else "identity_metadata_missing", [manifest_ref("name"), manifest_ref("steward"), manifest_ref("source")], "Identity metadata is declared catalogue context, not semantic validation."),
            _field_check("catalogue_readiness.health_report", "manifest", manifest, dataset_id, "health_report", "A health-report link is a local reference, not an availability guarantee."),
            _check("catalogue_readiness.manifest_health_parity", "pass", "manifest_health_id_match", [manifest_ref("id"), health_ref("dataset_id")], "Parity is limited to this snapshot and manifest pair."),
            _check("catalogue_readiness.schema_valid_envelope", "pass" if schema_valid else "unknown", "input_envelopes_schema_valid" if schema_valid else "input_envelopes_not_validated", [manifest_ref("id"), health_ref("dataset_id")], "Schema validity checks structure only; it does not validate content semantics."),
        ], "Catalogue readiness means recorded metadata is structurally sufficient for this named policy, not that the dataset is true or safe."),
    }
    states = [dimensions[name]["state"] for name in DIMENSIONS]
    overall = _overall_state(states)
    return {
        "profile_version": PROFILE_VERSION,
        "policy_id": POLICY_ID,
        "dimensions": dimensions,
        "overall": overall,
        "limitations": ["This is an evidence/readiness profile, not a universal quality score, semantic truth claim, certification, or admission decision."],
    }


def derive_snapshot(manifest: Mapping[str, Any], health: Mapping[str, Any]) -> dict[str, Any]:
    """Return a deep-copied health snapshot with profiles for every matched row."""
    datasets = manifest.get("datasets")
    rows = health.get("datasets")
    if not isinstance(datasets, list) or not isinstance(rows, list):
        raise QualityProfileError("manifest and health inputs must contain datasets arrays")
    manifest_by_id = {row.get("id"): row for row in datasets if isinstance(row, dict)}
    if len(manifest_by_id) != len(datasets) or any(not isinstance(key, str) or not key for key in manifest_by_id):
        raise QualityProfileError("manifest must contain unique stable dataset ids")
    output = json.loads(json.dumps(health))
    output_rows = output["datasets"]
    if len(output_rows) != len(rows):
        raise QualityProfileError("health datasets cannot be copied deterministically")
    seen: set[str] = set()
    for row in output_rows:
        if not isinstance(row, dict) or not isinstance(row.get("dataset_id"), str):
            raise QualityProfileError("health row has no stable dataset_id")
        dataset_id = row["dataset_id"]
        if dataset_id in seen:
            raise QualityProfileError(f"duplicate health dataset_id {dataset_id!r}")
        seen.add(dataset_id)
        entry = manifest_by_id.get(dataset_id)
        if not isinstance(entry, dict):
            raise QualityProfileError(f"health row has no matching manifest row for {dataset_id!r}")
        row["quality_profile"] = derive_profile(entry, row)
    missing = sorted(set(manifest_by_id) - seen)
    if missing:
        raise QualityProfileError(f"manifest datasets have no health rows: {', '.join(missing)}")
    return output


def _load(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise QualityProfileError(f"cannot load {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise QualityProfileError(f"{path} must contain a JSON object")
    return value


def _validate(value: Mapping[str, Any], schema_path: Path, label: str) -> None:
    schema = _load(schema_path)
    errors = sorted(Draft202012Validator(schema, format_checker=FormatChecker()).iter_errors(value), key=lambda error: list(error.absolute_path))
    if errors:
        raise QualityProfileError(f"{label} schema validation failed: {errors[0].message}")


def _write_atomic(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=ROOT / "datapulse.json")
    parser.add_argument("--health", type=Path, default=ROOT / "health/latest.json")
    parser.add_argument("--out", type=Path, help="Output health snapshot; defaults to --health for atomic in-place enrichment.")
    args = parser.parse_args(argv)
    try:
        manifest = _load(args.manifest)
        health = _load(args.health)
        _validate(manifest, ROOT / "datapulse.schema.json", "manifest")
        _validate(health, ROOT / "health.schema.json", "health")
        output = derive_snapshot(manifest, health)
        _validate(output, ROOT / "health.schema.json", "quality-profile output")
        _write_atomic(args.out or args.health, output)
    except QualityProfileError as exc:
        parser.error(str(exc))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
