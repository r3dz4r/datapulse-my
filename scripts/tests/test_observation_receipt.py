"""Tests pinning host-side observation receipts: signing, chaining, refusal, and offline verification.

Negative cases assert a specific named failure (tampered payload, wrong key,
expired/not-yet-valid key window, broken previous-receipt link, duplicate cycle
date) rather than skipping. Every fixture key is ephemeral; the real operator
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


def _verify(environment: dict[str, Any], receipt: dict[str, Any], chain_head: dict[str, Any]) -> list[str]:
    return verifier.verify_receipt(
        receipt,
        registry=_load(environment["registry_path"]),
        chain_head=chain_head,
    )


def _receipt(environment: dict[str, Any], cycle_date: str = "2026-09-18") -> dict[str, Any]:
    return _load(environment["output_root"] / "receipts" / f"{cycle_date}.json")


def _head(environment: dict[str, Any]) -> dict[str, Any]:
    return _load(environment["output_root"] / "chain_head.json")


def test_sign_then_verify_roundtrip(environment: dict[str, Any]) -> None:
    summary = _sign(environment)
    receipt = _receipt(environment)
    head = _head(environment)

    assert summary["sequence_number"] == 1
    assert summary["previous_receipt_id"] is None
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
    assert head["receipt_id"] == receipt["receipt_id"]
    assert head["previous_receipt_id"] is None
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
    assert head["receipt_id"] == second_receipt["receipt_id"]
    assert head["previous_receipt_id"] == first["receipt_id"]
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


def test_signer_refuses_duplicate_cycle_date(environment: dict[str, Any], capsys: pytest.CaptureFixture[str]) -> None:
    _sign(environment)
    receipt_path = environment["output_root"] / "receipts/2026-09-18.json"
    head_path = environment["output_root"] / "chain_head.json"
    receipt_before = receipt_path.read_bytes()
    head_before = head_path.read_bytes()

    # Python API: the refusal is a typed error naming the reason.
    with pytest.raises(signer.ObservationReceiptError) as error:
        _sign(environment, now=NOW + timedelta(hours=1))
    assert "receipt_already_exists" in str(error.value)

    # CLI: the same refusal is a non-zero exit with the reason on stderr.
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
    assert exit_code == 1
    assert "receipt_already_exists" in captured.err

    # Nothing was overwritten or advanced.
    assert receipt_path.read_bytes() == receipt_before
    assert head_path.read_bytes() == head_before
    assert _head(environment)["sequence_number"] == 1


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
            "--receipt",
            summary["receipt_path"],
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
    """A chain head found next to the receipt is enforced, not silently ignored."""
    _sign(environment)
    head_path = environment["output_root"] / "chain_head.json"
    head = _load(head_path)
    head["previous_receipt_id"] = "a" * 64
    _write(head_path, head)

    # No --chain-head: the verifier discovers the sibling head for itself.
    exit_code = verifier.main(
        [
            "--receipt",
            str(environment["output_root"] / "receipts/2026-09-18.json"),
            "--registry",
            str(environment["registry_path"]),
        ]
    )
    captured = capsys.readouterr()
    assert exit_code == 1
    assert "previous_receipt_mismatch" in captured.err
    assert "linkage: checked" in captured.out


def test_receipt_alone_passes_primary_checks_and_reports_linkage_unchecked(
    environment: dict[str, Any], tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A receipt in a third party's hands verifies without any chain head.

    Only the receipt is copied; no chain_head.json is reachable from its
    directory or its parent. The primary checks must still gate success, and
    the output must admit that linkage was not checked.
    """
    summary = _sign(environment)
    isolated = tmp_path / "isolated" / "nested"
    isolated.mkdir(parents=True)
    receipt_copy = isolated / "2026-09-18.json"
    receipt_copy.write_bytes(Path(summary["receipt_path"]).read_bytes())

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


def test_no_key_material_in_any_output(environment: dict[str, Any], capsys: pytest.CaptureFixture[str]) -> None:
    """Neither the private bytes nor the field name 'private_key' may leak out.

    Covers the receipt JSON, the chain head, and the verifier's stdout/stderr.
    """
    summary = _sign(environment)
    receipt_path = Path(summary["receipt_path"])
    head_path = Path(summary["chain_head_path"])
    private_b64 = _load(environment["key_path"])["private_key_base64"]

    exit_code = verifier.main(
        [
            "--receipt",
            str(receipt_path),
            "--registry",
            str(environment["registry_path"]),
            "--chain-head",
            str(head_path),
        ]
    )
    captured = capsys.readouterr()
    assert exit_code == 0

    outputs = {
        "receipt": receipt_path.read_text(encoding="utf-8"),
        "chain_head": head_path.read_text(encoding="utf-8"),
        "verifier_stdout": captured.out,
        "verifier_stderr": captured.err,
    }
    for label, text in outputs.items():
        assert private_b64 not in text, f"private key bytes leaked into {label}"
        assert "private_key" not in text, f"'private_key' appeared in {label}"


def test_cli_verify_names_failure_reason(environment: dict[str, Any], capsys: pytest.CaptureFixture[str]) -> None:
    summary = _sign(environment)
    receipt_path = Path(summary["receipt_path"])
    tampered = _load(receipt_path)
    tampered["payload"]["dataset_count"] = 42
    _write(receipt_path, tampered)

    exit_code = verifier.main(
        [
            "--receipt",
            str(receipt_path),
            "--registry",
            str(environment["registry_path"]),
            "--chain-head",
            summary["chain_head_path"],
        ]
    )
    captured = capsys.readouterr()
    assert exit_code == 1
    assert "receipt_id_mismatch" in captured.err
