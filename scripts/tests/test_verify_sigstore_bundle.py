"""Tests for DataPulse Sigstore DSSE bundle verification."""

from __future__ import annotations

import base64
import json
from pathlib import Path

import pytest

from scripts.gen_sigstore_bundle import generate_statement, statement_bytes
from scripts.tests.test_gen_sigstore_bundle import SOURCE_COMMIT, _inputs
from scripts.verify_sigstore_bundle import BundleError, verify_bundle

IDENTITY = (
    "https://github.com/r3dz4r/datapulse-my/"
    ".github/workflows/deploy-cloudflare-pages.yml@refs/heads/main"
)
ISSUER = "https://token.actions.githubusercontent.com"


def _bundle(tmp_path: Path) -> tuple[Path, Path, Path, Path]:
    health, manifest, chain_head = _inputs(tmp_path)
    statement = tmp_path / "health.latest.statement.json"
    statement.write_bytes(
        statement_bytes(generate_statement(health, manifest, chain_head, SOURCE_COMMIT))
    )
    bundle = tmp_path / "health.latest.sigstore.json"
    bundle.write_text(
        json.dumps(
            {
                "mediaType": "application/vnd.dev.sigstore.bundle.v0.3+json",
                "verificationMaterial": {
                    "certificate": {"rawBytes": "fixture-certificate"},
                    "tlogEntries": [{"logIndex": "42", "integratedTime": "1788000000"}],
                },
                "dsseEnvelope": {
                    "payload": base64.b64encode(statement.read_bytes()).decode("ascii"),
                    "payloadType": "application/vnd.in-toto+json",
                    "signatures": [{"sig": base64.b64encode(b"signature").decode("ascii")}],
                },
            }
        ),
        encoding="utf-8",
    )
    return health, manifest, chain_head, bundle


def _fake_cosign(tmp_path: Path, *, exit_code: int = 0) -> tuple[Path, Path]:
    executable = tmp_path / "cosign"
    arguments = tmp_path / "cosign-arguments.json"
    executable.write_text(
        "#!/usr/bin/env python3\n"
        "import json, sys\n"
        f"json.dump(sys.argv[1:], open({str(arguments)!r}, 'w', encoding='utf-8'))\n"
        f"raise SystemExit({exit_code})\n",
        encoding="utf-8",
    )
    executable.chmod(0o755)
    return executable, arguments


def test_verifier_checks_dsse_payload_digest_identity_and_issuer(tmp_path: Path) -> None:
    health, manifest, chain_head, bundle = _bundle(tmp_path)
    cosign, arguments = _fake_cosign(tmp_path)

    verified = verify_bundle(
        health=health,
        manifest=manifest,
        chain_head=chain_head,
        source_commit=SOURCE_COMMIT,
        bundle=bundle,
        identity=IDENTITY,
        issuer=ISSUER,
        cosign=cosign,
    )

    assert verified["subject_sha256"] == generate_statement(
        health, manifest, chain_head, SOURCE_COMMIT
    )["subject"][0]["digest"]["sha256"]
    assert json.loads(arguments.read_text(encoding="utf-8")) == [
        "verify-blob-attestation",
        "--bundle",
        str(bundle),
        "--certificate-identity",
        IDENTITY,
        "--certificate-oidc-issuer",
        ISSUER,
        "--type",
        "https://www.data-pulse.my/predicates/health-snapshot/v1",
        str(health),
    ]


def test_verifier_rejects_manifest_bytes_that_differ_from_signed_snapshot(tmp_path: Path) -> None:
    health, manifest, chain_head, bundle = _bundle(tmp_path)
    manifest.write_bytes(manifest.read_bytes() + b"\n")

    with pytest.raises(BundleError, match="signed manifest digest"):
        verify_bundle(
            health=health,
            manifest=manifest,
            chain_head=chain_head,
            source_commit=SOURCE_COMMIT,
            bundle=bundle,
            identity=IDENTITY,
            issuer=ISSUER,
        )


def test_verifier_rejects_missing_signed_manifest_binding(tmp_path: Path) -> None:
    health, manifest, chain_head, bundle = _bundle(tmp_path)
    value = json.loads(bundle.read_text(encoding="utf-8"))
    payload = json.loads(base64.b64decode(value["dsseEnvelope"]["payload"]))
    payload["predicate"].pop("signedManifest")
    value["dsseEnvelope"]["payload"] = base64.b64encode(
        statement_bytes(payload)
    ).decode("ascii")
    bundle.write_text(json.dumps(value), encoding="utf-8")

    with pytest.raises(BundleError, match="missing signed manifest binding"):
        verify_bundle(
            health=health,
            manifest=manifest,
            chain_head=chain_head,
            source_commit=SOURCE_COMMIT,
            bundle=bundle,
            identity=IDENTITY,
            issuer=ISSUER,
        )


@pytest.mark.parametrize(
    ("binding_path", "replacement", "message"),
    (
        (("ref",), "datapulse.json", "signed manifest reference"),
        (("digest", "sha256"), "f" * 64, "signed manifest digest"),
    ),
)
def test_verifier_rejects_tampered_signed_manifest_binding(
    tmp_path: Path,
    binding_path: tuple[str, ...],
    replacement: str,
    message: str,
) -> None:
    health, manifest, chain_head, bundle = _bundle(tmp_path)
    payload = json.loads(
        base64.b64decode(
            json.loads(bundle.read_text(encoding="utf-8"))["dsseEnvelope"]["payload"]
        )
    )
    binding = payload["predicate"]["signedManifest"]
    for key in binding_path[:-1]:
        binding = binding[key]
    binding[binding_path[-1]] = replacement
    value = json.loads(bundle.read_text(encoding="utf-8"))
    value["dsseEnvelope"]["payload"] = base64.b64encode(
        statement_bytes(payload)
    ).decode("ascii")
    bundle.write_text(json.dumps(value), encoding="utf-8")

    with pytest.raises(BundleError, match=message):
        verify_bundle(
            health=health,
            manifest=manifest,
            chain_head=chain_head,
            source_commit=SOURCE_COMMIT,
            bundle=bundle,
            identity=IDENTITY,
            issuer=ISSUER,
        )


def test_verifier_rejects_message_signature_bundle_for_dsse_contract(tmp_path: Path) -> None:
    health, manifest, chain_head, bundle = _bundle(tmp_path)
    value = json.loads(bundle.read_text(encoding="utf-8"))
    value["messageSignature"] = {"signature": "ZmFrZQ=="}
    value.pop("dsseEnvelope")
    bundle.write_text(json.dumps(value), encoding="utf-8")

    with pytest.raises(BundleError, match="DSSE"):
        verify_bundle(
            health=health,
            manifest=manifest,
            chain_head=chain_head,
            source_commit=SOURCE_COMMIT,
            bundle=bundle,
            identity=IDENTITY,
            issuer=ISSUER,
        )


def test_verifier_rejects_payload_or_transparency_log_drift(tmp_path: Path) -> None:
    health, manifest, chain_head, bundle = _bundle(tmp_path)
    value = json.loads(bundle.read_text(encoding="utf-8"))
    value["dsseEnvelope"]["payload"] = base64.b64encode(b"{}").decode("ascii")
    bundle.write_text(json.dumps(value), encoding="utf-8")

    with pytest.raises(BundleError, match="payload"):
        verify_bundle(
            health=health,
            manifest=manifest,
            chain_head=chain_head,
            source_commit=SOURCE_COMMIT,
            bundle=bundle,
            identity=IDENTITY,
            issuer=ISSUER,
        )

    health, manifest, chain_head, bundle = _bundle(tmp_path / "missing-tlog")
    value = json.loads(bundle.read_text(encoding="utf-8"))
    value["verificationMaterial"]["tlogEntries"] = []
    bundle.write_text(json.dumps(value), encoding="utf-8")
    with pytest.raises(BundleError, match="transparency"):
        verify_bundle(
            health=health,
            manifest=manifest,
            chain_head=chain_head,
            source_commit=SOURCE_COMMIT,
            bundle=bundle,
            identity=IDENTITY,
            issuer=ISSUER,
        )


def test_verifier_propagates_cosign_identity_failure(tmp_path: Path) -> None:
    health, manifest, chain_head, bundle = _bundle(tmp_path)
    cosign, _ = _fake_cosign(tmp_path, exit_code=1)

    with pytest.raises(BundleError, match="cosign verification failed"):
        verify_bundle(
            health=health,
            manifest=manifest,
            chain_head=chain_head,
            source_commit=SOURCE_COMMIT,
            bundle=bundle,
            identity=IDENTITY,
            issuer=ISSUER,
            cosign=cosign,
        )
