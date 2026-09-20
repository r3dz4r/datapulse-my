"""Byte-level contract tests for the DataPulse canonical JSON form.

The literal vectors in ``scripts/tests/fixtures/canonical_vectors.json`` are the
normative examples from ``specs/canonical-form.md``. These tests reuse
``canonical()`` from ``scripts.gen_attestations``; canonicalisation is never
reimplemented here.

The negative vectors are the important ones. Each one is a plausible but wrong
rendering of a payload that a lenient implementation could produce. The tests
assert that it does not match the canonical bytes and digest, and -- where the
vector says the wrong rendering is semantically equivalent -- that a
value-only comparison would have accepted it. That is the fail-closed proof:
byte comparison is the only thing standing between the two implementations.
"""

from __future__ import annotations

import base64
import hashlib
import json
from pathlib import Path
from typing import Any

import pytest
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from scripts.gen_attestations import canonical, sha

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "canonical_vectors.json"
VECTORS: dict[str, Any] = json.loads(FIXTURE.read_text(encoding="utf-8"))

POSITIVE: list[dict[str, Any]] = VECTORS["positive"]
NEGATIVE: list[dict[str, Any]] = VECTORS["negative"]
CANONICAL_FORM: list[dict[str, Any]] = VECTORS["canonical_form"]
KEYS: dict[str, dict[str, Any]] = {key["key_id"]: key for key in VECTORS["keys"]}
SIGNED_VECTORS: list[dict[str, Any]] = [*POSITIVE, *CANONICAL_FORM]

# Negative classes the specification requires. This guards the fixture against a
# class being deleted instead of fixed.
REQUIRED_NEGATIVE_CLASSES = frozenset(
    {
        "bom_prefixed",
        "trailing_newline_appended",
        "keys_reordered",
        "key_order_in_equivalent_object",
        "default_separator_whitespace",
        "indent_rendering",
        "float_value",
        "nan_value",
        "duplicate_keys",
        "ensure_ascii_rendering",
    }
)


def _reject_non_finite(token: str) -> object:
    """Reject NaN/Infinity the way a canonical verifier must."""
    raise ValueError(f"non-finite JSON number is not permitted in signed material: {token}")


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    """Reject duplicate object keys the way a canonical verifier must."""
    seen: set[str] = set()
    for key, _ in pairs:
        if key in seen:
            raise ValueError(f"duplicate JSON key is not permitted in signed material: {key}")
        seen.add(key)
    return dict(pairs)


def strict_load(text: str) -> Any:
    """Parse text as signed material: duplicates and non-finite numbers fail closed."""
    return json.loads(
        text,
        parse_constant=_reject_non_finite,
        object_pairs_hook=_reject_duplicate_keys,
    )


def _assert_no_floats(value: Any, where: str = "$") -> None:
    if isinstance(value, float):
        raise AssertionError(f"positive vector contains a prohibited float at {where}")
    if isinstance(value, dict):
        for key, item in value.items():
            _assert_no_floats(item, f"{where}.{key}")
    elif isinstance(value, list):
        for index, item in enumerate(value):
            _assert_no_floats(item, f"{where}[{index}]")


def _signature_verifies(public_key: Ed25519PublicKey, signature: bytes, payload: bytes) -> bool:
    """Return whether an Ed25519 signature authenticates the exact payload bytes."""
    try:
        public_key.verify(signature, payload)
    except InvalidSignature:
        return False
    return True


@pytest.mark.parametrize("vector", POSITIVE, ids=[v["name"] for v in POSITIVE])
def test_positive_vector_matches_bytes_and_digest(vector: dict[str, Any]) -> None:
    payload = vector["payload"]
    expected = vector["canonical_bytes"].encode("utf-8")

    produced = canonical(payload)

    assert produced == expected
    assert sha(produced) == vector["sha256"]
    # The stored expectation is internally consistent: hashing the exact
    # canonical byte string gives the recorded digest.
    assert hashlib.sha256(expected).hexdigest() == vector["sha256"]


@pytest.mark.parametrize("vector", SIGNED_VECTORS, ids=[v["name"] for v in SIGNED_VECTORS])
def test_signed_vector_verifies_exact_canonical_bytes_and_rejects_mutation(vector: dict[str, Any]) -> None:
    expected = vector["canonical_bytes"].encode("utf-8")
    payload = vector["payload"] if "payload" in vector else vector["payload_a"]
    signing = vector["signature"]
    key = KEYS[signing["key_id"]]
    signature = base64.b64decode(signing["signature_base64"], validate=True)
    public_key = Ed25519PublicKey.from_public_bytes(
        base64.b64decode(key["public_key_base64"], validate=True)
    )

    assert signing["algorithm"] == "Ed25519"
    assert key["algorithm"] == signing["algorithm"]
    assert canonical(payload) == expected
    assert _signature_verifies(public_key, signature, expected)

    mutated = bytearray(expected)
    mutated[-1] ^= 1
    assert not _signature_verifies(public_key, signature, bytes(mutated))


@pytest.mark.parametrize("vector", NEGATIVE, ids=[v["name"] for v in NEGATIVE])
def test_negative_vector_fails_closed(vector: dict[str, Any]) -> None:
    payload = json.loads(vector["payload_json"])
    canonical_bytes = canonical(payload)
    wrong = vector["wrong_bytes"].encode("utf-8")

    # Core assertion: the near-miss rendering does not match, byte-for-byte and
    # digest-for-digest. A verifier that compares digests must reject it.
    assert canonical_bytes != wrong
    assert sha(canonical_bytes) != sha(wrong)
    assert hashlib.sha256(canonical_bytes).hexdigest() != hashlib.sha256(wrong).hexdigest()

    # Prove the vector is not vacuous. When the wrong rendering is a faithful
    # encoding of the same logical value, a semantic-only comparison would have
    # accepted it; only the byte comparison catches it.
    if vector["wrong_bytes_semantically_equal"]:
        assert json.loads(vector["wrong_bytes"]) == payload

    # The specification requires a fail-closed parser to reject unsafe inputs.
    # Assert the strict parser actually raises rather than silently normalising.
    if vector["payload_rejected_by_strict_parser"]:
        with pytest.raises(ValueError):
            strict_load(vector["payload_json"])
    if vector["wrong_rejected_by_strict_parser"]:
        with pytest.raises(ValueError):
            strict_load(vector["wrong_bytes"])
    if vector["canonical_rejected_by_strict_parser"]:
        with pytest.raises(ValueError):
            strict_load(canonical_bytes.decode("utf-8"))


@pytest.mark.parametrize("vector", CANONICAL_FORM, ids=[v["name"] for v in CANONICAL_FORM])
def test_canonical_form_construction_paths_agree(vector: dict[str, Any]) -> None:
    payload_a = vector["payload_a"]
    payload_b = vector["payload_b"] if "payload_b" in vector else json.loads(vector["payload_b_json"])

    bytes_a = canonical(payload_a)
    bytes_b = canonical(payload_b)

    assert bytes_a == bytes_b
    assert bytes_a == vector["canonical_bytes"].encode("utf-8")
    assert sha(bytes_a) == vector["sha256"]
    assert sha(bytes_b) == vector["sha256"]


def test_positive_vectors_contain_no_floats() -> None:
    for vector in POSITIVE:
        _assert_no_floats(vector["payload"])


def test_fixture_covers_required_negative_classes() -> None:
    names = {vector["name"] for vector in NEGATIVE}
    assert REQUIRED_NEGATIVE_CLASSES <= names
