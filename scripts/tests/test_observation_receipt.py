"""Tests pinning host-side observation receipts: per-day accumulation, chaining, idempotence, and offline verification.

Negative cases assert a specific named failure (tampered payload, wrong key,
expired/not-yet-valid key window, broken previous-receipt link, tampered day
entry) rather than skipping. Every fixture key is ephemeral; the real operator
key under ~/.hermes is never read here.
"""

from __future__ import annotations

import base64
import hashlib
import importlib.util
import json
import os
import socket
import subprocess
import sys
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
from cryptography.hazmat.primitives.serialization import Encoding, NoEncryption, PrivateFormat, PublicFormat

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts import observation_receipt as signer  # noqa: E402
from scripts import observation_verify as verifier  # noqa: E402

NOW = datetime(2026, 9, 18, 14, 40, 32, tzinfo=timezone.utc)
KEY_ID = "ed25519-test"


def _write(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _keypair() -> tuple[Ed25519PrivateKey, str, str]:
    private = Ed25519PrivateKey.generate()
    raw = private.private_bytes(Encoding.Raw, PrivateFormat.Raw, NoEncryption())
    public = private.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
    return private, base64.b64encode(raw).decode("ascii"), base64.b64encode(public).decode("ascii")


def _write_health(path: Path, *, checked_at: str = "2026-09-18T14:40:32Z", statuses: tuple[str, ...] = ("fresh", "fresh", "stale")) -> None:
    datasets = [
        {"dataset_id": f"dataset-{index}", "status": status, "last_checked": checked_at}
        for index, status in enumerate(statuses)
    ]
    _write(path, {"schema": "datapulse/v0.4/dataset-health", "checked_at": checked_at, "_trust_summary": {}, "datasets": datasets})


def _health_document(
    *,
    checked_at: str = "2026-09-18T14:40:32Z",
    statuses: tuple[str, ...] = ("fresh", "fresh", "stale"),
    heartbeat: str | None = None,
    trust_summary_extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a health artifact with an optionally stamped volatile heartbeat."""
    datasets = [
        {"dataset_id": f"dataset-{index}", "status": status, "last_checked": checked_at}
        for index, status in enumerate(statuses)
    ]
    trust_summary: dict[str, Any] = dict(trust_summary_extra or {})
    if heartbeat is not None:
        trust_summary["pipeline_heartbeat_at"] = heartbeat
    return {
        "schema": "datapulse/v0.4/dataset-health",
        "checked_at": checked_at,
        "_trust_summary": trust_summary,
        "datasets": datasets,
    }


@pytest.fixture
def environment(tmp_path: Path) -> dict[str, Any]:
    private, private_b64, public_b64 = _keypair()
    key_path = tmp_path / "keys/observation.json"
    registry_path = tmp_path / "keys/registry.json"
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
    health_path = tmp_path / "health/latest.json"
    _write_health(health_path)
    return {
        "private": private,
        "public_b64": public_b64,
        "key_id": KEY_ID,
        "key_path": key_path,
        "registry_path": registry_path,
        "health_path": health_path,
        "methodology_path": tmp_path / "health/methodology.json",
        "output_root": tmp_path / "observation",
        "tmp_path": tmp_path,
    }


def _sign(environment: dict[str, Any], now: datetime = NOW) -> dict[str, Any]:
    return signer.sign_observation(
        output_root=environment["output_root"],
        health_path=environment["health_path"],
        methodology_path=environment["methodology_path"],
        key_path=environment["key_path"],
        registry_path=environment["registry_path"],
        now=now,
    )


def _direct_receipt(
    environment: dict[str, Any],
    *,
    previous_receipt_id: str | None = None,
    observed_at: str = signer.format_time(NOW),
) -> dict[str, Any]:
    """Build and sign a payload directly, bypassing the signer's registry window checks."""
    health = signer.load_json(environment["health_path"], "health_artifact")
    binding = signer.health_binding(health)
    payload = signer.build_payload(
        binding=binding,
        observed_at=observed_at,
        key_id=environment["key_id"],
        sequence_number=1,
        previous_receipt_id=previous_receipt_id,
        policy=None,
        profile_version=signer.verification_profile_version(),
    )
    return signer.create_receipt(payload, environment["private"])


def _registry(environment: dict[str, Any]) -> dict[str, Any]:
    return _load(environment["registry_path"])


def _verify(environment: dict[str, Any], receipt: dict[str, Any], chain_head: dict[str, Any] | None = None) -> list[str]:
    return verifier.verify_receipt(
        receipt,
        registry=_registry(environment),
        chain_head=chain_head,
    )


def _day_document(environment: dict[str, Any], cycle_date: str = "2026-09-18") -> dict[str, Any]:
    return _load(environment["output_root"] / "days" / f"{cycle_date}.json")


def _receipt(environment: dict[str, Any], cycle_date: str = "2026-09-18", index: int = 0) -> dict[str, Any]:
    return _day_document(environment, cycle_date)["receipts"][index]


def _head(environment: dict[str, Any]) -> dict[str, Any]:
    return _load(environment["output_root"] / "chain_head.json")


def _payload_inputs(environment: dict[str, Any]) -> dict[str, Any]:
    """Return fixed build inputs suitable for byte-level payload comparisons."""
    return {
        "binding": signer.health_binding(signer.load_json(environment["health_path"], "health_artifact")),
        "observed_at": signer.format_time(NOW),
        "key_id": environment["key_id"],
        "sequence_number": 1,
        "previous_receipt_id": None,
        "policy": None,
        "profile_version": "fixed-profile-version",
        "artifact_commit": "a" * 40,
    }


def test_payload_without_observer_cycle_key_is_byte_identical_to_head(
    environment: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    """The opt-in setting must leave legacy payload bytes and shape untouched."""
    monkeypatch.delenv(signer.OBSERVER_CYCLE_KEY_FILE_ENV, raising=False)
    source = subprocess.run(
        ["git", "show", "HEAD:scripts/observation_receipt.py"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    spec = importlib.util.spec_from_loader("head_observation_receipt", loader=None)
    assert spec is not None
    head_signer = importlib.util.module_from_spec(spec)
    head_signer.__file__ = str(ROOT / "scripts" / "observation_receipt.py")
    exec(compile(source, "HEAD:scripts/observation_receipt.py", "exec"), head_signer.__dict__)

    inputs = _payload_inputs(environment)
    current = signer.canonical_bytes(signer.build_payload(**inputs))
    before = head_signer.canonical_bytes(head_signer.build_payload(**inputs))

    assert current == before
    assert "observer_attestation" not in signer.build_payload(**inputs)


def test_payload_includes_deterministic_verifiable_observer_attestation(
    environment: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    """The observer signs the canonical artifact-binding statement inside the builder."""
    monkeypatch.setenv(signer.OBSERVER_CYCLE_KEY_FILE_ENV, str(environment["key_path"]))
    inputs = _payload_inputs(environment)

    first = signer.build_payload(**inputs)
    second = signer.build_payload(**inputs)
    attestation = first["observer_attestation"]
    statement = {
        "artifact_commit": "a" * 40,
        "health_artifact_sha256": inputs["binding"]["health_artifact_sha256"],
        "dataset_count": inputs["binding"]["dataset_count"],
        "key_id": environment["key_id"],
    }
    registry_public = base64.b64decode(_registry(environment)["keys"][0]["public_key_base64"], validate=True)

    assert list(attestation) == ["key_id", "signature_base64", "signed_at", "statement_sha256"]
    assert attestation["key_id"] == environment["key_id"]
    assert attestation["signed_at"] == inputs["observed_at"]
    assert attestation["statement_sha256"] == hashlib.sha256(signer.canonical_bytes(statement)).hexdigest()
    Ed25519PublicKey.from_public_bytes(registry_public).verify(
        base64.b64decode(attestation["signature_base64"], validate=True), signer.canonical_bytes(statement)
    )
    assert signer.canonical_bytes(first) == signer.canonical_bytes(second)


def test_sign_then_verify_roundtrip(environment: dict[str, Any]) -> None:
    summary = _sign(environment)
    receipt = _receipt(environment)
    day_document = _day_document(environment)
    head = _head(environment)

    assert summary["status"] == "signed"
    assert summary["sequence_number"] == 1
    assert summary["previous_receipt_id"] is None
    assert day_document["schema"] == signer.DAY_SCHEMA
    assert day_document["cycle_date"] == "2026-09-18"
    assert receipt["payload"]["schema"] == signer.RECEIPT_SCHEMA
    assert receipt["payload"]["cycle_date"] == "2026-09-18"
    assert receipt["payload"]["dataset_count"] == 3
    assert receipt["payload"]["freshness_status_counts"] == {"fresh": 2, "stale": 1}
    assert receipt["payload"]["policy_version"] is None
    assert receipt["payload"]["previous_receipt_id"] is None
    assert receipt["payload"]["limitations"] == list(signer.LIMITATIONS)
    # verification_profile_version binds the proof to the signer's own bytes.
    assert receipt["payload"]["verification_profile_version"] == hashlib.sha256(signer.SIGNER_PATH.read_bytes()).hexdigest()
    # valid_until is exactly observed_at + 26 hours.
    observed = signer.parse_time(receipt["payload"]["observed_at"])
    assert signer.parse_time(receipt["payload"]["valid_until"]) == observed + timedelta(hours=26)
    # receipt_id is the canonical payload hash.
    assert receipt["receipt_id"] == hashlib.sha256(signer.canonical_bytes(receipt["payload"])).hexdigest()
    assert head["schema"] == signer.CHAIN_HEAD_SCHEMA
    assert head["sequence_number"] == 1
    assert head["last_receipt_id"] == receipt["receipt_id"]
    assert head["day_file"] == "days/2026-09-18.json"
    assert head["day_receipt_count"] == 1
    assert _verify(environment, receipt, head) == []


def test_second_receipt_links_to_first(environment: dict[str, Any]) -> None:
    first = _sign(environment)
    _write_health(environment["health_path"], checked_at="2026-09-19T14:40:32Z", statuses=("fresh", "aging"))
    second = _sign(environment, now=NOW + timedelta(days=1))
    second_receipt = _receipt(environment, "2026-09-19")
    head = _head(environment)

    assert second["sequence_number"] == 2
    assert second["previous_receipt_id"] == first["receipt_id"]
    assert second_receipt["payload"]["previous_receipt_id"] == first["receipt_id"]
    assert head["sequence_number"] == 2
    assert head["last_receipt_id"] == second_receipt["receipt_id"]
    assert head["day_file"] == "days/2026-09-19.json"
    assert head["day_receipt_count"] == 1
    assert _verify(environment, second_receipt, head) == []


def test_verifier_rejects_tampered_payload(environment: dict[str, Any]) -> None:
    _sign(environment)
    receipt = _receipt(environment)
    receipt["payload"]["dataset_count"] = 999
    failures = _verify(environment, receipt, _head(environment))
    assert any(failure.startswith("receipt_id_mismatch") for failure in failures)
    assert any(failure.startswith("signature_invalid") for failure in failures)


def test_verifier_rejects_wrong_key(environment: dict[str, Any]) -> None:
    other_private, _, _ = _keypair()
    health = signer.load_json(environment["health_path"], "health_artifact")
    binding = signer.health_binding(health)
    payload = signer.build_payload(
        binding=binding,
        observed_at=signer.format_time(NOW),
        key_id=environment["key_id"],
        sequence_number=1,
        previous_receipt_id=None,
        policy=None,
        profile_version=signer.verification_profile_version(),
    )
    forged = signer.create_receipt(payload, other_private)
    failures = _verify(environment, forged, {"previous_receipt_id": None})
    assert any(failure.startswith("signature_invalid") for failure in failures)


def test_verifier_rejects_expired_key_window(environment: dict[str, Any]) -> None:
    registry = _load(environment["registry_path"])
    registry["keys"][0]["not_after"] = "2026-09-01T00:00:00Z"
    _write(environment["registry_path"], registry)
    failures = _verify(environment, _direct_receipt(environment), {"previous_receipt_id": None})
    assert any(failure.startswith("key_expired") for failure in failures)


def test_verifier_rejects_not_yet_valid_key_window(environment: dict[str, Any]) -> None:
    registry = _load(environment["registry_path"])
    registry["keys"][0]["not_before"] = "2027-01-01T00:00:00Z"
    registry["keys"][0]["not_after"] = "2028-01-01T00:00:00Z"
    _write(environment["registry_path"], registry)
    failures = _verify(environment, _direct_receipt(environment), {"previous_receipt_id": None})
    assert any(failure.startswith("key_not_yet_valid") for failure in failures)


def test_verifier_rejects_broken_previous_receipt_link(environment: dict[str, Any]) -> None:
    receipt = _direct_receipt(environment, previous_receipt_id="0" * 64)
    failures = _verify(environment, receipt, {"previous_receipt_id": "a" * 64})
    assert any(failure.startswith("previous_receipt_mismatch") for failure in failures)


def test_two_receipts_in_one_day_increment_and_link(environment: dict[str, Any]) -> None:
    first = _sign(environment)
    _write_health(environment["health_path"], checked_at="2026-09-18T15:40:32Z", statuses=("fresh", "aging"))
    second = _sign(environment, now=NOW + timedelta(hours=1))
    day_document = _day_document(environment)
    head = _head(environment)
    day_path = environment["output_root"] / "days/2026-09-18.json"

    assert len(day_document["receipts"]) == 2
    assert day_document["receipts"][0]["payload"]["sequence_number"] == 1
    assert day_document["receipts"][1]["payload"]["sequence_number"] == 2
    assert day_document["receipts"][1]["payload"]["previous_receipt_id"] == day_document["receipts"][0]["receipt_id"]
    assert (
        day_document["receipts"][0]["payload"]["health_artifact_sha256"]
        != day_document["receipts"][1]["payload"]["health_artifact_sha256"]
    )
    assert second["sequence_number"] == 2
    assert second["previous_receipt_id"] == first["receipt_id"]
    assert head["sequence_number"] == 2
    assert head["last_receipt_id"] == day_document["receipts"][1]["receipt_id"]
    assert head["day_file"] == "days/2026-09-18.json"
    assert head["day_receipt_count"] == 2

    for entry in day_document["receipts"]:
        failures, selected, linkage_checked = verifier.verify_day_receipt(
            day_document,
            registry=_registry(environment),
            receipt_id=entry["receipt_id"],
            chain_head=head,
            day_file_path=day_path,
        )
        assert failures == [], failures
        assert selected["receipt_id"] == entry["receipt_id"]
        assert linkage_checked is True


def test_resigning_same_artifact_reports_already_signed(
    environment: dict[str, Any], capsys: pytest.CaptureFixture[str]
) -> None:
    first = _sign(environment)
    day_path = environment["output_root"] / "days/2026-09-18.json"
    head_path = environment["output_root"] / "chain_head.json"
    day_before = day_path.read_bytes()
    head_before = head_path.read_bytes()

    # Python API: the steady five-minute case is a no-op, never an error.
    second = _sign(environment, now=NOW + timedelta(hours=1))
    assert second["status"] == "already_signed"
    assert second["receipt_id"] == first["receipt_id"]
    assert day_path.read_bytes() == day_before
    assert head_path.read_bytes() == head_before
    assert len(_day_document(environment)["receipts"]) == 1
    assert _head(environment)["sequence_number"] == 1

    # CLI: exit 0 and a line carrying 'already_signed' plus the receipt id.
    exit_code = signer.main(
        [
            "--output-root",
            str(environment["output_root"]),
            "--health",
            str(environment["health_path"]),
            "--methodology",
            str(environment["methodology_path"]),
            "--key",
            str(environment["key_path"]),
            "--registry",
            str(environment["registry_path"]),
            "--now",
            signer.format_time(NOW + timedelta(hours=2)),
        ]
    )
    captured = capsys.readouterr()
    assert exit_code == 0
    assert "already_signed" in captured.out
    assert first["receipt_id"] in captured.out
    # Still nothing was rewritten or advanced.
    assert day_path.read_bytes() == day_before
    assert head_path.read_bytes() == head_before


def test_second_day_rolls_sequence_and_links_via_chain_head(
    environment: dict[str, Any], tmp_path: Path
) -> None:
    first = _sign(environment)
    day1_head = _head(environment)
    prior_head_path = tmp_path / "prior-chain-head.json"
    _write(prior_head_path, day1_head)

    _write_health(environment["health_path"], checked_at="2026-09-19T14:40:32Z", statuses=("fresh", "aging"))
    second = _sign(environment, now=NOW + timedelta(days=1))
    day2_path = environment["output_root"] / "days/2026-09-19.json"
    day2 = _day_document(environment, "2026-09-19")
    head = _head(environment)

    assert second["sequence_number"] == 2
    assert day2["receipts"][0]["payload"]["previous_receipt_id"] == first["receipt_id"]
    # The rollover link came from the previous day's chain head.
    assert day2["receipts"][0]["payload"]["previous_receipt_id"] == day1_head["last_receipt_id"]
    assert head["sequence_number"] == 2
    assert head["last_receipt_id"] == day2["receipts"][0]["receipt_id"]
    assert head["day_file"] == "days/2026-09-19.json"
    assert head["day_receipt_count"] == 1

    # Against the prior day's head: the first entry must link back to it.
    failures, _, linkage_checked = verifier.verify_day_receipt(
        day2,
        registry=_registry(environment),
        receipt_id=second["receipt_id"],
        chain_head=day1_head,
        day_file_path=day2_path,
    )
    assert failures == [], failures
    assert linkage_checked is True
    # Against the current same-day head: the last entry must be its last receipt.
    failures, _, _ = verifier.verify_day_receipt(
        day2,
        registry=_registry(environment),
        receipt_id=second["receipt_id"],
        chain_head=head,
        day_file_path=day2_path,
    )
    assert failures == [], failures

    exit_code = verifier.main(
        [
            "--day-file",
            str(day2_path),
            "--receipt-id",
            second["receipt_id"],
            "--registry",
            str(environment["registry_path"]),
            "--chain-head",
            str(prior_head_path),
        ]
    )
    assert exit_code == 0


def test_tampered_middle_entry_fails_and_breaks_linkage(
    environment: dict[str, Any], capsys: pytest.CaptureFixture[str]
) -> None:
    states = (
        ("2026-09-18T14:00:00Z", ("fresh", "fresh", "stale")),
        ("2026-09-18T15:00:00Z", ("fresh", "aging", "stale")),
        ("2026-09-18T16:00:00Z", ("stale", "aging", "stale")),
    )
    for offset, (checked_at, statuses) in enumerate(states):
        _write_health(environment["health_path"], checked_at=checked_at, statuses=statuses)
        _sign(environment, now=NOW + timedelta(hours=offset))

    day_path = environment["output_root"] / "days/2026-09-18.json"
    day_document = _day_document(environment)
    assert len(day_document["receipts"]) == 3

    # Tamper the middle entry: its payload and, critically, its identity.
    day_document["receipts"][1]["payload"]["dataset_count"] = 999
    day_document["receipts"][1]["receipt_id"] = "0" * 64
    _write(day_path, day_document)
    head = _head(environment)

    # The tampered entry itself fails primary checks.
    failures, _, _ = verifier.verify_day_receipt(
        day_document,
        registry=_registry(environment),
        receipt_id="0" * 64,
        chain_head=head,
        day_file_path=day_path,
    )
    assert any(failure.startswith("receipt_id_mismatch") for failure in failures)
    assert any(failure.startswith("signature_invalid") for failure in failures)

    # The entry after it is intact on its own but reports broken linkage.
    entry_after = day_document["receipts"][2]["receipt_id"]
    failures_after, _, _ = verifier.verify_day_receipt(
        day_document,
        registry=_registry(environment),
        receipt_id=entry_after,
        chain_head=head,
        day_file_path=day_path,
    )
    assert any(failure.startswith("linkage_broken") for failure in failures_after), failures_after

    # The CLI names the linkage break and exits non-zero.
    exit_code = verifier.main(
        [
            "--day-file",
            str(day_path),
            "--receipt-id",
            entry_after,
            "--registry",
            str(environment["registry_path"]),
            "--chain-head",
            str(environment["output_root"] / "chain_head.json"),
        ]
    )
    captured = capsys.readouterr()
    assert exit_code == 1
    assert "linkage_broken" in captured.err


def test_cli_sign_and_verify_exit_codes(environment: dict[str, Any], capsys: pytest.CaptureFixture[str]) -> None:
    sign_exit = signer.main(
        [
            "--output-root",
            str(environment["output_root"]),
            "--health",
            str(environment["health_path"]),
            "--methodology",
            str(environment["methodology_path"]),
            "--key",
            str(environment["key_path"]),
            "--registry",
            str(environment["registry_path"]),
            "--now",
            signer.format_time(NOW),
            "--expected-key-id",
            KEY_ID,
        ]
    )
    assert sign_exit == 0
    summary = json.loads(capsys.readouterr().out)

    verify_exit = verifier.main(
        [
            "--day-file",
            summary["receipt_path"],
            "--receipt-id",
            summary["receipt_id"],
            "--registry",
            str(environment["registry_path"]),
            "--chain-head",
            summary["chain_head_path"],
        ]
    )
    assert verify_exit == 0
    captured = capsys.readouterr()
    assert (
        f"observation receipt verification completed: artifact claims NOT verified: {summary['receipt_path']}"
        in captured.out
    )
    # Keep the old phrase out of the contract so unchecked artifact claims cannot look like a general pass.
    assert "verification passed" not in captured.out
    assert "artifact_claims: NOT verified (reason: no --health artifact was supplied)" in captured.out
    # A supplied chain head is actually enforced, and the report says so.
    assert "linkage: checked" in captured.out
    assert f"key_id: {KEY_ID}" in captured.out


def test_verifier_enforces_adjacent_chain_head(
    environment: dict[str, Any], capsys: pytest.CaptureFixture[str]
) -> None:
    """A chain head found next to the day file is enforced, not silently ignored."""
    _sign(environment)
    head_path = environment["output_root"] / "chain_head.json"
    head = _load(head_path)
    head["last_receipt_id"] = "a" * 64
    _write(head_path, head)

    # No --chain-head: the verifier discovers the sibling head for itself.
    exit_code = verifier.main(
        [
            "--day-file",
            str(environment["output_root"] / "days/2026-09-18.json"),
            "--registry",
            str(environment["registry_path"]),
        ]
    )
    captured = capsys.readouterr()
    assert exit_code == 1
    assert "chain_head_mismatch" in captured.err
    assert "linkage: checked" in captured.out


def test_receipt_alone_passes_primary_checks_and_reports_linkage_unchecked(
    environment: dict[str, Any], tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A standalone receipt in a third party's hands verifies without any chain head.

    Only one entry is copied out; no chain_head.json is reachable from its
    directory or its parent. The primary checks must still gate success, and
    the output must admit that linkage was not checked.
    """
    _sign(environment)
    isolated = tmp_path / "isolated" / "nested"
    isolated.mkdir(parents=True)
    receipt_copy = isolated / "2026-09-18.json"
    _write(receipt_copy, _receipt(environment))

    exit_code = verifier.main(
        [
            "--receipt",
            str(receipt_copy),
            "--registry",
            str(environment["registry_path"]),
        ]
    )
    captured = capsys.readouterr()

    assert exit_code == 0
    assert captured.err == ""
    assert (
        f"observation receipt verification completed: artifact claims NOT verified: {receipt_copy}"
        in captured.out
    )
    # Keep the old phrase out of the contract so unchecked artifact claims cannot look like a general pass.
    assert "verification passed" not in captured.out
    assert "artifact_claims: NOT verified (reason: no --health artifact was supplied)" in captured.out
    assert "signature: verified" in captured.out
    assert "receipt_identity: verified" in captured.out
    assert "registry_validity_window: verified" in captured.out
    assert "linkage: unchecked" in captured.out
    # The stdout is itself evidence: identity, key id, and key window.
    receipt = _load(receipt_copy)
    assert f"receipt_id: {receipt['receipt_id']}" in captured.out
    assert f"key_id: {KEY_ID}" in captured.out
    assert "key_window:" in captured.out


def test_standalone_receipt_id_is_validated(
    environment: dict[str, Any], tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """--receipt-id is accepted with a standalone receipt and must match it."""
    first = _sign(environment)
    receipt_path = tmp_path / "standalone.json"
    _write(receipt_path, _receipt(environment))

    ok = verifier.main(
        [
            "--receipt",
            str(receipt_path),
            "--receipt-id",
            first["receipt_id"],
            "--registry",
            str(environment["registry_path"]),
        ]
    )
    assert ok == 0
    capsys.readouterr()

    bad = verifier.main(
        [
            "--receipt",
            str(receipt_path),
            "--receipt-id",
            "0" * 64,
            "--registry",
            str(environment["registry_path"]),
        ]
    )
    captured = capsys.readouterr()
    assert bad == 1
    assert "receipt_id_mismatch" in captured.err


def test_no_key_material_in_any_output(environment: dict[str, Any], capsys: pytest.CaptureFixture[str]) -> None:
    """Neither the private bytes nor the field name 'private_key' may leak out.

    Covers the day file, the chain head, and the verifier's stdout/stderr.
    """
    summary = _sign(environment)
    day_path = Path(summary["receipt_path"])
    head_path = Path(summary["chain_head_path"])
    private_b64 = _load(environment["key_path"])["private_key_base64"]

    exit_code = verifier.main(
        [
            "--day-file",
            str(day_path),
            "--receipt-id",
            summary["receipt_id"],
            "--registry",
            str(environment["registry_path"]),
            "--chain-head",
            str(head_path),
        ]
    )
    captured = capsys.readouterr()
    assert exit_code == 0

    normalize_exit = signer.main(["--normalize-digest", "--health", str(environment["health_path"])])
    normalize_captured = capsys.readouterr()
    assert normalize_exit == 0

    health_exit = verifier.main(
        [
            "--day-file",
            str(day_path),
            "--receipt-id",
            summary["receipt_id"],
            "--registry",
            str(environment["registry_path"]),
            "--chain-head",
            str(head_path),
            "--health",
            str(environment["health_path"]),
        ]
    )
    health_captured = capsys.readouterr()
    assert health_exit == 0

    outputs = {
        "day_file": day_path.read_text(encoding="utf-8"),
        "chain_head": head_path.read_text(encoding="utf-8"),
        "verifier_stdout": captured.out,
        "verifier_stderr": captured.err,
        "normalize_digest_stdout": normalize_captured.out,
        "normalize_digest_stderr": normalize_captured.err,
        "health_verifier_stdout": health_captured.out,
        "health_verifier_stderr": health_captured.err,
    }
    for label, text in outputs.items():
        assert private_b64 not in text, f"private key bytes leaked into {label}"
        assert "private_key" not in text, f"'private_key' appeared in {label}"


def test_cli_verify_names_failure_reason(environment: dict[str, Any], capsys: pytest.CaptureFixture[str]) -> None:
    summary = _sign(environment)
    day_path = Path(summary["receipt_path"])
    day_document = _load(day_path)
    day_document["receipts"][0]["payload"]["dataset_count"] = 42
    _write(day_path, day_document)

    exit_code = verifier.main(
        [
            "--day-file",
            str(day_path),
            "--receipt-id",
            summary["receipt_id"],
            "--registry",
            str(environment["registry_path"]),
            "--chain-head",
            summary["chain_head_path"],
        ]
    )
    captured = capsys.readouterr()
    assert exit_code == 1
    assert "receipt_id_mismatch" in captured.err


# ---------------------------------------------------------------------------
# Volatile-field normalization: bind the observation, not the liveness clock
# ---------------------------------------------------------------------------


def test_heartbeat_only_change_is_already_signed(
    environment: dict[str, Any], capsys: pytest.CaptureFixture[str]
) -> None:
    """Two artifacts differing only in pipeline_heartbeat_at share one digest."""
    first_document = _health_document(heartbeat="2026-09-18T14:40:00Z")
    _write(environment["health_path"], first_document)
    first = _sign(environment)
    first_digest = _receipt(environment)["payload"]["health_artifact_sha256"]

    second_document = _health_document(heartbeat="2026-09-18T14:45:00Z")
    # The two artifacts are byte-distinct but normalize to the same digest.
    assert signer.canonical_bytes(first_document) != signer.canonical_bytes(second_document)
    assert signer.normalized_health_digest(first_document) == signer.normalized_health_digest(second_document)
    _write(environment["health_path"], second_document)

    second = _sign(environment, now=NOW + timedelta(minutes=5))
    assert second["status"] == "already_signed"
    assert second["receipt_id"] == first["receipt_id"]
    day_document = _day_document(environment)
    assert len(day_document["receipts"]) == 1
    assert day_document["receipts"][0]["payload"]["health_artifact_sha256"] == first_digest

    # CLI: exit 0, reports already_signed, and writes nothing new.
    day_path = environment["output_root"] / "days/2026-09-18.json"
    before = day_path.read_bytes()
    exit_code = signer.main(
        [
            "--output-root",
            str(environment["output_root"]),
            "--health",
            str(environment["health_path"]),
            "--methodology",
            str(environment["methodology_path"]),
            "--key",
            str(environment["key_path"]),
            "--registry",
            str(environment["registry_path"]),
            "--now",
            signer.format_time(NOW + timedelta(minutes=10)),
        ]
    )
    captured = capsys.readouterr()
    assert exit_code == 0
    assert "already_signed" in captured.out
    assert day_path.read_bytes() == before
    assert len(_day_document(environment)["receipts"]) == 1


def test_other_field_change_changes_digest(environment: dict[str, Any]) -> None:
    """Every field except the volatile heartbeat still moves the digest."""
    heartbeat = "2026-09-18T14:40:00Z"
    baseline = _health_document(heartbeat=heartbeat)
    baseline_digest = signer.normalized_health_digest(baseline)

    # A different heartbeat alone does not move it.
    assert signer.normalized_health_digest(_health_document(heartbeat="2099-01-01T00:00:00Z")) == baseline_digest
    # A changed dataset status does.
    assert (
        signer.normalized_health_digest(_health_document(heartbeat=heartbeat, statuses=("fresh", "aging")))
        != baseline_digest
    )
    # A changed checked_at does.
    assert (
        signer.normalized_health_digest(_health_document(heartbeat=heartbeat, checked_at="2026-09-18T15:00:00Z"))
        != baseline_digest
    )
    # A sibling field inside _trust_summary does.
    assert (
        signer.normalized_health_digest(
            _health_document(heartbeat=heartbeat, trust_summary_extra={"pipeline_heartbeat_interval_seconds": 300})
        )
        != baseline_digest
    )
    # Removing only the heartbeat keeps (and hashes) the empty parent object.
    assert signer.normalize_health_artifact(_health_document())["_trust_summary"] == {}

    # A real change appends a second entry rather than reporting already_signed.
    _write(environment["health_path"], baseline)
    _sign(environment)
    _write(environment["health_path"], _health_document(heartbeat=heartbeat, statuses=("fresh", "aging")))
    second = _sign(environment, now=NOW + timedelta(minutes=5))
    assert second["status"] == "signed"
    assert len(_day_document(environment)["receipts"]) == 2


def test_normalize_digest_helper_reproduces_receipt(
    environment: dict[str, Any], capsys: pytest.CaptureFixture[str]
) -> None:
    """Only the served file and the receipt are needed to reproduce the digest."""
    _write(environment["health_path"], _health_document(heartbeat="2026-09-18T14:40:00Z"))
    _sign(environment)
    receipt = _receipt(environment)
    recorded = receipt["payload"]["health_artifact_sha256"]

    # The normalization statement is part of the signed payload.
    assert receipt["payload"]["normalization"] == signer.NORMALIZATION_NOTE
    assert receipt["receipt_id"] == hashlib.sha256(signer.canonical_bytes(receipt["payload"])).hexdigest()

    # Importable helper over the served artifact.
    artifact = signer.load_json(environment["health_path"], "health_artifact")
    assert signer.normalized_health_digest(artifact) == recorded

    # CLI helper prints exactly the recorded digest.
    exit_code = signer.main(["--normalize-digest", "--health", str(environment["health_path"])])
    captured = capsys.readouterr()
    assert exit_code == 0
    assert captured.err == ""
    assert captured.out.strip() == recorded


def test_verify_health_binding_pass_and_mismatch(
    environment: dict[str, Any], tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """--health reproduces the digest; a different artifact names the mismatch."""
    _write(environment["health_path"], _health_document(heartbeat="2026-09-18T14:40:00Z"))
    summary = _sign(environment)
    base_args = [
        "--day-file",
        summary["receipt_path"],
        "--receipt-id",
        summary["receipt_id"],
        "--registry",
        str(environment["registry_path"]),
        "--chain-head",
        summary["chain_head_path"],
    ]

    matching = verifier.main([*base_args, "--health", str(environment["health_path"])])
    captured = capsys.readouterr()
    assert matching == 0
    assert captured.err == ""
    assert "health_binding: checked" in captured.out

    mismatched_path = tmp_path / "mismatched-health.json"
    _write(
        mismatched_path,
        _health_document(heartbeat="2026-09-18T14:40:00Z", statuses=("fresh", "stale", "stale")),
    )
    mismatched = verifier.main([*base_args, "--health", str(mismatched_path)])
    captured = capsys.readouterr()
    assert mismatched == 1
    assert "health_artifact_mismatch" in captured.err
    # Both digests are named so the divergence is visible.
    declared = _receipt(environment)["payload"]["health_artifact_sha256"]
    reproduced = signer.normalized_health_digest(_load(mismatched_path))
    assert declared in captured.err
    assert reproduced in captured.err
    assert "health_binding: checked" in captured.out
    assert "artifact_claims: NOT verified (reason: artifact claim binding failed)" in captured.out


def test_verify_without_health_reports_binding_unchecked(
    environment: dict[str, Any], capsys: pytest.CaptureFixture[str]
) -> None:
    """Without --health the report admits the binding was not reproduced."""
    _write(environment["health_path"], _health_document(heartbeat="2026-09-18T14:40:00Z"))
    summary = _sign(environment)
    exit_code = verifier.main(
        [
            "--day-file",
            summary["receipt_path"],
            "--receipt-id",
            summary["receipt_id"],
            "--registry",
            str(environment["registry_path"]),
            "--chain-head",
            summary["chain_head_path"],
        ]
    )
    captured = capsys.readouterr()
    assert exit_code == 0
    assert captured.err == ""
    assert "health_binding: unchecked" in captured.out
    assert "artifact_claims: NOT verified (reason: no --health artifact was supplied)" in captured.out
    assert "signature: verified" in captured.out
    assert "receipt_identity: verified" in captured.out
    assert "registry_validity_window: verified" in captured.out
    assert "verification passed" not in captured.out


def test_require_health_binding_fails_when_health_was_not_supplied(
    environment: dict[str, Any], capsys: pytest.CaptureFixture[str]
) -> None:
    """Strict claim verification refuses a run that did not bind an artifact."""
    summary = _sign(environment)

    exit_code = verifier.main(
        [
            "--day-file",
            summary["receipt_path"],
            "--receipt-id",
            summary["receipt_id"],
            "--registry",
            str(environment["registry_path"]),
            "--chain-head",
            summary["chain_head_path"],
            "--require-health-binding",
        ]
    )
    captured = capsys.readouterr()
    assert exit_code == 1
    assert "health_binding: unchecked" in captured.out
    assert "artifact_claims: NOT verified" in captured.out
    assert "health_binding_required: artifact claim binding was required but not performed" in captured.err


# ---------------------------------------------------------------------------
# Health claim binding: the consumed counts must match the supplied artifact
# ---------------------------------------------------------------------------


def _claim_receipt(
    environment: dict[str, Any],
    *,
    binding: dict[str, Any] | None = None,
    dataset_count: Any = None,
    freshness_status_counts: Any = None,
) -> dict[str, Any]:
    """Sign a payload with a genuine digest but caller-supplied (possibly forged) claims.

    This deliberately bypasses the signer's own claim gate: the point is to model
    a receipt signed before that gate existed, or by a regressed signer, so the
    offline verifier is the only line of defence.
    """
    if binding is None:
        health = signer.load_json(environment["health_path"], "health_artifact")
        binding = signer.health_binding(health)
    else:
        binding = dict(binding)
    if dataset_count is not None:
        binding["dataset_count"] = dataset_count
    if freshness_status_counts is not None:
        binding["freshness_status_counts"] = freshness_status_counts
    payload = signer.build_payload(
        binding=binding,
        observed_at=signer.format_time(NOW),
        key_id=environment["key_id"],
        sequence_number=1,
        previous_receipt_id=None,
        policy=None,
        profile_version=signer.verification_profile_version(),
    )
    return signer.create_receipt(payload, environment["private"])


def _verify_with_health(environment: dict[str, Any], receipt: dict[str, Any]) -> list[str]:
    return verifier.verify_receipt(
        receipt,
        registry=_registry(environment),
        health=signer.load_json(environment["health_path"], "health_artifact"),
    )


def test_health_claim_binding_accepts_genuine_claims(environment: dict[str, Any]) -> None:
    """A genuine digest with the artifact's own counts still verifies cleanly."""
    _write(environment["health_path"], _health_document(heartbeat="2026-09-18T14:40:00Z"))
    _sign(environment)
    failures = _verify_with_health(environment, _receipt(environment))
    assert failures == []


def test_health_claim_binding_rejects_forged_dataset_count(environment: dict[str, Any]) -> None:
    """A correct digest does not excuse an invented dataset_count."""
    receipt = _claim_receipt(environment, dataset_count=999)
    failures = _verify_with_health(environment, receipt)
    assert failures == ["claim_mismatch: field=dataset_count claimed=999 derived=3"]


def test_health_claim_binding_rejects_forged_status_count(environment: dict[str, Any]) -> None:
    """One altered status bucket is a claim mismatch naming both maps."""
    receipt = _claim_receipt(environment, freshness_status_counts={"fresh": 1, "stale": 2})
    failures = _verify_with_health(environment, receipt)
    assert failures == [
        "claim_mismatch: field=freshness_status_counts claimed={'fresh': 1, 'stale': 2} "
        "derived={'fresh': 2, 'stale': 1}"
    ]


def test_health_claim_binding_rejects_extra_status_key(environment: dict[str, Any]) -> None:
    """An extra status key fails even when the other counts agree."""
    receipt = _claim_receipt(
        environment, freshness_status_counts={"fresh": 2, "stale": 1, "aging": 0}
    )
    failures = _verify_with_health(environment, receipt)
    assert failures == [
        "claim_mismatch: field=freshness_status_counts claimed={'fresh': 2, 'stale': 1, 'aging': 0} "
        "derived={'fresh': 2, 'stale': 1}"
    ]


def test_health_claim_binding_rejects_removed_status_key(environment: dict[str, Any]) -> None:
    """A removed status key fails even when the remaining counts agree."""
    receipt = _claim_receipt(environment, freshness_status_counts={"fresh": 3})
    failures = _verify_with_health(environment, receipt)
    assert failures == [
        "claim_mismatch: field=freshness_status_counts claimed={'fresh': 3} "
        "derived={'fresh': 2, 'stale': 1}"
    ]


def test_health_claim_binding_repr_exposes_wrong_type(environment: dict[str, Any]) -> None:
    """A string count must read as claimed='418', never claimed=418.

    The full verify path stops a string dataset_count earlier as a
    payload_field_type_invalid, so the helper is exercised directly to pin the
    repr-based formatting the claim message depends on.
    """
    _write_health(environment["health_path"], statuses=("fresh",) * 418)
    health = signer.load_json(environment["health_path"], "health_artifact")
    payload = {
        "health_artifact_sha256": signer.normalized_health_digest(health),
        "dataset_count": "418",
        "freshness_status_counts": {"fresh": 418},
    }
    failures = verifier._health_binding_failures(payload, health, environment["health_path"])
    assert failures == ["claim_mismatch: field=dataset_count claimed='418' derived=418"]
    assert "'418'" in failures[0]

    # The full path still fails, earlier, on the payload type; the claim binding
    # never silently accepts a wrong-typed claim.
    structured = _verify_with_health(environment, _claim_receipt(environment, dataset_count="418"))
    assert any(failure.startswith("payload_field_type_invalid") for failure in structured), structured


@pytest.mark.parametrize(
    "datasets",
    [
        pytest.param([], id="empty-array"),
        pytest.param([{"dataset_id": "a", "status": "fresh"}, "not-an-object"], id="non-object-row"),
        pytest.param([{"dataset_id": "", "status": "fresh"}], id="empty-dataset-id"),
        pytest.param([{"dataset_id": "a", "status": ""}], id="empty-status"),
        pytest.param([{"dataset_id": "a"}], id="missing-status"),
        pytest.param(
            [{"dataset_id": "a", "status": "fresh"}, {"dataset_id": "a", "status": "fresh"}],
            id="duplicate-dataset-id",
        ),
    ],
)
def test_claim_unverifiable_for_uncountable_rows(
    environment: dict[str, Any], tmp_path: Path, datasets: list[Any]
) -> None:
    """Rows that cannot be counted honestly are unverifiable, never a mismatch."""
    artifact = {
        "schema": "datapulse/v0.4/dataset-health",
        "checked_at": "2026-09-18T14:40:32Z",
        "_trust_summary": {},
        "datasets": datasets,
    }
    artifact_path = tmp_path / "uncountable-health.json"
    _write(artifact_path, artifact)
    binding = {
        "cycle_date": "2026-09-18",
        "dataset_count": 1,
        "freshness_status_counts": {"fresh": 1},
        "health_artifact_sha256": signer.normalized_health_digest(artifact),
    }
    receipt = _claim_receipt(environment, binding=binding)
    failures = verifier.verify_receipt(
        receipt,
        registry=_registry(environment),
        health=artifact,
        health_path=artifact_path,
    )
    assert failures == [
        "claim_unverifiable: health datasets cannot be counted "
        "(every row must be an object with a unique non-empty dataset_id and a non-empty string status)"
    ]
    assert not any(failure.startswith("claim_mismatch") for failure in failures), failures


def test_cli_forged_claim_exits_nonzero_with_binding_checked(
    environment: dict[str, Any], tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Through the CLI a forged count fails, names itself, and admits the binding ran."""
    receipt_path = tmp_path / "forged-count.json"
    _write(receipt_path, _claim_receipt(environment, dataset_count=999))

    exit_code = verifier.main(
        [
            "--receipt",
            str(receipt_path),
            "--registry",
            str(environment["registry_path"]),
            "--health",
            str(environment["health_path"]),
        ]
    )
    captured = capsys.readouterr()
    assert exit_code == 1
    assert "health_binding: checked" in captured.out
    assert "claim_mismatch: field=dataset_count claimed=999 derived=3" in captured.err


# ---------------------------------------------------------------------------
# Artifact binding by commit reference: the pointer is signed, not decorative
# ---------------------------------------------------------------------------


def _pointer_args(
    environment: dict[str, Any],
    *,
    artifact_commit: str | None,
    artifact_path: str | None = None,
) -> list[str]:
    """CLI args for a sign run, optionally carrying a commit pointer."""
    args = [
        "--output-root",
        str(environment["output_root"]),
        "--health",
        str(environment["health_path"]),
        "--methodology",
        str(environment["methodology_path"]),
        "--key",
        str(environment["key_path"]),
        "--registry",
        str(environment["registry_path"]),
        "--now",
        signer.format_time(NOW),
    ]
    if artifact_commit is not None:
        args += ["--artifact-commit", artifact_commit]
    if artifact_path is not None:
        args += ["--artifact-path", artifact_path]
    return args


def test_artifact_pointer_is_inside_signed_payload(
    environment: dict[str, Any], capsys: pytest.CaptureFixture[str]
) -> None:
    """Tampering artifact_commit alone breaks both the receipt id and signature."""
    commit = "a" * 40
    assert signer.main(_pointer_args(environment, artifact_commit=commit)) == 0
    capsys.readouterr()
    receipt = _receipt(environment)
    assert receipt["payload"]["artifact_commit"] == commit
    assert receipt["payload"]["artifact_path"] == signer.DEFAULT_ARTIFACT_PATH
    # Both fields are covered by the canonical payload hash.
    assert receipt["receipt_id"] == hashlib.sha256(signer.canonical_bytes(receipt["payload"])).hexdigest()

    receipt["payload"]["artifact_commit"] = "b" * 40
    failures = _verify(environment, receipt, _head(environment))
    assert any(failure.startswith("receipt_id_mismatch") for failure in failures), failures
    assert any(failure.startswith("signature_invalid") for failure in failures), failures


@pytest.mark.parametrize("bad_commit", ["abc", "A" * 40, "g" * 40, "1" * 39])
def test_sign_refuses_malformed_artifact_commit(
    environment: dict[str, Any], capsys: pytest.CaptureFixture[str], bad_commit: str
) -> None:
    """A short, uppercase, or non-hex pointer is refused, not silently stored."""
    exit_code = signer.main(_pointer_args(environment, artifact_commit=bad_commit))
    captured = capsys.readouterr()
    assert exit_code == 1
    assert "artifact_commit_malformed" in captured.err
    # Fail closed before touching the output tree.
    assert not (environment["output_root"] / "days").exists()


def test_verifier_prints_artifact_binding_pointer(
    environment: dict[str, Any], capsys: pytest.CaptureFixture[str]
) -> None:
    """The verifier echoes '<commit>@<path>' for a receipt that carries a pointer."""
    commit = "c" * 40
    assert signer.main(_pointer_args(environment, artifact_commit=commit, artifact_path="health/latest.json")) == 0
    summary = json.loads(capsys.readouterr().out)

    verify_exit = verifier.main(
        [
            "--day-file",
            summary["receipt_path"],
            "--receipt-id",
            summary["receipt_id"],
            "--registry",
            str(environment["registry_path"]),
            "--chain-head",
            summary["chain_head_path"],
            "--repo",
            "example-owner/example-repo",
        ]
    )
    captured = capsys.readouterr()
    assert verify_exit == 0
    assert f"artifact_binding: {commit}@health/latest.json" in captured.out
    assert (
        f"artifact_url: https://raw.githubusercontent.com/example-owner/example-repo/{commit}/health/latest.json "
        "(repository: supplied --repo)"
    ) in captured.out


def test_empty_artifact_commit_is_reported_absent_not_as_a_url(environment: dict[str, Any]) -> None:
    """An incomplete locator cannot produce a malformed retrieval instruction."""
    receipt = _direct_receipt(environment)
    payload = dict(receipt["payload"])
    payload["artifact_commit"] = ""
    payload["artifact_path"] = "health/latest.json"
    empty_locator_receipt = signer.create_receipt(payload, environment["private"])

    facts = verifier.checked_facts(
        empty_locator_receipt,
        _registry(environment),
        linkage_checked=False,
        repository="example-owner/example-repo",
    )
    assert facts["artifact_binding"] == "absent"
    assert facts["artifact_url"] is None


def test_mismatched_health_names_the_signed_artifact_url(
    environment: dict[str, Any], tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A moved served artifact points the verifier at the receipt's historical bytes."""
    commit = "d" * 40
    assert signer.main(_pointer_args(environment, artifact_commit=commit)) == 0
    summary = json.loads(capsys.readouterr().out)
    mismatched_path = tmp_path / "mismatched-health.json"
    _write(mismatched_path, _health_document(statuses=("fresh", "stale", "stale")))

    exit_code = verifier.main(
        [
            "--day-file",
            summary["receipt_path"],
            "--receipt-id",
            summary["receipt_id"],
            "--registry",
            str(environment["registry_path"]),
            "--chain-head",
            summary["chain_head_path"],
            "--health",
            str(mismatched_path),
            "--repo",
            "example-owner/example-repo",
        ]
    )
    captured = capsys.readouterr()
    assert exit_code == 1
    assert "health_artifact_mismatch" in captured.err
    assert "artifact_claims: NOT verified (reason: artifact claim binding failed)" in captured.out
    assert (
        f"receipt artifact URL: https://raw.githubusercontent.com/example-owner/example-repo/{commit}/health/latest.json"
    ) in captured.err


def test_default_verification_never_opens_a_network_socket(
    environment: dict[str, Any], monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Discoverability prints a locator but the offline verifier never fetches it."""
    summary = _sign(environment)

    def fail_network(*args: Any, **kwargs: Any) -> None:
        raise AssertionError("the default verifier must not open a network socket")

    monkeypatch.setattr(socket, "create_connection", fail_network)
    exit_code = verifier.main(
        [
            "--day-file",
            summary["receipt_path"],
            "--receipt-id",
            summary["receipt_id"],
            "--registry",
            str(environment["registry_path"]),
            "--chain-head",
            summary["chain_head_path"],
        ]
    )
    captured = capsys.readouterr()
    assert exit_code == 0
    assert "artifact_claims: NOT verified" in captured.out


def test_receipt_without_commit_reports_binding_absent(
    environment: dict[str, Any], capsys: pytest.CaptureFixture[str]
) -> None:
    """Omitting --artifact-commit records null and never implies a pointer exists."""
    assert signer.main(_pointer_args(environment, artifact_commit=None)) == 0
    summary = json.loads(capsys.readouterr().out)
    receipt = _receipt(environment)
    assert receipt["payload"]["artifact_commit"] is None
    assert receipt["payload"]["artifact_path"] is None

    verify_exit = verifier.main(
        [
            "--day-file",
            summary["receipt_path"],
            "--receipt-id",
            summary["receipt_id"],
            "--registry",
            str(environment["registry_path"]),
            "--chain-head",
            summary["chain_head_path"],
        ]
    )
    captured = capsys.readouterr()
    assert verify_exit == 0
    assert "artifact_binding: absent" in captured.out


def test_real_commit_round_trip_signs_offline_verifies(
    environment: dict[str, Any], tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Sign the on-disk artifact bound to HEAD; verify against that commit's bytes.

    The verifier stays offline: the caller extracts the bound bytes
    (``git show <sha>:health/latest.json``) and the existing ``--health`` digest
    check remains the binding proof.
    """
    head_sha = subprocess.run(
        ["git", "-C", str(ROOT), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    assert signer.ARTIFACT_COMMIT_PATTERN.fullmatch(head_sha) is not None

    extracted = tmp_path / "committed-health.json"
    extracted.write_bytes(
        subprocess.run(
            ["git", "-C", str(ROOT), "show", f"{head_sha}:health/latest.json"],
            check=True,
            capture_output=True,
        ).stdout
    )

    output_root = tmp_path / "roundtrip-observation"
    sign_exit = signer.main(
        [
            "--output-root",
            str(output_root),
            "--health",
            str(ROOT / "health/latest.json"),
            "--methodology",
            str(environment["methodology_path"]),
            "--key",
            str(environment["key_path"]),
            "--registry",
            str(environment["registry_path"]),
            "--now",
            signer.format_time(NOW),
            "--artifact-commit",
            head_sha,
            "--artifact-path",
            "health/latest.json",
        ]
    )
    assert sign_exit == 0
    summary = json.loads(capsys.readouterr().out)

    verify_exit = verifier.main(
        [
            "--day-file",
            summary["receipt_path"],
            "--receipt-id",
            summary["receipt_id"],
            "--registry",
            str(environment["registry_path"]),
            "--chain-head",
            summary["chain_head_path"],
            "--health",
            str(extracted),
        ]
    )
    captured = capsys.readouterr()
    assert verify_exit == 0
    assert captured.err == ""
    assert "health_binding: checked" in captured.out
    assert f"artifact_binding: {head_sha}@health/latest.json" in captured.out

    digest = signer.normalized_health_digest(signer.load_json(extracted, "health_artifact"))
    selected = json.loads(Path(summary["receipt_path"]).read_text(encoding="utf-8"))["receipts"][-1]
    assert selected["payload"]["health_artifact_sha256"] == digest
    print(f"round_trip_commit={head_sha} round_trip_digest={digest}")


# ---------------------------------------------------------------------------
# Socket signing: the observing process never holds key material
# ---------------------------------------------------------------------------


class _SignerStub:
    """A throwaway signer implementing the documented socket protocol.

    One request per connection, one newline-terminated JSON response, then the
    connection closes. The key is generated by the caller and exists only in
    this test; the real operator key and the real signer socket are never
    touched.
    """

    def __init__(
        self,
        path: Path,
        private: Ed25519PrivateKey,
        key_id: str,
        *,
        refuse_reason: str | None = None,
    ) -> None:
        self.path = path
        self.private = private
        self.key_id = key_id
        self.refuse_reason = refuse_reason
        self.requests: list[dict[str, Any]] = []
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._server: socket.socket | None = None

    def __enter__(self) -> "_SignerStub":
        server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        server.bind(os.fspath(self.path))
        server.listen(8)
        self._server = server
        self._thread = threading.Thread(target=self._serve, daemon=True)
        self._thread.start()
        return self

    def __exit__(self, *_exc: object) -> None:
        self._stop.set()
        # Wake a blocked accept() so the serving thread can observe the stop.
        try:
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as waker:
                waker.connect(os.fspath(self.path))
        except OSError:
            pass
        if self._thread is not None:
            self._thread.join(timeout=5)
        if self._server is not None:
            self._server.close()
        try:
            os.unlink(self.path)
        except OSError:
            pass

    def _serve(self) -> None:
        assert self._server is not None
        while not self._stop.is_set():
            try:
                connection, _ = self._server.accept()
            except OSError:
                return
            with connection:
                if self._stop.is_set():
                    return
                self._handle(connection)

    def _handle(self, connection: socket.socket) -> None:
        buffer = bytearray()
        while b"\n" not in buffer and not self._stop.is_set():
            chunk = connection.recv(65536)
            if not chunk:
                break
            buffer.extend(chunk)
        line = bytes(buffer).split(b"\n", 1)[0]
        try:
            request = json.loads(line.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            self._respond(connection, {"status": "error", "reason": "bad_request"})
            return
        self.requests.append(request)
        if self.refuse_reason is not None:
            self._respond(connection, {"status": "error", "reason": self.refuse_reason})
            return
        if request.get("request") != "sign" or request.get("purpose") != "datapulse-observation-receipt":
            self._respond(connection, {"status": "error", "reason": "unsupported_request"})
            return
        payload = base64.b64decode(request["payload_base64"], validate=True)
        self._respond(
            connection,
            {
                "status": "signed",
                "key_id": self.key_id,
                "algorithm": "ed25519",
                "signature_base64": base64.b64encode(self.private.sign(payload)).decode("ascii"),
            },
        )

    @staticmethod
    def _respond(connection: socket.socket, document: dict[str, Any]) -> None:
        connection.sendall(json.dumps(document, separators=(",", ":")).encode("utf-8") + b"\n")


def _socket_sign_args(environment: dict[str, Any], socket_path: Path) -> list[str]:
    """CLI args selecting the socket source; --key is omitted because the two are ambiguous."""
    return [
        "--output-root",
        str(environment["output_root"]),
        "--health",
        str(environment["health_path"]),
        "--methodology",
        str(environment["methodology_path"]),
        "--registry",
        str(environment["registry_path"]),
        "--signer-socket",
        str(socket_path),
        "--now",
        signer.format_time(NOW),
    ]

def test_socket_signing_matches_inline_signature_and_receipt_id(
    environment: dict[str, Any], tmp_path: Path
) -> None:
    """Case (a): the socket and inline paths are byte-identical for the same key."""
    socket_path = tmp_path / "signer.sock"
    socket_root = tmp_path / "socket-observation"
    inline_root = tmp_path / "inline-observation"

    with _SignerStub(socket_path, environment["private"], environment["key_id"]):
        socket_summary = signer.sign_observation(
            output_root=socket_root,
            health_path=environment["health_path"],
            methodology_path=environment["methodology_path"],
            registry_path=environment["registry_path"],
            signer_socket=socket_path,
            now=NOW,
        )
    inline_summary = signer.sign_observation(
        output_root=inline_root,
        health_path=environment["health_path"],
        methodology_path=environment["methodology_path"],
        key_path=environment["key_path"],
        registry_path=environment["registry_path"],
        now=NOW,
    )

    socket_receipt = json.loads((socket_root / "days/2026-09-18.json").read_text(encoding="utf-8"))["receipts"][0]
    inline_receipt = json.loads((inline_root / "days/2026-09-18.json").read_text(encoding="utf-8"))["receipts"][0]

    assert socket_summary["status"] == "signed"
    assert socket_summary["receipt_id"] == inline_summary["receipt_id"]
    assert socket_receipt["payload"] == inline_receipt["payload"]
    assert socket_receipt["signature_base64"] == inline_receipt["signature_base64"]
    assert socket_receipt["receipt_id"] == inline_receipt["receipt_id"]
    # The socket-signed receipt is still verifiable against the published registry.
    assert _verify(environment, socket_receipt, _load(socket_root / "chain_head.json")) == []

    print(f"socket_receipt_id={socket_receipt['receipt_id']}")
    print(f"inline_receipt_id={inline_receipt['receipt_id']}")
    print(f"socket_signature_base64={socket_receipt['signature_base64']}")
    print(f"inline_signature_base64={inline_receipt['signature_base64']}")


def test_socket_signing_selects_receipt_key_when_cycle_key_is_also_active(
    environment: dict[str, Any], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A second active key for cycle attestations must not freeze receipt signing."""
    monkeypatch.delenv(signer.OBSERVER_CYCLE_KEY_FILE_ENV, raising=False)
    expected_inputs = _payload_inputs(environment)
    expected_inputs["profile_version"] = signer.verification_profile_version()
    expected_payload = signer.build_payload(**expected_inputs)
    _, _, cycle_public_b64 = _keypair()
    registry = _registry(environment)
    registry["keys"].append(
        {
            "key_id": "ed25519-cycle-test",
            "scope": "cycle-attestation (test fixture)",
            "algorithm": "Ed25519",
            "public_key_base64": cycle_public_b64,
            "created_at": "2026-01-01T00:00:00Z",
            "not_before": "2026-01-01T00:00:00Z",
            "not_after": "2027-01-01T00:00:00Z",
            "status": "active",
            "supersedes": None,
            "compromised_at": None,
        }
    )
    _write(environment["registry_path"], registry)

    socket_path = tmp_path / "signer.sock"
    with _SignerStub(socket_path, environment["private"], environment["key_id"]):
        summary = signer.sign_observation(
            output_root=tmp_path / "socket-observation",
            health_path=environment["health_path"],
            methodology_path=environment["methodology_path"],
            registry_path=environment["registry_path"],
            signer_socket=socket_path,
            now=NOW,
            artifact_commit="a" * 40,
        )

    receipt = _load(Path(summary["receipt_path"]))["receipts"][0]
    assert summary["status"] == "signed"
    assert receipt["payload"] == expected_payload
    assert signer.canonical_bytes(receipt["payload"]) == signer.canonical_bytes(expected_payload)


def test_socket_signing_refuses_registry_without_active_receipt_key(
    environment: dict[str, Any], tmp_path: Path
) -> None:
    """Scope filtering must fail closed instead of selecting an unrelated active key."""
    registry = _registry(environment)
    registry["keys"][0]["scope"] = "cycle-attestation (test fixture)"
    _write(environment["registry_path"], registry)

    socket_path = tmp_path / "signer.sock"
    with _SignerStub(socket_path, environment["private"], environment["key_id"]) as stub:
        with pytest.raises(signer.ObservationReceiptError, match="key_id_not_in_registry"):
            signer.sign_observation(
                output_root=tmp_path / "socket-observation",
                health_path=environment["health_path"],
                methodology_path=environment["methodology_path"],
                registry_path=environment["registry_path"],
                signer_socket=socket_path,
                now=NOW,
            )

    assert stub.requests == []
    assert not (tmp_path / "socket-observation" / "days").exists()


def test_socket_request_carries_exact_documented_keys(
    environment: dict[str, Any], tmp_path: Path
) -> None:
    """Case (b): the request is exactly request/purpose/payload_base64 over canonical bytes."""
    socket_path = tmp_path / "signer.sock"
    with _SignerStub(socket_path, environment["private"], environment["key_id"]) as stub:
        signer.sign_observation(
            output_root=tmp_path / "socket-observation",
            health_path=environment["health_path"],
            methodology_path=environment["methodology_path"],
            registry_path=environment["registry_path"],
            signer_socket=socket_path,
            now=NOW,
        )

    assert len(stub.requests) == 1
    request = stub.requests[0]
    assert set(request) == {"request", "purpose", "payload_base64"}
    assert request["request"] == "sign"
    assert request["purpose"] == "datapulse-observation-receipt"
    sent = base64.b64decode(request["payload_base64"], validate=True)

    receipt = json.loads((tmp_path / "socket-observation/days/2026-09-18.json").read_text(encoding="utf-8"))[
        "receipts"
    ][0]
    # The bytes on the wire are exactly the canonical bytes hashed for receipt_id.
    assert sent == signer.canonical_bytes(receipt["payload"])
    assert hashlib.sha256(sent).hexdigest() == receipt["receipt_id"]


def test_socket_mode_never_reads_the_key_path(
    environment: dict[str, Any], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Case (c): with no signing flags the socket is the default, so the inline key path is never opened.

    The module's default socket and inline key path are redirected to a throwaway
    stub and a path that does not exist. If the default source consulted the key
    file the run would fail; it succeeds and verifies.
    """
    socket_path = tmp_path / "signer.sock"
    missing_key = tmp_path / "keys/does-not-exist.json"
    assert not missing_key.exists()
    monkeypatch.setattr(signer, "DEFAULT_SIGNER_SOCKET", socket_path)
    monkeypatch.setattr(signer, "DEFAULT_KEY_PATH", missing_key)

    with _SignerStub(socket_path, environment["private"], environment["key_id"]):
        summary = signer.sign_observation(
            output_root=tmp_path / "socket-observation",
            health_path=environment["health_path"],
            methodology_path=environment["methodology_path"],
            registry_path=environment["registry_path"],
            now=NOW,
        )

    assert summary["status"] == "signed"
    assert not missing_key.exists()
    receipt = json.loads((tmp_path / "socket-observation/days/2026-09-18.json").read_text(encoding="utf-8"))[
        "receipts"
    ][0]
    assert _verify(environment, receipt, _load(tmp_path / "socket-observation/chain_head.json")) == []


def test_socket_absent_records_signer_unavailable(
    environment: dict[str, Any], tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Case (d): a missing socket is named signer_unavailable, not swallowed."""
    missing_socket = tmp_path / "absent.sock"
    with pytest.raises(signer.ObservationReceiptError, match="signer_unavailable"):
        signer.sign_observation(
            output_root=tmp_path / "socket-observation",
            health_path=environment["health_path"],
            methodology_path=environment["methodology_path"],
            registry_path=environment["registry_path"],
            signer_socket=missing_socket,
            now=NOW,
        )

    exit_code = signer.main(_socket_sign_args(environment, missing_socket))
    captured = capsys.readouterr()
    assert exit_code == 1
    assert "signer_unavailable" in captured.err
    # Fail-closed: nothing was written for the failed observation.
    assert not (environment["output_root"] / "days").exists()


def test_socket_refusal_records_signer_refused_reason(
    environment: dict[str, Any], tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Case (d): an error response is named signer_refused:<reason>."""
    socket_path = tmp_path / "signer.sock"
    with _SignerStub(socket_path, environment["private"], environment["key_id"], refuse_reason="payload_not_receipt"):
        with pytest.raises(signer.ObservationReceiptError, match="signer_refused:payload_not_receipt"):
            signer.sign_observation(
                output_root=tmp_path / "raised-observation",
                health_path=environment["health_path"],
                methodology_path=environment["methodology_path"],
                registry_path=environment["registry_path"],
                signer_socket=socket_path,
                now=NOW,
            )
        exit_code = signer.main(_socket_sign_args(environment, socket_path))
    captured = capsys.readouterr()
    assert exit_code == 1
    assert "signer_refused:payload_not_receipt" in captured.err


def test_default_socket_signs_without_signing_flags(
    environment: dict[str, Any], tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """With no signing flags the default socket signs, and it matches --signer-socket byte-for-byte.

    The module's public default socket constant is redirected to the throwaway
    stub (the module's default mechanism, not a private internal). The signature
    must verify against the stub's own public key, and the default run must be
    byte-identical to an explicit ``--signer-socket`` run for the same key and
    payload.
    """
    socket_path = tmp_path / "signer.sock"
    monkeypatch.setattr(signer, "DEFAULT_SIGNER_SOCKET", socket_path)
    default_root = tmp_path / "default-observation"
    explicit_root = tmp_path / "explicit-observation"
    common = [
        "--health",
        str(environment["health_path"]),
        "--methodology",
        str(environment["methodology_path"]),
        "--registry",
        str(environment["registry_path"]),
        "--now",
        signer.format_time(NOW),
    ]

    with _SignerStub(socket_path, environment["private"], environment["key_id"]) as stub:
        default_exit = signer.main(["--output-root", str(default_root), *common])
        default_out = capsys.readouterr().out
        explicit_exit = signer.main(
            ["--output-root", str(explicit_root), *common, "--signer-socket", str(socket_path)]
        )
        explicit_out = capsys.readouterr().out

    assert default_exit == 0
    assert explicit_exit == 0
    assert len(stub.requests) == 2

    default_summary = json.loads(default_out)
    explicit_summary = json.loads(explicit_out)
    assert default_summary["status"] == "signed"

    default_day = (default_root / "days/2026-09-18.json").read_bytes()
    explicit_day = (explicit_root / "days/2026-09-18.json").read_bytes()
    assert default_day == explicit_day
    assert default_summary["receipt_id"] == explicit_summary["receipt_id"]

    receipt = json.loads(default_day)["receipts"][0]
    # The signature verifies against the stub's own throwaway public key.
    stub_public_raw = environment["private"].public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
    Ed25519PublicKey.from_public_bytes(stub_public_raw).verify(
        base64.b64decode(receipt["signature_base64"]), signer.canonical_bytes(receipt["payload"])
    )
    assert _verify(environment, receipt, _load(default_root / "chain_head.json")) == []


def test_both_signing_flags_are_ambiguous(
    environment: dict[str, Any], tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Supplying --key and --signer-socket together is refused, never silently preferred."""
    socket_path = tmp_path / "signer.sock"
    exit_code = signer.main(
        [
            "--output-root",
            str(tmp_path / "cli-observation"),
            "--health",
            str(environment["health_path"]),
            "--methodology",
            str(environment["methodology_path"]),
            "--key",
            str(environment["key_path"]),
            "--registry",
            str(environment["registry_path"]),
            "--signer-socket",
            str(socket_path),
            "--now",
            signer.format_time(NOW),
        ]
    )
    captured = capsys.readouterr()
    assert exit_code == 1
    assert "ambiguous_signing_source" in captured.err
    # Fail closed before touching the output tree or dialling the socket.
    assert not (tmp_path / "cli-observation" / "days").exists()

    with pytest.raises(signer.ObservationReceiptError, match="ambiguous_signing_source"):
        signer.sign_observation(
            output_root=tmp_path / "api-observation",
            health_path=environment["health_path"],
            methodology_path=environment["methodology_path"],
            key_path=environment["key_path"],
            registry_path=environment["registry_path"],
            signer_socket=socket_path,
            now=NOW,
        )
    assert not (tmp_path / "api-observation" / "days").exists()
