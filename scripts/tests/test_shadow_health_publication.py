from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from scripts import shadow_health_publication as shadow


ROOT = Path(__file__).resolve().parents[2]
CLI = ROOT / "scripts/shadow_health_publication.py"
SOURCE_COMMIT = "a" * 40
HEALTH_COMMIT = "b" * 40


def write_health(path: Path, status: str = "fresh", checked_at: str = "2026-09-09T00:00:00Z") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({
        "_trust_summary": {"status": "ok"},
        "checked_at": checked_at,
        "datasets": [
            {"dataset_id": "beta", "status": status, "secret": "do-not-publish"},
            {"dataset_id": "alpha", "status": "aging", "token": "also-secret"},
        ],
    }, indent=2) + "\n", encoding="utf-8")


def run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(CLI), *args],
        capture_output=True,
        text=True,
        check=False,
    )


def create(health: Path, envelope: Path) -> subprocess.CompletedProcess[str]:
    return run("create", "--health", str(health), "--output", str(envelope),
               "--source-commit", SOURCE_COMMIT, "--health-commit", HEALTH_COMMIT)


def compare(health: Path, envelope: Path, source: str = SOURCE_COMMIT,
            health_commit: str = HEALTH_COMMIT) -> subprocess.CompletedProcess[str]:
    return run("compare", "--health", str(health), "--envelope", str(envelope),
               "--source-commit", source, "--health-commit", health_commit)


def result(command: subprocess.CompletedProcess[str]) -> dict[str, object]:
    return json.loads(command.stdout)


def test_create_and_compare_valid_candidate(tmp_path: Path) -> None:
    health = tmp_path / "health" / "latest.json"
    envelope = tmp_path / "runtime" / "candidate.json"
    write_health(health)

    created = create(health, envelope)
    compared = compare(health, envelope)

    assert created.returncode == 0
    assert compared.returncode == 0
    assert result(compared) == {"equivalent": True}
    candidate = json.loads(envelope.read_text(encoding="utf-8"))
    assert list(candidate) == ["schema", "version", "source_commit", "health_commit", "checked_at", "dataset_count", "health_sha256", "semantic_sha256"]
    assert candidate["dataset_count"] == 2


def test_tampered_health_and_changed_status_are_not_equivalent(tmp_path: Path) -> None:
    health = tmp_path / "health" / "latest.json"
    envelope = tmp_path / "runtime" / "candidate.json"
    write_health(health)
    assert create(health, envelope).returncode == 0

    health.write_bytes(health.read_bytes() + b"\n")
    compared = compare(health, envelope)
    payload = result(compared)
    assert compared.returncode != 0
    assert payload["mismatches"] == ["health_sha256"]

    write_health(health, status="stale")
    compared = compare(health, envelope)

    assert compared.returncode != 0
    payload = result(compared)
    assert payload["equivalent"] is False
    assert "health_sha256" in payload["mismatches"]
    assert "semantic_sha256" in payload["mismatches"]


def test_commit_identity_mismatch_is_rejected(tmp_path: Path) -> None:
    health = tmp_path / "health" / "latest.json"
    envelope = tmp_path / "runtime" / "candidate.json"
    write_health(health)
    assert create(health, envelope).returncode == 0

    compared = compare(health, envelope, source="c" * 40)

    assert compared.returncode != 0
    assert result(compared) == {"equivalent": False, "error": "source_commit_mismatch"}

    compared = compare(health, envelope, health_commit="c" * 40)

    assert compared.returncode != 0
    assert result(compared) == {"equivalent": False, "error": "health_commit_mismatch"}


def test_malformed_envelope_is_rejected(tmp_path: Path) -> None:
    health = tmp_path / "health" / "latest.json"
    envelope = tmp_path / "runtime" / "candidate.json"
    write_health(health)
    envelope.parent.mkdir()
    envelope.write_text('{"schema":"wrong"}\n', encoding="utf-8")

    compared = compare(health, envelope)

    assert compared.returncode != 0
    assert result(compared) == {"equivalent": False, "error": "invalid_envelope"}


def test_create_is_byte_deterministic_and_omits_dataset_secrets(tmp_path: Path) -> None:
    health = tmp_path / "health" / "latest.json"
    first = tmp_path / "runtime" / "first.json"
    second = tmp_path / "runtime" / "second.json"
    write_health(health)

    assert create(health, first).returncode == 0
    assert create(health, second).returncode == 0

    assert first.read_bytes() == second.read_bytes()
    assert b"do-not-publish" not in first.read_bytes()
    assert b"also-secret" not in first.read_bytes()


def test_invalid_health_preserves_existing_output(tmp_path: Path) -> None:
    health = tmp_path / "health" / "latest.json"
    envelope = tmp_path / "runtime" / "candidate.json"
    write_health(health)
    envelope.parent.mkdir()
    envelope.write_bytes(b"preserve-me\n")
    health.write_text("not json", encoding="utf-8")

    created = create(health, envelope)

    assert created.returncode != 0
    assert envelope.read_bytes() == b"preserve-me\n"


def test_atomic_replace_failure_preserves_existing_output(tmp_path: Path) -> None:
    health = tmp_path / "health" / "latest.json"
    envelope = tmp_path / "runtime" / "candidate.json"
    write_health(health)
    envelope.parent.mkdir()
    envelope.write_bytes(b"preserve-me\n")

    with patch.object(shadow.os, "replace", side_effect=OSError("forced")):
        with pytest.raises(shadow.UnsafeOutputError, match="write_failed"):
            shadow.create(health, envelope, SOURCE_COMMIT, HEALTH_COMMIT)

    assert envelope.read_bytes() == b"preserve-me\n"


def test_output_symlink_and_canonical_health_target_are_rejected(tmp_path: Path) -> None:
    health = tmp_path / "health" / "latest.json"
    target = tmp_path / "runtime" / "real.json"
    symlink = tmp_path / "runtime" / "candidate.json"
    write_health(health)
    target.parent.mkdir()
    symlink.symlink_to(target)

    linked = create(health, symlink)
    canonical = create(health, health)

    assert linked.returncode != 0
    assert canonical.returncode != 0
    assert not target.exists()


def test_rejected_arguments_and_traversal_do_not_echo_secret_or_path(tmp_path: Path) -> None:
    health = tmp_path / "health" / "latest.json"
    write_health(health)
    secret = "very-secret-argument"

    invalid_commit = run("create", "--health", str(health), "--output", str(tmp_path / "runtime" / "candidate.json"),
                         "--source-commit", secret, "--health-commit", HEALTH_COMMIT)
    traversal = create(health, tmp_path / "runtime" / ".." / "candidate.json")

    assert invalid_commit.returncode != 0
    assert secret not in invalid_commit.stdout + invalid_commit.stderr
    assert result(invalid_commit) == {"equivalent": False, "error": "invalid_commit"}
    assert traversal.returncode != 0
    assert result(traversal) == {"equivalent": False, "error": "unsafe_output"}
