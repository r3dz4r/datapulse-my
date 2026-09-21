"""Tests for the published canonical-form vector key and re-sign client."""

from __future__ import annotations

import base64
import hashlib
import json
import os
import socket
import subprocess
import sys
import threading
from pathlib import Path
from typing import Any

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat


ROOT = Path(__file__).resolve().parents[2]
KEYS_PATH = ROOT / "docs/.well-known/datapulse-vector-keys.json"
FIXTURE_PATH = ROOT / "scripts/tests/fixtures/canonical_vectors.json"
TOOL_PATH = ROOT / "scripts/resign_canonical_vectors.py"
KEY_ID = "ed25519-ca7f3249f56ab81b"
PUBLIC_KEY = "RDcwEtdEPEUO6llnqbkrhwArGBHY865+dvpORfEbOKk="
PURPOSE = "Signs canonical-form test vectors only; never observation receipts."


def canonical(value: Any) -> bytes:
    """Return the canonical bytes specified by canonical-form.md."""
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


class SignerStub:
    """One-request-per-connection signer that keeps its test key only in memory."""

    def __init__(self, path: Path, private_key: Ed25519PrivateKey, refuse_code: str | None = None) -> None:
        self.path = path
        self.private_key = private_key
        self.refuse_code = refuse_code
        self.requests: list[dict[str, Any]] = []
        self._stop = threading.Event()
        self._server: socket.socket | None = None
        self._thread: threading.Thread | None = None

    def __enter__(self) -> SignerStub:
        server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        server.bind(os.fspath(self.path))
        server.listen(8)
        self._server = server
        self._thread = threading.Thread(target=self._serve, daemon=True)
        self._thread.start()
        return self

    def __exit__(self, *_exc: object) -> None:
        self._stop.set()
        try:
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as waker:
                waker.connect(os.fspath(self.path))
        except OSError:
            pass
        assert self._thread is not None
        self._thread.join(timeout=5)
        assert self._server is not None
        self._server.close()
        try:
            self.path.unlink()
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
                request = self._read_request(connection)
                if request is None:
                    continue
                self.requests.append(request)
                if set(request) != {"purpose", "payload"} or request["purpose"] != "canonical-form-v1":
                    self._respond(connection, {"ok": False, "error": {"code": "unsupported_request"}})
                    continue
                if self.refuse_code is not None:
                    self._respond(connection, {"ok": False, "error": {"code": self.refuse_code}})
                    continue
                signature = self.private_key.sign(canonical(request["payload"]))
                self._respond(
                    connection,
                    {
                        "ok": True,
                        "signature_base64": base64.b64encode(signature).decode("ascii"),
                        "payload_sha256": hashlib.sha256(canonical(request["payload"])).hexdigest(),
                    },
                )

    @staticmethod
    def _read_request(connection: socket.socket) -> dict[str, Any] | None:
        data = bytearray()
        while b"\n" not in data:
            chunk = connection.recv(65536)
            if not chunk:
                return None
            data.extend(chunk)
        document = json.loads(bytes(data).split(b"\n", 1)[0].decode("utf-8"))
        return document if isinstance(document, dict) else None

    @staticmethod
    def _respond(connection: socket.socket, document: dict[str, Any]) -> None:
        connection.sendall(canonical(document) + b"\n")


def _write_test_registry(path: Path, private_key: Ed25519PrivateKey) -> dict[str, Any]:
    """Create a temporary public-only registry matching the ephemeral stub key."""
    public_key = base64.b64encode(
        private_key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
    ).decode("ascii")
    registry = json.loads(KEYS_PATH.read_text(encoding="utf-8"))
    registry["keys"][0]["public_key_base64"] = public_key
    path.write_text(json.dumps(registry), encoding="utf-8")
    return registry["keys"][0]


def _run_tool(socket_path: Path, fixture_path: Path, keys_path: Path) -> subprocess.CompletedProcess[str]:
    """Invoke the re-sign command exactly as an operator would."""
    return subprocess.run(
        [sys.executable, os.fspath(TOOL_PATH), "--socket", os.fspath(socket_path), "--fixture", os.fspath(fixture_path), "--keys", os.fspath(keys_path)],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )


def test_published_vector_key_is_self_describing_and_vector_only() -> None:
    """The public registry is independently usable without the fixture."""
    registry = json.loads(KEYS_PATH.read_text(encoding="utf-8"))
    assert registry["schema"] == "datapulse/v1/vector-key-registry"
    assert registry["version"] == 1
    assert registry["generated_at"].endswith("Z")
    assert registry["updated_at"].endswith("Z")
    key = next(entry for entry in registry["keys"] if entry["key_id"] == KEY_ID)
    assert key["status"] == "active"
    assert key["purpose"] == PURPOSE
    assert key["public_key_base64"] == PUBLIC_KEY
    assert key["algorithm"] == "Ed25519"
    assert key["not_before"].endswith("Z")
    assert key["not_after"].endswith("Z")
    Ed25519PublicKey.from_public_bytes(base64.b64decode(key["public_key_base64"], validate=True))


def test_resign_tool_rewrites_copy_only_after_stubbed_signatures_verify(tmp_path: Path) -> None:
    """A socket response replaces all signatures and every replacement verifies."""
    fixture_path = tmp_path / "canonical_vectors.json"
    fixture_path.write_bytes(FIXTURE_PATH.read_bytes())
    private_key = Ed25519PrivateKey.generate()
    keys_path = tmp_path / "vector-keys.json"
    key = _write_test_registry(keys_path, private_key)
    socket_path = tmp_path / "vectors.sock"

    with SignerStub(socket_path, private_key) as stub:
        result = _run_tool(socket_path, fixture_path, keys_path)

    assert result.returncode == 0, result.stderr
    document = json.loads(fixture_path.read_text(encoding="utf-8"))
    assert document["keys"] == [key]
    signed = [*document["positive"], *document["canonical_form"]]
    assert len(stub.requests) == len(signed)
    public_key = Ed25519PublicKey.from_public_bytes(base64.b64decode(key["public_key_base64"], validate=True))
    for vector, request in zip(signed, stub.requests, strict=True):
        payload = vector.get("payload", vector.get("payload_a"))
        assert request == {"purpose": "canonical-form-v1", "payload": payload}
        signature = base64.b64decode(vector["signature"]["signature_base64"], validate=True)
        public_key.verify(signature, canonical(payload))
        mutated = dict(payload)
        mutated["test_mutation"] = True
        try:
            public_key.verify(signature, canonical(mutated))
        except InvalidSignature:
            pass
        else:
            raise AssertionError("mutated vector payload unexpectedly verified")


def test_resign_tool_fails_closed_without_socket(tmp_path: Path) -> None:
    """An unavailable signer cannot modify even a copied fixture."""
    fixture_path = tmp_path / "canonical_vectors.json"
    fixture_path.write_bytes(FIXTURE_PATH.read_bytes())
    original = fixture_path.read_bytes()
    result = _run_tool(tmp_path / "missing.sock", fixture_path, KEYS_PATH)
    assert result.returncode != 0
    assert fixture_path.read_bytes() == original


def test_resign_tool_names_signer_refusal_code_and_preserves_fixture(tmp_path: Path) -> None:
    """A documented signer refusal is an error, not a successful re-sign."""
    fixture_path = tmp_path / "canonical_vectors.json"
    fixture_path.write_bytes(FIXTURE_PATH.read_bytes())
    original = fixture_path.read_bytes()
    private_key = Ed25519PrivateKey.generate()
    keys_path = tmp_path / "vector-keys.json"
    _write_test_registry(keys_path, private_key)
    socket_path = tmp_path / "vectors.sock"

    with SignerStub(socket_path, private_key, refuse_code="key_unavailable"):
        result = _run_tool(socket_path, fixture_path, keys_path)

    assert result.returncode != 0
    assert "key_unavailable" in result.stderr
    assert fixture_path.read_bytes() == original
