from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_workflow_uses_pinned_ci_runner_and_app_token() -> None:
    workflow = (ROOT / '.github/workflows/derive-surfaces.yml').read_text()
    runner = (ROOT / 'scripts/regenerate_surfaces.py').read_text()
    assert 'actions/create-github-app-token@v1' in workflow
    assert 'scripts/regenerate_surfaces.py --ci' in workflow
    assert "env['SOURCE_DATE_EPOCH'] = epoch" in runner
    assert 'DATAPULSE_SOURCE_COMMIT_DATE' not in workflow + runner
    assert 'git diff --quiet' in workflow
    assert "if: steps.derive.outputs.changed == 'true'" in workflow
    assert 'git switch' not in workflow and 'git checkout -b' not in workflow
    assert 'cancel-in-progress: false' in workflow
    assert 'health/history.jsonl' not in workflow


def test_classifier_uses_base_map_and_payload() -> None:
    ci = (ROOT / '.github/workflows/ci.yml').read_text()
    assert 'git show "$BASE_SHA:config/surface-owners.json"' in ci
    assert 'GITHUB_EVENT_PATH' in ci
    assert 'author.endswith("[bot]")' in ci
    assert 'datapulse-release' in ci


def test_classifier_enforces_base_owned_paths_for_unknown_and_human(tmp_path) -> None:
    import json
    import os
    import subprocess
    import sys

    ci = (ROOT / '.github/workflows/ci.yml').read_text()
    source = ci.split("              python3 -c '\n", 1)[1].split("\n          '\n", 1)[0]
    source = '\n'.join(line[10:] for line in source.splitlines())
    owners = [{'command': ['python3', 'generator.py'], 'surfaces': ['data/jsonld/**', 'health/drift.json'], 'derivable_in_ci': False, 'reason': 'history unavailable'}]
    (tmp_path / 'surface-owners-base.json').write_text(json.dumps(owners))
    (tmp_path / 'surface-changes.bin').write_bytes(b'data/jsonld/a.json\0')
    event_path = tmp_path / 'event.json'
    env = dict(os.environ, GITHUB_EVENT_PATH=str(event_path))

    def run(author):
        event_path.write_text(json.dumps({'pull_request': {'user': author}}))
        return subprocess.run([sys.executable, '-c', source], cwd=tmp_path, env=env, capture_output=True, text=True)

    assert run({'login': 'human'}).returncode != 0
    assert run(None).returncode != 0
    assert run({'login': 'datapulse-release'}).returncode == 0
    assert run({'login': 'any[bot]'}).returncode == 0
    (tmp_path / 'surface-owners-base.json').write_text('{')
    assert run({'login': 'any[bot]'}).returncode != 0


def test_failed_classifier_fails_required_safety_net() -> None:
    ci = (ROOT / '.github/workflows/ci.yml').read_text()
    safety_net = ci.split('  deterministic-safety-net:', 1)[1]
    gate = safety_net.split('      - name: Require successful pull request classification', 1)[1].split('      - name:', 1)[0]
    assert "needs.classify.result != 'success'" in gate
    assert 'exit 1' in gate
