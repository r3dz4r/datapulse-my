"""Selector and workflow contracts for attestation append promotion."""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

from scripts.select_append_candidate import _append_day, select_superseded_siblings

import yaml


ROOT = Path(__file__).resolve().parents[2]
SELECTOR = ROOT / "scripts/select_append_candidate.py"
WORKFLOW = ROOT / ".github/workflows/attestation-append-merge.yml"
DEPLOY_WORKFLOW = ROOT / ".github/workflows/deploy-cloudflare-pages.yml"
APPEND_PRODUCER = ROOT / "scripts/submit_attestation_append.sh"


def _produced_title(day: str) -> str:
    producer = APPEND_PRODUCER.read_text(encoding="utf-8")
    match = re.search(r'--title "([^"\n]+)"', producer)
    assert match is not None
    template = match.group(1)
    assert "$day" in template
    return template.replace("$day", day)


def test_append_day_matches_producer_title() -> None:
    day = "2026-10-09"
    assert _append_day({"title": _produced_title(day)}) == day


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


def test_oldest_append_is_selected_from_file(tmp_path: Path) -> None:
    rows = [
        _pull_request(11, "attestation/append-old", "2026-10-09T00:01:00Z"),
        _pull_request(12, "attestation/append-new", "2026-10-09T00:02:00Z"),
    ]
    result = _select(rows, path=tmp_path / "prs.json")
    assert (result.returncode, result.stdout, result.stderr) == (0, "11\n", "")


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


def test_older_open_append_is_retained() -> None:
    rows = [
        _pull_request(30, "attestation/append-older-sibling", "2026-10-09T00:01:00Z"),
        _pull_request(31, "attestation/append-newer-sibling", "2026-10-09T00:02:00Z"),
    ]
    result = _select(rows)
    assert (result.returncode, result.stdout, result.stderr) == (0, "30\n", "")
    assert result.stdout != "31\n"


def test_created_at_tie_selects_lower_number() -> None:
    rows = [
        _pull_request(42, "attestation/append-higher", "2026-10-09T00:01:00Z"),
        _pull_request(41, "attestation/append-lower", "2026-10-09T00:01:00Z"),
    ]
    result = _select(rows)
    assert (result.returncode, result.stdout, result.stderr) == (0, "41\n", "")


def test_same_day_does_not_prove_supersession() -> None:
    def row(number: int, day: str, state: str = "OPEN") -> dict[str, object]:
        result = _pull_request(number, f"attestation/append-{number}", f"2026-10-{number:02d}T00:00:00Z")
        result.update(title=_produced_title(day), state=state)
        return result

    rows = [row(50, "2026-10-09"), row(48, "2026-10-09"), row(47, "2026-10-09"), row(49, "2026-10-09", "CLOSED"), row(51, "2026-10-10")]
    assert select_superseded_siblings(rows, 50) == []


def test_close_only_same_day_exact_blob_subset_after_merge() -> None:
    first = "attestations/2026-10-09/revisions/" + "a" * 64 + "/chain_head.json"
    second = "attestations/2026-10-09/revisions/" + "b" * 64 + "/chain_head.json"

    def file(path: str, sha: str = "1" * 40) -> dict[str, str]:
        return {"filename": path, "sha": sha, "status": "added"}

    def row(number: int, state: str, day: str, files: list[dict[str, str]]) -> dict[str, object]:
        return {
            "number": number, "state": state, "title": _produced_title(day),
            "headRefName": f"attestation/append-{number}", "files": files,
        }

    merged = row(50, "MERGED", "2026-10-09", [file(first), file(second)])
    rows = [
        merged,
        row(48, "OPEN", "2026-10-09", [file(first)]),
        row(47, "OPEN", "2026-10-09", [file(first, "2" * 40)]),
        row(46, "OPEN", "2026-10-09", [file("attestations/2026-10-09/revisions/" + "c" * 64 + "/chain_head.json")]),
        row(45, "OPEN", "2026-10-10", [file(first)]),
        row(44, "OPEN", "2026-10-09", []),
    ]
    assert select_superseded_siblings(rows, 50) == [48]
    assert select_superseded_siblings([{**merged, "state": "OPEN"}, *rows[1:]], 50) == []


def test_conflicting_or_failed_append_does_not_starve_compatible_evidence() -> None:
    rows = [
        {**_pull_request(1, "attestation/append-conflicting", "2026-10-09T00:01:00Z"), "mergeable": "CONFLICTING"},
        {**_pull_request(2, "attestation/append-fork", "2026-10-09T00:02:00Z"),
         "statusCheckRollup": [{"conclusion": "FAILURE"}]},
        _pull_request(3, "attestation/append-compatible", "2026-10-09T00:03:00Z"),
    ]
    assert _select(rows).stdout == "3\n"


def test_append_merge_workflow_push_trigger_and_shape() -> None:
    workflow = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    triggers = workflow.get("on", workflow.get(True, {}))
    assert {"push", "schedule", "workflow_dispatch"} <= set(triggers)
    assert triggers["push"] == {"branches": ["attestation/append-*"]}
    assert triggers["schedule"] == [{"cron": "37 * * * *"}]
    assert triggers["workflow_dispatch"] is None
    assert workflow["permissions"] == {"contents": "write", "pull-requests": "write"}
    assert workflow["concurrency"]["cancel-in-progress"] is False
    job = workflow["jobs"]["merge"]
    assert job["environment"] == "production"
    checkout = next(step for step in job["steps"] if step.get("uses") == "actions/checkout@v4")
    assert checkout["with"]["persist-credentials"] is False
    assert any(step.get("uses") == "actions/create-github-app-token@v1" for step in job["steps"])


def test_append_merge_workflow_run_trigger_tracks_append_ci() -> None:
    workflow = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    triggers = workflow.get("on", workflow.get(True, {}))
    assert triggers["workflow_run"] == {
        "workflows": ["Pull request CI"],
        "types": ["completed"],
        "branches": ["attestation/append-*"],
    }


def test_append_merge_workflow_run_requires_same_repository() -> None:
    workflow = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    job = workflow["jobs"]["merge"]
    condition = job["if"]
    assert "needs.check_production_ref.outputs.admitted == 'true'" in condition
    assert "github.event_name != 'workflow_run'" in condition
    assert "github.event.workflow_run.head_repository.full_name == github.repository" in condition
    assert job["needs"] == "check_production_ref"
    assert job["environment"] == "production"


def test_accepted_append_retriggers_pages_deploy() -> None:
    workflow = yaml.safe_load(DEPLOY_WORKFLOW.read_text(encoding="utf-8"))
    triggers = workflow.get("on", workflow.get(True, {}))
    assert "attestations/**" in triggers["push"]["paths"]


def _run_candidate_step(
    tmp_path: Path, rows: list[dict[str, object]], *, event: str, ref: str
) -> tuple[subprocess.CompletedProcess[str], Path]:
    workflow = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    step = next(step for step in workflow["jobs"]["merge"]["steps"] if step.get("id") == "candidate")
    bin_path = tmp_path / "bin"
    bin_path.mkdir()
    gh = bin_path / "gh"
    gh.write_text('#!/bin/sh\nprintf "%s\\n" "$FAKE_PR_LIST"\n', encoding="utf-8")
    gh.chmod(0o755)
    output = tmp_path / "github-output"
    env = {
        **os.environ,
        "PATH": f"{bin_path}:{os.environ['PATH']}",
        "FAKE_PR_LIST": json.dumps(rows),
        "RUNNER_TEMP": str(tmp_path),
        "GITHUB_EVENT_NAME": event,
        "GITHUB_REF_NAME": ref,
        "GITHUB_OUTPUT": str(output),
    }
    result = subprocess.run(
        ["bash", "-c", step["run"]],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
        timeout=5,
    )
    return result, output


def test_scheduled_append_merge_exits_early_without_open_append(tmp_path: Path) -> None:
    rows = [_pull_request(5, "session/other", "2026-10-09T00:01:00Z")]
    result, output = _run_candidate_step(tmp_path, rows, event="schedule", ref="main")
    assert (result.returncode, result.stdout, result.stderr) == (
        0,
        "No open attestation append pull request; nothing to do.\n",
        "",
    )
    assert not output.exists()


def test_scheduled_append_merge_selects_oldest_from_main(tmp_path: Path) -> None:
    rows = [
        _pull_request(30, "attestation/append-older", "2026-10-09T00:01:00Z"),
        _pull_request(31, "attestation/append-newer", "2026-10-09T00:02:00Z"),
    ]
    result, output = _run_candidate_step(tmp_path, rows, event="schedule", ref="main")
    assert result.returncode == 0, result.stderr
    assert result.stdout == "Selected pull request #30 for attestation/append-older.\n"
    assert output.read_text(encoding="utf-8") == "number=30\n"


def test_push_for_later_append_waits_without_arming(tmp_path: Path) -> None:
    rows = [
        _pull_request(30, "attestation/append-older", "2026-10-09T00:01:00Z"),
        _pull_request(31, "attestation/append-newer", "2026-10-09T00:02:00Z"),
    ]
    result, output = _run_candidate_step(
        tmp_path, rows, event="push", ref="attestation/append-newer"
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout == (
        "Waiting append attestation/append-newer; "
        "oldest append is #30 (attestation/append-older).\n"
    )
    assert not output.exists()
