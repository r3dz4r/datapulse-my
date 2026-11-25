#!/usr/bin/env python3
"""Materialise signed evidence separately from pinned publication data.

accepted-observation.json is a versioned, unsigned index of the daily signed
evidence. Its observed_at and published_at are the binding's two clocks;
source_commit identifies the pinned Git revision used to recover that evidence,
health_sha256 hashes the uncompressed snapshot at health_snapshot_ref, and
binding_ref identifies the signed envelope covering those exact bytes. It makes
no signature claim about the independently published health/latest.json.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

LOGGER = logging.getLogger(__name__)
MAX_AGE_SECONDS = 36 * 60 * 60
# Restore the pinned data build as a unit, including nested metadata and retained
# evidence. Code, templates, discovery and the independent release proof stay at
# the pinned publishing revision; the dashboard is rendered from those sources.
OBSERVATION_BUILD_PATHS = (
    'health', 'data', 'badges', 'deltas', 'record-evidence', 'feed.xml',
    'changelog.json', 'catalog-snapshot.json', 'catalog-graph.json',
    'datapulse_summary.json', 'docs/okf', 'docs/datasets', 'observation-receipts',
)


class SelectionError(ValueError):
    """Accepted inputs are missing, inconsistent, or expired."""


def atomic_write(path: Path, content: bytes) -> None:
    """Publish complete bytes within the isolated report directory."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + '.tmp')
    temporary.write_bytes(content)
    temporary.replace(path)


def report_age(health: Path, binding: Path, now: datetime) -> dict[str, Any]:
    """Measure both signed clocks, independently of the Pages deployment clock."""
    content = health.read_bytes()
    snapshot = json.loads(content)
    payload = json.loads(binding.read_bytes())["payload"]
    claim = payload["health"]
    ids = [row["dataset_id"] for row in snapshot["datasets"]]
    if (not ids or any(not isinstance(item, str) or not item for item in ids)
            or len(ids) != len(set(ids)) or type(claim.get('dataset_count')) is not int or claim != {
        "artifact_ref": "health/latest.json",
        "artifact_sha256": hashlib.sha256(content).hexdigest(),
        "dataset_count": len(ids),
        "dataset_ids_sha256": hashlib.sha256(json.dumps(sorted(ids), ensure_ascii=False,
            sort_keys=True, separators=(',', ':')).encode()).hexdigest(),
        "observed_at": snapshot["checked_at"],
    }):
        # A newer served snapshot needs independent exact-byte evidence. Keep
        # the accepted-set diagnostic when that evidence cannot be verified.
        from scripts.verify_attestation_binding import verify_contract

        try:
            if type(claim.get('dataset_count')) is not int:
                raise SelectionError('accepted binding count must be an integer')
            result = verify_contract(health.parent.parent, now=now)
            if result['daily_anchor']['health'] != claim or result['observation_receipt'] is None:
                raise SelectionError('receipt does not cover this binding')
        except (ValueError, KeyError, TypeError, OSError) as error:
            raise SelectionError("health digest/count/ids/observation time disagree with accepted binding") from error
    max_age = payload["freshness"]["max_age_seconds"]
    if type(max_age) is not int or max_age != MAX_AGE_SECONDS:
        raise SelectionError("signed report age policy must remain 36 hours")
    ages = []
    for value in (claim["observed_at"], payload["published_at"]):
        timestamp = datetime.fromisoformat(value.replace('Z', '+00:00'))
        if timestamp.tzinfo is None:
            raise SelectionError("report timestamps must include a UTC offset")
        ages.append((now - timestamp).total_seconds())
    observation_age = (now - datetime.fromisoformat(snapshot['checked_at'].replace('Z', '+00:00'))).total_seconds()
    return {
        "observed_at": snapshot["checked_at"], "published_at": payload["published_at"],
        "observation_age_seconds": observation_age, "envelope_age_seconds": ages[1],
        "max_age_seconds": MAX_AGE_SECONDS,
        "report_age_status": "current" if all(0 <= age <= MAX_AGE_SECONDS for age in [*ages, observation_age]) else "expired",
    }


def _archive_files(root: Path, revision: str, out: Path, paths: tuple[str, ...]) -> None:
    with subprocess.Popen([
        'git', 'archive', revision, *paths,
    ], cwd=root, stdout=subprocess.PIPE) as process:
        try:
            with tarfile.open(fileobj=process.stdout, mode='r|') as archive:
                for member in archive:
                    path = Path(member.name)
                    if path.is_absolute() or '..' in path.parts or not (member.isfile() or member.isdir()):
                        raise SelectionError(f"nonregular accepted input: {member.name}")
                    target = out / path
                    if member.isdir():
                        target.mkdir(parents=True, exist_ok=True)
                    else:
                        source = archive.extractfile(member)
                        if source is None:
                            raise SelectionError(f"unreadable accepted input: {member.name}")
                        with source:
                            atomic_write(target, source.read())
        except BaseException:
            process.terminate()
            process.wait()
            raise
        if process.wait():
            raise SelectionError("git archive failed for pinned accepted inputs")


def _export(root: Path, revision: str, out: Path) -> None:
    # Export only committed, regular source inputs; never trust a dirty checkout
    # or an untracked candidate, nor follow symlinks during materialisation.
    if out.exists():
        raise SelectionError("accepted report output must not already exist")
    out.parent.mkdir(parents=True, exist_ok=True)
    # Historical sibling selection needs first-parent merge order. Keep HEAD at
    # the pinned main commit so the unmodified verifier can prove that order.
    subprocess.run(['git', 'worktree', 'add', '--detach', '--no-checkout', str(out), revision],
                   cwd=root, check=True, capture_output=True)
    _archive_files(root, revision, out, (
        'attestations', 'datapulse.json', 'docs/.well-known/datapulse-probe-keys.json',
    ))


def restore_observation_build(root: Path, revision: str, publication: Path) -> str:
    """Recover pinned data without replacing the separately verified signing inputs."""
    identity_path = publication / 'publication-identity.json'
    identity = json.loads(identity_path.read_bytes())
    health_bytes = (publication / 'health/latest.json').read_bytes()
    if (re.fullmatch(r'[0-9a-f]{40}', revision) is None
            or identity['accepted_main_commit'] != revision
            or hashlib.sha256(health_bytes).hexdigest() != identity['health_sha256']):
        raise SelectionError('accepted observation build identity differs from pinned report')
    blob = subprocess.check_output(['git', 'hash-object', '--stdin'], input=health_bytes, cwd=root).decode().strip()
    # Follow only the pinned main ancestry. A candidate branch or a later main
    # observation can never supply accepted evidence, even if its date matches.
    candidates = subprocess.check_output([
        'git', 'log', '--first-parent', '--format=%H', revision, '--', 'health/latest.json',
    ], cwd=root, text=True).splitlines()
    source = None
    for commit in candidates:
        candidate = subprocess.check_output([
            'git', 'rev-parse', f'{commit}:health/latest.json',
        ], cwd=root, text=True).strip()
        if candidate == blob:
            source = commit
            break
    if source is None:
        raise SelectionError('no committed observation build matches the exact accepted health bytes')
    main_health = json.loads(subprocess.check_output([
        'git', 'show', f'{revision}:health/latest.json'], cwd=root))
    if identity.get('observation_receipt_ref'):
        pinned = subprocess.check_output(['git', 'show', f'{revision}:health/latest.json'], cwd=root)
        if pinned != health_bytes:
            raise SelectionError('no committed observation build matches the exact accepted health bytes')
        # A receipt-only commit can carry evidence missing from the health commit.
        source = revision
    # The 36-hour policy belongs to the signed evidence (checked by select_report
    # and report_age). Publication data must equal the pinned source, so its lag
    # relative to that source is zero; the daily append cadence cannot bound it.
    lag = {'main_observed_at': main_health['checked_at'], 'served_lag_seconds': 0,
           'served_lag_bound_seconds': 0, 'served_lag_health_commits': 0,
           'served_lag_status': 'pinned_source',
           'served_lag_cause': 'current: data equals main health at the pinned revision'}
    LOGGER.info('Served lag: %s', json.dumps(lag, sort_keys=True))
    paths = tuple(subprocess.check_output([
        'git', 'ls-tree', '--name-only', revision, '--', *OBSERVATION_BUILD_PATHS,
    ], cwd=root, text=True).splitlines())
    required = set(OBSERVATION_BUILD_PATHS) - {'docs/okf', 'docs/datasets', 'observation-receipts'}
    if not required <= set(paths):
        raise SelectionError('accepted observation build is incomplete: ' + ', '.join(sorted(required - set(paths))))
    with tempfile.TemporaryDirectory(prefix='accepted-build-', dir=publication.parent) as temporary:
        build = Path(temporary)
        _archive_files(root, revision, build, paths)
        pinned_bytes = subprocess.check_output(['git', 'show', f'{revision}:health/latest.json'], cwd=root)
        if (build / 'health/latest.json').read_bytes() != pinned_bytes:
            raise SelectionError('pinned data build health bytes changed')
        snapshot = json.loads((build / 'catalog-snapshot.json').read_bytes())
        graph = json.loads((build / 'catalog-graph.json').read_bytes())
        observed = main_health['checked_at']
        if not (snapshot['generated_at'] == snapshot['health']['checked_at']
                == graph['generated_at'] == observed):
            raise SelectionError('accepted observation build contains inconsistent clocks')
        for name in OBSERVATION_BUILD_PATHS:
            target = root / name
            if target.is_symlink() or target.is_file():
                target.unlink()
            elif target.exists():
                shutil.rmtree(target)
            origin = build / name
            if origin.is_dir():
                shutil.copytree(origin, target)
            elif origin.is_file():
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(origin, target)
    identity['accepted_observation_build_commit'] = source
    identity['observation_build_commit'] = revision
    identity['data_observed_at'] = observed
    identity['data_health_sha256'] = hashlib.sha256(pinned_bytes).hexdigest()
    identity.update(lag)
    atomic_write(identity_path, (json.dumps(identity, sort_keys=True, indent=2) + '\n').encode())
    LOGGER.info('Data observation build %s: health and catalogs observed at %s; signed accepted observation %s',
                revision, observed, identity.get('anchor_observed_at', identity['observed_at']))
    return revision


def prefer_receipt_covered_snapshot(root: Path, revision: str, out: Path, now: datetime) -> dict[str, Any] | None:
    """Prefer verified pinned cycle bytes; retain the accepted set otherwise."""
    from scripts.verify_attestation_binding import matching_snapshot_receipt, verify_contract

    accepted_bytes = (out / 'health/latest.json').read_bytes()
    receipt = None
    source = 'receipt_absent_fallback (accepted_set)'
    try:
        paths = tuple(subprocess.check_output([
            'git', 'ls-tree', '--name-only', revision, '--', 'observation-receipts',
        ], cwd=root, text=True).splitlines())
        if paths:
            _archive_files(root, revision, out, paths)
            content = subprocess.check_output(['git', 'show', f'{revision}:health/latest.json'], cwd=root)
            receipt = matching_snapshot_receipt(out, content, now)
            atomic_write(out / 'health/latest.json', content)
            # The unchanged verifier enforces membership, chronology, age and
            # the daily anchor as well as the receipt's exact artifact digest.
            verify_contract(out, now=now)
            source = 'receipt_covered_snapshot'
    except (ValueError, KeyError, TypeError, OSError, subprocess.CalledProcessError) as error:
        atomic_write(out / 'health/latest.json', accepted_bytes)
        receipt = None
        LOGGER.info('Receipt preference unavailable: %s', error)
    LOGGER.info('Health selection source: %s', source)
    return receipt


def select_report(root: Path, revision: str, out: Path, now: datetime) -> dict[str, Any]:
    """Resolve the accepted spine from Git and recover its signed health bytes."""
    from scripts.attestation_sets import FILES, set_directory, snapshot_content, verify_set
    from scripts.verify_attestation_append import accepted_discovery
    from scripts.verify_attestation_binding import verify_contract

    if re.fullmatch(r'[0-9a-f]{40}', revision) is None:
        raise SelectionError("accepted main commit must be a pinned full SHA")
    LOGGER.info('Resolve accepted main commit %s', revision)
    document = accepted_discovery(root, revision)
    head = document['current_head']
    _export(root, revision, out)
    directory = set_directory(document['heads'][head])
    revision_head = out / directory / 'revisions' / head / 'chain_head.json'
    if revision_head.is_file():
        directory = revision_head.parent.relative_to(out).as_posix()
    reference = directory + '/chain_head.json'
    LOGGER.info('Verify immutable accepted set %s', reference)
    verify_set(out, reference)
    binding = json.loads((out / directory / 'binding.json').read_bytes())
    claim = binding['payload']['health']
    snapshots = [out / directory / name for name in ('health.json', 'health.json.gz')
                 if (out / directory / name).is_file()]
    if len(snapshots) != 1:
        raise SelectionError(f"accepted set {directory} has no unique recoverable health snapshot")
    atomic_write(out / 'health/latest.json', snapshot_content(snapshots[0]))
    manifest_bytes = (out / 'datapulse.json').read_bytes()
    manifest = json.loads(manifest_bytes)
    index = json.loads((out / directory / 'index.json').read_bytes())
    ids = [row['id'] for row in manifest['datasets']]
    if len(ids) != len(set(ids)) or set(ids) != set(index['attestations']):
        raise SelectionError("pinned manifest membership differs from accepted report")
    for row in manifest['datasets']:
        envelope = json.loads((out / index['attestations'][row['id']]).read_bytes())
        if row['url'] != envelope['payload']['source_url']:
            raise SelectionError(f"pinned manifest source URL differs for {row['id']}")
    # These are projections of the accepted immutable set, never new envelopes.
    for name in FILES:
        atomic_write(out / 'attestations/latest' / name, (out / directory / name).read_bytes())
    atomic_write(out / 'attestations/chain-index.json',
                 (json.dumps(document, ensure_ascii=False, indent=2) + '\n').encode())
    atomic_write(out / '.attestations/chain_head.json', (out / reference).read_bytes())
    age = report_age(out / 'health/latest.json', out / directory / 'binding.json', now)
    LOGGER.info('Report age: %s', json.dumps(age, sort_keys=True))
    if age['report_age_status'] != 'current':
        raise SelectionError("accepted report exceeds 36 hours or has future timestamps")
    LOGGER.info('Verify materialised binding and accepted history')
    result = verify_contract(out, now=now)
    if result['health'] != claim or result['ed25519']['chain_head'] != head:
        raise SelectionError("materialised accepted report identity changed")
    # This index always names the daily signed binding and immutable snapshot.
    # Receipt preference below continues to select signing inputs exactly as
    # before; neither that choice nor newer publication data rewrites the anchor.
    accepted = {
        'schema': 'datapulse/v1/accepted-observation',
        'description': ('Unsigned index of signed accepted evidence; observed_at is the signed '
                        'observation clock, published_at is the envelope clock, source_commit is '
                        'the recovery revision, and health_sha256 hashes the uncompressed '
                        'health_snapshot_ref. binding_ref is the signed envelope. '
                        'This index does not attest the published health/latest.json.'),
        'observed_at': claim['observed_at'], 'published_at': age['published_at'],
        'source_commit': revision, 'health_sha256': claim['artifact_sha256'],
        'health_snapshot_ref': snapshots[0].relative_to(out).as_posix(),
        'binding_ref': directory + '/binding.json', 'chain_head_ref': reference,
        'accepted_chain_head': head, 'max_age_seconds': MAX_AGE_SECONDS,
    }
    atomic_write(out / 'accepted-observation.json',
                 (json.dumps(accepted, sort_keys=True, indent=2) + '\n').encode())
    data_bytes = subprocess.check_output(['git', 'show', f'{revision}:health/latest.json'], cwd=root)
    identity = {'accepted_main_commit': revision, 'accepted_chain_head': head,
                'health_sha256': claim['artifact_sha256'], 'dataset_count': claim['dataset_count'],
                'manifest_sha256': hashlib.sha256(manifest_bytes).hexdigest(),
                'health_snapshot_ref': snapshots[0].relative_to(out).as_posix(),
                'observed_at': age['observed_at'], 'published_at': age['published_at'],
                'data_observed_at': json.loads(data_bytes)['checked_at'],
                'data_health_sha256': hashlib.sha256(data_bytes).hexdigest(),
                'signed_observed_at': claim['observed_at'],
                'max_age_seconds': MAX_AGE_SECONDS}
    # Preserve every accepted-set precondition and diagnostic before considering
    # the optional cycle source. Absence never invalidates the accepted report.
    receipt = prefer_receipt_covered_snapshot(root, revision, out, now)
    if receipt is not None:
        age = report_age(out / 'health/latest.json', out / directory / 'binding.json', now)
        content = (out / 'health/latest.json').read_bytes()
        identity.update({
            'health_sha256': hashlib.sha256(content).hexdigest(),
            'health_snapshot_ref': 'health/latest.json',
            'anchor_health_snapshot_ref': snapshots[0].relative_to(out).as_posix(),
            'anchor_observed_at': claim['observed_at'],
            'observation_receipt_ref': receipt['reference'],
            'observation_receipt_id': receipt['receipt_id'],
            'receipt_observed_at': receipt['payload']['observed_at'],
            'observed_at': age['observed_at'],
        })
    atomic_write(out / 'publication-identity.json',
                 (json.dumps(identity, sort_keys=True, indent=2) + '\n').encode())
    return {**identity, **age}


def main() -> int:
    """Select a pinned report, or measure a served report without selecting one."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path('.'))
    parser.add_argument('--revision')
    parser.add_argument('--out', type=Path)
    parser.add_argument('--measure-age', action='store_true')
    parser.add_argument('--restore-observation-build', action='store_true')
    parser.add_argument('--publication', type=Path)
    parser.add_argument('--health', type=Path, default=Path('health/latest.json'))
    parser.add_argument('--binding', type=Path, default=Path('attestations/latest/binding.json'))
    parser.add_argument('--now')
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format='%(message)s', stream=sys.stdout)
    try:
        now = datetime.fromisoformat(args.now.replace('Z', '+00:00')) if args.now else datetime.now(timezone.utc)
        if now.tzinfo is None:
            raise SelectionError('verification time must include a UTC offset')
        if args.restore_observation_build:
            if not args.revision or args.publication is None:
                parser.error('--revision and --publication are required for build restoration')
            restore_observation_build(args.root.resolve(), args.revision, args.publication.resolve())
            identity = json.loads((args.publication / 'publication-identity.json').read_bytes())
            summary = os.environ.get('GITHUB_STEP_SUMMARY')
            if summary:
                with open(summary, 'a', encoding='utf-8') as output:
                    output.write(f"Data observation time: {identity['data_observed_at']}; "
                                 f"signed accepted observation time: {identity.get('signed_observed_at', identity['observed_at'])}; "
                                 f"signed evidence: accepted-observation.json. Data trails pinned source "
                                 f"by {identity['served_lag_seconds']}s ({identity['served_lag_health_commits']} health commits); "
                                 "data must equal pinned source; signed evidence policy remains 36h.\n")
            return 0
        if args.measure_age:
            identity = report_age(args.health, args.binding, now)
        else:
            if not args.revision or args.out is None:
                parser.error('--revision and --out are required for selection')
            identity = select_report(args.root.resolve(), args.revision, args.out.resolve(), now)
        LOGGER.info('%s', json.dumps(identity, sort_keys=True))
        summary = os.environ.get('GITHUB_STEP_SUMMARY')
        if summary:
            with open(summary, 'a', encoding='utf-8') as output:
                output.write(f"Data observation time: {identity.get('data_observed_at', 'not measured')}; "
                             f"signed accepted observation time: {identity.get('signed_observed_at', identity['observed_at'])}; "
                             f"signed evidence: accepted-observation.json; envelope published at {identity['published_at']}. "
                             f"Report age: {identity['observation_age_seconds']:.0f}s observed / "
                             f"{identity['envelope_age_seconds']:.0f}s published; policy 129600s (36h): "
                             f"{identity['report_age_status']}.\n")
        return 0 if identity['report_age_status'] == 'current' else 1
    except (ValueError, KeyError, TypeError, OSError, subprocess.CalledProcessError) as error:
        LOGGER.error('REFUSED: %s', error)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
