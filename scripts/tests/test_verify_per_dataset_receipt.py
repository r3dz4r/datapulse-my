"""Tests for per-dataset receipt verification."""

from __future__ import annotations

import base64
import json
import subprocess
import sys
from pathlib import Path

from scripts.gen_per_dataset_receipt import generate_receipts
from scripts.tests.test_gen_per_dataset_receipt import _inputs
from scripts.verify_per_dataset_receipt import BundleError, verify_receipt


IDENTITY = "https://github.com/r3dz4r/datapulse-my/.github/workflows/deploy-cloudflare-pages.yml@refs/heads/main"
ISSUER = "https://token.actions.githubusercontent.com"


def _bundle(statement: bytes) -> dict[str, object]:
    return {
        "mediaType": "application/vnd.dev.sigstore.bundle.v0.3+json",
        "dsseEnvelope": {
            "payloadType": "application/vnd.in-toto+json",
            "payload": base64.b64encode(statement).decode("ascii"),
            "signatures": [{"sig": base64.b64encode(b"fixture signature").decode("ascii")}],
        },
    }


def test_verifier_accepts_matching_dsse_payload(tmp_path: Path) -> None:
    health, manifest, data = _inputs(tmp_path)
    generate_receipts(health, manifest, data, quick_test=True)
    for identifier in ("fuelprice", "cpi_3d", "dosm_lfs_month"):
        statement = (data / f"{identifier}.receipt.statement.json").read_bytes()
        (data / f"{identifier}.receipt.sigstore.json").write_text(json.dumps(_bundle(statement)), encoding="utf-8")
        assert len(verify_receipt(dataset_id=identifier, health=health, manifest=manifest, data_dir=data, identity=IDENTITY, issuer=ISSUER)) == 64


def test_quick_cli_rejects_tampered_statement_before_trusting_bundle(tmp_path: Path) -> None:
    health, manifest, data = _inputs(tmp_path)
    generate_receipts(health, manifest, data, quick_test=True)
    for sample_id in ("cpi_3d", "dosm_lfs_month"):
        sample_statement = (data / f"{sample_id}.receipt.statement.json").read_bytes()
        (data / f"{sample_id}.receipt.sigstore.json").write_text(
            json.dumps(_bundle(sample_statement)), encoding="utf-8"
        )
    identifier = "fuelprice"
    statement_path = data / f"{identifier}.receipt.statement.json"
    statement = json.loads(statement_path.read_text())
    statement["subject"][0]["digest"]["sha256"] = "0" * 64
    statement_path.write_text(json.dumps(statement), encoding="utf-8")
    (data / f"{identifier}.receipt.sigstore.json").write_text(json.dumps(_bundle(statement_path.read_bytes())), encoding="utf-8")

    completed = subprocess.run([
        sys.executable, "scripts/verify_per_dataset_receipt.py", "--quick-test",
        "--health", str(health), "--manifest", str(manifest), "--data-dir", str(data),
        "--certificate-identity", IDENTITY, "--certificate-oidc-issuer", ISSUER,
    ], cwd=Path(__file__).resolve().parents[2], check=False, capture_output=True, text=True)

    assert completed.returncode != 0
    assert "persisted statement differs" in completed.stderr
