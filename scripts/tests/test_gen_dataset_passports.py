"""Contract tests for deterministic, evidence-bounded Dataset Passport v1."""

from __future__ import annotations

import copy
import json
import shutil
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator, FormatChecker

from scripts.gen_dataset_passports import PassportError, build_passport, generate


ROOT = Path(__file__).resolve().parents[2]


def _inputs() -> tuple[dict, dict, dict, dict]:
    manifest = json.loads((ROOT / "datapulse.json").read_text(encoding="utf-8"))
    health = json.loads((ROOT / "health/latest.json").read_text(encoding="utf-8"))
    graph = json.loads((ROOT / "catalog-graph.json").read_text(encoding="utf-8"))
    attestations = json.loads((ROOT / "attestations/latest/index.json").read_text(encoding="utf-8"))
    return manifest, health, graph, attestations


def _passport(dataset_id: str) -> dict:
    manifest, snapshot, graph, attestations = _inputs()
    entry = next(row for row in manifest["datasets"] if row["id"] == dataset_id)
    health = next(row for row in snapshot["datasets"] if row["dataset_id"] == dataset_id)
    return build_passport(ROOT, entry, health, graph, attestations)


def test_passport_projects_complete_metadata_and_existing_quality_profile_exactly() -> None:
    passport = _passport("fuelprice")
    assert passport["identity"]["dataset_id"] == "fuelprice"
    assert passport["identity"]["canonical_url"].startswith("https://")
    assert passport["intended_use"]["declared_purpose"]["state"] == "not_evaluated"
    assert passport["quality_profile"] == next(
        row["quality_profile"] for row in _inputs()[1]["datasets"] if row["dataset_id"] == "fuelprice"
    )
    assert passport["licence_and_attribution"]["limitation"].startswith("Declared metadata")


def test_passport_preserves_missing_expected_count_and_non_ready_profile() -> None:
    manifest, snapshot, graph, attestations = _inputs()
    entry = next(row for row in manifest["datasets"] if row["expected_record_count"] is None)
    health = next(row for row in snapshot["datasets"] if row["dataset_id"] == entry["id"])
    passport = build_passport(ROOT, entry, health, graph, attestations)
    assert passport["health_evidence"]["expected_record_count"] is None
    states = {row["quality_profile"]["overall"] for row in snapshot["datasets"]}
    assert {"ready", "indeterminate", "not_ready"} <= states


def test_record_evidence_is_pilot_bounded_and_lineage_is_not_transformation_claim() -> None:
    pilot = _passport("pharmaceutical_products")
    other = _passport("fuelprice")
    assert pilot["record_evidence"] == {
        "schema": "record-evidence/v1",
        "reference": "record-evidence/pharmaceutical_products/latest.json",
        "dataset_id": "pharmaceutical_products",
    }
    assert other["record_evidence"]["reason"] == "record_evidence_not_enabled_for_dataset"
    assert other["lineage"]["transformation_lineage"]["state"] == "not_evaluated"
    assert "not full transformation lineage" in other["lineage"]["catalogue_relationships"]["limitation"]


def test_passport_schema_rejects_unknown_fields() -> None:
    passport = _passport("fuelprice")
    passport["invented_quality_claim"] = True
    schema = json.loads((ROOT / "passport.schema.json").read_text(encoding="utf-8"))
    assert list(Draft202012Validator(schema, format_checker=FormatChecker()).iter_errors(passport))


def test_generator_rejects_manifest_health_id_mismatch(tmp_path: Path) -> None:
    for relative in ("datapulse.json", "datapulse.schema.json", "health.schema.json", "passport.schema.json", "catalog-graph.json", "attestations/latest/index.json"):
        source, destination = ROOT / relative, tmp_path / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
    health_path = tmp_path / "health/latest.json"
    health_path.parent.mkdir(parents=True)
    health = json.loads((ROOT / "health/latest.json").read_text(encoding="utf-8"))
    health["datasets"] = health["datasets"][1:]
    health_path.write_text(json.dumps(health), encoding="utf-8")
    with pytest.raises(PassportError, match="IDs differ"):
        generate(tmp_path, tmp_path / "out")


def test_generator_is_atomic_schema_valid_and_byte_identical(tmp_path: Path) -> None:
    first, second = tmp_path / "first", tmp_path / "second"
    assert generate(ROOT, first) == 418
    assert generate(ROOT, second) == 418
    assert sorted(path.name for path in first.glob("*.json")) == sorted(path.name for path in second.glob("*.json"))
    assert len(list(first.glob("*.json"))) == 419
    assert not list(first.glob("*.tmp"))
    assert all((first / name).read_bytes() == (second / name).read_bytes() for name in (path.name for path in first.glob("*.json")))
    schema = json.loads((ROOT / "passport.schema.json").read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    for path in first.glob("*.json"):
        if path.name != "index.json":
            assert not list(validator.iter_errors(json.loads(path.read_text(encoding="utf-8")))), path
