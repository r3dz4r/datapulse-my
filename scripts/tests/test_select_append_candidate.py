"""Selector and workflow contracts for attestation append promotion."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[2]
SELECTOR = ROOT / "scripts/select_append_candidate.py"
WORKFLOW = ROOT / ".github/workflows/attestation-append-merge.yml"
DEPLOY_WORKFLOW = ROOT / ".github/workflows/deploy-cloudflare-pages.yml"


def _pull_request(number: int, head: str, created_at: str) -> dict[str, object]:
    return {"number": number, "headRefName": head, "createdAt": created_at}


def _select(rows: list[dict[str, object]], *, path: Path | None = None) -> subprocess.CompletedProcess[str]:
    if path is None:
        return subprocess.run(
            [sys.executable, str(SELECTOR)],
            input=json.dumps(rows),
            text=True,
            capture_output=True,
            check=False,
        )
    path.write_text(json.dumps(rows), encoding="utf-8")
    return subprocess.run(
        [sys.executable, str(SELECTOR), str(path)],
        text=True,
        capture_output=True,
        check=False,
    )


def test_newest_append_is_selected_from_file(tmp_path: Path) -> None:
    rows = [
        _pull_request(11, "attestation/append-old", "2026-10-09T00:01:00Z"),
        _pull_request(12, "attestation/append-new", "2026-10-09T00:02:00Z"),
    ]
    result = _select(rows, path=tmp_path / "prs.json")
    assert (result.returncode, result.stdout, result.stderr) == (0, "12\n", "")


def test_non_append_heads_are_ignored() -> None:
    rows = [
        _pull_request(11, "attestation/append-witness", "2026-10-09T00:01:00Z"),
        _pull_request(12, "session/other", "2026-10-09T00:02:00Z"),
        _pull_request(13, "health-automation", "2026-10-09T00:03:00Z"),
    ]
    result = _select(rows)
    assert (result.returncode, result.stdout, result.stderr) == (0, "11\n", "")


def test_empty_list_has_empty_output_and_succeeds() -> None:
    result = _select([])
    assert (result.returncode, result.stdout, result.stderr) == (0, "", "")


def test_older_open_sibling_is_not_selected() -> None:
    rows = [
        _pull_request(30, "attestation/append-older-sibling", "2026-10-09T00:01:00Z"),
        _pull_request(31, "attestation/append-newer-sibling", "2026-10-09T00:02:00Z"),
    ]
    result = _select(rows)
    assert (result.returncode, result.stdout, result.stderr) == (0, "31\n", "")
    assert result.stdout != "30\n"


def test_created_at_tie_selects_higher_number() -> None:
    rows = [
        _pull_request(42, "attestation/append-higher", "2026-10-09T00:01:00Z"),
        _pull_request(41, "attestation/append-lower", "2026-10-09T00:01:00Z"),
    ]
    result = _select(rows)
    assert (result.returncode, result.stdout, result.stderr) == (0, "42\n", "")


def test_append_merge_workflow_push_trigger_and_shape() -> None:
    workflow = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    triggers = workflow.get("on", workflow.get(True, {}))
    assert triggers == {"push": {"branches": ["attestation/append-*"]}}
    assert workflow["permissions"] == {"contents": "write", "pull-requests": "write"}
    assert workflow["concurrency"]["cancel-in-progress"] is False
    job = workflow["jobs"]["merge"]
    assert job["environment"] == "production"
    checkout = next(step for step in job["steps"] if step.get("uses") == "actions/checkout@v4")
    assert checkout["with"]["persist-credentials"] is False
    assert any(step.get("uses") == "actions/create-github-app-token@v1" for step in job["steps"])


def test_accepted_append_retriggers_pages_deploy() -> None:
    workflow = yaml.safe_load(DEPLOY_WORKFLOW.read_text(encoding="utf-8"))
    triggers = workflow.get("on", workflow.get(True, {}))
    assert "attestations/**" in triggers["push"]["paths"]
