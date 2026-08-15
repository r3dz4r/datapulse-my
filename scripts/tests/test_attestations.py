from __future__ import annotations

import base64
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
from cryptography.hazmat.primitives.serialization import Encoding, NoEncryption, PrivateFormat, PublicFormat

from scripts import gen_attestations as ga


def write(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value) + "\n")


def fixture_root(tmp_path: Path) -> tuple[Path, Path]:
    private = Ed25519PrivateKey.generate()
    raw = private.private_bytes(Encoding.Raw, PrivateFormat.Raw, NoEncryption())
    pub = private.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
    key_id = "ed25519-test"
    key = tmp_path / "private.json"
    write(key, {"key_id": key_id, "private_key_base64": base64.b64encode(raw).decode(), "public_key_base64": base64.b64encode(pub).decode()})
    write(tmp_path / "docs/.well-known/datapulse-probe-keys.json", {"schema":"datapulse/v1/probe-key-registry", "keys":[{"key_id":key_id,"public_key_base64":base64.b64encode(pub).decode(),"not_before":"2026-01-01T00:00:00Z","not_after":"2027-01-01T00:00:00Z","status":"active"}]})
    write(tmp_path / "datapulse.json", {"datasets":[{"id":"sample","name":"Sample","source":"Agency","url":"https://example.test/data","refresh_frequency":"daily"}]})
    write(tmp_path / "health/latest.json", {"checked_at":"2026-08-15T00:00:00Z","datasets":[{"dataset_id":"sample","last_checked":"2026-08-15T00:00:00Z","request_url":"https://example.test/data","access_dependency":"direct","status":"fresh","staleness_days":0,"first_row_hash":"shape-v1:"+"a"*64}]})
    write(tmp_path / "health/trends.json", {"datasets":[{"dataset_id":"sample","publish_on_time_pct":100,"trend":"stable"}]})
    write(tmp_path / "health/drift.json", {"datasets":[{"dataset_id":"sample","verdict":"stable"}]})
    write(tmp_path / "health/reconciliation.json", {"groups":[]})
    (tmp_path / "health/history.jsonl").write_text(json.dumps({"dataset_id":"sample","observed_at":"2026-08-15T00:00:00Z"})+"\n")
    return tmp_path, key


def test_generator_signs_daily_digest_and_chain(tmp_path: Path):
    root, key = fixture_root(tmp_path)
    ga.generate(root, key, datetime(2026, 8, 15, 1, tzinfo=timezone.utc))
    env = json.loads((root / "attestations/2026-08-15/sample.json").read_text())
    payload = env["payload"]
    Ed25519PublicKey.from_public_bytes(base64.b64decode(payload["signer_pubkey_base64"])).verify(base64.b64decode(env["signature_base64"]), ga.canonical(payload))
    assert env["chain_link"] == ga.sha(bytes.fromhex(payload["previous_chain_head"])+ga.canonical(payload))
    assert payload["probe_count_24h"] == 1 and payload["content_fingerprint"]["scope"] == "first-row-or-headers"


def test_signed_manifest_url_tamper_invalidates_signature(tmp_path: Path):
    root, key = fixture_root(tmp_path); ga.generate(root, key, datetime(2026, 8, 15, 1, tzinfo=timezone.utc))
    env = json.loads((root / "attestations/2026-08-15/sample.json").read_text()); env["payload"]["source_url"] = "https://attacker.test/data"
    with pytest.raises(InvalidSignature):
        Ed25519PublicKey.from_public_bytes(base64.b64decode(env["payload"]["signer_pubkey_base64"])).verify(base64.b64decode(env["signature_base64"]), ga.canonical(env["payload"]))


def test_second_day_links_to_first_day(tmp_path: Path):
    root, key = fixture_root(tmp_path); ga.generate(root, key, datetime(2026, 8, 15, 1, tzinfo=timezone.utc)); first = json.loads((root / "attestations/latest/chain_head.json").read_text())["chain_head"]
    ga.generate(root, key, datetime(2026, 8, 16, 1, tzinfo=timezone.utc)); second = json.loads((root / "attestations/latest/chain_head.json").read_text())
    assert second["payload"]["previous_chain_head"] == first and second["chain_head"] != first


def test_browser_digest_does_not_invent_receipt(tmp_path: Path):
    root, key = fixture_root(tmp_path); health = json.loads((root / "health/latest.json").read_text()); health["datasets"][0].update(access_dependency="browser", first_row_hash=None); write(root / "health/latest.json", health)
    ga.generate(root, key, datetime(2026, 8, 15, 1, tzinfo=timezone.utc)); payload = json.loads((root / "attestations/2026-08-15/sample.json").read_text())["payload"]
    assert payload["content_fingerprint"] is None and payload["browser_receipt"]["available"] is False


def test_methodology_v1_exact_score(tmp_path: Path):
    root, key = fixture_root(tmp_path); ga.generate(root, key, datetime(2026, 8, 15, 1, tzinfo=timezone.utc)); row = json.loads((root / "attestations/latest/scores.json").read_text())["datasets"][0]
    assert row["components"] == {"freshness":100,"reliability":100,"trend":75,"drift":100,"cross_source_agreement":50}
    assert row["score"] == 90.0 and row["methodology_version"] == 1


def test_canonical_json_is_utf8_sorted_and_compact() -> None:
    assert ga.canonical({"é": "✓", "a": 1}) == b'{"a":1,"\xc3\xa9":"\xe2\x9c\x93"}'


def test_missing_shape_fingerprint_is_null(tmp_path: Path):
    root, key = fixture_root(tmp_path)
    health = json.loads((root / "health/latest.json").read_text()); health["datasets"][0].pop("first_row_hash")
    write(root / "health/latest.json", health)
    ga.generate(root, key, datetime(2026, 8, 15, 1, tzinfo=timezone.utc))
    payload = json.loads((root / "attestations/2026-08-15/sample.json").read_text())["payload"]
    assert payload["content_fingerprint"] is None


def test_key_registry_rejects_expired_signer(tmp_path: Path):
    root, key = fixture_root(tmp_path)
    registry = json.loads((root / "docs/.well-known/datapulse-probe-keys.json").read_text()); registry["keys"][0]["not_after"] = "2026-08-01T00:00:00Z"
    write(root / "docs/.well-known/datapulse-probe-keys.json", registry)
    with pytest.raises(ValueError, match="not active"):
        ga.generate(root, key, datetime(2026, 8, 15, 1, tzinfo=timezone.utc))


def test_init_key_refuses_overwrite(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    path = tmp_path / "key.json"; path.write_text("{}")
    monkeypatch.setattr("sys.argv", ["init_keys.py", "--private-key", str(path), "--registry", str(tmp_path / "registry.json")])
    with pytest.raises(SystemExit, match="refusing to overwrite"):
        __import__("scripts.init_keys", fromlist=["main"]).main()
