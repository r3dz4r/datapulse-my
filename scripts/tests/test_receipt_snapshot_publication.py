#!/usr/bin/env python3
"""Publish pinned snapshot bytes only with independently signed cycle evidence."""
from __future__ import annotations

import base64
import hashlib
import json
from datetime import datetime, timedelta
from pathlib import Path

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

from scripts import gen_attestations as ga
from scripts.select_accepted_health import SelectionError, select_report
from scripts.tests.test_attestation_binding import NOW, dump, load
from scripts.tests.test_attestation_projections import git
from scripts.tests.test_attestations import fixture_root
from scripts.verify_attestation_binding import ContractError, canonical, verify_contract


def write_snapshot_receipt(root: Path, payload_overrides: dict | None = None) -> Path:
    """Fixture for the requested raw-byte contract, independent of the producer."""
    content = (root / 'health/latest.json').read_bytes()
    health = json.loads(content)
    private = Ed25519PrivateKey.generate()
    registry_path = root / 'docs/.well-known/datapulse-probe-keys.json'
    registry = load(registry_path)
    registry['keys'] = [row for row in registry['keys'] if row['key_id'] != 'receipt-test']
    registry['keys'].append({
        'key_id': 'receipt-test', 'purpose': 'observation-receipt-signing',
        'public_key_base64': base64.b64encode(private.public_key().public_bytes(
            Encoding.Raw, PublicFormat.Raw)).decode(),
        'status': 'active', 'not_before': '2026-01-01T00:00:00Z',
        'not_after': '2027-01-01T00:00:00Z',
    })
    dump(registry_path, registry)
    day = health['checked_at'][:10]
    payload = {
        'schema': 'datapulse/v1/observation-receipt', 'cycle_date': day,
        'observed_at': health['checked_at'], 'artifact_path': 'health/latest.json',
        'health_artifact_sha256': hashlib.sha256(content).hexdigest(),
        'dataset_count': len(health['datasets']), 'key_id': 'receipt-test',
        'valid_until': (datetime.fromisoformat(health['checked_at'].replace('Z', '+00:00'))
                        + timedelta(hours=26)).isoformat(),
    }
    payload.update(payload_overrides or {})
    receipt = {'payload': payload,
               'receipt_id': hashlib.sha256(canonical(payload)).hexdigest(),
               'signature_base64': base64.b64encode(private.sign(canonical(payload))).decode()}
    path = root / f'observation-receipts/days/{day}.json'
    path.parent.mkdir(parents=True, exist_ok=True)
    dump(path, {'schema': 'datapulse/v1/observation-day', 'cycle_date': day,
                'receipts': [receipt]})
    return path


def pinned_snapshot(tmp_path: Path) -> tuple[Path, str, Path]:
    root, key = fixture_root(tmp_path / 'repo')
    ga.generate(root, key, NOW)
    health = load(root / 'health/latest.json')
    health['checked_at'] = '2026-08-15T02:00:00Z'
    health['datasets'][0]['last_checked'] = health['checked_at']
    dump(root / 'health/latest.json', health)
    receipt_path = write_snapshot_receipt(root)
    (root / '.gitignore').write_text('private.json\n')
    git(root, 'init', '-b', 'main')
    git(root, 'config', 'user.name', 'Test')
    git(root, 'config', 'user.email', 'test@example.test')
    git(root, 'add', '-A')
    git(root, 'commit', '-m', 'daily anchor and receipt-covered newer snapshot')
    return root, git(root, 'rev-parse', 'HEAD'), receipt_path


def test_matching_receipt_publishes_exact_pinned_bytes_and_preserves_daily_anchor(tmp_path: Path) -> None:
    root, revision, _ = pinned_snapshot(tmp_path)
    content = (root / 'health/latest.json').read_bytes()
    anchor = {p.relative_to(root): p.read_bytes() for base in ('attestations', '.attestations')
              for p in (root / base).rglob('*') if p.is_file()}
    # A dirty checkout must never supply the published snapshot or receipt.
    (root / 'health/latest.json').write_text('{}')
    out = tmp_path / 'publication'
    result = select_report(root, revision, out, NOW + timedelta(hours=2))
    assert (out / 'health/latest.json').read_bytes() == content
    for path, original in anchor.items():
        assert (out / path).read_bytes() == original, path
    verification = verify_contract(out, now=NOW + timedelta(hours=2))
    assert verification['health']['artifact_sha256'] == hashlib.sha256(content).hexdigest()
    assert verification['daily_anchor']['health'] == load(out / 'attestations/latest/binding.json')['payload']['health']
    assert result['observed_at'] == '2026-08-15T02:00:00Z'
    assert result['anchor_observed_at'] == '2026-08-15T00:00:00Z'
    assert result['health_snapshot_ref'] == 'health/latest.json'
    assert result['observation_receipt_ref'] == 'observation-receipts/days/2026-08-15.json'


@pytest.mark.parametrize('damage', ['missing', 'different_hash', 'bad_signature'])
@pytest.mark.parametrize('snapshot_kind', ['daily', 'newer'])
def test_selector_fails_closed_before_writing_snapshot(tmp_path: Path, damage: str, snapshot_kind: str) -> None:
    root, _, receipt_path = pinned_snapshot(tmp_path)
    if snapshot_kind == 'daily':
        from scripts.attestation_sets import selected_directory, snapshot_content
        content = snapshot_content(root / selected_directory(root) / 'health.json.gz')
        (root / 'health/latest.json').write_bytes(content)
        receipt_path = write_snapshot_receipt(root)
    digest = hashlib.sha256((root / 'health/latest.json').read_bytes()).hexdigest()
    if damage == 'missing':
        receipt_path.unlink()
    else:
        document = load(receipt_path)
        receipt = document['receipts'][0]
        if damage == 'different_hash':
            receipt['payload']['health_artifact_sha256'] = '0' * 64
        else:
            receipt['signature_base64'] = base64.b64encode(b'\0' * 64).decode()
        dump(receipt_path, document)
    git(root, 'add', '-A')
    git(root, 'commit', '-m', 'damaged cycle evidence')
    out = tmp_path / 'publication'
    with pytest.raises((SelectionError, ContractError)) as error:
        select_report(root, git(root, 'rev-parse', 'HEAD'), out, NOW + timedelta(hours=2))
    assert digest in str(error.value)
    assert 'observation-receipts/days/2026-08-15.json' in str(error.value)
    assert not (out / 'health/latest.json').exists()


@pytest.mark.parametrize('damage', ['missing', 'bad_signature', 'bad_chain', 'wrong_purpose',
                                    'expired_receipt', 'wrong_count', 'wrong_cycle', 'normalized_digest',
                                    'future_receipt', 'wrong_path', 'different_dataset'])
def test_fresher_served_snapshot_requires_valid_receipt_and_daily_chain(tmp_path: Path, damage: str) -> None:
    root, _, receipt_path = pinned_snapshot(tmp_path)
    if damage == 'missing':
        receipt_path.unlink()
    elif damage == 'bad_chain':
        path = root / 'attestations/latest/chain_head.json'
        document = load(path)
        document['chain_head'] = '0' * 64
        dump(path, document)
    elif damage == 'wrong_purpose':
        path = root / 'docs/.well-known/datapulse-probe-keys.json'
        document = load(path)
        document['keys'][-1]['purpose'] = 'attestation-chain-signing'
        dump(path, document)
    elif damage == 'different_dataset':
        health = load(root / 'health/latest.json')
        health['datasets'][0]['dataset_id'] = 'other'
        dump(root / 'health/latest.json', health)
        write_snapshot_receipt(root)
    else:
        document = load(receipt_path)
        receipt = document['receipts'][0]
        if damage == 'bad_signature':
            receipt['signature_base64'] = base64.b64encode(b'\0' * 64).decode()
        else:
            changes = {
                'expired_receipt': {'valid_until': '2026-08-15T01:30:00Z'},
                'wrong_count': {'dataset_count': 2},
                'wrong_cycle': {'cycle_date': '2026-08-14'},
                'future_receipt': {'observed_at': '2026-08-15T04:00:00Z'},
                'wrong_path': {'artifact_path': 'health/other.json'},
            }
            if damage == 'normalized_digest':
                from scripts.observation_receipt import normalized_health_digest
                changes[damage] = {'health_artifact_sha256': normalized_health_digest(
                    load(root / 'health/latest.json'))}
            write_snapshot_receipt(root, changes[damage])
        if damage == 'bad_signature':
            dump(receipt_path, document)
    with pytest.raises(ContractError):
        verify_contract(root, now=NOW + timedelta(hours=2), allow_newer_health=True)
