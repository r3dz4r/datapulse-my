"""Tests for deterministic DataPulse health attestation statements."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from scripts.gen_sigstore_bundle import (
    SIGNED_MANIFEST_REF,
    PREDICATE_TYPE,
    STATEMENT_TYPE,
    StatementError,
    generate_statement,
    statement_bytes,
)

SOURCE_COMMIT = "0123456789abcdef0123456789abcdef01234567"


def _inputs(tmp_path: Path) -> tuple[Path, Path, Path]:
    health = tmp_path / "health/latest.json"
    manifest = tmp_path / "datapulse.json"
    chain_head = tmp_path / ".attestations/chain_head.json"
    health.parent.mkdir(parents=True)
    chain_head.parent.mkdir(parents=True)
    health.write_bytes(
        b'{"schema":"datapulse/v0.4/dataset-health","checked_at":"2026-08-29T13:31:05Z",'
        b'"_trust_summary":{},"datasets":[{"dataset_id":"alpha"},{"dataset_id":"beta"}]}\n'
    )
    manifest.write_text(
        json.dumps(
            {
                "$schema": "https://www.data-pulse.my/datapulse.schema.json",
                "datasets": [
                    {"id": "alpha", "methodology_version": 2},
                    {"id": "beta", "methodology_version": 2},
                ],
            }
        ),
        encoding="utf-8",
    )
    chain_head.write_text(
        json.dumps(
            {
                "schema": "datapulse/v1/daily-chain-head-envelope",
                "payload": {
                    "schema": "datapulse/v1/daily-chain-head",
                    "date": "2026-08-29",
                    "dataset_count": 2,
                },
                "chain_head": "a" * 64,
                "signature_base64": "fixture-signature",
            }
        ),
        encoding="utf-8",
    )
    return health, manifest, chain_head


def test_statement_is_byte_deterministic_and_binds_exact_health_bytes(tmp_path: Path) -> None:
    health, manifest, chain_head = _inputs(tmp_path)

    first = statement_bytes(
        generate_statement(health, manifest, chain_head, SOURCE_COMMIT)
    )
    second = statement_bytes(
        generate_statement(health, manifest, chain_head, SOURCE_COMMIT)
    )

    assert first == second
    statement = json.loads(first)
    assert statement["_type"] == STATEMENT_TYPE
    assert statement["predicateType"] == PREDICATE_TYPE
    assert statement["subject"] == [
        {
            "name": "health/latest.json",
            "digest": {"sha256": hashlib.sha256(health.read_bytes()).hexdigest()},
        }
    ]
    assert statement["predicate"]["signedManifest"] == {
        "ref": SIGNED_MANIFEST_REF,
        "digest": {"sha256": hashlib.sha256(manifest.read_bytes()).hexdigest()},
    }


def test_predicate_contains_only_grounded_phase_one_metadata(tmp_path: Path) -> None:
    health, manifest, chain_head = _inputs(tmp_path)

    predicate = generate_statement(
        health, manifest, chain_head, SOURCE_COMMIT
    )["predicate"]

    assert predicate == {
        "schema": "datapulse/v1/health-snapshot-attestation",
        "datasetCount": 2,
        "healthCheckedAt": "2026-08-29T13:31:05Z",
        "sourceCommit": SOURCE_COMMIT,
        "methodologyVersion": 2,
        "signedManifest": {
            "ref": "signatures/datapulse.json",
            "digest": {"sha256": hashlib.sha256(manifest.read_bytes()).hexdigest()},
        },
        "legacyEd25519": {
            "chainHeadRef": ".attestations/chain_head.json",
            "chainHead": "a" * 64,
        },
    }


@pytest.mark.parametrize(
    ("target", "mutation", "message"),
    (
        ("health", lambda value: value.pop("checked_at"), "checked_at"),
        ("health", lambda value: value.__setitem__("datasets", []), "datasets"),
        (
            "manifest",
            lambda value: value["datasets"][1].__setitem__("methodology_version", 3),
            "methodology_version",
        ),
        ("chain", lambda value: value.__setitem__("chain_head", "not-a-digest"), "chain_head"),
    ),
)
def test_malformed_or_inconsistent_inputs_are_rejected(
    tmp_path: Path, target: str, mutation: object, message: str
) -> None:
    health, manifest, chain_head = _inputs(tmp_path)
    path = {"health": health, "manifest": manifest, "chain": chain_head}[target]
    value = json.loads(path.read_text(encoding="utf-8"))
    mutation(value)  # type: ignore[operator]
    path.write_text(json.dumps(value), encoding="utf-8")

    with pytest.raises(StatementError, match=message):
        generate_statement(health, manifest, chain_head, SOURCE_COMMIT)


def test_source_commit_and_health_schema_are_validated(tmp_path: Path) -> None:
    health, manifest, chain_head = _inputs(tmp_path)
    value = json.loads(health.read_text(encoding="utf-8"))
    value["schema"] = "attacker/v1"
    health.write_text(json.dumps(value), encoding="utf-8")

    with pytest.raises(StatementError, match="health schema"):
        generate_statement(health, manifest, chain_head, SOURCE_COMMIT)
    with pytest.raises(StatementError, match="source commit"):
        generate_statement(health, manifest, chain_head, "main")


def test_statement_cannot_capture_secret_material(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    health, manifest, chain_head = _inputs(tmp_path)
    monkeypatch.setenv("A_PRIVATE_SIGNING_KEY", "do-not-copy-this-secret")

    rendered = statement_bytes(
        generate_statement(health, manifest, chain_head, SOURCE_COMMIT)
    )

    assert b"do-not-copy-this-secret" not in rendered
    assert b"private" not in rendered.lower()
    assert b"token" not in rendered.lower()
