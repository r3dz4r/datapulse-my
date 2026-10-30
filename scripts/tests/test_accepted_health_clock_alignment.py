"""Exercise canonical binding against an accepted H0 and a newer checkout H1."""
from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from datetime import datetime, timedelta, timezone

import pytest
import yaml

from scripts import gen_attestations as ga
from scripts.select_accepted_health import SelectionError, restore_observation_build
from scripts.tests.test_attestation_projections import git
from scripts.tests.test_attestations import fixture_root

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / '.github/workflows/deploy-cloudflare-pages.yml'
DERIVED_CLOCKS = ('health/trends.json', 'health/drift.json', 'health/reconciliation.json',
                  'health/evidence-coverage.json', 'health/probe_counts.json')


def _step(name: str, job: str = 'deploy') -> str:
    workflow = yaml.safe_load(WORKFLOW.read_text())
    return next(step['run'] for step in workflow['jobs'][job]['steps']
                if step.get('name') == name)


def _run(root: Path, env: dict[str, str], command: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(['bash', '-c', command], cwd=root, env=env,
                          text=True, capture_output=True, timeout=120)


def _write(path: Path, document: dict) -> None:
    path.write_text(json.dumps(document, indent=2) + '\n')


@pytest.fixture(scope='module')
def bound_observation(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, dict[str, str], str, str]:
    """Use real local artifacts, generators, signatures and the unmodified gate."""
    temporary = tmp_path_factory.mktemp('accepted-clock')
    root, key = fixture_root(temporary / 'repo')
    registry = (root / 'docs/.well-known/datapulse-probe-keys.json').read_bytes()
    # No live reads and no writes to the source checkout. All generation is isolated.
    for directory in ('scripts', 'mcp', 'config', 'docs', 'data', 'health', 'badges',
                      'deltas', 'record-evidence'):
        shutil.copytree(ROOT / directory, root / directory, dirs_exist_ok=True,
                        ignore=shutil.ignore_patterns('__pycache__', '.pytest_cache',
                                                     'history.jsonl', 'as_of', 'staging-signed-health'))
    for name in ('datapulse.json', 'datapulse.schema.json', 'health.schema.json',
                 'agent.json', 'mcp.json', 'agent.schema.json', 'mcp.schema.json', 'record-evidence.schema.json',
                 'llms.txt', 'catalog-snapshot.json', 'catalog-graph.json',
                 'datapulse_summary.json', 'changelog.json', 'feed.xml'):
        shutil.copy2(ROOT / name, root / name)
    (root / 'docs/.well-known/datapulse-probe-keys.json').write_bytes(registry)
    (root / '.gitignore').write_text('private.json\n__pycache__/\n')
    now = datetime.now(timezone.utc).replace(microsecond=0)
    observed = (now - timedelta(hours=2)).isoformat().replace('+00:00', 'Z')
    newer = now.isoformat().replace('+00:00', 'Z')
    health = json.loads((root / 'health/latest.json').read_bytes())
    health['checked_at'] = observed
    _write(root / 'health/latest.json', health)
    for name in DERIVED_CLOCKS:
        document = json.loads((root / name).read_bytes())
        document['generated_at'] = observed
        _write(root / name, document)
    env = os.environ | {'PATH': f'{Path(sys.executable).parent}:{os.environ["PATH"]}',
                        'DATAPULSE_PYTHON_BIN': sys.executable,
                        'RUNNER_TEMP': str(temporary / 'runner'),
                        'GITHUB_OUTPUT': str(temporary / 'output'),
                        'GITHUB_STEP_SUMMARY': str(temporary / 'summary')}
    Path(env['RUNNER_TEMP']).mkdir()
    git(root, 'init', '-b', 'main')
    git(root, 'config', 'user.name', 'Test')
    git(root, 'config', 'user.email', 'test@example.test')
    ga.generate(root, key, now - timedelta(hours=1))
    generate = 'python3 scripts/gen_catalog_snapshot.py\npython3 scripts/gen_catalog_graph.py'
    result = _run(root, env, generate)
    assert result.returncode == 0, result.stdout + result.stderr
    git(root, 'add', '-A')
    git(root, 'commit', '-m', 'accepted observation build H0')
    env['ACCEPTED_BUILD_SHA'] = git(root, 'rev-parse', 'HEAD')
    # H1 carries a complete newer build. Replacing only its health is the defect.
    health['checked_at'] = newer
    _write(root / 'health/latest.json', health)
    for name in DERIVED_CLOCKS:
        document = json.loads((root / name).read_bytes())
        document['generated_at'] = newer
        _write(root / name, document)
    result = _run(root, env, generate)
    assert result.returncode == 0, result.stdout + result.stderr
    git(root, 'add', '-A')
    git(root, 'commit', '-m', 'newer checkout build H1')
    env['PROMOTION_SOURCE_SHA'] = git(root, 'rev-parse', 'HEAD')
    result = _run(root, env, _step('Select and verify pinned accepted health report', 'sign_health'))
    assert result.returncode == 0, result.stdout + result.stderr
    git(root, 'restore', '.')
    assert json.loads((root / 'health/latest.json').read_bytes())['checked_at'] == newer
    result = _run(root, env, _step('Bind built dashboard to accepted sign-time trust plane'))
    assert result.returncode == 0, result.stdout + result.stderr
    assert 'Post-deploy release invariants: PASS' in result.stdout
    return root, env, observed, newer


def test_binding_publishes_one_accepted_observation_and_discloses_it(bound_observation) -> None:
    root, env, observed, newer = bound_observation
    assert observed < newer
    snapshot = json.loads((root / 'catalog-snapshot.json').read_bytes())
    assert snapshot['generated_at'] == snapshot['health']['checked_at'] == observed
    assert json.loads((root / 'catalog-graph.json').read_bytes())['generated_at'] == observed
    assert json.loads((root / 'health/latest.json').read_bytes())['checked_at'] == observed
    for name in DERIVED_CLOCKS:
        assert json.loads((root / name).read_bytes())['generated_at'] == observed, name
    site = root / '_site'
    site.mkdir()
    for name in ('health', 'attestations', '.attestations'):
        shutil.copytree(root / name, site / name)
    shutil.copy2(root / 'datapulse.json', site / 'datapulse.json')
    shutil.copy2(root / 'docs/index.html', site / 'index.html')
    env = env | {'ACCEPTED_MAIN_COMMIT': env['PROMOTION_SOURCE_SHA'], 'ACCEPTED_OBSERVED_AT': observed}
    result = _run(root, env, _step('Verify accepted report identity and disclose observation time'))
    assert result.returncode == 0, result.stdout + result.stderr
    assert f'<time datetime="{observed}">{observed}</time>' in (site / 'index.html').read_text()
    identity = json.loads((site / 'publication-identity.json').read_bytes())
    assert identity['observed_at'] == observed
    assert identity['observation_build_commit'] == env['ACCEPTED_BUILD_SHA']
    assert identity['observation_build_commit'] != env['PROMOTION_SOURCE_SHA']


@pytest.mark.parametrize('path,keys', [
    ('catalog-snapshot.json', ('generated_at',)),
    ('catalog-snapshot.json', ('health', 'checked_at')),
    ('catalog-graph.json', ('generated_at',)),
])
def test_mixed_observation_clocks_still_fail_the_real_invariant(bound_observation, path, keys) -> None:
    root, env, _, newer = bound_observation
    target = root / path
    original = target.read_bytes()
    document = json.loads(original)
    value = document
    for key in keys[:-1]:
        value = value[key]
    value[keys[-1]] = newer
    try:
        _write(target, document)
        result = _run(root, env, 'bash scripts/verify_release_invariants.sh --local')
        assert result.returncode != 0, result.stdout + result.stderr
        assert 'AssertionError' in result.stderr
        assert 'Post-deploy release invariants: PASS' not in result.stdout
    finally:
        target.write_bytes(original)


@pytest.mark.parametrize('damage', ['uncommitted_bytes', 'incomplete_build'])
def test_binding_refuses_missing_build_provenance_before_overwriting_checkout(tmp_path: Path, damage: str) -> None:
    import hashlib

    from scripts.tests.test_deploy_cloudflare_pages_contract import _accepted_workflow_case, _select_step

    root, revision, _, env = _accepted_workflow_case(tmp_path)
    result = _run(root, env, _select_step()['run'])
    assert result.returncode == 0, result.stdout + result.stderr
    publication = Path(env['RUNNER_TEMP']) / 'sigstore-publication'
    git(root, 'restore', '.')
    before = (root / 'health/latest.json').read_bytes()
    if damage == 'uncommitted_bytes':
        snapshot = publication / 'health/latest.json'
        snapshot.write_bytes(snapshot.read_bytes() + b' ')
        identity_path = publication / 'publication-identity.json'
        identity = json.loads(identity_path.read_bytes())
        identity['health_sha256'] = hashlib.sha256(snapshot.read_bytes()).hexdigest()
        _write(identity_path, identity)
        message = 'no committed observation build matches'
    else:
        message = 'accepted observation build is incomplete'
    with pytest.raises(SelectionError, match=message):
        restore_observation_build(root, revision, publication)
    assert (root / 'health/latest.json').read_bytes() == before
