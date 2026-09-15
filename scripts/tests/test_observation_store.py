"""Tests pinning the Phase 2 observation store's layout, limits, and authority model."""

from __future__ import annotations

import json
import re
import shutil
import sys
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
from observation_store import (  # noqa: E402
    DigestFormatError,
    EnvelopePlacementError,
    ObjectNotFoundError,
    PayloadTooLargeError,
    blob_path,
    canonical_json,
    ensure_index,
    global_limits,
    list_observations,
    put_blob,
    put_envelope,
    put_normalized,
    put_policy,
    read_blob,
    read_normalized,
    rebuild_index_from_envelopes,
    upsert_observation,
    write_manifest,
)

DIGEST_FORM = re.compile(r"^sha256:[0-9a-f]{64}$")


def _file_count(root: Path) -> int:
    return sum(1 for candidate in root.rglob("*") if candidate.is_file())


def _envelope(dataset_id: str, observation_id: str, observed_at: str) -> dict[str, Any]:
    return {
        "schema": "historical-observation/v2",
        "dataset_id": dataset_id,
        "observation_id": observation_id,
        "observed_at": observed_at,
    }


def test_put_blob_is_idempotent_and_never_rewrites_existing_file(tmp_path: Path) -> None:
    """Protects the evidence value of the original blob's timestamp: identical bytes are a no-op."""
    data = b"identical source bytes, written twice"
    first_digest = put_blob(data, root=tmp_path)
    path = blob_path(first_digest, root=tmp_path)
    stat_before = path.stat()
    second_digest = put_blob(data, root=tmp_path)
    stat_after = path.stat()
    assert first_digest == second_digest
    # A rewrite would go through mkstemp + os.replace: new inode, new mtime.
    assert stat_after.st_ino == stat_before.st_ino
    assert stat_after.st_mtime_ns == stat_before.st_mtime_ns


def test_digest_form_and_blob_prefix_directory(tmp_path: Path) -> None:
    """Protects the digest convention: sha256:<64 lowercase hex>, filed under its first two hex."""
    data = b"layout pinning bytes"
    digest = put_blob(data, root=tmp_path)
    assert DIGEST_FORM.fullmatch(digest)
    hexdigest = digest.removeprefix("sha256:")
    path = blob_path(digest, root=tmp_path)
    assert path.name == f"{hexdigest}.raw"
    assert path.parent.name == hexdigest[:2]
    assert path.parent.parent.name == "sha256"
    assert path.parent.parent.parent.name == "blobs"
    assert path.parent.parent.parent.parent == tmp_path


def test_read_blob_round_trips_and_rejects_bad_digests(tmp_path: Path) -> None:
    """Protects retrieval integrity: bytes come back exactly, and bad digests fail typed."""
    data = b"round trip payload"
    digest = put_blob(data, root=tmp_path)
    assert read_blob(digest, root=tmp_path) == data
    absent = "sha256:" + ("0" * 64)
    with pytest.raises(ObjectNotFoundError):
        read_blob(absent, root=tmp_path)
    with pytest.raises(DigestFormatError):
        read_blob("deadbeef", root=tmp_path)
    with pytest.raises(DigestFormatError):
        read_blob("sha256:" + ("a" * 63), root=tmp_path)


def test_oversized_raw_payload_is_refused_and_writes_nothing(tmp_path: Path) -> None:
    """Protects the bounded-store guarantee: one byte over the cap writes no file at all."""
    put_blob(b"small blob that stays", root=tmp_path)
    files_before = _file_count(tmp_path)
    limit = global_limits()["max_raw_bytes"]
    oversized = b"\x00" * (limit + 1)
    with pytest.raises(PayloadTooLargeError):
        put_blob(oversized, root=tmp_path)
    assert _file_count(tmp_path) == files_before


def test_put_normalized_is_byte_stable_and_compact(tmp_path: Path) -> None:
    """Protects canonical-form stability: key order never changes digest or stored bytes."""
    first = put_normalized({"b": 2, "a": 1}, root=tmp_path)
    second = put_normalized({"a": 1, "b": 2}, root=tmp_path)
    assert first == second
    stored = read_normalized(first, root=tmp_path)
    assert stored == b'{"a":1,"b":2}'
    assert b": " not in stored
    assert b", " not in stored
    nested_first = put_normalized({"z": {"y": 2, "x": 1}}, root=tmp_path)
    nested_second = put_normalized({"z": {"x": 1, "y": 2}}, root=tmp_path)
    assert nested_first == nested_second
    assert read_normalized(nested_first, root=tmp_path) == canonical_json({"z": {"x": 1, "y": 2}})


def test_put_envelope_placement_and_identity_validation(tmp_path: Path) -> None:
    """Protects the envelope path contract and the identity checks that keep it safe."""
    envelope = _envelope("fuelprice", "obs-fuelprice-20260913", "2026-09-13T00:06:42Z")
    path = put_envelope("fuelprice", "obs-fuelprice-20260913", envelope, root=tmp_path)
    assert path == tmp_path / "envelopes" / "fuelprice" / "2026" / "09" / "obs-fuelprice-20260913.json"
    assert json.loads(path.read_text(encoding="utf-8")) == envelope
    # A non-UTC offset must file by the UTC instant, not the wall clock.
    offset = _envelope("fuelprice", "obs-fuelprice-20260101", "2026-01-01T00:30:00+02:00")
    offset_path = put_envelope("fuelprice", "obs-fuelprice-20260101", offset, root=tmp_path)
    assert offset_path == tmp_path / "envelopes" / "fuelprice" / "2025" / "12" / "obs-fuelprice-20260101.json"
    for bad_observation_id in ("fuelprice-20260913", "obs-UPPERCASE"):
        with pytest.raises(EnvelopePlacementError):
            put_envelope(
                "fuelprice",
                bad_observation_id,
                _envelope("fuelprice", bad_observation_id, "2026-09-13T00:06:42Z"),
                root=tmp_path,
            )
    for bad_dataset_id in ("datasets/fuelprice", "../escape", "datasets\\fuelprice", ".."):
        with pytest.raises(EnvelopePlacementError):
            put_envelope(
                bad_dataset_id,
                "obs-any-observation",
                _envelope(bad_dataset_id, "obs-any-observation", "2026-09-13T00:06:42Z"),
                root=tmp_path,
            )


def test_index_newest_first_and_rebuild_recovers_every_envelope(tmp_path: Path) -> None:
    """Protects the authority model: envelopes, not the index, are the record (P1 and P2)."""
    moments = {
        "obs-newest": "2026-09-13T00:06:42Z",
        "obs-middle": "2026-09-01T12:00:00Z",
        "obs-oldest": "2026-08-15T00:00:00Z",
    }
    for observation_id, observed_at in moments.items():
        envelope = _envelope("fuelprice", observation_id, observed_at)
        path = put_envelope("fuelprice", observation_id, envelope, root=tmp_path)
        if observation_id != "obs-middle":
            upsert_observation("fuelprice", observation_id, observed_at, path, root=tmp_path)
    rows_before = list_observations("fuelprice", root=tmp_path)
    assert [row["observation_id"] for row in rows_before] == ["obs-newest", "obs-oldest"]
    # P1: a misfiled envelope without its own observation_id must be refused, not papered over.
    orphan = {"schema": "historical-observation/v2", "dataset_id": "misfiled", "observed_at": "2026-09-13T00:06:42Z"}
    put_envelope("misfiled", "obs-orphan-1", orphan, root=tmp_path)
    (tmp_path / "indexes" / "observations.sqlite").unlink()
    with pytest.raises(EnvelopePlacementError, match="observation_id"):
        rebuild_index_from_envelopes(root=tmp_path)
    shutil.rmtree(tmp_path / "envelopes" / "misfiled")
    # P2: rebuild recovers every envelope on disk, including one never upserted.
    on_disk = sum(
        1 for candidate in (tmp_path / "envelopes").rglob("*.json") if candidate.is_file()
    )
    assert rebuild_index_from_envelopes(root=tmp_path) == on_disk == 3
    rows_after = list_observations("fuelprice", root=tmp_path)
    assert [row["observation_id"] for row in rows_after] == ["obs-newest", "obs-middle", "obs-oldest"]
    assert [row for row in rows_after if row["observation_id"] != "obs-middle"] == rows_before


def test_no_temporary_files_remain_after_successful_writes(tmp_path: Path) -> None:
    """Protects atomicity's other half: no *.tmp survivor is ever left under the root."""
    put_blob(b"raw bytes", root=tmp_path)
    put_normalized({"a": 1}, root=tmp_path)
    envelope = _envelope("fuelprice", "obs-fuelprice-20260913", "2026-09-13T00:06:42Z")
    envelope_path = put_envelope("fuelprice", "obs-fuelprice-20260913", envelope, root=tmp_path)
    upsert_observation("fuelprice", "obs-fuelprice-20260913", "2026-09-13T00:06:42Z", envelope_path, root=tmp_path)
    ensure_index(root=tmp_path)
    put_policy("fuelprice", {"mode": "full_vintage"}, root=tmp_path)
    write_manifest("2026-09-15", {"observations": 1}, root=tmp_path)
    rebuild_index_from_envelopes(root=tmp_path)
    strays = [
        candidate for candidate in tmp_path.rglob("*") if candidate.is_file() and candidate.name.endswith(".tmp")
    ]
    assert strays == []


def test_store_mandates_directory_and_file_modes(tmp_path: Path) -> None:
    """Protects the permission posture: directories 750, files 640, umask-proof."""
    envelope = _envelope("fuelprice", "obs-fuelprice-20260913", "2026-09-13T00:06:42Z")
    put_blob(b"mode pinning bytes", root=tmp_path)
    put_normalized({"mode": 1}, root=tmp_path)
    put_envelope("fuelprice", "obs-fuelprice-20260913", envelope, root=tmp_path)
    put_policy("fuelprice", {"mode": "full_vintage"}, root=tmp_path)
    write_manifest("2026-09-15", {"mode": "checked"}, root=tmp_path)
    ensure_index(root=tmp_path)
    for directory in (entry for entry in tmp_path.rglob("*") if entry.is_dir()):
        assert directory.stat().st_mode & 0o777 == 0o750, directory
    for file in (entry for entry in tmp_path.rglob("*") if entry.is_file()):
        assert file.stat().st_mode & 0o777 == 0o640, file
