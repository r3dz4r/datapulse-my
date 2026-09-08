"""Focused offline tests for additive dataset quality profiles."""

from __future__ import annotations

import copy
import json
import subprocess
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker

from scripts.gen_quality_profile import (
    DIMENSIONS,
    QualityProfileError,
    _dimension,
    _dimension_state,
    _overall_state,
    derive_snapshot,
)


ROOT = Path(__file__).resolve().parents[2]
NOW = "2026-09-01T00:00:00Z"


def manifest_row() -> dict[str, object]:
    return {
        "id": "sample",
        "name": "Sample dataset",
        "url": "https://example.test/catalogue/sample",
        "source": "Example catalogue",
        "steward": "Example Steward",
        "custodian": "example-custodian",
        "licence": "Example Open Licence",
        "attribution": "Example Steward",
        "refresh_frequency": "daily",
        "expected_record_count": 12,
        "geo_coverage": "Malaysia",
        "namespace": "other",
        "methodology_version": 3,
        "health_report": "data/sample.md",
        "attestation_ref": "attestations/2026-09-01/sample.json",
    }


def health_row() -> dict[str, object]:
    return {
        "dataset_id": "sample",
        "last_checked": NOW,
        "url": "https://example.test/catalogue/sample",
        "request_url": "https://example.test/catalogue/sample",
        "status": "fresh",
        "status_reason": None,
        "http_status": 200,
        "access_method": "direct curl GET",
        "schema_fingerprint": "sha256:" + "a" * 64,
        "column_count": 4,
        "record_count": 12,
        "record_count_estimated": False,
        "record_count_within_tolerance": True,
    }


def inputs() -> tuple[dict[str, object], dict[str, object]]:
    return (
        {"$schema": "https://www.data-pulse.my/datapulse.schema.json", "datasets": [manifest_row()]},
        {
            "schema": "datapulse/v0.4/dataset-health",
            "checked_at": NOW,
            "_trust_summary": {
                "checked_at": NOW,
                "datasets_total": 1,
                "by_status": {
                    "fresh": 1,
                    "aging": 0,
                    "stale": 0,
                    "discontinued": 0,
                    "degraded": 0,
                    "browser_dependent": 0,
                    "unreachable": 0,
                    "unknown": 0,
                    "unknown_freshness": 0,
                    "reference": 0,
                },
            },
            "datasets": [health_row()],
        },
    )


def profile() -> dict[str, object]:
    manifest, health = inputs()
    return derive_snapshot(manifest, health)["datasets"][0]["quality_profile"]


def test_profile_has_exact_dimensions_and_a_bounded_readiness_claim() -> None:
    result = profile()

    assert result["profile_version"] == "datapulse-quality-profile/v1"
    assert result["policy_id"] == "datapulse-quality-readiness/v1"
    assert tuple(result["dimensions"]) == DIMENSIONS
    assert result["overall"] == "ready"
    for dimension in result["dimensions"].values():
        assert set(dimension) == {
            "state", "checks", "coverage", "reason_codes", "evidence_refs", "limitations", "policy_basis"
        }
        assert dimension["coverage"]["applicable"] == len(dimension["checks"])
        assert all("source" in ref and "path" in ref for ref in dimension["evidence_refs"])
        assert dimension["limitations"]


def test_missing_signal_is_unknown_not_neutral_or_not_applicable() -> None:
    manifest, health = inputs()
    manifest["datasets"][0].pop("licence")
    manifest["datasets"][0].pop("attribution")
    health["datasets"][0].pop("schema_fingerprint")
    health["datasets"][0].pop("column_count")

    result = derive_snapshot(manifest, health)["datasets"][0]["quality_profile"]

    assert result["dimensions"]["licensing"]["state"] == "unknown"
    assert result["dimensions"]["licensing"]["coverage"]["unknown"] == 2
    assert result["dimensions"]["reproducibility"]["state"] == "unknown"
    assert result["overall"] == "indeterminate"
    assert "not_applicable" not in {
        check["state"] for check in result["dimensions"]["licensing"]["checks"]
    }


def test_not_applicable_requires_the_explicit_reference_dataset_rule() -> None:
    manifest, health = inputs()
    manifest["datasets"][0]["data_type"] = "reference"
    manifest["datasets"][0].pop("refresh_frequency")

    result = derive_snapshot(manifest, health)["datasets"][0]["quality_profile"]
    cadence = result["dimensions"]["governance"]["checks"][2]

    assert cadence["state"] == "not_applicable"
    assert cadence["reason_codes"] == ["cadence_not_applicable_reference_dataset"]
    assert result["dimensions"]["governance"]["coverage"]["not_applicable"] == 1
    assert result["dimensions"]["governance"]["coverage"]["applicable"] == 2


def test_dimension_aggregation_keeps_all_not_applicable_distinct_from_pass() -> None:
    checks = [
        {"state": "not_applicable", "reason_codes": ["rule_a"], "evidence_refs": []},
        {"state": "not_applicable", "reason_codes": ["rule_b"], "evidence_refs": []},
    ]

    result = _dimension(checks, "Both checks are explicitly out of scope.")

    assert _dimension_state(["pass", "not_applicable"]) == "pass"
    assert _dimension_state(["not_applicable", "not_applicable"]) == "not_applicable"
    assert _dimension_state(["pass", "unknown", "not_applicable"]) == "unknown"
    assert _dimension_state(["pass", "fail", "unknown"]) == "fail"
    assert result["state"] == "not_applicable"
    assert result["coverage"] == {
        "applicable": 0,
        "evaluated": 0,
        "passed": 0,
        "failed": 0,
        "unknown": 0,
        "not_applicable": 2,
    }


def test_overall_aggregation_prioritizes_fail_then_unknown_then_ready() -> None:
    assert _overall_state(["pass", "not_applicable"] * 3) == "ready"
    assert _overall_state(["pass", "unknown", "not_applicable"]) == "indeterminate"
    assert _overall_state(["pass", "unknown", "fail"]) == "not_ready"


def test_observed_failure_is_not_ready_and_conflicts_are_preserved() -> None:
    manifest, health = inputs()
    health["datasets"][0]["status"] = "unreachable"
    health["datasets"][0]["request_url"] = "https://mirror.example.test/sample"

    result = derive_snapshot(manifest, health)["datasets"][0]["quality_profile"]
    fair = result["dimensions"]["fair"]
    provenance = result["dimensions"]["provenance"]

    assert fair["state"] == "fail"
    assert "observed_access_unreachable" in fair["reason_codes"]
    assert provenance["state"] == "unknown"
    assert "source_observed_url_conflict" in provenance["reason_codes"]
    assert result["overall"] == "not_ready"


def test_all_dimensions_have_inspectable_existing_input_mappings() -> None:
    result = profile()

    expected_check_ids = {
        "fair": ("fair.catalogue_metadata", "fair.observed_access", "fair.shape_metadata", "fair.reuse_metadata"),
        "licensing": ("licensing.declared_licence", "licensing.declared_attribution"),
        "provenance": ("provenance.source_url", "provenance.steward_or_custodian", "provenance.observation", "provenance.source_observed_boundary"),
        "governance": ("governance.methodology_version", "governance.status_reason_slot", "governance.declared_cadence"),
        "reproducibility": ("reproducibility.shape_fingerprint", "reproducibility.retrieval_timestamp", "reproducibility.record_count", "reproducibility.attestation_reference"),
        "catalogue_readiness": ("catalogue_readiness.stable_id", "catalogue_readiness.identity_metadata", "catalogue_readiness.health_report", "catalogue_readiness.manifest_health_parity", "catalogue_readiness.schema_valid_envelope"),
    }
    for name, check_ids in expected_check_ids.items():
        checks = result["dimensions"][name]["checks"]
        assert tuple(check["check_id"] for check in checks) == check_ids


def test_profile_is_schema_valid_and_repeated_derivation_is_byte_identical() -> None:
    manifest, health = inputs()
    first = derive_snapshot(manifest, health)
    second = derive_snapshot(manifest, health)
    schema = json.loads((ROOT / "health.schema.json").read_text(encoding="utf-8"))

    assert json.dumps(first, sort_keys=True, separators=(",", ":")) == json.dumps(second, sort_keys=True, separators=(",", ":"))
    assert list(Draft202012Validator(schema, format_checker=FormatChecker()).iter_errors(first)) == []


def test_schema_rejects_incomplete_quality_profile_contract() -> None:
    manifest, health = inputs()
    output = derive_snapshot(manifest, health)
    output["datasets"][0]["quality_profile"]["dimensions"].pop("fair")
    schema = json.loads((ROOT / "health.schema.json").read_text(encoding="utf-8"))

    errors = list(Draft202012Validator(schema, format_checker=FormatChecker()).iter_errors(output))

    assert errors


def test_cli_writes_atomically_to_explicit_output_without_network(tmp_path: Path) -> None:
    manifest, health = inputs()
    manifest_path = tmp_path / "datapulse.json"
    health_path = tmp_path / "latest.json"
    output_path = tmp_path / "profiled.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    health_path.write_text(json.dumps(health), encoding="utf-8")

    command = [
        "python3", "scripts/gen_quality_profile.py", "--manifest", str(manifest_path),
        "--health", str(health_path), "--out", str(output_path),
    ]
    first = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
    assert first.returncode == 0, first.stderr
    first_bytes = output_path.read_bytes()
    second = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
    assert second.returncode == 0, second.stderr
    assert output_path.read_bytes() == first_bytes
    assert not (tmp_path / "profiled.json.tmp").exists()


def test_cli_rejects_invalid_source_health_without_overwriting_output(tmp_path: Path) -> None:
    manifest, health = inputs()
    manifest_path = tmp_path / "datapulse.json"
    health_path = tmp_path / "latest.json"
    output_path = tmp_path / "profiled.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    health.pop("schema")
    health_path.write_text(json.dumps(health), encoding="utf-8")
    output_path.write_bytes(b"previous-output")

    result = subprocess.run(
        [
            "python3", "scripts/gen_quality_profile.py", "--manifest", str(manifest_path),
            "--health", str(health_path), "--out", str(output_path),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode != 0
    assert "health schema validation failed" in result.stderr
    assert output_path.read_bytes() == b"previous-output"
    assert not (tmp_path / "profiled.json.tmp").exists()


def test_invalid_or_mismatched_inputs_fail_closed() -> None:
    manifest, health = inputs()
    health["datasets"][0]["dataset_id"] = "different"

    try:
        derive_snapshot(manifest, health)
    except QualityProfileError as error:
        assert "no matching manifest" in str(error)
    else:  # pragma: no cover - makes the failure explicit if fail-closed changes.
        raise AssertionError("mismatched manifest/health inputs must fail closed")
