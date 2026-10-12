#!/usr/bin/env python3
"""Keep compact snapshots recoverable and bound to same-day corrections."""
from __future__ import annotations

import gzip
import hashlib
import re
from datetime import datetime, timezone
from pathlib import Path

import pytest

from scripts import gen_attestations as ga
from scripts.attestation_sets import discovery, snapshot_content, verify_set
from scripts.tests.test_attestations import fixture_root, write
from scripts.verify_attestation_binding import ContractError

DAY = "2026-08-15"
NOW = datetime(2026, 8, 15, 1, tzinfo=timezone.utc)


def test_snapshot_is_small_deterministic_and_correctable(tmp_path: Path) -> None:
    root, key = fixture_root(tmp_path)
    health_path = root / "health/latest.json"
    health = ga.load(health_path)
    health["datasets"][0]["evidence"] = "repeatable health evidence " * 40_000
    write(health_path, health)
    original_bytes = health_path.read_bytes()

    ga.generate(root, key, NOW)
    original_head = discovery(root)["current_head"]
    original_directory = root / "attestations" / DAY / "revisions" / original_head
    original_snapshot = original_directory / "health.json.gz"
    compressed = original_snapshot.read_bytes()
    assert compressed[3] & 0x08 == 0  # gzip contains no source filename
    assert compressed[4:8] == b"\x00" * 4  # gzip mtime is fixed
    assert len(compressed) * 10 < len(original_bytes)
    assert gzip.decompress(compressed) == original_bytes
    assert (root / "attestations" / DAY / "health.json.gz").read_bytes() == compressed
    ga.generate(root, key, NOW)
    assert original_snapshot.read_bytes() == compressed

    health["datasets"][0]["status"] = "degraded"
    write(health_path, health)
    corrected_bytes = health_path.read_bytes()
    ga.generate(root, key, datetime(2026, 8, 15, 2, tzinfo=timezone.utc))
    chain = discovery(root)
    correction_directory = root / chain["heads"][chain["current_head"]].rsplit("/", 1)[0]
    binding = ga.load(correction_directory / "binding.json")
    record = binding["payload"]["correction"]
    correction_snapshot = root / record["health_snapshot_ref"]
    assert record["health_snapshot_ref"].endswith("/health.json.gz")
    assert correction_snapshot.is_file()
    assert snapshot_content(correction_snapshot) == corrected_bytes
    assert hashlib.sha256(snapshot_content(correction_snapshot)).hexdigest() == record["health_sha256"]
    assert original_snapshot.read_bytes() == compressed
    verify_set(root, chain["heads"][chain["current_head"]])

    correction_snapshot.write_bytes(gzip.compress(b"wrong", mtime=0))
    with pytest.raises(ContractError, match="snapshot digest is invalid"):
        verify_set(root, chain["heads"][chain["current_head"]])


def test_legacy_raw_snapshot_still_verifies(tmp_path: Path) -> None:
    root, key = fixture_root(tmp_path)
    ga.generate(root, key, NOW)
    chain = discovery(root)
    day = root / "attestations" / DAY
    revision = day / "revisions" / chain["current_head"]
    for directory in (day, revision):
        compressed = directory / "health.json.gz"
        (directory / "health.json").write_bytes(gzip.decompress(compressed.read_bytes()))
        compressed.unlink()
    verify_set(root, chain["heads"][chain["current_head"]])
    verify_set(root, f"attestations/{DAY}/revisions/{chain['current_head']}/chain_head.json")


def test_attestation_day_byte_ceiling_refuses_prepared_day(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    root, key = fixture_root(tmp_path)
    monkeypatch.setenv("ATTESTATION_DAY_MAX_BYTES", "1")

    with pytest.raises(ga.AttestationDaySizeError) as error:
        ga.generate(root, key, NOW)

    match = re.fullmatch(
        rf"attestation day {DAY} is (\d+) bytes; ATTESTATION_DAY_MAX_BYTES limit is 1 bytes",
        str(error.value),
    )
    assert match is not None
    assert int(match[1]) > 1
    assert not (root / "attestations" / DAY).exists()
