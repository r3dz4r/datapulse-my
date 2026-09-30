"""Hermetic tests for verify_mcp_deployment extract and comparison logic."""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
from typing import Any

import pytest
import yaml

from scripts.verify_mcp_deployment import extract_deployed_sha, recorded_sha


ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github/workflows/provenance-drift.yml"


def _provenance_workflow() -> dict[str, Any]:
    return yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))


def test_provenance_workflow_audits_default_branch_without_pr_or_push_gate() -> None:
    workflow = _provenance_workflow()
    # PyYAML's YAML 1.1 loader treats the Actions key 'on' as True.
    triggers = workflow[True]
    assert set(triggers) == {"schedule", "workflow_dispatch"}
    assert triggers["schedule"] == [{"cron": "17 * * * *"}]
    assert workflow["permissions"] == {"contents": "read"}
    assert workflow["concurrency"] == {
        "group": "provenance-drift", "cancel-in-progress": False,
    }
    job = workflow["jobs"]["provenance"]
    assert job["if"] == "github.ref == format('refs/heads/{0}', github.event.repository.default_branch)"
    assert job["timeout-minutes"] == 5
    assert job["permissions"] == {"contents": "read", "issues": "write"}
    checkout, verify, notify = job["steps"]
    assert checkout["with"]["ref"] == "${{ github.event.repository.default_branch }}"
    assert verify["id"] == "verify"
    assert verify["env"]["MCP_ENDPOINT"] == "https://mcp.data-pulse.my/mcp"
    assert 'python3 scripts/verify_mcp_deployment.py' in verify["run"]
    assert '--repo-path "$GITHUB_WORKSPACE"' in verify["run"]
    assert "continue-on-error" not in verify
    assert notify["if"] == "failure() && steps.verify.outputs.exit_code == '1'"
    assert notify["uses"] == "actions/github-script@v7"
    script = notify["with"]["script"]
    assert "@${context.repo.owner}" in script
    assert "github.rest.issues.listForRepo" in script
    assert "creator: 'github-actions[bot]'" in script
    assert "!issue.pull_request && issue.title === title" in script
    assert "github.rest.issues.update" in script
    assert "github.rest.issues.create" in script
    assert "actions/runs/${context.runId}" in script


@pytest.mark.parametrize(
    ("verifier_status", "gate_status", "annotation"),
    [(0, 0, ""), (1, 1, "::error"), (2, 0, "::warning"), (7, 7, "::error")],
)
def test_provenance_gate_preserves_mismatch_and_skips_unreachable(
    tmp_path: Path, verifier_status: int, gate_status: int, annotation: str,
) -> None:
    verify = _provenance_workflow()["jobs"]["provenance"]["steps"][1]
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    python = fake_bin / "python3"
    python.write_text(
        f"#!/bin/bash\nprintf 'verifier evidence\\n'\nexit {verifier_status}\n",
        encoding="utf-8",
    )
    python.chmod(0o755)
    output = tmp_path / "output"
    summary = tmp_path / "summary"
    result = subprocess.run(
        ["bash", "--noprofile", "--norc", "-e", "-o", "pipefail", "-c", verify["run"]],
        cwd=ROOT,
        env={
            **os.environ,
            **verify["env"],
            "PATH": f"{fake_bin}{os.pathsep}{os.environ['PATH']}",
            "GITHUB_WORKSPACE": str(ROOT),
            "RUNNER_TEMP": str(tmp_path),
            "GITHUB_OUTPUT": str(output),
            "GITHUB_STEP_SUMMARY": str(summary),
        },
        capture_output=True,
        text=True,
        check=False,
        timeout=10,
    )
    assert result.returncode == gate_status, result.stdout + result.stderr
    assert output.read_text(encoding="utf-8") == f"exit_code={verifier_status}\n"
    assert "verifier evidence" in result.stdout
    assert "verifier evidence" in summary.read_text(encoding="utf-8")
    if annotation:
        assert annotation in result.stdout
    if verifier_status == 2:
        assert "::error" not in result.stdout
        assert "no mismatch established" in result.stdout


class TestExtractDeployedSha:
    @pytest.mark.parametrize(
        ("server_info", "expected"),
        [
            pytest.param(
                {"source_commit_sha": "abcd1234abcd1234abcd1234abcd1234abcd1234"},
                "abcd1234abcd1234abcd1234abcd1234abcd1234",
                id="field_present_40hex",
            ),
            pytest.param(
                {"source_commit_sha": "45da36b"},
                "45da36b",
                id="field_present_short",
            ),
            pytest.param(
                {"version": "v4.0.0b3+45da36b"},
                "45da36b",
                id="version_suffix_7hex",
            ),
            pytest.param(
                {"version": "v4.0.0b3+45da36b487c7a329fc9c19adabb6d07c8976c3f3"},
                "45da36b487c7a329fc9c19adabb6d07c8976c3f3",
                id="version_suffix_40hex",
            ),
            pytest.param(
                {"version": "v4.0.0b3"},
                "<missing>",
                id="version_no_suffix",
            ),
            pytest.param(
                {},
                "<missing>",
                id="empty_dict",
            ),
            pytest.param(
                {"source_commit_sha": "", "version": "v4.0.0b3+deadbeef"},
                "deadbeef",
                id="empty_field_falls_back_to_version",
            ),
            pytest.param(
                {"source_commit_sha": None, "version": "v4.0.0b3+deadbeef"},
                "deadbeef",
                id="null_field_falls_back_to_version",
            ),
        ],
    )
    def test_extract_deployed_sha(self, server_info: dict[str, Any], expected: str) -> None:
        assert extract_deployed_sha(server_info) == expected


class TestRecordedSha:
    def test_reads_from_mcp_json(self, tmp_path: Path) -> None:
        mcp = tmp_path / "mcp.json"
        mcp.write_text(
            json.dumps({
                "server": {
                    "source_commit_sha": "45da36b487c7a329fc9c19adabb6d07c8976c3f3",
                }
            }),
            encoding="utf-8",
        )
        assert recorded_sha(tmp_path) == "45da36b487c7a329fc9c19adabb6d07c8976c3f3"


class TestComparisonNormalization:
    @pytest.mark.parametrize(
        ("deployed", "recorded", "match"),
        [
            pytest.param("45da36b", "45da36b487c7a329fc9c19adabb6d07c8976c3f3", True, id="short_vs_full"),
            pytest.param("45da36b487c7a329fc9c19adabb6d07c8976c3f3", "45da36b", True, id="full_vs_short"),
            pytest.param("45da36b", "45da36b", True, id="both_short_equal"),
            pytest.param("45da36c", "45da36b487c7a329fc9c19adabb6d07c8976c3f3", False, id="differing_short"),
            pytest.param("deadbeef", "45da36b487c7a329fc9c19adabb6d07c8976c3f3", False, id="completely_different"),
        ],
    )
    def test_short_form_comparison(self, deployed: str, recorded: str, match: bool) -> None:
        assert (deployed[:7] == recorded[:7]) is match
