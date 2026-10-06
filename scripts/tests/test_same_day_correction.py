#!/usr/bin/env python3
"""Hermetic contract B: corrected evidence is appended; originals are preserved."""
from __future__ import annotations

import base64
from collections.abc import Iterator
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import tempfile

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from scripts import gen_attestations as ga
from scripts.attestation_commit_back import commit_message_for_changed_paths
from scripts.tests.test_attestations import fixture_root, write
from scripts.verify_attestation_binding import ContractError, verify_contract
from scripts.verify_chain_linearity import ChainLinearityError, verify_chain_linearity


ROOT = Path(__file__).resolve().parents[2]
NOW = datetime(2026, 8, 15, 1, tzinfo=timezone.utc)
DAY = NOW.date().isoformat()


@pytest.fixture
def isolated_root(monkeypatch: pytest.MonkeyPatch) -> Iterator[tuple[Path, Path]]:
    def deny_network(*args: object, **kwargs: object) -> None:
        raise AssertionError("network is forbidden in the correction test")

    monkeypatch.setattr(socket, "socket", deny_network)
    monkeypatch.setenv("GIT_CEILING_DIRECTORIES", str(ROOT))
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", os.devnull)
    with tempfile.TemporaryDirectory(prefix=".same-day-test-", dir=ROOT) as directory:
        yield fixture_root(Path(directory))


def evidence_bytes(root: Path) -> dict[str, bytes]:
    return {path.relative_to(root).as_posix(): path.read_bytes()
            for path in (root / "attestations").rglob("*.json")}


def verify_binding(root: Path, moment: datetime = NOW) -> dict:
    # The real strict CLI, with no inherited signing configuration or fallback flags.
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts/verify_attestation_binding.py"),
         "--root", str(root), "--now", moment.isoformat()],
        cwd=root, text=True, capture_output=True,
        env={"PATH": "/usr/bin:/bin", "TMPDIR": str(root),
             "PYTHONDONTWRITEBYTECODE": "1"},
    )
    assert result.returncode == 0, f"binding exit {result.returncode}: {result.stdout}{result.stderr}"
    verified = json.loads(result.stdout)
    assert verified["freshness"]["status"] == "current"
    return verified


def test_unchanged_day_preserves_every_evidence_byte(isolated_root: tuple[Path, Path]) -> None:
    root, key = isolated_root
    ga.generate(root, key, NOW)
    original = evidence_bytes(root)
    manifest = (root / "datapulse.json").read_bytes()
    ga.generate(root, root / "unused-key.json", NOW + timedelta(hours=1))
    assert evidence_bytes(root) == original
    assert (root / "datapulse.json").read_bytes() == manifest
    verify_binding(root, NOW + timedelta(hours=1))


def test_same_day_correction_preserves_independently_verified_original(
    isolated_root: tuple[Path, Path],
) -> None:
    root, key = isolated_root
    ga.generate(root, key, NOW)
    verify_binding(root)
    original = evidence_bytes(root)
    original_health = (root / "health/latest.json").read_bytes()
    original_head = ga.load(root / "attestations/latest/chain_head.json")["chain_head"]
    public = Ed25519PublicKey.from_public_bytes(base64.b64decode(
        ga.load(root / "docs/.well-known/datapulse-probe-keys.json")["keys"][0]["public_key_base64"]
    ))

    health = ga.load(root / "health/latest.json")
    health["datasets"][0]["status"] = "stale"  # Exactly one input field changes.
    write(root / "health/latest.json", health)
    correction_time = NOW + timedelta(hours=1)
    ga.generate(root, key, correction_time)
    verified = verify_binding(root, correction_time)
    assert verified["health"]["artifact_sha256"] == ga.sha((root / "health/latest.json").read_bytes())
    index = ga.load(root / "attestations/latest/index.json")
    corrected = ga.load(root / index["attestations"]["sample"])
    assert corrected["payload"]["last_status"] == "stale"
    public.verify(base64.b64decode(corrected["signature_base64"]), ga.canonical(corrected["payload"]))
    head = ga.load(root / index["chain_head_ref"])
    assert head["chain_head"] != original_head
    assert head["payload"]["previous_chain_head"] == original_head
    assert verified["ed25519"]["chain_head"] == head["chain_head"]
    assert index["chain_head_ref"] != f"attestations/{DAY}/chain_head.json"
    binding = ga.load(root / index["binding_ref"])
    record = binding["payload"]["correction"]
    assert record == head["payload"]["correction"]
    assert record["original_chain_head"] == original_head
    assert record["supersedes_chain_head"] == original_head
    assert record["previous_health_sha256"] == ga.sha(original_health)
    assert (root / record["health_snapshot_ref"]).read_bytes() == (root / "health/latest.json").read_bytes()
    assert (root / f"attestations/{DAY}/health.json").read_bytes() == original_health
    assert verify_chain_linearity(root).chain_head == head["chain_head"]
    assert ga.load(root / "datapulse.json")["datasets"][0]["attestation_ref"] == index["attestations"]["sample"]

    for reference, body in original.items():
        if reference.startswith(f"attestations/{DAY}/"):
            assert (root / reference).read_bytes() == body
            envelope = json.loads(body)
            if "signature_base64" in envelope:
                public.verify(base64.b64decode(envelope["signature_base64"]), ga.canonical(envelope["payload"]))
    assert ga.load(root / "attestations/chain-index.json")["heads"][original_head] == f"attestations/{DAY}/chain_head.json"
    added = set(evidence_bytes(root)) - set(original)
    assert commit_message_for_changed_paths(added, DAY) is not None

    # Select preserved original bytes in an independent historical verification plane.
    archive = root / "original-plane"
    for reference, body in original.items():
        destination = archive / reference
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(body)
    (archive / "health").mkdir()
    (archive / "health/latest.json").write_bytes(original_health)
    shutil.copytree(root / "docs", archive / "docs")
    historical = verify_binding(archive)
    assert historical["ed25519"]["chain_head"] == original_head
    print("ORIGINAL: every preserved signature verifies; independent strict binding exit 0")

    corrected_bytes = evidence_bytes(root)
    ga.generate(root, key, correction_time + timedelta(minutes=1))
    assert evidence_bytes(root) == corrected_bytes
    ga.generate(root, key, NOW + timedelta(days=1))
    verify_binding(root, NOW + timedelta(days=1))
    assert ga.load(root / "attestations/latest/chain_head.json")["payload"]["previous_chain_head"] == head["chain_head"]


def corrected_root(root: Path, key: Path) -> dict:
    ga.generate(root, key, NOW)
    health = ga.load(root / "health/latest.json")
    health["datasets"][0]["status"] = "stale"
    write(root / "health/latest.json", health)
    ga.generate(root, key, NOW + timedelta(hours=1))
    return ga.load(root / "attestations/latest/index.json")


def test_multiple_corrections_and_restoring_original_input_append_in_order(
    isolated_root: tuple[Path, Path],
) -> None:
    root, key = isolated_root
    first = corrected_root(root, key)
    prior = ga.load(root / first["chain_head_ref"])["chain_head"]
    original_health = (root / f"attestations/{DAY}/health.json").read_bytes()
    for hour, status in ((3, "unreachable"), (4, "fresh")):
        health = ga.load(root / "health/latest.json")
        health["datasets"][0]["status"] = status
        write(root / "health/latest.json", health)
        before = evidence_bytes(root)
        moment = NOW + timedelta(hours=hour)
        ga.generate(root, key, moment)
        verified = verify_binding(root, moment)
        assert ga.load(root / verified["ed25519"]["chain_head_ref"])["payload"]["previous_chain_head"] == prior
        for ref, body in before.items():
            if ref.startswith(f"attestations/{DAY}/"):
                assert (root / ref).read_bytes() == body
        prior = verified["ed25519"]["chain_head"]
    assert (root / "health/latest.json").read_bytes() == original_health
    assert len(ga.load(root / "attestations/chain-index.json")["heads"]) == 4


def test_health_byte_change_without_row_change_still_has_signed_provenance(
    isolated_root: tuple[Path, Path],
) -> None:
    root, key = isolated_root
    ga.generate(root, key, NOW)
    original_head = ga.load(root / "attestations/latest/chain_head.json")["chain_head"]
    path = root / "health/latest.json"
    path.write_bytes(path.read_bytes() + b"\n")
    ga.generate(root, key, NOW + timedelta(hours=1))
    verified = verify_binding(root, NOW + timedelta(hours=1))
    assert verified["ed25519"]["chain_head"] != original_head
    assert verified["claims"] == {"artifact_signed": False, "rekor_witnessed": False,
                                  "source_truth_verified": False}
    with pytest.raises(ContractError, match="required Rekor"):
        verify_contract(root, now=NOW + timedelta(hours=1), require_rekor=True)


@pytest.mark.parametrize("kind", ["snapshot", "metadata", "rollback", "duplicate", "unsafe"])
def test_invalid_correction_fails_closed(isolated_root: tuple[Path, Path], kind: str) -> None:
    root, key = isolated_root
    index = corrected_root(root, key)
    if kind == "snapshot":
        (root / index["binding_ref"]).parent.joinpath("health.json").write_bytes(b"{}\n")
    elif kind == "metadata":
        head = ga.load(root / index["chain_head_ref"])
        head["payload"]["correction"]["original_chain_head"] = "0" * 64
        write(root / index["chain_head_ref"], head)
    elif kind == "rollback":
        for filename in ("binding.json", "chain_head.json", "index.json", "scores.json"):
            shutil.copy2(root / f"attestations/{DAY}/{filename}", root / f"attestations/latest/{filename}")
    else:
        chain = ga.load(root / "attestations/chain-index.json")
        chain["heads"]["f" * 64] = (index["chain_head_ref"] if kind == "duplicate"
                                     else f"attestations/{DAY}/revisions/../../chain_head.json")
        write(root / "attestations/chain-index.json", chain)
    with pytest.raises(ContractError):
        verify_contract(root, now=NOW + timedelta(hours=2))
    if kind == "rollback":
        with pytest.raises(ChainLinearityError):
            verify_chain_linearity(root)
        ga.generate(root, key, NOW + timedelta(hours=2))
        verify_binding(root, NOW + timedelta(hours=2))
    else:
        before = evidence_bytes(root)
        with pytest.raises(ValueError, match="corrupt or inconsistent"):
            ga.generate(root, key, NOW + timedelta(hours=2))
        assert evidence_bytes(root) == before


def test_wrapper_appends_correction_with_real_generator(isolated_root: tuple[Path, Path]) -> None:
    root, key = isolated_root
    now = datetime.now(timezone.utc).replace(microsecond=0)
    health = ga.load(root / "health/latest.json")
    health["checked_at"] = health["datasets"][0]["last_checked"] = now.isoformat()
    write(root / "health/latest.json", health)
    registry_path = root / "docs/.well-known/datapulse-probe-keys.json"
    registry = ga.load(registry_path)
    registry["keys"][0]["not_before"] = (now - timedelta(days=1)).isoformat()
    registry["keys"][0]["not_after"] = (now + timedelta(days=2)).isoformat()
    write(registry_path, registry)
    for name in ("refresh_chain_head.sh", "gen_attestations.py", "verify_attestation_binding.py"):
        destination = root / "scripts" / name
        destination.parent.mkdir(exist_ok=True)
        shutil.copy2(ROOT / "scripts" / name, destination)
    env = {"PATH": f"{Path(sys.executable).parent}:/usr/bin:/bin", "TMPDIR": str(root),
           "PYTHONDONTWRITEBYTECODE": "1", "GIT_CEILING_DIRECTORIES": str(ROOT),
           "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull}
    def refresh() -> None:
        result = subprocess.run(["bash", str(root / "scripts/refresh_chain_head.sh"), str(key)],
                                cwd=root, env=env, text=True, capture_output=True)
        assert result.returncode == 0, result.stdout + result.stderr
    refresh()
    original = evidence_bytes(root)
    health["datasets"][0]["status"] = "stale"
    write(root / "health/latest.json", health)
    refresh()
    moment = datetime.now(timezone.utc) + timedelta(seconds=1)
    verified = verify_binding(root, moment)
    assert "/revisions/" in verified["ed25519"]["chain_head_ref"]
    for ref, body in original.items():
        if ref.startswith(f"attestations/{now.date().isoformat()}/"):
            assert (root / ref).read_bytes() == body
    assert (root / ".attestations/chain_head.json").read_bytes() == (root / "attestations/latest/chain_head.json").read_bytes()
    corrected = evidence_bytes(root)
    refresh()
    assert evidence_bytes(root) == corrected
