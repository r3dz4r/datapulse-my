#!/usr/bin/env python3
"""Execute the workflow's actual policy and orchestration without network access."""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

import pytest
import yaml


WORKFLOW = Path(__file__).resolve().parents[2] / ".github/workflows/session-branch-reaper.yml"
REPOSITORY = "r3dz4r/datapulse-my"
BRANCH = "session/finished"
SHA = "a" * 40


def _workflow() -> dict:
    return yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))


def _script() -> str:
    return _workflow()["jobs"]["reap"]["steps"][0]["with"]["script"]


def _node(source: str, data: object) -> object:
    result = subprocess.run(
        ["node", "-e", source], input=json.dumps(data), text=True,
        capture_output=True, check=True, timeout=10,
    )
    return json.loads(result.stdout)


def _branch(name: str = BRANCH, protected: bool = False) -> dict:
    return {"name": name, "protected": protected, "commit": {"sha": SHA}}


def _pull(name: str = BRANCH, state: str = "closed", merged: bool = True) -> dict:
    return {
        "number": 1, "state": state, "merged_at": "2026-11-01T00:00:00Z" if merged else None,
        "head": {"ref": name, "sha": SHA, "repo": {"full_name": REPOSITORY}},
    }


def _verdict(branch: dict, pulls: list[dict], script: str | None = None) -> dict:
    function = re.search(r"(?ms)^function deletionVerdict\(.*?^\}", script or _script())
    assert function is not None, "workflow must expose its single deletion guard"
    source = function.group(0) + """
const args = JSON.parse(require('fs').readFileSync(0, 'utf8'));
console.log(JSON.stringify(deletionVerdict(...args)));
"""
    return _node(source, [branch, pulls, REPOSITORY])


def test_workflow_shape_and_least_privilege() -> None:
    workflow = _workflow()
    # PyYAML uses YAML 1.1, where an unquoted `on` becomes True.
    triggers = workflow.get("on", workflow.get(True))
    assert set(triggers) == {"pull_request", "workflow_dispatch"}
    assert triggers["pull_request"] == {"types": ["closed"]}
    dry_run = triggers["workflow_dispatch"]["inputs"]["dry_run"]
    assert dry_run["type"] == "boolean" and dry_run["default"] is True
    assert workflow["permissions"] == {}
    assert set(workflow["jobs"]) == {"reap"}
    job = workflow["jobs"]["reap"]
    assert job["permissions"] == {"contents": "write"}
    condition = job["if"]
    for gate in ("workflow_dispatch", "pull_request", "'closed'", "'session/'",
                 "head.repo.full_name", "github.repository", "pull_request.state"):
        assert gate in condition
    assert len(job["steps"]) == 1
    step = job["steps"][0]
    assert step["uses"].startswith("actions/github-script@")
    assert step["with"]["github-token"] == "${{ github.token }}"
    assert "${{" not in step["with"]["script"], "PR data must never become executable code"
    assert "secrets." not in WORKFLOW.read_text(encoding="utf-8")


@pytest.mark.parametrize("name", ["main", "health-automation", "health-snapshots",
                                      "release-please--branches--main", "release-please--anything"])
def test_guard_refuses_reserved_refs(name: str) -> None:
    verdict = _verdict(_branch(name), [_pull(name)])
    assert verdict == {"delete": False, "reason": "reserved ref"}


@pytest.mark.parametrize("name", ["feature/work", "session", "session/", "release/v1"])
def test_guard_refuses_non_session_refs(name: str) -> None:
    assert _verdict(_branch(name), [_pull(name)])["delete"] is False


def test_guard_refuses_protected_session_ref() -> None:
    assert _verdict(_branch(protected=True), [_pull()]) == {
        "delete": False, "reason": "protected or protection unknown",
    }


def test_guard_refuses_open_pr_even_with_an_older_closed_pr() -> None:
    assert _verdict(_branch(), [_pull(), _pull(state="open")]) == {
        "delete": False, "reason": "open pull request",
    }


@pytest.mark.parametrize("merged", [True, False], ids=["merged", "closed-unmerged"])
def test_guard_accepts_closed_session_pr(merged: bool) -> None:
    verdict = _verdict(_branch(), [_pull(merged=merged)])
    assert verdict["delete"] is True
    assert verdict["reason"] == ("merged PR #1" if merged else "abandoned PR #1")


def test_guard_refuses_no_pr_or_new_work_or_foreign_fork() -> None:
    assert _verdict(_branch(), [])["delete"] is False
    pull = _pull()
    pull["head"]["sha"] = "b" * 40
    assert _verdict(_branch(), [pull])["delete"] is False
    pull = _pull()
    pull["head"]["repo"]["full_name"] = "someone/fork"
    assert _verdict(_branch(), [pull])["delete"] is False


def test_guard_fails_closed_when_protection_is_unknown() -> None:
    branch = _branch()
    del branch["protected"]
    assert _verdict(branch, [_pull()])["delete"] is False


def test_refusal_assertion_detects_an_unsafe_guard() -> None:
    # Mutation proof: the same refusal assertion must reject an always-delete guard.
    unsafe = "function deletionVerdict() {\n  return {delete: true};\n}"
    with pytest.raises(AssertionError):
        assert _verdict(_branch("main"), [_pull("main")], unsafe)["delete"] is False


def _run_workflow(
    *, event: str = "workflow_dispatch", inputs: dict | None = None,
    branches: list[dict] | None = None, pulls: list[dict] | None = None,
    action: str = "closed", payload_pr: dict | None = None, failure: str = "",
) -> dict:
    """Run the entire Actions script with a closed, in-memory API surface."""
    source = """
const fixture = JSON.parse(require('fs').readFileSync(0, 'utf8'));
const calls = [], logs = [], deleted = [];
const context = {
  repo: {owner: 'r3dz4r', repo: 'datapulse-my'}, eventName: fixture.event,
  payload: {inputs: fixture.inputs, action: fixture.action, pull_request: fixture.pr}
};
const endpoint = name => async args => {
  calls.push({name, args});
  if (name === fixture.failure) throw Object.assign(new Error('API refused'), {status: 403});
  if (name === 'refs') return fixture.branches.map(b => ({ref: `refs/heads/${b.name}`}));
  if (name === 'pulls') return fixture.pulls;
  if (name === 'branch') {
    const branch = fixture.branches.find(b => b.name === args.branch);
    if (!branch) throw Object.assign(new Error('Absent'), {status: 404});
    return {data: branch};
  }
  if (name === 'delete') deleted.push(args.ref);
};
const github = {
  rest: {git: {listMatchingRefs: endpoint('refs'), deleteRef: endpoint('delete')},
    repos: {getBranch: endpoint('branch')}, pulls: {list: endpoint('pulls')}},
  paginate: (method, args) => method(args)
};
const AsyncFunction = Object.getPrototypeOf(async function() {}).constructor;
(async () => {
  let error = null;
  try {
    await new AsyncFunction('github', 'context', 'core', fixture.script)(
      github, context, {info: message => logs.push(message)});
  } catch (caught) { error = caught.message; }
  console.log(JSON.stringify({calls, logs, deleted, error}));
})();
"""
    return _node(source, {
        "script": _script(), "event": event, "inputs": inputs, "action": action,
        "pr": payload_pr if payload_pr is not None else _pull(),
        "branches": branches if branches is not None else [_branch()],
        "pulls": pulls if pulls is not None else [_pull()], "failure": failure,
    })


@pytest.mark.parametrize("inputs", [None, {}, {"dry_run": "true"}, {"dry_run": "FALSE"}])
def test_sweep_defaults_to_dry_run(inputs: dict | None) -> None:
    result = _run_workflow(inputs=inputs)
    assert not result["error"]
    assert result["deleted"] == []
    assert result["logs"] == [f"KEEP {BRANCH}: dry run; would delete; merged PR #1"]
    assert result["calls"][0]["args"]["ref"] == "heads/session/"


def test_sweep_deletes_only_finished_refs_and_prints_each_reason() -> None:
    names = [BRANCH, "session/abandoned", "session/active", "session/orphan", "session/protected"]
    pulls = [_pull(), _pull(names[1], merged=False), _pull(names[2], state="open"), _pull(names[4])]
    branches = [_branch(name, protected=name == names[4]) for name in names]
    result = _run_workflow(inputs={"dry_run": "false"}, branches=branches, pulls=pulls)
    assert not result["error"]
    assert result["deleted"] == [f"heads/{BRANCH}", "heads/session/abandoned"]
    assert result["logs"] == [
        f"DELETED {BRANCH}: merged PR #1", "DELETED session/abandoned: abandoned PR #1",
        "KEEP session/active: open pull request", "KEEP session/orphan: no closed PR for current tip",
        "KEEP session/protected: protected or protection unknown",
    ]
    queries = [call["args"] for call in result["calls"] if call["name"] == "pulls"]
    assert all(query["state"] == "all" and query["per_page"] == 100 and "base" not in query
               for query in queries)


@pytest.mark.parametrize("merged", [True, False], ids=["merged", "abandoned"])
def test_close_event_uses_same_guard_and_never_sweeps(merged: bool) -> None:
    result = _run_workflow(event="pull_request", pulls=[_pull(merged=merged)],
                           payload_pr=_pull(merged=merged))
    assert not result["error"]
    assert result["deleted"] == [f"heads/{BRANCH}"]
    assert "refs" not in [call["name"] for call in result["calls"]]


@pytest.mark.parametrize("name", ["main", "health-automation", "health-snapshots",
                                      "release-please--branches--main", "feature/work"])
def test_event_cannot_bypass_ref_guard(name: str) -> None:
    result = _run_workflow(event="pull_request", branches=[_branch(name)],
                           pulls=[_pull(name)], payload_pr=_pull(name))
    assert result["deleted"] == []


def test_event_keeps_branch_with_any_open_pr() -> None:
    result = _run_workflow(event="pull_request", pulls=[_pull(), _pull(state="open")])
    assert result["deleted"] == []
    assert result["logs"] == [f"KEEP {BRANCH}: open pull request"]


@pytest.mark.parametrize("case", ["foreign-fork", "reopened", "wrong-event"])
def test_event_rejects_foreign_or_non_closed_context(case: str) -> None:
    pull = _pull(state="open" if case == "reopened" else "closed")
    if case == "foreign-fork":
        pull["head"]["repo"]["full_name"] = "someone/fork"
    result = _run_workflow(event="push" if case == "wrong-event" else "pull_request",
                           payload_pr=pull)
    assert result["deleted"] == [] and result["calls"] == []


@pytest.mark.parametrize("endpoint", ["refs", "branch", "pulls", "delete"])
def test_api_errors_fail_closed_without_retry(endpoint: str) -> None:
    result = _run_workflow(inputs={"dry_run": "false"}, failure=endpoint)
    assert result["error"] == "API refused"
    assert result["deleted"] == []
    assert sum(call["name"] == endpoint for call in result["calls"]) == 1


def test_missing_ref_is_an_idempotent_keep() -> None:
    result = _run_workflow(event="pull_request", branches=[])
    assert result["error"] is None and result["deleted"] == []
    assert result["logs"] == [f"KEEP {BRANCH}: ref already absent"]
