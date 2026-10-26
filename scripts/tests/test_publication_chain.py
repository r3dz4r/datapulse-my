#!/usr/bin/env python3
"""Fail-closed successor decisions and the workflow's single dispatch boundary."""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys

import pytest
import yaml

from scripts import publication_chain


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/publication_chain.py"
WORKFLOW = ROOT / ".github/workflows/deploy-cloudflare-pages.yml"


def test_publication_chain_uses_verified_main_head_without_append_tokens() -> None:
    signing = yaml.safe_load(WORKFLOW.read_text())["jobs"]["sign_health"]
    assert signing["outputs"]["accepted_head_state"] == "${{ steps.accepted_head.outputs.state }}"
    assert not any(step.get("uses") == "actions/create-github-app-token@v1" for step in signing["steps"])
    guard = next(step for step in signing["steps"] if step.get("id") == "accepted_head")
    assert "if" not in guard
    assert 'accepted = accepted_discovery(root, revision)' in guard["run"]


def inputs(**overrides: object) -> dict[str, object]:
    return {
        "publication_result": "success", "published_sha": "a" * 40,
        "main_sha": "b" * 40, "chain_depth": "0", "max_depth": "3",
    } | overrides


def test_success_with_new_main_chains_once() -> None:
    assert publication_chain.decide(inputs(chain_depth=1)) == {
        "decision": "chain", "reason": "newer_main", "next_depth": 2,
    }


@pytest.mark.parametrize(("overrides", "reason"), [
    ({"main_sha": "a" * 40}, "equal_shas"),
    ({"publication_result": "failure"}, "not_succeeded"),
    ({"publication_result": "cancelled"}, "not_succeeded"),
    ({"publication_result": "skipped"}, "not_succeeded"),
    ({"chain_depth": 3}, "depth_exhausted"),
    ({"chain_depth": 4}, "depth_exhausted"),
    ({"max_depth": 0}, "depth_exhausted"),
])
def test_terminal_decisions(overrides: dict[str, object], reason: str) -> None:
    assert publication_chain.decide(inputs(**overrides)) == {
        "decision": "stop", "reason": reason, "next_depth": None,
    }


@pytest.mark.parametrize("field", list(inputs()))
@pytest.mark.parametrize("value", [None, "", [], {}, True, "unreadable"])
def test_unreadable_input_names_the_field(field: str, value: object) -> None:
    result = publication_chain.decide(inputs(**{field: value}))
    assert result == {
        "decision": "stop", "reason": f"invalid_{field}", "next_depth": None,
    }


@pytest.mark.parametrize("field", list(inputs()))
def test_missing_input_names_the_field(field: str) -> None:
    payload = inputs()
    del payload[field]
    assert publication_chain.decide(payload) == {
        "decision": "stop", "reason": f"invalid_{field}", "next_depth": None,
    }


@pytest.mark.parametrize("field", ["chain_depth", "max_depth"])
@pytest.mark.parametrize("value", [-1, 1.5, "1.0", "-1", "+1", " 1", "01", "9" * 5000])
def test_depth_must_be_a_nonnegative_integer(field: str, value: object) -> None:
    assert publication_chain.decide(inputs(**{field: value}))["reason"] == f"invalid_{field}"


@pytest.mark.parametrize("field", ["published_sha", "main_sha"])
@pytest.mark.parametrize("value", ["a" * 39, "a" * 41, "A" * 40, "g" * 40, "a" * 40 + "\n"])
def test_sha_must_be_a_full_lowercase_revision(field: str, value: str) -> None:
    assert publication_chain.decide(inputs(**{field: value}))["reason"] == f"invalid_{field}"


def test_unexpected_error_cannot_chain(monkeypatch: pytest.MonkeyPatch) -> None:
    def broken(*args: object) -> bool:
        raise RuntimeError("unreadable")

    monkeypatch.setattr(publication_chain, "_valid_sha", broken)
    assert publication_chain.decide(inputs()) == {
        "decision": "stop", "reason": "decision_error", "next_depth": None,
    }


def test_unreadable_stream_exits_zero(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str],
) -> None:
    class BrokenStream:
        def read(self) -> str:
            raise OSError("cannot read publication inputs")

    monkeypatch.setattr(sys, "stdin", BrokenStream())
    assert publication_chain.main() == 0
    assert json.loads(capsys.readouterr().out) == {
        "decision": "stop", "reason": "unreadable_input", "next_depth": None,
    }


@pytest.mark.parametrize(("payload", "reason"), [
    ("", "unreadable_input"), ("{", "unreadable_input"),
    ("[]", "invalid_input"), ("null", "invalid_input"),
    ('{"main_sha": NaN}', "unreadable_input"),
    ('{"publication_result":"failure","publication_result":"success"}', "unreadable_input"),
    (json.dumps(inputs()), "newer_main"),
    (json.dumps(inputs(publication_result="failure")), "not_succeeded"),
    (json.dumps(inputs(main_sha="a" * 40)), "equal_shas"),
])
def test_cli_always_exits_zero_with_machine_readable_decision(payload: str, reason: str) -> None:
    result = subprocess.run(
        [sys.executable, str(SCRIPT)], input=payload, text=True,
        capture_output=True, check=False, timeout=5,
    )
    assert result.returncode == 0, result.stderr
    verdict = json.loads(result.stdout)
    assert verdict["reason"] == reason
    assert verdict["decision"] == ("chain" if reason == "newer_main" else "stop")


def workflow() -> dict:
    return yaml.safe_load(WORKFLOW.read_text())


def test_successor_reuses_selection_and_preserves_global_lock() -> None:
    parsed = workflow()
    trigger = parsed.get("on", parsed.get(True))
    assert trigger["workflow_dispatch"]["inputs"]["chain_depth"]["default"] == "0"
    assert parsed["env"]["PUBLICATION_CHAIN_MAX_DEPTH"] == 3
    assert parsed["concurrency"] == {
        "group": "cloudflare-pages-deploy", "queue": "single", "cancel-in-progress": False,
    }
    job = parsed["jobs"]["publication_chain"]
    assert set(job["needs"]) == {"classify", "sign_health", "deploy", "publication_freshness"}
    assert job["if"] == "always() && !cancelled()"
    assert job["permissions"] == {"contents": "read", "actions": "write"}
    steps = job["steps"]
    dispatch = next(step for step in steps if step.get("id") == "successor")
    assert "success()" in dispatch["if"] and "!cancelled()" in dispatch["if"]
    assert "steps.chain.outputs.decision == 'chain'" in dispatch["if"]
    assert "needs.deploy.result == 'success'" in dispatch["if"]
    assert "needs.publication_freshness.result == 'success'" in dispatch["if"]
    assert dispatch["run"].count("gh api") == 1
    assert "/deploy-cloudflare-pages.yml/dispatches" in dispatch["run"]
    assert '-f ref=main' in dispatch["run"]
    assert 'inputs[chain_depth]=$NEXT_DEPTH' in dispatch["run"]
    assert "--ref" not in dispatch["run"]
    assert steps[-1]["if"] == "always()"
    assert "GITHUB_STEP_SUMMARY" in steps[-1]["run"]


@pytest.mark.parametrize(("result", "head", "depth", "read_status", "event", "expected"), [
    ("success", "b" * 40, "0", 0, "workflow_dispatch", "newer_main"),
    ("success", "a" * 40, "0", 0, "workflow_dispatch", "equal_shas"),
    ("failure", "b" * 40, "0", 0, "workflow_dispatch", "not_succeeded"),
    ("cancelled", "b" * 40, "0", 0, "workflow_dispatch", "not_succeeded"),
    ("success", "b" * 40, "3", 0, "workflow_dispatch", "depth_exhausted"),
    ("success", "b" * 40, "", 0, "workflow_dispatch", "invalid_chain_depth"),
    ("success", "b" * 40, "0", 1, "workflow_dispatch", "invalid_main_sha"),
    ("success", "garbage", "0", 0, "workflow_dispatch", "invalid_main_sha"),
    ("success", "b" * 40, "", 0, "workflow_run", "newer_main"),
])
def test_workflow_decision_reads_live_head_and_fails_closed(
    tmp_path: Path, result: str, head: str, depth: str, read_status: int, event: str, expected: str,
) -> None:
    gh = tmp_path / "gh"
    gh.write_text('#!/bin/bash\nprintf "%s\\n" "$TEST_HEAD"\nexit "$TEST_READ_STATUS"\n')
    gh.chmod(0o755)
    output = tmp_path / "output"
    job = workflow()["jobs"]["publication_chain"]
    step = next(step for step in job["steps"] if step.get("id") == "chain")
    env = os.environ | {
        "PATH": f"{tmp_path}:{os.environ['PATH']}", "TEST_HEAD": head,
        "TEST_READ_STATUS": str(read_status), "GITHUB_OUTPUT": str(output),
        "GITHUB_EVENT_NAME": event, "GITHUB_REPOSITORY": "test/repo",
        "PUBLICATION_RESULT": result, "PUBLISHED_SHA": "a" * 40,
        "CHAIN_DEPTH": depth, "PUBLICATION_CHAIN_MAX_DEPTH": "3",
    }
    completed = subprocess.run(
        ["bash", "-c", step["run"]], cwd=ROOT, env=env,
        text=True, capture_output=True, check=False, timeout=10,
    )
    assert completed.returncode == 0, completed.stderr
    fields = dict(line.split("=", 1) for line in output.read_text().splitlines())
    assert fields["reason"] == expected
    assert fields["decision"] == ("chain" if expected == "newer_main" else "stop")
    assert fields["next_depth"] == ("1" if expected == "newer_main" else "")


@pytest.mark.parametrize("dispatch_status", [0, 1])
def test_dispatch_has_one_attempt_and_reports_outcome(tmp_path: Path, dispatch_status: int) -> None:
    gh = tmp_path / "gh"
    calls = tmp_path / "calls"
    summary = tmp_path / "summary"
    gh.write_text(
        '#!/bin/bash\n{\n  printf "CALL\\n"\n  printf "%s\\n" "$@"\n} >> "$TEST_CALLS"\nexit "$TEST_STATUS"\n'
    )
    gh.chmod(0o755)
    steps = workflow()["jobs"]["publication_chain"]["steps"]
    dispatch = next(step for step in steps if step.get("id") == "successor")
    env = os.environ | {
        "PATH": f"{tmp_path}:{os.environ['PATH']}", "TEST_CALLS": str(calls),
        "TEST_STATUS": str(dispatch_status), "NEXT_DEPTH": "2",
        "GITHUB_REPOSITORY": "test/repo", "GITHUB_STEP_SUMMARY": str(summary),
        "DECISION": "chain", "REASON": "newer_main",
        "DISPATCH_OUTCOME": "success" if dispatch_status == 0 else "failure",
    }
    completed = subprocess.run(
        ["bash", "-c", dispatch["run"]], env=env,
        text=True, capture_output=True, check=False, timeout=10,
    )
    assert completed.returncode == dispatch_status, completed.stderr
    assert calls.read_text().splitlines() == [
        "CALL", "api", "--method", "POST",
        "repos/test/repo/actions/workflows/deploy-cloudflare-pages.yml/dispatches",
        "-f", "ref=main", "-f", "inputs[chain_depth]=2",
    ]
    subprocess.run(["bash", "-c", steps[-1]["run"]], env=env, check=True, timeout=5)
    assert summary.read_text() == (
        "Publication successor: chain (newer_main); dispatched depth 2.\n"
        if dispatch_status == 0 else
        "Publication successor: stop (dispatch_failure); no retry.\n"
    )


def test_missing_decision_script_stops_and_summarizes(tmp_path: Path) -> None:
    steps = workflow()["jobs"]["publication_chain"]["steps"]
    decide = next(step for step in steps if step.get("id") == "chain")
    output = tmp_path / "output"
    summary = tmp_path / "summary"
    env = os.environ | {
        "GITHUB_OUTPUT": str(output), "GITHUB_STEP_SUMMARY": str(summary),
        "GITHUB_EVENT_NAME": "workflow_run", "PUBLICATION_RESULT": "failure",
        "PUBLISHED_SHA": "", "CHAIN_DEPTH": "", "PUBLICATION_CHAIN_MAX_DEPTH": "3",
    }
    completed = subprocess.run(
        ["bash", "-c", decide["run"]], cwd=tmp_path, env=env,
        text=True, capture_output=True, check=False, timeout=10,
    )
    assert completed.returncode == 0, completed.stderr
    assert "decision=stop\nreason=decision_unavailable\nnext_depth=\n" == output.read_text()
    env |= {"DECISION": "stop", "REASON": "decision_unavailable", "NEXT_DEPTH": "", "DISPATCH_OUTCOME": "skipped"}
    subprocess.run(["bash", "-c", steps[-1]["run"]], env=env, check=True, timeout=5)
    assert summary.read_text() == "Publication successor: stop (decision_unavailable).\n"
