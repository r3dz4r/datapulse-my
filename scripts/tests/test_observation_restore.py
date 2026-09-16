"""Restore proofs for the observation store: archive, delete the source, verify.

Every store here is built through observation_store so the addressing is real
(digest-derived blob and normalized paths, identity-addressed envelopes), and
every proof runs against pytest tmp_path so no real runtime root is touched.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts import verify_observation_restore as restore_proof
from scripts.observation_store import (
    blob_path,
    canonical_json,
    put_blob,
    put_envelope,
    put_normalized,
    read_blob,
    read_normalized,
)

DATASET_ID = "dataset-restore"
OBSERVATION_ID = "obs-restore-0001"
NORMALIZED_PAYLOAD = {"observations": 2, "sum": 8}


def _build_store(root: Path) -> dict[str, Any]:
    """A real store: one raw blob, one retained normalized projection, one
    envelope in the contract's digest namespaces whose provenance transform
    pins the projection's addressing digest exactly where capture pins it —
    so the envelope is readable and every reference it carries resolves."""
    raw = json.dumps(
        {"dataset_id": DATASET_ID, "rows": [{"kiosk_id": 1, "value": 3}, {"kiosk_id": 2, "value": 5}]},
        sort_keys=True,
    ).encode("utf-8")
    source_digest = put_blob(raw, root=root)
    projection_digest = put_normalized(NORMALIZED_PAYLOAD, root=root)
    envelope = {
        "schema": "datapulse/v1/historical-observation",
        "dataset_id": DATASET_ID,
        "observation_id": OBSERVATION_ID,
        "observed_at": "2026-09-15T08:00:00Z",
        "source_digest": source_digest,
        # Identity-namespace digest over the envelope's canonical form; it
        # addresses no path in the store, so it is never resolved to one.
        "observation_digest": "observation:sha256:"
        + hashlib.sha256(OBSERVATION_ID.encode("utf-8")).hexdigest(),
        "normalized_projection": {
            "state": "retained",
            "format": "json-array-of-objects",
            "record_count": 2,
        },
        "field_provenance": {
            "normalized_projection": {
                "transform": (
                    "observation_normalize profile fixture/v1; "
                    f"projection_digest {projection_digest}"
                )
            }
        },
    }
    envelope_path = put_envelope(DATASET_ID, OBSERVATION_ID, envelope, root=root)
    return {
        "source_digest": source_digest,
        "projection_digest": projection_digest,
        "raw": raw,
        "envelope_path": envelope_path,
    }


def _inventory_hash(root: Path) -> str:
    """Digest over every file's relative path and bytes — any change moves it."""
    digest = hashlib.sha256()
    for path in sorted(candidate for candidate in root.rglob("*") if candidate.is_file()):
        digest.update(path.relative_to(root).as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(hashlib.sha256(path.read_bytes()).digest())
    return digest.hexdigest()


def _run_cli(archive: Path) -> subprocess.CompletedProcess[str]:
    script = REPO_ROOT / "scripts" / "verify_observation_restore.py"
    return subprocess.run(
        [sys.executable, str(script), "--archive", str(archive)],
        capture_output=True,
        text=True,
    )


def test_round_trip_verifies_clean_and_inventory_matches_source(tmp_path: Path) -> None:
    store = tmp_path / "store"
    built = _build_store(store)

    report = restore_proof.round_trip(store, workdir=tmp_path)

    verification = report["verification"]
    assert verification["verified"] is True
    assert verification["matches_source"]["matches"] is True
    assert verification["counts"]["ok"] == 2
    assert verification["counts"]["envelopes"] == 1
    assert not store.exists()
    assert Path(report["archive"]).is_file()
    restored = Path(report["restored_root"])
    assert restored.is_dir()
    assert read_blob(built["source_digest"], root=restored) == built["raw"]
    assert read_normalized(built["projection_digest"], root=restored) == canonical_json(NORMALIZED_PAYLOAD)
    assert built["envelope_path"].name in {
        path.name for path in restore_proof.store_inventory(restored)
    }


def test_source_tree_is_gone_before_verification_runs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    store = tmp_path / "store"
    _build_store(store)
    real_verify = restore_proof.verify_restored
    observed: dict[str, Any] = {}

    def spy(restored_root: Path, *, expected_inventory: set[Path] | None = None) -> dict[str, Any]:
        assert not store.exists(), "source tree must already be deleted when verification runs"
        observed["called"] = True
        return real_verify(restored_root, expected_inventory=expected_inventory)

    monkeypatch.setattr(restore_proof, "verify_restored", spy)
    report = restore_proof.round_trip(store, workdir=tmp_path)

    assert observed.get("called") is True
    assert report["source_deleted"] is True
    assert report["verification"]["verified"] is True


def test_tampered_blob_is_reported_corrupt_and_never_repaired(tmp_path: Path) -> None:
    store = tmp_path / "store"
    built = _build_store(store)
    report = restore_proof.round_trip(store, workdir=tmp_path)
    assert report["verification"]["verified"] is True
    restored = Path(report["restored_root"])

    blob = blob_path(built["source_digest"], root=restored)
    tampered = blob.read_bytes()[:-1] + bytes([blob.read_bytes()[-1] ^ 0xFF])
    blob.write_bytes(tampered)
    fingerprint_before = _inventory_hash(restored)

    result = restore_proof.verify_restored(restored)

    assert result["verified"] is False
    assert result["counts"]["corrupt"] == 1
    assert result["counts"]["dangling_references"] == 0
    failure = result["failures"]["corrupt"][0]
    assert failure["path"] == blob.relative_to(restored).as_posix()
    assert failure["digest"] == built["source_digest"]
    assert blob.read_bytes() == tampered
    assert _inventory_hash(restored) == fingerprint_before


def test_missing_blob_referenced_by_envelope_is_a_dangling_reference(tmp_path: Path) -> None:
    store = tmp_path / "store"
    built = _build_store(store)
    report = restore_proof.round_trip(store, workdir=tmp_path)
    restored = Path(report["restored_root"])

    blob = blob_path(built["source_digest"], root=restored)
    blob.unlink()

    result = restore_proof.verify_restored(restored)

    assert result["verified"] is False
    assert result["counts"]["dangling_references"] == 1
    dangling = result["dangling_references"][0]
    assert dangling["dataset_id"] == DATASET_ID
    assert dangling["observation_id"] == OBSERVATION_ID
    assert dangling["field"] == "source_digest"
    assert dangling["digest"] == built["source_digest"]
    assert dangling["expected_path"] == blob.relative_to(restored).as_posix()


def test_restore_refuses_a_non_empty_destination(tmp_path: Path) -> None:
    store = tmp_path / "store"
    _build_store(store)
    archive = restore_proof.archive_store(store, tmp_path / "store.tar")

    destination = tmp_path / "destination"
    destination.mkdir()
    (destination / "sentinel.txt").write_text("pre-existing\n", encoding="utf-8")

    with pytest.raises(restore_proof.RestoreError):
        restore_proof.restore_store(archive, destination)

    assert sorted(path.name for path in destination.iterdir()) == ["sentinel.txt"]


def test_cli_exits_zero_on_a_good_archive(tmp_path: Path) -> None:
    store = tmp_path / "store"
    _build_store(store)
    archive = restore_proof.archive_store(store, tmp_path / "store.tar")

    completed = _run_cli(archive)

    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert "verified: True" in completed.stdout


def test_cli_exits_non_zero_when_the_store_no_longer_verifies(tmp_path: Path) -> None:
    store = tmp_path / "store"
    built = _build_store(store)
    blob_path(built["source_digest"], root=store).write_bytes(built["raw"] + b"tampered")
    archive = restore_proof.archive_store(store, tmp_path / "store.tar")

    completed = _run_cli(archive)

    assert completed.returncode != 0
    assert "verified: False" in completed.stdout
