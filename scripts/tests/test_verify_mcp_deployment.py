"""Hermetic tests for verify_mcp_deployment extract and comparison logic."""

from __future__ import annotations

import json
import os
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
import subprocess
import sys
from typing import Any, Iterator

import pytest
import yaml

from scripts.verify_mcp_deployment import (
    RepositoryHistoryError,
    extract_deployed_sha,
    newest_mcp_sha,
)


ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github/workflows/provenance-drift.yml"
VERIFY_SCRIPT = ROOT / "scripts/verify_mcp_deployment.py"


@pytest.fixture
def mock_mcp_endpoint() -> Iterator[tuple[str, type[BaseHTTPRequestHandler]]]:
    """Serve the production handshake shape locally for verifier CLI tests."""

    class MockMCPHandler(BaseHTTPRequestHandler):
        source_commit_sha = "0" * 40

        def do_POST(self) -> None:  # noqa: N802
            content_length = int(self.headers.get("Content-Length", "0"))
            request = json.loads(self.rfile.read(content_length))
            assert self.headers["Accept"] == "application/json, text/event-stream"
            method = request["method"]
            if method == "initialize":
                body: dict[str, Any] | None = {
                    "jsonrpc": "2.0",
                    "id": request["id"],
                    "result": {
                        "protocolVersion": "2025-03-26",
                        "capabilities": {},
                        "serverInfo": {
                            "name": "DataPulse MY",
                            "version": "v3.4.7+0000000",
                            "source_commit_sha": self.source_commit_sha,
                            "source_commit_date": "2026-08-09",
                        },
                    },
                }
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Mcp-Session-Id", "test-session")
            elif method == "notifications/initialized":
                body = None
                self.send_response(202)
            else:
                body = {
                    "jsonrpc": "2.0",
                    "id": request["id"],
                    "result": {"tools": []},
                }
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
            encoded = b"" if body is None else json.dumps(body).encode("utf-8")
            self.send_header("Content-Length", str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)

        def log_message(self, format: str, *args: object) -> None:
            return

    server = HTTPServer(("127.0.0.1", 0), MockMCPHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}/mcp", MockMCPHandler
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def _run_verifier(endpoint: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(VERIFY_SCRIPT), "--endpoint", endpoint],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
        timeout=10,
    )


def test_verify_cli_reports_match_from_loopback_marker(
    mock_mcp_endpoint: tuple[str, type[BaseHTTPRequestHandler]],
) -> None:
    endpoint, handler = mock_mcp_endpoint
    handler.source_commit_sha = newest_mcp_sha(ROOT)  # type: ignore[attr-defined]

    result = _run_verifier(endpoint)

    assert result.returncode == 0
    assert "OK: deployed" in result.stdout
    assert "matches deployed MCP code revision" in result.stdout


def test_verify_cli_reports_mismatch_from_loopback_marker(
    mock_mcp_endpoint: tuple[str, type[BaseHTTPRequestHandler]],
) -> None:
    endpoint, _ = mock_mcp_endpoint

    result = _run_verifier(endpoint)

    assert result.returncode == 1
    assert "MISMATCH: deployed=" in result.stdout


def test_verify_cli_reports_unreachable_loopback_endpoint() -> None:
    result = _run_verifier("http://127.0.0.1:1/mcp")

    assert result.returncode == 2
    assert "UNREACHABLE:" in result.stdout


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
    assert checkout["with"]["fetch-depth"] == 0
    assert verify["id"] == "verify"
    assert verify["env"]["MCP_ENDPOINT"] == "https://mcp.data-pulse.my/mcp"
    assert verify["env"]["DEFAULT_BRANCH"] == "${{ github.event.repository.default_branch }}"
    assert 'python3 scripts/verify_mcp_deployment.py' in verify["run"]
    assert '--repo-path "$GITHUB_WORKSPACE"' in verify["run"]
    assert '--default-branch "$DEFAULT_BRANCH"' in verify["run"]
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


class TestNewestMcpSha:
    def test_reads_newest_mcp_commit_from_origin_default_branch(self) -> None:
        expected = subprocess.check_output(
            ["git", "log", "-1", "--format=%H", "origin/main", "--", "mcp/server.py", "scripts/gen_per_dataset_receipt.py", "scripts/verify_per_dataset_receipt.py"],
            cwd=ROOT,
            text=True,
        ).strip()

        assert newest_mcp_sha(ROOT) == expected

    def test_derives_default_branch_when_origin_head_is_absent(
        self, tmp_path: Path,
    ) -> None:
        clone = tmp_path / "ci-checkout"
        subprocess.run(["git", "clone", "-q", str(ROOT), str(clone)], check=True)
        subprocess.run(
            ["git", "symbolic-ref", "refs/remotes/origin/HEAD", "refs/remotes/origin/main"],
            cwd=clone,
            check=True,
        )
        assert subprocess.check_output(
            ["git", "symbolic-ref", "--quiet", "refs/remotes/origin/HEAD"],
            cwd=clone,
            text=True,
        ).strip() == "refs/remotes/origin/main"
        subprocess.run(
            ["git", "update-ref", "--no-deref", "-d", "refs/remotes/origin/HEAD"],
            cwd=clone,
            check=True,
        )
        assert subprocess.run(
            ["git", "symbolic-ref", "--quiet", "refs/remotes/origin/HEAD"],
            cwd=clone,
            check=False,
        ).returncode != 0
        expected = subprocess.check_output(
            ["git", "log", "-1", "--format=%H", "HEAD", "--", "mcp/server.py", "scripts/gen_per_dataset_receipt.py", "scripts/verify_per_dataset_receipt.py"],
            cwd=clone,
            text=True,
        ).strip()

        assert newest_mcp_sha(clone) == expected

    def test_derives_default_branch_when_origin_head_target_is_absent(
        self, tmp_path: Path,
    ) -> None:
        clone = tmp_path / "ci-checkout"
        subprocess.run(["git", "clone", "-q", str(ROOT), str(clone)], check=True)
        subprocess.run(
            ["git", "update-ref", "--no-deref", "refs/remotes/origin/HEAD", "HEAD"],
            cwd=clone,
            check=True,
        )
        assert subprocess.run(
            ["git", "symbolic-ref", "--quiet", "refs/remotes/origin/HEAD"],
            cwd=clone,
            check=False,
            capture_output=True,
        ).returncode != 0
        assert subprocess.check_output(
            ["git", "rev-parse", "--verify", "refs/remotes/origin/HEAD^{commit}"],
            cwd=clone,
            text=True,
        ).strip() == subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=clone, text=True,
        ).strip()
        assert subprocess.check_output(
            ["git", "remote", "get-url", "origin"], cwd=clone, text=True,
        ).strip() == str(ROOT)
        subprocess.run(
            ["git", "update-ref", "--no-deref", "-d", "refs/remotes/origin/HEAD"],
            cwd=clone,
            check=True,
        )
        assert subprocess.run(
            ["git", "rev-parse", "--verify", "refs/remotes/origin/HEAD^{commit}"],
            cwd=clone,
            check=False,
            capture_output=True,
        ).returncode != 0
        expected = subprocess.check_output(
            ["git", "log", "-1", "--format=%H", "HEAD", "--", "mcp/server.py", "scripts/gen_per_dataset_receipt.py", "scripts/verify_per_dataset_receipt.py"],
            cwd=clone,
            text=True,
        ).strip()

        assert newest_mcp_sha(clone) == expected

    def test_uses_checked_out_history_when_origin_is_unavailable(self, tmp_path: Path) -> None:
        clone = tmp_path / "no-origin-checkout"
        subprocess.run(["git", "clone", "-q", str(ROOT), str(clone)], check=True)
        subprocess.run(["git", "remote", "remove", "origin"], cwd=clone, check=True)
        subprocess.run(
            ["git", "update-ref", "--no-deref", "-d", "refs/remotes/origin/HEAD"],
            cwd=clone,
            check=True,
        )
        assert subprocess.check_output(
            ["git", "log", "-1", "--format=%H", "HEAD", "--", "mcp/server.py", "scripts/gen_per_dataset_receipt.py", "scripts/verify_per_dataset_receipt.py"],
            cwd=clone,
            text=True,
        ).strip() == newest_mcp_sha(clone)

    def test_shallow_clone_cannot_derive_a_passing_expected_revision(
        self, tmp_path: Path,
    ) -> None:
        source = tmp_path / "source"
        bare = tmp_path / "origin.git"
        clone = tmp_path / "shallow"
        source.mkdir()
        subprocess.run(["git", "init", "-q", "-b", "main"], cwd=source, check=True)
        subprocess.run(
            ["git", "config", "user.email", "test@example.invalid"], cwd=source, check=True,
        )
        subprocess.run(["git", "config", "user.name", "Test"], cwd=source, check=True)
        (source / "mcp").mkdir()
        (source / "mcp/server.py").write_text("first\n", encoding="utf-8")
        subprocess.run(["git", "add", "mcp/server.py"], cwd=source, check=True)
        subprocess.run(["git", "commit", "-qm", "mcp revision"], cwd=source, check=True)
        (source / "README.md").write_text("tip\n", encoding="utf-8")
        subprocess.run(["git", "add", "README.md"], cwd=source, check=True)
        subprocess.run(["git", "commit", "-qm", "non-mcp tip"], cwd=source, check=True)
        subprocess.run(["git", "clone", "--bare", "-q", str(source), str(bare)], check=True)
        subprocess.run(
            ["git", "clone", "--depth", "1", "-q", f"file://{bare}", str(clone)],
            check=True,
        )
        assert subprocess.check_output(
            ["git", "rev-parse", "--is-shallow-repository"], cwd=clone, text=True,
        ).strip() == "true"

        with pytest.raises(RepositoryHistoryError, match="history is shallow"):
            newest_mcp_sha(clone)


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
