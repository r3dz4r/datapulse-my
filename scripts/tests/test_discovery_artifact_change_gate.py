#!/usr/bin/env python3
"""Exercise the required PR gate with discovery artifacts from the old base."""

from __future__ import annotations

import asyncio
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest
import yaml

from scripts import gen_mcp_reference
from scripts.classify_change import is_append_only_change, is_health_only_change
from scripts.tests.test_ci_required_gate_contract import _job_runs


ROOT = Path(__file__).resolve().parents[2]


def _test_step() -> dict:
    workflow = yaml.load(
        (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8"),
        Loader=yaml.BaseLoader,
    )
    job = workflow["jobs"]["deterministic-safety-net"]
    assert _job_runs("pull_request", "refs/pull/42/merge", "success", "false")
    assert _job_runs("merge_group", "refs/heads/gh-readonly-queue/main/pr-42", "success", "false")
    assert _job_runs("push", "refs/heads/some-branch", "success", "true")
    assert not _job_runs("push", "refs/heads/main", "success", "true")
    assert "continue-on-error" not in job
    checkout = next(step for step in job["steps"] if step.get("name") == "Check out repository")
    assert checkout["with"]["fetch-depth"] == "0"
    step = next(
        step for step in job["steps"]
        if step.get("name") == "Run repository-contract and MCP tests"
    )
    assert step["if"] == "env.FULL_VERIFICATION == 'true'"
    assert "continue-on-error" not in step
    assert "python3 -m pytest -q scripts/tests/ mcp/tests/" in step["run"]
    return step


def _git(root: Path, *args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=root, text=True).strip()


@pytest.mark.parametrize(
    ("changed_path", "stale_exit"),
    [
        ("mcp/server.py", 1),
        ("scripts/gen_per_dataset_receipt.py", 1),
        ("scripts/verify_per_dataset_receipt.py", 1),
        ("mcp/tests/test_future.py", 0),
        ("mcp/future-documentation.md", 0),
    ],
)
def test_pr_gate_checks_candidate_history_and_restores_default_ref(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, changed_path: str, stale_exit: int,
) -> None:
    """A runtime-only change must fail before it becomes default-branch history."""
    assert not is_health_only_change([changed_path], ci_artifact_profile=True)
    assert not is_append_only_change([changed_path])
    step = _test_step()
    # Exercise a non-main default branch too; the gate must use repository metadata.
    monkeypatch.delenv("DATAPULSE_SOURCE_COMMIT_SHA", raising=False)
    monkeypatch.delenv("DATAPULSE_SOURCE_COMMIT_DATE", raising=False)
    repository = tmp_path / "repository"
    repository.mkdir()
    for relative in (
        "datapulse.json", "health.schema.json", "mcp.schema.json", "agent.schema.json",
        "config/public-surfaces.json", "config/public-surfaces.schema.json",
        "README.md", "llms.txt", "docs/mcp-deploy.md", "mcp/server.py",
    ):
        target = repository / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / relative, target)
    _git(repository, "init", "-q", "--initial-branch=topic")
    _git(repository, "config", "user.name", "Discovery Gate Test")
    _git(repository, "config", "user.email", "discovery@example.invalid")
    _git(repository, "add", ".")
    _git(repository, "commit", "-qm", "base source")
    base_source = _git(repository, "rev-parse", "HEAD")
    asyncio.run(gen_mcp_reference.generate(repository, source_sha=base_source))
    _git(repository, "add", ".")
    _git(repository, "commit", "-qm", "base discovery artifacts")
    accepted_base = _git(repository, "rev-parse", "HEAD")
    default_ref = "refs/remotes/origin/trunk"
    _git(repository, "update-ref", default_ref, accepted_base)
    _git(repository, "symbolic-ref", "refs/remotes/origin/HEAD", default_ref)
    changed = repository / changed_path
    changed.parent.mkdir(parents=True, exist_ok=True)
    with changed.open("a", encoding="utf-8") as stream:
        stream.write("\n# Candidate change without discovery regeneration.\n")
    _git(repository, "add", changed_path)
    _git(repository, "commit", "-qm", "candidate source")
    # Reproduce the old false green: default-branch history still matches the artifacts.
    assert gen_mcp_reference._source_identity(repository, None, None)[0] == base_source

    provenance = tmp_path / "test_discovery_provenance.py"
    shutil.copy2(ROOT / "scripts/tests/test_discovery_provenance.py", provenance)
    # Keep all three real provenance assertions, changing only their fixture root.
    (tmp_path / "conftest.py").write_text(
        "from pathlib import Path\n"
        "def pytest_collection_modifyitems(items):\n"
        "    for item in items:\n"
        "        item.module.ROOT = Path(__file__).parent / 'repository'\n",
        encoding="utf-8",
    )
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    runner = fake_bin / "python3"
    runner.write_text(
        '#!/bin/bash\nset -Eeuo pipefail\n'
        '[[ "$*" == "-m pytest -q scripts/tests/ mcp/tests/" ]]\n'
        'exec "$TEST_PYTHON" -m pytest -q "$PROVENANCE_TEST"\n',
        encoding="utf-8",
    )
    runner.chmod(0o755)
    environment = os.environ | {
        "DEFAULT_BRANCH": "trunk",
        "PATH": f"{fake_bin}:{os.environ['PATH']}",
        "PYTHONPATH": str(ROOT),
        "TEST_PYTHON": sys.executable,
        "PROVENANCE_TEST": str(provenance),
    }

    def run_gate() -> subprocess.CompletedProcess[str]:
        result = subprocess.run(
            ["bash", "-c", step["run"]], cwd=repository, env=environment,
            capture_output=True, text=True, check=False,
        )
        assert _git(repository, "rev-parse", default_ref) == accepted_base
        assert _git(repository, "status", "--porcelain") == ""
        return result

    stale = run_gate()
    assert stale.returncode == stale_exit, stale.stdout + stale.stderr
    if stale_exit:
        assert "2 failed, 1 passed" in stale.stdout
        assert "agent.json source.commit_sha" in stale.stdout
        candidate_source = _git(repository, "log", "-1", "--format=%H", "HEAD", "--", changed_path)
        asyncio.run(gen_mcp_reference.generate(repository, source_sha=candidate_source))
        _git(repository, "add", ".")
        _git(repository, "commit", "-qm", "refresh candidate discovery artifacts")
        fresh = run_gate()
        assert fresh.returncode == 0, fresh.stdout + fresh.stderr
        assert "3 passed" in fresh.stdout
    else:
        assert "3 passed" in stale.stdout
    assert step.get("env", {}).get("DEFAULT_BRANCH") == (
        "${{ github.event.repository.default_branch }}"
    )
