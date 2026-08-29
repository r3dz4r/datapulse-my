from __future__ import annotations

import json
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path

from scripts import gen_attestations as ga
from scripts.tests.test_attestations import (
    fixture_rekor_reference,
    fixture_root,
    write,
)
from scripts.verify_attestation_plane_state import PlaneState, classify_plane


NOW = datetime(2026, 8, 15, 1, tzinfo=timezone.utc)
ROOT = Path(__file__).resolve().parents[2]


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_current_verified_rekor_plane_is_healthy(tmp_path: Path) -> None:
    root, key = fixture_root(tmp_path)
    rekor = fixture_rekor_reference(root, "rekor-fixture")
    ga.generate(root, key, NOW, rekor)

    result = classify_plane(root, now=NOW + timedelta(hours=1))

    assert result.state is PlaneState.HEALTHY


def test_stale_explicitly_unsigned_plane_is_signer_down(tmp_path: Path) -> None:
    root, key = fixture_root(tmp_path)
    ga.generate(root, key, NOW)

    result = classify_plane(root, now=NOW + timedelta(days=4))

    assert result.state is PlaneState.SIGNER_DOWN


def test_split_date_stale_unsigned_plane_is_signer_down(tmp_path: Path) -> None:
    root, key = fixture_root(tmp_path)
    ga.generate(root, key, NOW)
    first_day = NOW.date().isoformat()
    first_index = (root / f"attestations/{first_day}/index.json").read_bytes()
    first_head = (root / f"attestations/{first_day}/chain_head.json").read_bytes()

    second = NOW + timedelta(days=1)
    health = _load(root / "health/latest.json")
    health["checked_at"] = "2026-08-16T00:00:00Z"
    health["datasets"][0]["last_checked"] = health["checked_at"]
    write(root / "health/latest.json", health)
    ga.generate(root, key, second)
    (root / "attestations/latest/index.json").write_bytes(first_index)
    (root / "attestations/latest/chain_head.json").write_bytes(first_head)

    result = classify_plane(root, now=NOW + timedelta(days=4))

    assert result.state is PlaneState.SIGNER_DOWN


def test_truncated_chain_head_is_corrupt(tmp_path: Path) -> None:
    root, key = fixture_root(tmp_path)
    ga.generate(root, key, NOW)
    (root / "attestations/latest/chain_head.json").write_text(
        '{"schema":"datapulse/v1/daily-chain-head-envelope"',
        encoding="utf-8",
    )

    result = classify_plane(root, now=NOW + timedelta(days=4))

    assert result.state is PlaneState.CORRUPT


def test_unverified_signed_claim_is_corrupt(tmp_path: Path) -> None:
    root, key = fixture_root(tmp_path)
    ga.generate(root, key, NOW)
    binding_path = root / "attestations/latest/binding.json"
    binding = _load(binding_path)
    binding["claims"]["artifact_signed"] = True
    write(binding_path, binding)

    result = classify_plane(root, now=NOW + timedelta(days=4))

    assert result.state is PlaneState.CORRUPT


def test_cli_reports_signer_down_for_stale_unsigned_plane(tmp_path: Path) -> None:
    root, key = fixture_root(tmp_path)
    ga.generate(root, key, NOW)

    completed = subprocess.run(
        [
            "python3",
            "scripts/verify_attestation_plane_state.py",
            "--planedir",
            str(root),
            "--now",
            "2026-08-19T01:00:00Z",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    assert completed.stdout.strip() == "signer_down"
