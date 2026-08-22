"""Tests for MCP source-to-deployment synchronization."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
SYNC_SCRIPT = ROOT / "scripts/sync_mcp_deployment.sh"


@pytest.fixture
def stamped_repo(tmp_path: Path) -> tuple[Path, str]:
    repo = tmp_path / "repo"
    (repo / "mcp").mkdir(parents=True)
    (repo / "scripts").mkdir()
    shutil.copy2(
        ROOT / "scripts/bump_mcp_source_version.py",
        repo / "scripts/bump_mcp_source_version.py",
    )
    (repo / "mcp/server.py").write_text(
        'import os\n'
        'SOURCE_COMMIT_SHA = os.getenv("DATAPULSE_MCP_SOURCE_SHA", "dev")\n'
        'SOURCE_COMMIT_DATE = os.getenv("DATAPULSE_MCP_SOURCE_DATE", "unreleased")\n',
        encoding="utf-8",
    )
    (repo / "mcp.json").write_text(
        json.dumps(
            {
                "server": {
                    "source_commit_sha": "REPLACE_ME_AT_RELEASE",
                    "source_commit_date": "REPLACE_ME_AT_RELEASE",
                }
            }
        )
        + "\n",
        encoding="utf-8",
    )
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    subprocess.run(
        ["git", "config", "user.email", "test@example.invalid"], cwd=repo, check=True
    )
    subprocess.run(["git", "config", "user.name", "Test"], cwd=repo, check=True)
    subprocess.run(["git", "add", "."], cwd=repo, check=True)
    subprocess.run(
        ["git", "commit", "-q", "-m", "fixture"],
        cwd=repo,
        check=True,
        env={
            **os.environ,
            "GIT_AUTHOR_DATE": "2026-08-09T00:00:00+08:00",
            "GIT_COMMITTER_DATE": "2026-08-09T00:00:00+08:00",
        },
    )
    sha = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=repo, text=True
    ).strip()
    return repo, sha


def test_server_py_exposes_source_commit_sha() -> None:
    server_source = (ROOT / "mcp/server.py").read_text(encoding="utf-8")

    assert "SOURCE_COMMIT_SHA = " in server_source
    assert "source_commit_sha" in server_source


def test_mcp_json_includes_source_commit_sha_field() -> None:
    discovery = json.loads((ROOT / "mcp.json").read_text(encoding="utf-8"))

    assert "source_commit_sha" in discovery["server"]


def test_bump_script_stamps_server_py(stamped_repo: tuple[Path, str]) -> None:
    repo, sha = stamped_repo

    subprocess.run(
        ["python3", "scripts/bump_mcp_source_version.py"], cwd=repo, check=True
    )

    server_source = (repo / "mcp/server.py").read_text(encoding="utf-8")
    assert f'os.getenv("DATAPULSE_MCP_SOURCE_SHA", "{sha}")' in server_source


def test_bump_script_stamps_mcp_json(stamped_repo: tuple[Path, str]) -> None:
    repo, sha = stamped_repo

    subprocess.run(
        ["python3", "scripts/bump_mcp_source_version.py"], cwd=repo, check=True
    )

    discovery = json.loads((repo / "mcp.json").read_text(encoding="utf-8"))
    assert discovery["server"]["source_commit_sha"] == sha


def test_verify_script_detects_mismatch() -> None:
    unreachable = subprocess.run(
        [
            "python3",
            "scripts/verify_mcp_deployment.py",
            "--endpoint",
            "http://127.0.0.1:1",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
        timeout=10,
    )
    assert unreachable.returncode == 2
    assert "UNREACHABLE:" in unreachable.stdout

    class MockMCPHandler(BaseHTTPRequestHandler):
        source_commit_sha = "0" * 40

        def do_POST(self) -> None:  # noqa: N802
            content_length = int(self.headers.get("Content-Length", "0"))
            request = json.loads(self.rfile.read(content_length))
            assert self.headers["Accept"] == "application/json, text/event-stream"
            method = request["method"]
            if method == "initialize":
                body = {
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
        mismatch = subprocess.run(
            [
                "python3",
                "scripts/verify_mcp_deployment.py",
                "--endpoint",
                f"http://127.0.0.1:{server.server_port}/mcp",
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
            timeout=10,
        )
        MockMCPHandler.source_commit_sha = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
        ).strip()
        match = subprocess.run(
            [
                "python3",
                "scripts/verify_mcp_deployment.py",
                "--endpoint",
                f"http://127.0.0.1:{server.server_port}/mcp",
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
            timeout=10,
        )
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)

    assert mismatch.returncode == 1
    assert "MISMATCH: deployed=" in mismatch.stdout
    assert match.returncode == 0
    assert "OK: deployed matches repo HEAD" in match.stdout


def test_release_build_profile_includes_bump_step() -> None:
    listed = subprocess.run(
        ["bash", "scripts/generate.sh", "release-build", "--list"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    )

    assert "0. python3 scripts/bump_mcp_source_version.py" in listed.stdout


@pytest.mark.parametrize(
    ("source_fastmcp_version", "runtime_version", "live_sha", "malformed", "expected_surface"),
    [
        ("4.0.0b3", "v4.0.0b3+aaaaaaa", None, False, "FastMCP serverInfo.version source marker"),
        ("3.4.7", "v3.4.7+aaaaaaa", "a" * 40, False, "legacy serverInfo.source_commit_sha"),
        ("4.0.0b3", "v4.0.0b3+bbbbbbb", None, False, None),
        ("4.0.0b3", "v4.0.0b3+aaaaaaa", None, True, None),
    ],
)
def test_sync_verifies_fastmcp_identity_and_rolls_back_on_failure(
    tmp_path: Path,
    source_fastmcp_version: str,
    runtime_version: str,
    live_sha: str | None,
    malformed: bool,
    expected_surface: str | None,
) -> None:
    source = tmp_path / "source.py"
    deployed = tmp_path / "deployed.py"
    source_text = (
        'import os\n'
        f'FASTMCP_VERSION = "{source_fastmcp_version}"\n'
        'SOURCE_COMMIT_SHA = os.getenv("DATAPULSE_MCP_SOURCE_SHA", "'
        + "a" * 40
        + '")\n'
    )
    source.write_text(source_text, encoding="utf-8")
    deployed.write_text("old deployed source\n", encoding="utf-8")

    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    (fake_bin / "systemctl").write_text(
        "#!/usr/bin/env bash\nexit 0\n", encoding="utf-8"
    )
    (fake_bin / "systemctl").chmod(0o755)

    class MockMCPHandler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:  # noqa: N802
            content_length = int(self.headers.get("Content-Length", "0"))
            request = json.loads(self.rfile.read(content_length))
            method = request["method"]
            if method == "initialize":
                if malformed:
                    payload = "not-json"
                else:
                    info = {"name": "DataPulse MY", "version": runtime_version}
                    if live_sha is not None:
                        info["source_commit_sha"] = live_sha
                    payload = json.dumps(
                        {
                            "jsonrpc": "2.0",
                            "id": request["id"],
                            "result": {
                                "protocolVersion": "2025-03-26",
                                "capabilities": {},
                                "serverInfo": info,
                            },
                        }
                    )
                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream")
                self.send_header("Mcp-Session-Id", "sync-test-session")
                encoded = f"data: {payload}\n\n".encode("utf-8")
            elif method == "notifications/initialized":
                self.send_response(202)
                encoded = b""
            else:
                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream")
                encoded = (
                    b'data: {"jsonrpc":"2.0","id":2,"result":{"tools":[{"name":"probe",'
                    b'"annotations":{"readOnlyHint":true,"destructiveHint":false,'
                    b'"idempotentHint":true,"openWorldHint":true}}]}}\n\n'
                )
            self.send_header("Content-Length", str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)

        def log_message(self, format: str, *args: object) -> None:
            return

    server = HTTPServer(("127.0.0.1", 0), MockMCPHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        result = subprocess.run(
            [
                str(SYNC_SCRIPT),
                "--source",
                str(source),
                "--deployed-path",
                str(deployed),
                "--endpoint",
                f"http://127.0.0.1:{server.server_port}/mcp",
                "--service",
                "sync-test.service",
                "--drop-in",
                str(tmp_path / "drop-in.conf"),
            ],
            cwd=ROOT,
            env={"PATH": f"{fake_bin}:{os.environ['PATH']}"},
            capture_output=True,
            text=True,
            check=False,
            timeout=20,
        )
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)

    if expected_surface is not None:
        assert result.returncode == 0, result.stderr
        assert deployed.read_text(encoding="utf-8") == source_text
        assert f"identity surface={expected_surface}" in result.stdout
    else:
        assert result.returncode != 0
        assert deployed.read_text(encoding="utf-8") == "old deployed source\n"
        assert "live identity mismatch:" in result.stderr
        assert "checked=legacy serverInfo.source_commit_sha or FastMCP serverInfo.version" in result.stderr
