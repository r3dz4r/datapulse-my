#!/usr/bin/env python3
"""Regenerate the surfaces listed in config/surface-owners.json."""
from __future__ import annotations

import argparse
import json
import glob
import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
OWNERS = ROOT / 'config/surface-owners.json'
AUTHOR_NAME = 'datapulse-derive[bot]'
AUTHOR_EMAIL = 'datapulse-derive[bot]@users.noreply.github.com'
LOG_DIR = ROOT / 'var/derive-surfaces'


def load_owners(path: Path = OWNERS) -> list[dict]:
    """Read and validate the ordered ownership map."""
    value = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(value, list) or not value:
        raise ValueError('ownership map must be a nonempty list')
    for row in value:
        if not isinstance(row, dict) or not isinstance(row.get('command'), list) or len(row['command']) < 2 or not all(isinstance(x, str) and x for x in row['command']):
            raise ValueError('invalid generator command')
        if not isinstance(row.get('surfaces'), list) or not row['surfaces'] or not all(isinstance(x, str) and x and not x.startswith('/') and '..' not in Path(x).parts for x in row['surfaces']):
            raise ValueError('invalid owned surfaces')
        if type(row.get('derivable_in_ci')) is not bool or (not row['derivable_in_ci'] and not isinstance(row.get('reason'), str)) or (not row['derivable_in_ci'] and not row['reason'].strip()):
            raise ValueError('invalid CI derivability or missing reason')
        if 'clean_directory' in row and row['clean_directory'] != 'data/passports':
            raise ValueError('invalid clean directory')
    return value


def pin() -> tuple[str, str]:
    """Select the newest committer timestamp not authored by this lane."""
    result = subprocess.run(['git', 'log', '--format=%H%x09%ct%x09%an%x09%ae'], cwd=ROOT, text=True, capture_output=True, check=True)
    for line in result.stdout.splitlines():
        commit, epoch, author, email = line.split('\t', 3)
        if (author, email) != (AUTHOR_NAME, AUTHOR_EMAIL):
            return commit, epoch
    raise ValueError('no commit outside the derive lane')


def changed_paths(owners: list[dict]) -> set[str]:
    """List owned paths differing from HEAD, including new untracked files."""
    import fnmatch
    tracked = subprocess.run(['git', 'diff', '--name-only', '-z', 'HEAD'], cwd=ROOT, capture_output=True, check=True).stdout
    untracked = subprocess.run(['git', 'ls-files', '--others', '--exclude-standard', '-z'], cwd=ROOT, capture_output=True, check=True).stdout
    patterns = [surface for row in owners for surface in row['surfaces']]
    return {os.fsdecode(p) for p in (tracked + untracked).split(b'\0') if p and any(fnmatch.fnmatchcase(os.fsdecode(p), pattern) for pattern in patterns)}


def surface_fingerprints(owners: list[dict]) -> dict[str, str]:
    """Fingerprint all owned files, including ignored build outputs."""
    paths: set[Path] = set()
    for row in owners:
        for pattern in row['surfaces']:
            for name in glob.glob(str(ROOT / pattern), recursive=True):
                path = Path(name)
                if path.is_file():
                    paths.add(path)
    return {str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest() for path in paths}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--ci', action='store_true')
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()
    try:
        owners = load_owners()
        commit, epoch = pin()
        if not args.dry_run:
            LOG_DIR.mkdir(parents=True, exist_ok=True)
            (LOG_DIR / 'pin.txt').write_text(f'commit={commit}\nSOURCE_DATE_EPOCH={epoch}\n', encoding='utf-8')
        env = os.environ.copy()
        env['SOURCE_DATE_EPOCH'] = epoch
        selected = []
        for row in owners:
            if args.ci and not row['derivable_in_ci']:
                for surface in row['surfaces']:
                    print(f"Skipping {surface}: {row['reason']}")
            else:
                selected.append(row)
                if args.dry_run:
                    print(f"Run {' '.join(row['command'])}")
        if not args.dry_run:
            # Some owners consume earlier outputs but run before their writers.
            # Repeat the ordered sequence until the whole surface set settles.
            for _ in range(4):
                before = surface_fingerprints(selected)
                for row in selected:
                    name = Path(row['command'][1]).name
                    if 'clean_directory' in row:
                        directory = ROOT / row['clean_directory']
                        if directory.exists():
                            shutil.rmtree(directory)
                    log = LOG_DIR / f'{name}.log'
                    with log.open('w', encoding='utf-8') as output:
                        result = subprocess.run(row['command'], cwd=ROOT, env=env, stdout=output, stderr=subprocess.STDOUT, check=False)
                    if result.returncode:
                        print(f'{name} failed with exit {result.returncode}; log: {log}; pin {commit} ({epoch})', file=sys.stderr)
                        return result.returncode if result.returncode > 0 else 1
                if surface_fingerprints(selected) == before:
                    break
            else:
                raise ValueError(f'owned surfaces did not converge after four passes; pin {commit} ({epoch}); see generator logs')
        if not args.dry_run:
            changed = changed_paths(owners)
            if changed:
                print(f'{len(changed)} surfaces changed')
                if args.check:
                    return 1
        return 0
    except (OSError, ValueError, json.JSONDecodeError, subprocess.CalledProcessError) as error:
        print(f'regeneration refused: {error}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
