from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_owner_order_and_ci_exclusions() -> None:
    owners = json.loads((ROOT / 'config/surface-owners.json').read_text())
    assert [Path(row['command'][1]).name for row in owners] == [
        f'gen_{name}.py' for name in (
            'quality_profile', 'catalog_snapshot', 'catalog_graph', 'dataset_passports',
            'trends', 'drift', 'evidence_coverage', 'public_summary', 'readme',
            'ai_catalog', 'mcp_reference', 'llms_summary', 'jsonld_catalog', 'reconciliation',
        )
    ]
    assert {Path(row['command'][1]).stem for row in owners if not row['derivable_in_ci']} == {
        'gen_trends', 'gen_drift', 'gen_evidence_coverage'
    }
    assert all(row.get('reason') for row in owners if not row['derivable_in_ci'])


def test_pin_ignores_only_derive_author(tmp_path, monkeypatch) -> None:
    import importlib.util
    import os
    import subprocess

    spec = importlib.util.spec_from_file_location('regen', ROOT / 'scripts/regenerate_surfaces.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, 'ROOT', tmp_path)
    subprocess.run(['git', 'init', '-q'], cwd=tmp_path, check=True)
    subprocess.run(['git', 'config', 'user.name', 'human'], cwd=tmp_path, check=True)
    subprocess.run(['git', 'config', 'user.email', 'human@example.invalid'], cwd=tmp_path, check=True)

    def commit(name, email, date):
        env = dict(os.environ, GIT_AUTHOR_NAME=name, GIT_AUTHOR_EMAIL=email,
                   GIT_COMMITTER_DATE=date, GIT_AUTHOR_DATE=date)
        subprocess.run(['git', 'commit', '--allow-empty', '-qm', 'test'], cwd=tmp_path, env=env, check=True)

    commit('human', 'human@example.invalid', '2024-01-01T00:00:00Z')
    original = module.pin()
    commit(module.AUTHOR_NAME, module.AUTHOR_EMAIL, '2024-01-02T00:00:00Z')
    assert module.pin() == original
    commit('datapulse-release[bot]', 'release@example.invalid', '2024-01-03T00:00:00Z')
    assert module.pin() != original
    assert module.pin()[1] == '1704240000'


def test_pinned_public_summary_clock(monkeypatch) -> None:
    from scripts.gen_public_summary import _now_iso
    monkeypatch.setenv('SOURCE_DATE_EPOCH', '1700000000')
    assert _now_iso() == '2023-11-14T22:13:20+00:00'


def test_runner_ci_skip_failure_and_check(tmp_path, monkeypatch, capsys) -> None:
    import importlib.util
    import subprocess
    import sys

    spec = importlib.util.spec_from_file_location('regen', ROOT / 'scripts/regenerate_surfaces.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, 'ROOT', tmp_path)
    monkeypatch.setattr(module, 'LOG_DIR', tmp_path / 'logs')
    monkeypatch.setattr(module, 'pin', lambda: ('a' * 40, '1700000000'))
    subprocess.run(['git', 'init', '-q'], cwd=tmp_path, check=True)
    subprocess.run(['git', 'config', 'user.name', 'test'], cwd=tmp_path, check=True)
    subprocess.run(['git', 'config', 'user.email', 'test@example.invalid'], cwd=tmp_path, check=True)
    (tmp_path / 'surface').write_text('stale')
    subprocess.run(['git', 'add', 'surface'], cwd=tmp_path, check=True)
    subprocess.run(['git', 'commit', '-qm', 'base'], cwd=tmp_path, check=True)
    generator = tmp_path / 'generator.py'
    generator.write_text("from pathlib import Path\nPath('surface').write_text('fresh')\n")
    rows = [dict(command=[sys.executable, str(generator)], surfaces=['surface'], derivable_in_ci=True)]
    rows += [dict(command=[sys.executable, 'unused.py'], surfaces=[name], derivable_in_ci=False, reason='runtime history required') for name in ('trends', 'drift', 'coverage')]
    monkeypatch.setattr(module, 'load_owners', lambda: rows)
    monkeypatch.setattr(sys, 'argv', ['runner', '--ci', '--check'])
    assert module.main() == 1
    output = capsys.readouterr().out
    assert all(name in output for name in ('trends', 'drift', 'coverage'))
    assert (tmp_path / 'surface').read_text() == 'fresh'
    subprocess.run(['git', 'add', 'surface'], cwd=tmp_path, check=True)
    subprocess.run(['git', 'commit', '-qm', 'fresh'], cwd=tmp_path, check=True)
    assert module.main() == 0
    capsys.readouterr()
    generator.write_text('raise SystemExit(7)\n')
    assert module.main() == 7
    assert 'generator.py' in capsys.readouterr().err
    monkeypatch.setattr(sys, 'argv', ['runner', '--dry-run'])
    assert module.main() == 0
    assert capsys.readouterr().out.count('unused.py') == 3


def test_real_map_dry_run_skips_only_non_ci_owners() -> None:
    import subprocess
    import sys

    cmd = [sys.executable, 'scripts/regenerate_surfaces.py', '--dry-run']
    default = subprocess.run(cmd, cwd=ROOT, check=True, text=True, capture_output=True).stdout
    ci = subprocess.run(cmd + ['--ci'], cwd=ROOT, check=True, text=True, capture_output=True).stdout
    for name in ('trends', 'drift', 'evidence_coverage'):
        assert f'gen_{name}.py' in default
        assert f'gen_{name}.py' not in ci
    for surface in ('health/trends.json', 'health/drift.json', 'health/evidence-coverage.json'):
        assert f'Skipping {surface}:' in ci


def test_runner_converges_backward_dependencies(tmp_path, monkeypatch, capsys) -> None:
    import importlib.util
    import subprocess
    import sys

    spec = importlib.util.spec_from_file_location('regen', ROOT / 'scripts/regenerate_surfaces.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, 'ROOT', tmp_path)
    monkeypatch.setattr(module, 'LOG_DIR', tmp_path / 'logs')
    monkeypatch.setattr(module, 'pin', lambda: ('b' * 40, '1700000000'))
    subprocess.run(['git', 'init', '-q'], cwd=tmp_path, check=True)
    subprocess.run(['git', 'config', 'user.name', 'test'], cwd=tmp_path, check=True)
    subprocess.run(['git', 'config', 'user.email', 'test@example.invalid'], cwd=tmp_path, check=True)
    (tmp_path / 'input').write_text('old')
    (tmp_path / 'output').write_text('old')
    subprocess.run(['git', 'add', 'input', 'output'], cwd=tmp_path, check=True)
    subprocess.run(['git', 'commit', '-qm', 'base'], cwd=tmp_path, check=True)
    first = tmp_path / 'first.py'
    first.write_text("from pathlib import Path\nPath('output').write_bytes(Path('input').read_bytes())\n")
    second = tmp_path / 'second.py'
    second.write_text("from pathlib import Path\nPath('input').write_text('new')\n")
    owners = [dict(command=[sys.executable, str(script)], surfaces=[surface], derivable_in_ci=True) for script, surface in ((first, 'output'), (second, 'input'))]
    monkeypatch.setattr(module, 'load_owners', lambda: owners)
    monkeypatch.setattr(sys, 'argv', ['runner'])
    assert module.main() == 0
    assert (tmp_path / 'output').read_text() == 'new'
    before = ((tmp_path / 'input').read_bytes(), (tmp_path / 'output').read_bytes())
    assert module.main() == 0
    assert ((tmp_path / 'input').read_bytes(), (tmp_path / 'output').read_bytes()) == before
    assert 'SOURCE_DATE_EPOCH=1700000000' in (tmp_path / 'logs/pin.txt').read_text()
