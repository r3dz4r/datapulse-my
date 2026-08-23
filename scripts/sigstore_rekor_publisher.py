#!/usr/bin/env python3
"""Fail-closed, additive Cosign/Rekor publisher for one canonical artifact.

This module deliberately does not know how the legacy Ed25519 envelope is
made.  Its caller supplies the exact bytes that envelope identifies and a
per-run manifest that names their SHA-256.  A service wrapper owns the signer
credential boundary; this process only passes a non-secret key reference to
Cosign.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import logging
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol
from urllib.parse import urlsplit
from urllib.request import urlopen


LOG = logging.getLogger(__name__)
COSIGN_VERSION = "v3.1.3"
ALLOWED_CREDENTIAL_ENVS = frozenset({"OPENBAO_TOKEN", "VAULT_TOKEN"})


class ConfigError(ValueError):
    """A local publisher configuration violates the contract."""


class PublishError(RuntimeError):
    """Publishing did not produce independently verifiable evidence."""


@dataclass(frozen=True)
class ProcessResult:
    returncode: int
    stdout: str
    stderr: str


class Runtime(Protocol):
    def run(self, command: list[str]) -> ProcessResult: ...

    def get(self, url: str) -> None: ...


class SubprocessRuntime:
    """No command output is relayed because it may contain provider details."""

    def run(self, command: list[str]) -> ProcessResult:
        completed = subprocess.run(command, check=False, capture_output=True, text=True)
        return ProcessResult(completed.returncode, completed.stdout, completed.stderr)

    def get(self, url: str) -> None:
        with urlopen(url, timeout=5) as response:
            if not 200 <= response.status < 300:
                raise OSError("endpoint returned non-success")


def _read_json(path: Path, name: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ConfigError(f"invalid {name} configuration") from exc
    if not isinstance(value, dict):
        raise ConfigError(f"invalid {name} configuration")
    return value


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as artifact:
        for block in iter(lambda: artifact.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _safe_private_endpoint(value: object) -> str:
    if not isinstance(value, str):
        raise ConfigError("private Rekor endpoint is required")
    parsed = urlsplit(value)
    if parsed.scheme != "http" or parsed.hostname not in {"127.0.0.1", "::1", "localhost"} or parsed.username or parsed.password:
        raise ConfigError("Rekor endpoint must be loopback-only HTTP")
    return value.rstrip("/")


def _nonempty_path(value: object, name: str) -> str:
    if not isinstance(value, str) or not value:
        raise ConfigError(f"{name} is required")
    if not Path(value).is_file():
        raise ConfigError(f"{name} does not exist")
    return value


def _is_digest(value: object) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(char in "0123456789abcdef" for char in value)


def _normalise_log_id(value: object) -> str:
    """Cosign bundles encode LogID keyIds as base64; Rekor APIs use hex."""
    if _is_digest(value):
        return value
    if not isinstance(value, str):
        raise ConfigError("Rekor LogID is invalid")
    try:
        decoded = base64.b64decode(value, validate=True).hex()
    except (ValueError, UnicodeEncodeError) as exc:
        raise ConfigError("Rekor LogID is invalid") from exc
    if not _is_digest(decoded):
        raise ConfigError("Rekor LogID is invalid")
    return decoded


def _normalise_bundle_digest(value: object) -> str | None:
    """Normalise Cosign v3 digest bytes and retain legacy hex fixtures."""
    if _is_digest(value):
        return value
    if not isinstance(value, str):
        return None
    try:
        decoded = base64.b64decode(value, validate=True)
    except (ValueError, UnicodeEncodeError):
        return None
    if len(decoded) != hashlib.sha256().digest_size:
        return None
    return decoded.hex()


def _atomic_json(path: Path, content: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    try:
        temporary.write_text(json.dumps(content, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


class Publisher:
    """Publish one immutable artifact without changing legacy attestations."""

    def __init__(self, artifact: Path, bundle_out: Path, reference_out: Path, run_manifest: Path, rekor_config: Path, signing_config: Path, run_id: str, cosign: str, runtime: Runtime | None = None) -> None:
        self.artifact = artifact
        self.bundle_out = bundle_out
        self.reference_out = reference_out
        self.run_manifest = run_manifest
        self.rekor_config = rekor_config
        self.signing_config = signing_config
        self.run_id = run_id
        self.cosign = cosign
        self.runtime = runtime or SubprocessRuntime()

    def _config(self) -> tuple[str, str, str, frozenset[str], str, str]:
        rekor = _read_json(self.rekor_config, "Rekor")
        endpoint = _safe_private_endpoint(rekor.get("endpoint"))
        proxy = _safe_private_endpoint(rekor.get("consistency_proxy_endpoint"))
        root = _nonempty_path(rekor.get("trusted_root"), "trusted root")
        log_ids_value = rekor.get("trusted_log_ids")
        if not isinstance(log_ids_value, list) or not log_ids_value:
            raise ConfigError("trusted Rekor LogIDs are required")
        try:
            log_ids = frozenset(_normalise_log_id(log_id) for log_id in log_ids_value)
        except ConfigError as exc:
            raise ConfigError("trusted Rekor LogIDs must be non-zero SHA-256 identifiers") from exc
        if any(log_id == "0" * 64 for log_id in log_ids):
            raise ConfigError("trusted Rekor LogIDs must be non-zero SHA-256 identifiers")
        signing = _read_json(self.signing_config, "signing")
        key_ref = signing.get("key_ref")
        verification_key = signing.get("verification_key")
        credential_env = signing.get("credential_env")
        cosign_signing_config = signing.get("cosign_signing_config")
        if not isinstance(key_ref, str) or not key_ref or not isinstance(credential_env, str) or credential_env not in ALLOWED_CREDENTIAL_ENVS:
            raise ConfigError("signing credential configuration is not permitted")
        verification_key_path = _nonempty_path(verification_key, "verification key")
        cosign_config = _nonempty_path(cosign_signing_config, "Cosign signing config")
        cosign_document = _read_json(Path(cosign_config), "Cosign signing")
        tlogs = cosign_document.get("rekorTlogUrls")
        try:
            valid_tlogs = isinstance(tlogs, list) and bool(tlogs) and all(isinstance(item, dict) and _safe_private_endpoint(item.get("url")) == proxy for item in tlogs)
        except ConfigError:
            valid_tlogs = False
        if not valid_tlogs:
            raise ConfigError("Cosign signing config must use the configured private consistency proxy")
        # The future UID-65532 wrapper supplies this environment to Cosign.  Do
        # not inspect it here: reading it risks accidental logging or copying.
        return endpoint, proxy, root, log_ids, cosign_config, verification_key_path

    def _fresh_digest(self) -> str:
        if not self.artifact.is_file():
            raise PublishError("canonical artifact is unavailable")
        manifest = _read_json(self.run_manifest, "run manifest")
        digest = _sha256(self.artifact)
        if manifest.get("run_id") != self.run_id or manifest.get("artifact_sha256") != digest:
            raise PublishError("canonical artifact does not match run manifest")
        return digest

    def _assert_output_paths(self) -> None:
        paths = (self.artifact, self.bundle_out, self.reference_out, self.run_manifest, self.rekor_config, self.signing_config)
        resolved = tuple(path.resolve(strict=False) for path in paths)
        if resolved[1] == resolved[2] or resolved[1] in resolved[:1] + resolved[3:] or resolved[2] in resolved[:1] + resolved[3:]:
            raise ConfigError("bundle and reference paths must be new, additive outputs")
        if self.bundle_out.exists() or self.reference_out.exists():
            raise PublishError("additive bundle/reference output already exists")

    def _run_or_fail(self, command: list[str], phase: str) -> None:
        result = self.runtime.run(command)
        if result.returncode != 0:
            # Do not include stdout/stderr: KMS providers can place credential
            # context in diagnostics.
            raise PublishError(f"Cosign {phase} failed")

    @staticmethod
    def _bundle_digest_and_proof(bundle_path: Path, expected_digest: str, log_ids: frozenset[str]) -> dict[str, Any]:
        try:
            bundle = json.loads(bundle_path.read_text(encoding="utf-8"))
            signature = bundle["messageSignature"]["messageDigest"]
            entries = bundle["verificationMaterial"]["tlogEntries"]
            entry = entries[0]
            log_id = _normalise_log_id(entry["logId"]["keyId"])
            proof = entry["inclusionProof"]
            promise = entry["inclusionPromise"]["signedEntryTimestamp"]
            canonicalized_body = base64.b64decode(entry["canonicalizedBody"], validate=True)
            log_index = entry["logIndex"]
        except (OSError, json.JSONDecodeError, KeyError, IndexError, TypeError, ValueError, ConfigError) as exc:
            raise PublishError("Cosign bundle is incomplete") from exc
        if signature.get("algorithm") != "SHA2_256" or _normalise_bundle_digest(signature.get("digest")) != expected_digest:
            raise PublishError("Cosign bundle digest does not match canonical artifact")
        if (
            log_id not in log_ids
            or not isinstance(proof, dict)
            or not proof
            or not isinstance(promise, str)
            or not promise
            or not canonicalized_body
            or isinstance(log_index, bool)
            or not isinstance(log_index, int)
            or log_index < 0
        ):
            raise PublishError("Cosign bundle lacks trusted Rekor inclusion proof")
        return {
            "log_id": log_id,
            "log_index": log_index,
            "uuid": hashlib.sha256(canonicalized_body).hexdigest(),
            "inclusion_proof": True,
            "signed_entry_timestamp": True,
        }

    def publish(self) -> None:
        endpoint, proxy, trusted_root, log_ids, cosign_config, verification_key = self._config()
        digest = self._fresh_digest()
        self._assert_output_paths()
        try:
            self.runtime.get(endpoint)
            if proxy != endpoint:
                self.runtime.get(proxy)
        except OSError as exc:
            raise PublishError("private Rekor endpoint unavailable") from exc
        version = self.runtime.run([self.cosign, "version"])
        if version.returncode != 0 or COSIGN_VERSION not in version.stdout:
            raise PublishError("required Cosign v3.1.3 is unavailable")

        signing = _read_json(self.signing_config, "signing")
        temporary_bundle = self.bundle_out.with_name(f".{self.bundle_out.name}.tmp")
        temporary_bundle.unlink(missing_ok=True)
        try:
            # v3.1.3 uses a signing-config rather than a --rekor-url override.
            self._run_or_fail([self.cosign, "sign-blob", "--bundle", str(temporary_bundle), "--signing-config", cosign_config, "--key", signing["key_ref"], "--trusted-root", trusted_root, "--yes", str(self.artifact)], "signing")
            if _sha256(self.artifact) != digest:
                raise PublishError("canonical artifact changed while publishing")
            rekor = self._bundle_digest_and_proof(temporary_bundle, digest, log_ids)
            self._run_or_fail([self.cosign, "verify-blob", "--bundle", str(temporary_bundle), "--trusted-root", trusted_root, "--key", verification_key, str(self.artifact)], "verification")
            if _sha256(self.artifact) != digest:
                raise PublishError("canonical artifact changed while publishing")
            os.replace(temporary_bundle, self.bundle_out)
            artifact_ref = "health/latest.json" if self.run_id == f"health-{digest}" else str(self.artifact)
            _atomic_json(self.reference_out, {"artifact": artifact_ref, "artifact_sha256": digest, "bundle": self.bundle_out.name, "run_id": self.run_id, "schema": "datapulse/v1/sigstore-rekor-reference", "rekor": rekor})
            LOG.info("published additive Sigstore bundle for run_id=%s", self.run_id)
        except Exception:
            temporary_bundle.unlink(missing_ok=True)
            self.bundle_out.unlink(missing_ok=True)
            self.reference_out.unlink(missing_ok=True)
            raise


def publisher_from_args(argv: list[str] | None = None) -> Publisher:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact", required=True, type=Path)
    parser.add_argument("--bundle-out", required=True, type=Path)
    parser.add_argument("--reference-out", required=True, type=Path)
    parser.add_argument("--run-manifest", required=True, type=Path)
    parser.add_argument("--rekor-config", required=True, type=Path)
    parser.add_argument("--signing-config", required=True, type=Path)
    parser.add_argument("--run-id", required=True)
    pinned_cosign = Path("/usr/local/bin/cosign")
    parser.add_argument("--cosign", default=str(pinned_cosign) if pinned_cosign.is_file() and os.access(pinned_cosign, os.X_OK) else None)
    args = parser.parse_args(argv)
    if args.cosign is None:
        parser.error("--cosign is required when the pinned Cosign binary is unavailable")
    return Publisher(args.artifact, args.bundle_out, args.reference_out, args.run_manifest, args.rekor_config, args.signing_config, args.run_id, args.cosign)


def main() -> None:
    logging.basicConfig(level=os.environ.get("SIGSTORE_REKOR_PUBLISHER_LOG_LEVEL", "INFO"), format="%(message)s")
    publisher_from_args().publish()


if __name__ == "__main__":
    main()
