#!/usr/bin/env python3
"""Probe the served attestation question against a local checkout.

Main's raw ``health/latest.json`` is auto-merged every cycle while a binding is
minted and landed later, so a plain main checkout is always ahead of the binding
it carries and can never verify. Production never serves that pairing: Pages
publishes what ``select_accepted_health.select_report`` materialises at a pinned
main commit, namely the accepted set's own health snapshot beside projections of
that same set. This probe materialises exactly that publication in a disposable
worktree and lets the unmodified selector and verifier refuse it.

Exit status: 0 verified, 1 refused (materialised publication and its binding
disagree, or the accepted evidence is invalid), 2 unverifiable (the publication
could not be materialised, so nothing was checked).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import logging
import signal
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.select_accepted_health import select_report  # noqa: E402
from scripts.verify_attestation_binding import ContractError  # noqa: E402

VERIFIED, REFUSED, UNVERIFIABLE = 0, 1, 2


class Unverifiable(RuntimeError):
    """The served publication could not be materialised, so it was not checked."""


class Refused(ValueError):
    """The materialised publication does not verify against its binding."""


def resolve_revision(root: Path, revision: str) -> str:
    """Pin a revision name to the full commit SHA the selector requires."""
    try:
        return subprocess.run(
            ['git', 'rev-parse', '--verify', '--quiet', f'{revision}^{{commit}}'],
            cwd=root, check=True, capture_output=True, text=True,
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError) as error:
        raise Unverifiable(f'cannot resolve revision {revision!r} in {root}') from error


def _remove_worktree(root: Path, out: Path) -> None:
    # select_report registers its output as a detached worktree of root. Remove
    # only that registration; other sessions' worktrees are not ours to prune.
    if not out.exists():
        return
    result = subprocess.run(['git', 'worktree', 'remove', '--force', str(out)],
                            cwd=root, capture_output=True, text=True, check=False)
    if result.returncode:
        print(f'probe_attestation.py: warning: could not remove probe worktree {out}: '
              f'{result.stderr.strip()}', file=sys.stderr)


def probe(root: Path, revision: str, now: datetime) -> dict[str, Any]:
    """Materialise the accepted publication at revision and verify it."""
    pinned = resolve_revision(root, revision)
    with tempfile.TemporaryDirectory(prefix='attestation-probe-') as temporary:
        out = Path(temporary) / 'publication'
        try:
            identity = select_report(root, pinned, out, now)
            health = (out / 'health/latest.json').read_bytes()
            binding = json.loads((out / 'attestations/latest/binding.json').read_bytes())
        except ContractError as error:
            raise Refused(str(error)) from error
        except Exception as error:
            # Past this point the accepted health bytes are on disk, so the
            # selector examined the publication itself and refused it.
            if (out / 'health/latest.json').is_file():
                raise Refused(f'{type(error).__name__}: {error}') from error
            raise Unverifiable(f'cannot materialise accepted publication at {pinned}: '
                               f'{type(error).__name__}: {error}') from error
        finally:
            _remove_worktree(root, out)
    # The digest lives at payload.health.artifact_sha256; there is no top-level
    # health_sha256. Re-read it by that path so a missing field can never match.
    health_sha256 = hashlib.sha256(health).hexdigest()
    payload = binding.get('payload') if isinstance(binding, dict) else None
    claim = payload.get('health') if isinstance(payload, dict) else None
    bound = claim.get('artifact_sha256') if isinstance(claim, dict) else None
    if not isinstance(bound, str) or bound != health_sha256 or identity['health_sha256'] != bound:
        raise Refused(f'materialised health {health_sha256} is not bound (binding carries {bound!r})')
    return {
        'schema': 'datapulse/v1/attestation-probe-result',
        'status': 'verified',
        'materialisation': 'select_accepted_health.select_report',
        'accepted_main_commit': pinned,
        'accepted_chain_head': identity['accepted_chain_head'],
        'health_sha256': health_sha256,
        'bound_health_sha256': bound,
        'health_bytes': len(health),
        'claims': binding.get('claims'),
        'report_age_status': identity['report_age_status'],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parent.parent)
    parser.add_argument('--revision', default='origin/main',
                        help='main commit or ref to probe (not fetched; default: origin/main)')
    parser.add_argument('--now')
    args = parser.parse_args(argv)
    # Selector progress goes to stderr so stdout carries only the verdict.
    logging.basicConfig(level=logging.INFO, format='%(message)s', stream=sys.stderr)
    try:
        now = datetime.fromisoformat(args.now.replace('Z', '+00:00')) if args.now else datetime.now(timezone.utc)
        if now.tzinfo is None:
            raise Unverifiable('verification time must include a UTC offset')
        result = probe(args.root.resolve(), args.revision, now)
    except Refused as error:
        print(f'probe_attestation.py: REFUSED: {error}')
        return REFUSED
    except (Unverifiable, ValueError) as error:
        print(f'probe_attestation.py: UNVERIFIABLE: {error}')
        return UNVERIFIABLE
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, separators=(',', ':')))
    return VERIFIED


def _terminated(*_: object) -> None:
    # SystemExit bypasses the verdict handlers, so termination is never a refusal.
    print('probe_attestation.py: UNVERIFIABLE: terminated before verification completed', flush=True)
    sys.exit(UNVERIFIABLE)


if __name__ == '__main__':
    # Unwind on SIGTERM so the probe worktree is removed, and say it was not checked.
    signal.signal(signal.SIGTERM, _terminated)
    raise SystemExit(main())
