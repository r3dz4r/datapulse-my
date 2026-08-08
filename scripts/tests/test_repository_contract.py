import json
import shutil
from pathlib import Path

import pytest

from scripts.verify_repository_contract import verify_repository_contract


FIXTURE = Path(__file__).parent / "fixtures/repository_contract/valid"


@pytest.fixture
def repository(tmp_path: Path) -> Path:
    root = tmp_path / "repository"
    shutil.copytree(FIXTURE, root)
    return root


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def test_valid_fixture_passes(repository: Path) -> None:
    assert verify_repository_contract(repository) == []


def test_duplicate_manifest_id_reports_the_id(repository: Path) -> None:
    manifest_path = repository / "datapulse.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["datasets"][1]["id"] = "alpha"
    write_json(manifest_path, manifest)

    errors = verify_repository_contract(repository)

    assert any("datapulse.json" in error and "duplicate" in error and "alpha" in error for error in errors)


def test_missing_health_id_reports_the_id(repository: Path) -> None:
    health_path = repository / "health/latest.json"
    health = json.loads(health_path.read_text(encoding="utf-8"))
    health["datasets"] = health["datasets"][:1]
    health["_trust_summary"] = {"datasets_total": 1, "by_status": {"fresh": 1}}
    write_json(health_path, health)

    errors = verify_repository_contract(repository)

    assert any("health/latest.json" in error and "missing IDs" in error and "beta" in error for error in errors)


def test_extra_health_id_reports_the_id(repository: Path) -> None:
    health_path = repository / "health/latest.json"
    health = json.loads(health_path.read_text(encoding="utf-8"))
    health["datasets"].append({"dataset_id": "gamma", "status": "fresh"})
    health["_trust_summary"] = {"datasets_total": 3, "by_status": {"fresh": 2, "stale": 1}}
    write_json(health_path, health)

    errors = verify_repository_contract(repository)

    assert any("health/latest.json" in error and "extra IDs" in error and "gamma" in error for error in errors)
