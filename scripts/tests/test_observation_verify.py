"""Behavioural tests for the observation-age fact in ``observation_verify``.

The age is observational, never gating: a large age is reported and the run
still exits 0. Without ``--health`` the artifact's ``checked_at`` is
unavailable, so the fact degrades to ``unchecked`` exactly as
``health_binding`` does. The age is computed only from the artifact's
``checked_at``; ``cycle_date`` is date-only and is never used to manufacture a
duration. Every key here is an ephemeral fixture; the operator key and registry
are never read.
"""

from __future__ import annotations

import base64
import json
import socket
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, NoEncryption, PrivateFormat, PublicFormat

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts import observation_receipt as signer  # noqa: E402
from scripts import observation_verify as verifier  # noqa: E402

NOW = datetime(2026, 9, 26, 2, 54, 0, tzinfo=timezone.utc)
OBSERVED_AT = "2026-09-26T02:54:00Z"
KEY_ID = "ed25519-age-test"


def _write(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def _keypair() -> tuple[Ed25519PrivateKey, str, str]:
    private = Ed25519PrivateKey.generate()
    raw = private.private_bytes(Encoding.Raw, PrivateFormat.Raw, NoEncryption())
    public = private.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
    return private, base64.b64encode(raw).decode("ascii"), base64.b64encode(public).decode("ascii")


def _health_document(checked_at: str, statuses: tuple[str, ...] = ("fresh", "fresh", "stale")) -> dict[str, Any]:
    return {
        "schema": "datapulse/v0.4/dataset-health",
        "checked_at": checked_at,
        "_trust_summary": {},
        "datasets": [
            {"dataset_id": f"dataset-{index}", "status": status, "last_checked": checked_at}
            for index, status in enumerate(statuses)
        ],
    }


def _prepare(tmp_path: Path, *, checked_at: str) -> dict[str, Any]:
    """Build ephemeral keys and one signed receipt at ``observed_at == NOW``.

    The fixture shape (key file, registry, health artifact, signed day file) is
    copied from ``test_observation_receipt.py`` so the age is exercised against
    the same receipt contract, not a hand-assembled stand-in.
    """
    _, private_b64, public_b64 = _keypair()
    key_path = tmp_path / "keys/observation.json"
    registry_path = tmp_path / "keys/registry.json"
    health_path = tmp_path / "health/latest.json"
    _write(
        key_path,
        {
            "schema": "datapulse/v1/private-probe-key",
            "key_id": KEY_ID,
            "private_key_base64": private_b64,
            "public_key_base64": public_b64,
            "created_at": "2026-01-01T00:00:00Z",
        },
    )
    _write(
        registry_path,
        {
            "schema": "datapulse/v2/probe-key-registry",
            "version": 2,
            "keys": [
                {
                    "key_id": KEY_ID,
                    "scope": "observation-receipts (test fixture)",
                    "algorithm": "Ed25519",
                    "public_key_base64": public_b64,
                    "created_at": "2026-01-01T00:00:00Z",
                    "not_before": "2026-01-01T00:00:00Z",
                    "not_after": "2027-01-01T00:00:00Z",
                    "status": "active",
                    "supersedes": None,
                    "compromised_at": None,
                }
            ],
        },
    )
    _write(health_path, _health_document(checked_at))
    output_root = tmp_path / "observation"
    summary = signer.sign_observation(
        output_root=output_root,
        health_path=health_path,
        methodology_path=tmp_path / "health/methodology.json",
        key_path=key_path,
        registry_path=registry_path,
        now=NOW,
    )
    day_path = Path(summary["receipt_path"])
    return {
        "key_id": KEY_ID,
        "private_b64": private_b64,
        "health_path": health_path,
        "registry_path": registry_path,
        "output_root": output_root,
        "day_path": day_path,
        "receipt_id": summary["receipt_id"],
        "health": json.loads(health_path.read_text(encoding="utf-8")),
        "registry": json.loads(registry_path.read_text(encoding="utf-8")),
        "day_document": json.loads(day_path.read_text(encoding="utf-8")),
    }


def _verify_args(environment: dict[str, Any], *, health: Path | None = None) -> list[str]:
    args = [
        "--day-file",
        str(environment["day_path"]),
        "--receipt-id",
        environment["receipt_id"],
        "--registry",
        str(environment["registry_path"]),
    ]
    if health is not None:
        args += ["--health", str(health)]
    return args


def test_age_fact_is_present_in_facts_and_printed(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The exact ``observed_at - checked_at`` duration appears in both surfaces."""
    environment = _prepare(tmp_path, checked_at="2026-09-26T02:53:56Z")
    expected = (
        "4s (observed_at 2026-09-26T02:54:00Z "
        "minus artifact checked_at 2026-09-26T02:53:56Z)"
    )
    receipt = environment["day_document"]["receipts"][0]
    facts = verifier.checked_facts(
        receipt,
        environment["registry"],
        linkage_checked=True,
        binding_checked=True,
        health=environment["health"],
    )
    assert facts["observation_age"] == expected

    exit_code = verifier.main(_verify_args(environment, health=environment["health_path"]))
    captured = capsys.readouterr()
    assert exit_code == 0
    assert f"  observation_age: {expected}" in captured.out
    assert "artifact_claims: verified" in captured.out


@pytest.mark.parametrize(
    ("checked_at", "expected_age"),
    [
        pytest.param("2026-09-26T02:53:56Z", "4s", id="seconds"),
        pytest.param("2026-09-26T02:52:30Z", "1m 30s", id="minutes"),
        pytest.param("2026-09-26T00:54:00Z", "2h 0m 0s", id="hours"),
        pytest.param("2026-09-25T02:54:00Z", "1d 0h 0m 0s", id="day"),
    ],
)
def test_age_equals_observed_at_minus_checked_at(
    tmp_path: Path, checked_at: str, expected_age: str
) -> None:
    """The reported age is the checked_at distance, not distance from midnight.

    ``cycle_date`` for every case is the artifact's date, so a subtraction of
    that date from ``observed_at`` would produce a different, fabricated number.
    """
    environment = _prepare(tmp_path, checked_at=checked_at)
    receipt = environment["day_document"]["receipts"][0]
    age = verifier.checked_facts(
        receipt,
        environment["registry"],
        linkage_checked=False,
        binding_checked=True,
        health=environment["health"],
    )["observation_age"]
    assert age == (
        f"{expected_age} (observed_at {OBSERVED_AT} minus artifact checked_at {checked_at})"
    )
    assert "cycle_date" not in age


def test_without_health_age_is_unchecked_and_exit_zero(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """No artifact means no timestamp: the fact degrades, the run still passes."""
    environment = _prepare(tmp_path, checked_at="2026-09-26T02:53:56Z")
    exit_code = verifier.main(_verify_args(environment))
    captured = capsys.readouterr()
    assert exit_code == 0
    assert captured.err == ""
    assert "  observation_age: unchecked (reason: no --health artifact was supplied)" in captured.out
    assert "health_binding: unchecked" in captured.out
    # The existing degradation line for artifact claims is untouched.
    assert "artifact_claims: NOT verified (reason: no --health artifact was supplied)" in captured.out


def test_large_age_is_reported_and_still_exits_zero(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A ten-day-old artifact is reported in full and never gated on."""
    environment = _prepare(tmp_path, checked_at="2026-09-16T02:53:56Z")
    expected = (
        "10d 0h 0m 4s (observed_at 2026-09-26T02:54:00Z "
        "minus artifact checked_at 2026-09-16T02:53:56Z)"
    )
    exit_code = verifier.main(_verify_args(environment, health=environment["health_path"]))
    captured = capsys.readouterr()
    assert exit_code == 0
    assert f"  observation_age: {expected}" in captured.out
    assert "signature: verified" in captured.out


def test_existing_quiet_and_failure_paths_keep_their_exit_codes(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The additive fact changes neither a passing nor a failing exit code."""
    environment = _prepare(tmp_path, checked_at="2026-09-26T02:53:56Z")

    quiet = verifier.main(_verify_args(environment, health=environment["health_path"]))
    captured = capsys.readouterr()
    assert quiet == 0
    assert "receipt_identity: verified" in captured.out

    tampered = environment["day_document"]
    tampered["receipts"][0]["payload"]["dataset_count"] = 999
    environment["day_path"].write_text(json.dumps(tampered, indent=2) + "\n", encoding="utf-8")
    broken = verifier.main(_verify_args(environment, health=environment["health_path"]))
    captured = capsys.readouterr()
    assert broken == 1
    assert "receipt_id_mismatch" in captured.err


def test_age_never_opens_a_network_socket(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Computing the age stays entirely offline, like every other check."""
    environment = _prepare(tmp_path, checked_at="2026-09-26T02:53:56Z")

    def fail_network(*args: Any, **kwargs: Any) -> None:
        raise AssertionError("the verifier must not open a network socket")

    monkeypatch.setattr(socket, "create_connection", fail_network)
    exit_code = verifier.main(_verify_args(environment, health=environment["health_path"]))
    captured = capsys.readouterr()
    assert exit_code == 0
    assert "observation_age:" in captured.out
