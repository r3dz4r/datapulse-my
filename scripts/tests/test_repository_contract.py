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


def test_unresolved_custodian_reports_the_id(repository: Path) -> None:
    manifest_path = repository / "datapulse.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["datasets"][0]["custodian"] = "missing"
    write_json(manifest_path, manifest)

    assert any("unresolved custodian" in error and "missing" in error for error in verify_repository_contract(repository))


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


def test_approved_json_envelope_subset_passes(repository: Path) -> None:
    errors = verify_repository_contract(repository)

    assert not [error for error in errors if "data/json" in error]


def test_unapproved_report_orphan_fails_with_path(repository: Path) -> None:
    (repository / "data/rogue.md").write_text("# Rogue\n", encoding="utf-8")

    errors = verify_repository_contract(repository)

    assert any("data/rogue.md" in error and "orphan" in error for error in errors)


def test_portfolio_total_literal_fails_with_path_and_line(repository: Path) -> None:
    (repository / "README.md").write_text("# Fixture\n\nWe publish 2 datasets.\n", encoding="utf-8")

    errors = verify_repository_contract(repository)

    assert any("README.md:3" in error and "2 datasets" in error for error in errors)


def test_approved_literal_exclusion_passes(repository: Path) -> None:
    readme = repository / "README.md"
    readme.write_text("# Fixture\n\nHistorical snapshot: 2 datasets.\n", encoding="utf-8")
    scope_path = repository / "scripts/contract-scope.json"
    scope = json.loads(scope_path.read_text(encoding="utf-8"))
    scope["literal_detection"]["exclusions"] = [
        {
            "path": "README.md",
            "line_pattern": "^Historical snapshot: 2 datasets\\.$",
            "reason": "Historical fixture, not a live portfolio total"
        }
    ]
    write_json(scope_path, scope)

    assert verify_repository_contract(repository) == []


def test_unknown_probe_policy_id_reports_the_id(repository: Path) -> None:
    policy_path = repository / "scripts/probe-policy.json"
    policy = json.loads(policy_path.read_text(encoding="utf-8"))
    policy["datasets"]["rogue_probe"] = {"adapter": "direct"}
    write_json(policy_path, policy)

    errors = verify_repository_contract(repository)

    assert any("probe-policy.json" in error and "rogue_probe" in error for error in errors)
