from __future__ import annotations

import hashlib
import json
import base64
from pathlib import Path
from typing import Any

import pytest

from scripts.sigstore_rekor_publisher import ConfigError, ProcessResult, PublishError, Publisher, publisher_from_args


LOG_ID = "a" * 64
RUN_ID = "health-" + hashlib.sha256(b"daily evidence").hexdigest()


class FakeRuntime:
    def __init__(self, bundle: dict[str, Any] | None = None, *, fail_sign: bool = False, fail_verify: bool = False) -> None:
        self.bundle = bundle or valid_bundle(b"daily evidence")
        self.fail_sign = fail_sign
        self.fail_verify = fail_verify
        self.calls: list[list[str]] = []
        self.gets: list[str] = []

    def run(self, command: list[str]) -> ProcessResult:
        self.calls.append(command)
        if command[1:] == ["version"]:
            return ProcessResult(0, "GitVersion: v3.1.3\n", "")
        if command[1:] == ["sign-blob", "--help"]:
            return ProcessResult(0, "  --rekor-url string\n", "")
        if command[1] == "sign-blob":
            if self.fail_sign:
                return ProcessResult(1, "", "private-signing-secret")
            Path(command[command.index("--bundle") + 1]).write_text(json.dumps(self.bundle), encoding="utf-8")
            return ProcessResult(0, "", "")
        if command[1] == "verify-blob":
            return ProcessResult(1 if self.fail_verify else 0, "", "private-signing-secret" if self.fail_verify else "")
        raise AssertionError(command)

    def get(self, url: str) -> None:
        self.gets.append(url)


def valid_bundle(artifact: bytes, **overrides: Any) -> dict[str, Any]:
    digest = hashlib.sha256(artifact).hexdigest()
    body = base64.b64encode(b"fixture Rekor body").decode("ascii")
    root_hash = base64.b64encode(hashlib.sha256(b"\x00" + base64.b64decode(body)).digest()).decode("ascii")
    result: dict[str, Any] = {
        "mediaType": "application/vnd.dev.sigstore.bundle.v0.3+json",
        "messageSignature": {"messageDigest": {"algorithm": "SHA2_256", "digest": digest}},
        "verificationMaterial": {"tlogEntries": [{"logId": {"keyId": LOG_ID}, "logIndex": 0, "canonicalizedBody": body, "inclusionProof": {"rootHash": root_hash, "hashes": [], "treeSize": 1}, "inclusionPromise": {"signedEntryTimestamp": "fixture-set"}}]},
    }
    result.update(overrides)
    return result


def config_files(tmp_path: Path, artifact: bytes = b"daily evidence") -> tuple[Path, Path, Path, Path, Path]:
    source = tmp_path / "daily.json"; source.write_bytes(artifact)
    run_id = "health-" + hashlib.sha256(artifact).hexdigest()
    manifest = tmp_path / "run.json"; manifest.write_text(json.dumps({"run_id": run_id, "artifact_sha256": hashlib.sha256(artifact).hexdigest()}), encoding="utf-8")
    root = tmp_path / "trusted-root.json"; root.write_text("{}", encoding="utf-8")
    verification_key = tmp_path / "datapulse-cosign.pub"; verification_key.write_text("public key", encoding="utf-8")
    cosign_config = tmp_path / "cosign-signing-config.json"; cosign_config.write_text(json.dumps({"rekorTlogUrls": [{"url": "http://127.0.0.1:9301"}]}), encoding="utf-8")
    rekor = tmp_path / "rekor.json"; rekor.write_text(json.dumps({"endpoint": "http://127.0.0.1:9301", "consistency_proxy_endpoint": "http://127.0.0.1:9301", "trusted_log_ids": [LOG_ID], "trusted_root": str(root)}), encoding="utf-8")
    signing = tmp_path / "signing.json"; signing.write_text(json.dumps({"key_ref": "openbao://daily", "verification_key": str(verification_key), "credential_env": "OPENBAO_TOKEN", "cosign_signing_config": str(cosign_config)}), encoding="utf-8")
    return source, manifest, rekor, signing, tmp_path / "bundle.json"


def publisher(tmp_path: Path, runtime: FakeRuntime | None = None) -> tuple[Publisher, Path, Path]:
    source, manifest, rekor, signing, bundle = config_files(tmp_path)
    reference = tmp_path / "reference.json"
    return Publisher(source, bundle, reference, manifest, rekor, signing, RUN_ID, "/opt/cosign", runtime or FakeRuntime()), bundle, reference


def test_success_writes_additive_bundle_and_reference_with_shared_digest(tmp_path: Path) -> None:
    subject, bundle, reference = publisher(tmp_path)
    subject.publish()
    assert bundle.exists() and reference.exists()
    assert json.loads(reference.read_text())["artifact_sha256"] == hashlib.sha256(b"daily evidence").hexdigest()
    assert json.loads(reference.read_text())["artifact"] == "health/latest.json"
    assert json.loads(reference.read_text())["bundle"] == "bundle.json"
    assert json.loads(bundle.read_text())["messageSignature"]["messageDigest"]["digest"] == json.loads(reference.read_text())["artifact_sha256"]
    assert json.loads(reference.read_text())["rekor"] == {
        "log_id": LOG_ID,
        "log_index": 0,
        "uuid": hashlib.sha256(b"fixture Rekor body").hexdigest(),
        "inclusion_proof": True,
        "signed_entry_timestamp": True,
    }


def test_signs_with_openbao_key_ref_and_verifies_with_static_public_key(tmp_path: Path) -> None:
    runtime = FakeRuntime()
    subject, _bundle, _reference = publisher(tmp_path, runtime)
    verification_key = str(json.loads(subject.signing_config.read_text(encoding="utf-8"))["verification_key"])

    subject.publish()

    sign_command = next(command for command in runtime.calls if command[1] == "sign-blob")
    verify_command = next(command for command in runtime.calls if command[1] == "verify-blob")
    assert sign_command[sign_command.index("--key") + 1] == "openbao://daily"
    assert verify_command[verify_command.index("--key") + 1] == verification_key


def test_missing_verification_key_fails_closed_before_network(tmp_path: Path) -> None:
    subject, _bundle, _reference = publisher(tmp_path)
    signing = json.loads(subject.signing_config.read_text(encoding="utf-8"))
    del signing["verification_key"]
    subject.signing_config.write_text(json.dumps(signing), encoding="utf-8")

    with pytest.raises(ConfigError, match="verification key"):
        subject.publish()

    assert subject.runtime.gets == []  # type: ignore[attr-defined]


def test_cosign_v3_base64_bundle_digest_normalises_to_artifact_hex(tmp_path: Path) -> None:
    bundle = valid_bundle(b"daily evidence")
    bundle["messageSignature"]["messageDigest"]["digest"] = base64.b64encode(hashlib.sha256(b"daily evidence").digest()).decode("ascii")
    subject, output, reference = publisher(tmp_path, FakeRuntime(bundle))
    subject.publish()
    assert output.exists() and reference.exists()
    assert json.loads(reference.read_text())["artifact_sha256"] == hashlib.sha256(b"daily evidence").hexdigest()


@pytest.mark.parametrize(
    "digest, algorithm",
    [
        (base64.b64encode(b"wrong digest").decode("ascii"), "SHA2_256"),
        ("not-base64", "SHA2_256"),
        (base64.b64encode(b"short").decode("ascii"), "SHA2_256"),
        (base64.b64encode(hashlib.sha256(b"daily evidence").digest()).decode("ascii"), "SHA3_256"),
    ],
)
def test_invalid_cosign_v3_bundle_digest_is_rejected_before_outputs(tmp_path: Path, digest: str, algorithm: str) -> None:
    bundle = valid_bundle(b"daily evidence")
    bundle["messageSignature"]["messageDigest"] = {"algorithm": algorithm, "digest": digest}
    subject, output, reference = publisher(tmp_path, FakeRuntime(bundle))
    with pytest.raises(PublishError, match="digest"):
        subject.publish()
    assert not output.exists() and not reference.exists()


def test_rejects_stale_or_mismatched_run_identity_before_network(tmp_path: Path) -> None:
    subject, _bundle, _reference = publisher(tmp_path)
    subject.run_manifest.write_text(json.dumps({"run_id": "other", "artifact_sha256": "a" * 64}), encoding="utf-8")
    with pytest.raises(PublishError, match="run manifest"):
        subject.publish()
    assert subject.runtime.gets == []  # type: ignore[attr-defined]


def test_rejects_artifact_mutation_after_signing(tmp_path: Path) -> None:
    runtime = FakeRuntime()
    subject, bundle, reference = publisher(tmp_path, runtime)
    original = runtime.run
    def mutate(command: list[str]) -> ProcessResult:
        result = original(command)
        if command[1] == "sign-blob": subject.artifact.write_bytes(b"changed")
        return result
    runtime.run = mutate  # type: ignore[method-assign]
    with pytest.raises(PublishError, match="artifact changed"):
        subject.publish()
    assert not bundle.exists() and not reference.exists()


def test_unavailable_endpoint_fails_before_cosign(tmp_path: Path) -> None:
    runtime = FakeRuntime(); runtime.get = lambda url: (_ for _ in ()).throw(OSError("private-secret"))  # type: ignore[method-assign]
    subject, _bundle, _reference = publisher(tmp_path, runtime)
    with pytest.raises(PublishError, match="endpoint unavailable"):
        subject.publish()
    assert runtime.calls == []


def test_cosign_error_is_not_retried_or_leaked(tmp_path: Path) -> None:
    runtime = FakeRuntime(fail_sign=True); subject, bundle, reference = publisher(tmp_path, runtime)
    with pytest.raises(PublishError) as error: subject.publish()
    assert "private-signing-secret" not in str(error.value)
    assert len([call for call in runtime.calls if call[1] == "sign-blob"]) == 1
    assert not bundle.exists() and not reference.exists()


@pytest.mark.parametrize("bundle", [valid_bundle(b"daily evidence", verificationMaterial={"tlogEntries": [{"logId": {"keyId": LOG_ID}, "logIndex": 3}]}), valid_bundle(b"daily evidence", verificationMaterial={"tlogEntries": [{"logId": {"keyId": "0" * 64}, "logIndex": 3, "inclusionProof": {"x": 1}}]})])
def test_absent_proof_or_invalid_log_id_is_rejected(tmp_path: Path, bundle: dict[str, Any]) -> None:
    subject, output, reference = publisher(tmp_path, FakeRuntime(bundle))
    with pytest.raises(PublishError, match="bundle"):
        subject.publish()
    assert not output.exists() and not reference.exists()


def test_independent_verify_failure_blocks_outputs_and_secret_leak(tmp_path: Path) -> None:
    subject, bundle, reference = publisher(tmp_path, FakeRuntime(fail_verify=True))
    with pytest.raises(PublishError) as error: subject.publish()
    assert "private-signing-secret" not in str(error.value)
    assert not bundle.exists() and not reference.exists()


def test_cli_requires_all_explicit_contract_inputs(tmp_path: Path) -> None:
    with pytest.raises(SystemExit): publisher_from_args([])
    source, manifest, rekor, signing, bundle = config_files(tmp_path)
    reference = tmp_path / "reference.json"
    configured = publisher_from_args(["--artifact", str(source), "--bundle-out", str(bundle), "--reference-out", str(reference), "--run-manifest", str(manifest), "--rekor-config", str(rekor), "--signing-config", str(signing), "--run-id", RUN_ID, "--cosign", "/opt/cosign"])
    assert configured.run_id == RUN_ID


def test_credential_name_is_whitelisted_and_never_placed_in_argv(tmp_path: Path) -> None:
    source, manifest, rekor, signing, bundle = config_files(tmp_path)
    signing.write_text(json.dumps({"key_ref": "openbao://daily", "credential_env": "NOT_ALLOWED"}), encoding="utf-8")
    with pytest.raises(ConfigError, match="credential"):
        Publisher(source, bundle, tmp_path / "ref", manifest, rekor, signing, RUN_ID, "/opt/cosign", FakeRuntime()).publish()


def test_base64_bundle_log_id_matches_the_hex_trusted_log_id(tmp_path: Path) -> None:
    bundle = valid_bundle(b"daily evidence")
    bundle["verificationMaterial"]["tlogEntries"][0]["logId"]["keyId"] = base64.b64encode(bytes.fromhex(LOG_ID)).decode("ascii")
    subject, output, _reference = publisher(tmp_path, FakeRuntime(bundle))
    subject.publish()
    assert output.exists()


def test_public_or_different_tlog_url_in_signing_config_is_rejected(tmp_path: Path) -> None:
    source, manifest, rekor, signing, bundle = config_files(tmp_path)
    cosign_config = tmp_path / "cosign-signing-config.json"
    cosign_config.write_text(json.dumps({"rekorTlogUrls": [{"url": "https://rekor.sigstore.dev"}]}), encoding="utf-8")
    with pytest.raises(ConfigError, match="private consistency proxy"):
        Publisher(source, bundle, tmp_path / "ref", manifest, rekor, signing, RUN_ID, "/opt/cosign", FakeRuntime()).publish()


def test_existing_output_is_never_replaced_or_deleted(tmp_path: Path) -> None:
    subject, bundle, _reference = publisher(tmp_path)
    bundle.write_text("legacy evidence", encoding="utf-8")
    with pytest.raises(PublishError, match="already exists"):
        subject.publish()
    assert bundle.read_text(encoding="utf-8") == "legacy evidence"
