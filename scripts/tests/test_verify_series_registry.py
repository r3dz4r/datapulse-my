"""Coverage for the dataset series registry verifier.

Each failure class in the phase-0 brief has a test that mutates a throwaway copy
of the repository surface. The mutation control at the end corrupts the registry
in a copy and asserts the verifier changes from exit 0 to exit 1; the checked-in
registry is never written.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from scripts.verify_series_registry import (
    RegistryParseError,
    RegistryUnavailableError,
    verify,
)


ROOT = Path(__file__).resolve().parents[2]
VERIFIER = ROOT / "scripts/verify_series_registry.py"
SCHEMA = ROOT / "config/series-registry.schema.json"
REGISTRY = ROOT / "config/series-registry.json"

DUPLICATE_REGISTRY = """{
  "schema": "datapulse/v1/series-registry",
  "series": {
    "cpi_core_inflation": {
      "schema_id": "dosm_cpi_2d_core_inflation_v1",
      "schema_version": 1,
      "dataset_ids": ["cpi_core_inflation"],
      "previous_schema_ids": [],
      "basis": "first declaration",
      "reviewed_at": "2026-09-20",
      "reviewer": "operator"
    },
    "cpi_core_inflation": {
      "schema_id": "dosm_cpi_2d_core_inflation_v1",
      "schema_version": 1,
      "dataset_ids": ["dosm_cpi_core_inflation"],
      "previous_schema_ids": [],
      "basis": "second declaration",
      "reviewed_at": "2026-09-20",
      "reviewer": "operator"
    }
  }
}
"""


def _fixture_root(tmp_path: Path) -> Path:
    root = tmp_path / "series-root"
    (root / "config").mkdir(parents=True)
    shutil.copy2(SCHEMA, root / "config/series-registry.schema.json")
    shutil.copy2(REGISTRY, root / "config/series-registry.json")
    manifest = {
        "datasets": [
            {
                "id": "cpi_core_inflation",
                "series_code": "cpi_core_inflation",
                "schema_id": "dosm_cpi_2d_core_inflation_v1",
            },
            {
                "id": "dosm_cpi_core_inflation",
                "series_code": "cpi_core_inflation",
                "schema_id": "dosm_cpi_2d_core_inflation_v1",
            },
            {"id": "fuelprice"},
        ]
    }
    (root / "datapulse.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return root


def _registry_path(root: Path) -> Path:
    return root / "config/series-registry.json"


def _registry_document(root: Path) -> dict:
    return json.loads(_registry_path(root).read_text(encoding="utf-8"))


def _write_registry(root: Path, document: object) -> None:
    _registry_path(root).write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")


def _write_manifest(root: Path, manifest: object) -> None:
    (root / "datapulse.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


def _run(root: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(VERIFIER), "--root", str(root)],
        text=True,
        capture_output=True,
        check=False,
    )


def _combined(result: subprocess.CompletedProcess[str]) -> str:
    return result.stdout + result.stderr


def test_repository_registry_passes() -> None:
    result = _run(ROOT)
    assert result.returncode == 0, _combined(result)
    assert "series registry verified" in _combined(result)
    assert verify(ROOT) == []


def test_datasets_without_series_identity_are_not_failures(tmp_path: Path) -> None:
    root = _fixture_root(tmp_path)
    manifest = json.loads((root / "datapulse.json").read_text(encoding="utf-8"))
    manifest["datasets"].extend({"id": f"unidentified_{index}"} for index in range(416))
    _write_manifest(root, manifest)

    result = _run(root)

    assert result.returncode == 0, _combined(result)
    assert verify(root) == []


def test_missing_registry_fails(tmp_path: Path) -> None:
    root = _fixture_root(tmp_path)
    _registry_path(root).unlink()

    result = _run(root)

    assert result.returncode == 1
    assert "required file is missing" in _combined(result)
    with pytest.raises(RegistryUnavailableError):
        verify(root)


def test_unparseable_registry_fails(tmp_path: Path) -> None:
    root = _fixture_root(tmp_path)
    _registry_path(root).write_text('{"schema": "datapulse/v1/series-registry",', encoding="utf-8")

    result = _run(root)

    assert result.returncode == 1
    assert "invalid JSON" in _combined(result)
    with pytest.raises(RegistryParseError):
        verify(root)


def test_schema_violation_names_offending_entry(tmp_path: Path) -> None:
    root = _fixture_root(tmp_path)
    document = _registry_document(root)
    del document["series"]["cpi_core_inflation"]["schema_id"]
    _write_registry(root, document)

    result = _run(root)

    assert result.returncode == 1
    assert "series.cpi_core_inflation" in _combined(result)


def test_duplicate_series_code_with_differing_dataset_ids_fails(tmp_path: Path) -> None:
    root = _fixture_root(tmp_path)
    _registry_path(root).write_text(DUPLICATE_REGISTRY, encoding="utf-8")

    result = _run(root)

    assert result.returncode == 1
    output = _combined(result)
    assert "cpi_core_inflation" in output
    assert "declared more than once" in output
    assert "differing dataset_ids" in output


def test_one_series_across_multiple_dataset_ids_is_allowed(tmp_path: Path) -> None:
    root = _fixture_root(tmp_path)
    entry = _registry_document(root)["series"]["cpi_core_inflation"]

    assert entry["dataset_ids"] == ["cpi_core_inflation", "dosm_cpi_core_inflation"]
    assert verify(root) == []


def test_schema_id_change_without_version_increment_fails(tmp_path: Path) -> None:
    root = _fixture_root(tmp_path)
    document = _registry_document(root)
    entry = document["series"]["cpi_core_inflation"]
    entry["previous_schema_ids"] = ["dosm_cpi_2d_core_inflation_v1"]
    entry["schema_id"] = "dosm_cpi_2d_core_inflation_v2"
    _write_registry(root, document)
    manifest = json.loads((root / "datapulse.json").read_text(encoding="utf-8"))
    for row in manifest["datasets"]:
        if "schema_id" in row:
            row["schema_id"] = "dosm_cpi_2d_core_inflation_v2"
    _write_manifest(root, manifest)

    result = _run(root)

    assert result.returncode == 1
    assert "schema_version" in _combined(result)


def test_incremented_schema_id_is_allowed(tmp_path: Path) -> None:
    root = _fixture_root(tmp_path)
    document = _registry_document(root)
    entry = document["series"]["cpi_core_inflation"]
    entry["previous_schema_ids"] = ["dosm_cpi_2d_core_inflation_v1"]
    entry["schema_id"] = "dosm_cpi_2d_core_inflation_v2"
    entry["schema_version"] = 2
    _write_registry(root, document)
    manifest = json.loads((root / "datapulse.json").read_text(encoding="utf-8"))
    for row in manifest["datasets"]:
        if "schema_id" in row:
            row["schema_id"] = "dosm_cpi_2d_core_inflation_v2"
    _write_manifest(root, manifest)

    result = _run(root)

    assert result.returncode == 0, _combined(result)


def test_unregistered_series_in_manifest_fails(tmp_path: Path) -> None:
    root = _fixture_root(tmp_path)
    manifest = json.loads((root / "datapulse.json").read_text(encoding="utf-8"))
    manifest["datasets"].append({"id": "rogue", "series_code": "rogue_series"})
    _write_manifest(root, manifest)

    result = _run(root)

    assert result.returncode == 1
    output = _combined(result)
    assert "rogue_series" in output
    assert "absent from" in output


def test_manifest_series_not_listed_in_dataset_ids_fails(tmp_path: Path) -> None:
    root = _fixture_root(tmp_path)
    manifest = json.loads((root / "datapulse.json").read_text(encoding="utf-8"))
    manifest["datasets"].append(
        {
            "id": "unmapped",
            "series_code": "cpi_core_inflation",
            "schema_id": "dosm_cpi_2d_core_inflation_v1",
        }
    )
    _write_manifest(root, manifest)

    result = _run(root)

    assert result.returncode == 1
    assert "not listed" in _combined(result)


def test_unregistered_series_in_passport_fails(tmp_path: Path) -> None:
    root = _fixture_root(tmp_path)
    passports = root / "data/passports"
    passports.mkdir(parents=True)
    (passports / "rogue.json").write_text(
        json.dumps({"identity": {"dataset_id": "rogue"}, "series_code": "rogue_series"}),
        encoding="utf-8",
    )

    result = _run(root)

    assert result.returncode == 1
    output = _combined(result)
    assert "rogue_series" in output
    assert "data/passports/rogue.json" in output


def test_registered_series_in_passport_is_allowed(tmp_path: Path) -> None:
    root = _fixture_root(tmp_path)
    passports = root / "data/passports"
    passports.mkdir(parents=True)
    (passports / "cpi.json").write_text(
        json.dumps(
            {
                "identity": {"dataset_id": "dosm_cpi_core_inflation"},
                "series_code": "cpi_core_inflation",
            }
        ),
        encoding="utf-8",
    )

    result = _run(root)

    assert result.returncode == 0, _combined(result)


def test_mutation_control_fails_on_corrupted_copy(tmp_path: Path) -> None:
    root = _fixture_root(tmp_path)
    control = _run(root)
    assert control.returncode == 0, _combined(control)

    document = _registry_document(root)
    document["series"]["cpi_core_inflation"]["dataset_ids"] = ["cpi_core_inflation"]
    _write_registry(root, document)

    mutated = _run(root)

    assert mutated.returncode == 1
    assert "not listed" in _combined(mutated)
    on_disk = json.loads(REGISTRY.read_text(encoding="utf-8"))
    assert on_disk["series"]["cpi_core_inflation"]["dataset_ids"] == [
        "cpi_core_inflation",
        "dosm_cpi_core_inflation",
    ]
