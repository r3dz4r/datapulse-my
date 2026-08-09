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
                            "version": "v3.4.5+0000000",
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
