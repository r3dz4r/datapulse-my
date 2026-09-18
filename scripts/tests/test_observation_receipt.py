"""Tests pinning host-side observation receipts: per-day accumulation, chaining, idempotence, and offline verification.

Negative cases assert a specific named failure (tampered payload, wrong key,
expired/not-yet-valid key window, broken previous-receipt link, tampered day
entry) rather than skipping. Every fixture key is ephemeral; the real operator
key under ~/.hermes is never read here.
"""

from __future__ import annotations

import base64
import hashlib
import json
import sys
from datetime import datetime, timedelta, timezone
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
            "schema": "datapulse/v1/probe-key-registry",
            "version": 1,
            "keys": [
                {
                    "key_id": KEY_ID,
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
    assert "verification passed" in captured.out
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
    assert "verification passed" in captured.out
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

    outputs = {
        "day_file": day_path.read_text(encoding="utf-8"),
        "chain_head": head_path.read_text(encoding="utf-8"),
        "verifier_stdout": captured.out,
        "verifier_stderr": captured.err,
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
