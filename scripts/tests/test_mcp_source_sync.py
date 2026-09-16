"""Tests for MCP source-to-deployment synchronization."""

from __future__ import annotations

import json
import os
import re
import shutil
import socket
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
        recorded = json.loads((ROOT / "mcp.json").read_text(encoding="utf-8"))[
            "server"
        ]["source_commit_sha"]
        MockMCPHandler.source_commit_sha = recorded
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
    assert "OK: deployed" in match.stdout
    assert "matches recorded stamp in mcp.json" in match.stdout


def test_release_build_profile_includes_bump_step() -> None:
    listed = subprocess.run(
        ["bash", "scripts/generate.sh", "release-build", "--list"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    )

    assert "0. python3 scripts/bump_mcp_source_version.py" in listed.stdout


def test_service_like_server_import_resolves_repository_scripts(tmp_path: Path) -> None:
    deployed_dir = tmp_path / "deployed"
    deployed_dir.mkdir()
    shutil.copy2(ROOT / "mcp/server.py", deployed_dir / "server.py")

    probe = subprocess.run(
        [
            "python3",
            "-c",
            (
                "import importlib.util; "
                "spec = importlib.util.spec_from_file_location(\"datapulse_mcp_server\", \"server.py\"); "
                "module = importlib.util.module_from_spec(spec); "
                "spec.loader.exec_module(module); "
                "print(module.generate_per_dataset_statement.__module__)"
            ),
        ],
        cwd=deployed_dir,
        env={**os.environ, "PYTHONPATH": str(ROOT)},
        capture_output=True,
        text=True,
        check=False,
        timeout=20,
    )

    assert probe.returncode == 0, probe.stderr
    assert probe.stdout.strip() == "scripts.gen_per_dataset_receipt"


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
    # The marker literals are a deliberately stale release-build stamp; the
    # deployed copy must be stamped from the caller-supplied commit, so the
    # installed markers provably do not come from these literals.
    source_text = (
        'import os\n'
        f'FASTMCP_VERSION = "{source_fastmcp_version}"\n'
        'SOURCE_COMMIT_SHA = os.getenv("DATAPULSE_MCP_SOURCE_SHA", "'
        + "c" * 40
        + '")\n'
        'SOURCE_COMMIT_DATE = os.getenv("DATAPULSE_MCP_SOURCE_DATE", "1999-12-31")\n'
    )
    expected_deployed_text = source_text.replace("c" * 40, "a" * 40).replace(
        "1999-12-31", "2024-01-15"
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
            env={
                "PATH": f"{fake_bin}:{os.environ['PATH']}",
                # Outside a git checkout the commit is supplied explicitly via
                # the environment pair the server already honours.
                "DATAPULSE_MCP_SOURCE_SHA": "a" * 40,
                "DATAPULSE_MCP_SOURCE_DATE": "2024-01-15",
            },
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
        assert deployed.read_text(encoding="utf-8") == expected_deployed_text
        assert (tmp_path / "drop-in.conf").read_text(encoding="utf-8") == (
            "[Service]\n"
            "# The deployed file is authoritative; stale manual environment overrides must not\n"
            "# mask the SOURCE_COMMIT_SHA/SOURCE_COMMIT_DATE embedded by release-build.\n"
            "UnsetEnvironment=DATAPULSE_MCP_SOURCE_SHA DATAPULSE_MCP_SOURCE_DATE\n"
            "Environment=PYTHONPATH=/home/redza/datapulse-my\n"
        )
        assert f"identity surface={expected_surface}" in result.stdout
    else:
        assert result.returncode != 0
        assert deployed.read_text(encoding="utf-8") == "old deployed source\n"
        assert "live identity mismatch:" in result.stderr
        assert f"head_sha={'a' * 40}" in result.stderr
        assert "head_short_sha=aaaaaaa" in result.stderr
        assert "served_short_sha=" in result.stderr


def test_sync_requires_explicit_sha_outside_a_work_tree(tmp_path: Path) -> None:
    """Without a checkout the script must demand a sha, never fall back to empty."""
    source = tmp_path / "source.py"
    deployed = tmp_path / "deployed.py"
    source.write_text(
        'import os\n'
        'FASTMCP_VERSION = "4.0.0b3"\n'
        'SOURCE_COMMIT_SHA = os.getenv("DATAPULSE_MCP_SOURCE_SHA", "'
        + "c" * 40
        + '")\n'
        'SOURCE_COMMIT_DATE = os.getenv("DATAPULSE_MCP_SOURCE_DATE", "1999-12-31")\n',
        encoding="utf-8",
    )
    deployed.write_text("old deployed source\n", encoding="utf-8")

    def run_sync(extra_args: list[str]) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [
                str(SYNC_SCRIPT),
                "--source",
                str(source),
                "--deployed-path",
                str(deployed),
                "--endpoint",
                "http://127.0.0.1:1/mcp",
                "--service",
                "sync-test.service",
                "--drop-in",
                str(tmp_path / "drop-in.conf"),
                *extra_args,
            ],
            cwd=ROOT,
            env={"PATH": os.environ["PATH"]},
            capture_output=True,
            text=True,
            check=False,
            timeout=20,
        )

    missing = run_sync([])
    assert missing.returncode != 0
    assert "no source sha available" in missing.stderr
    assert str(source) in missing.stderr
    assert "--source-sha" in missing.stderr
    assert "DATAPULSE_MCP_SOURCE_SHA" in missing.stderr
    assert "fatal:" not in missing.stderr
    assert deployed.read_text(encoding="utf-8") == "old deployed source\n"

    half_override = run_sync(["--source-sha", "a" * 40])
    assert half_override.returncode != 0
    assert "--source-sha requires --source-date" in half_override.stderr


class _ReadinessStubHandler(BaseHTTPRequestHandler):
    """MCP stub honouring the sync script's identity and annotation contract."""

    runtime_version = "v1.2.3+aaaaaaa"

    def do_POST(self) -> None:  # noqa: N802
        content_length = int(self.headers.get("Content-Length", "0"))
        request = json.loads(self.rfile.read(content_length))
        method = request["method"]
        if method == "initialize":
            payload = json.dumps(
                {
                    "jsonrpc": "2.0",
                    "id": request["id"],
                    "result": {
                        "protocolVersion": "2025-03-26",
                        "capabilities": {},
                        "serverInfo": {
                            "name": "DataPulse MY",
                            "version": self.runtime_version,
                        },
                    },
                }
            )
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Mcp-Session-Id", "sync-readiness-session")
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


def _free_scratch_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])


class _DelayedMCPStub:
    """Keeps the port refused (nothing listening) for `delay` seconds, then
    serves — the shape of a draining service whose replacement has not bound
    the socket yet."""

    def __init__(self, port: int, delay: float) -> None:
        self._server = HTTPServer(
            ("127.0.0.1", port), _ReadinessStubHandler, bind_and_activate=False
        )
        self._activated = threading.Event()
        self._timer = threading.Timer(delay, self._activate)

    def _activate(self) -> None:
        self._server.server_bind()
        self._server.server_activate()
        self._activated.set()
        self._server.serve_forever()

    def start(self) -> None:
        self._timer.start()

    def close(self) -> None:
        self._timer.cancel()
        if self._activated.is_set():
            self._server.shutdown()
            self._server.server_close()


class _SilentListener(threading.Thread):
    """Accepts connections and never answers — a genuinely dead endpoint."""

    def __init__(self, port: int) -> None:
        super().__init__(daemon=True)
        self._socket = socket.socket()
        self._socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._socket.bind(("127.0.0.1", port))
        self._socket.listen(8)
        self._socket.settimeout(0.5)
        self._held: list[socket.socket] = []
        self._stopped = threading.Event()

    def run(self) -> None:
        while not self._stopped.is_set():
            try:
                conn, _ = self._socket.accept()
            except socket.timeout:
                continue
            self._held.append(conn)

    def close(self) -> None:
        self._stopped.set()
        self.join(timeout=5)
        for conn in self._held:
            conn.close()
        self._socket.close()


def _readiness_fixture(tmp_path: Path) -> tuple[Path, Path, dict[str, str]]:
    source = tmp_path / "source.py"
    deployed = tmp_path / "deployed.py"
    source.write_text(
        'import os\n'
        'FASTMCP_VERSION = "1.2.3"\n'
        'SOURCE_COMMIT_SHA = os.getenv("DATAPULSE_MCP_SOURCE_SHA", "'
        + "c" * 40
        + '")\n'
        'SOURCE_COMMIT_DATE = os.getenv("DATAPULSE_MCP_SOURCE_DATE", "1999-12-31")\n',
        encoding="utf-8",
    )
    deployed.write_text("old deployed source\n", encoding="utf-8")
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    (fake_bin / "systemctl").write_text(
        "#!/usr/bin/env bash\nexit 0\n", encoding="utf-8"
    )
    (fake_bin / "systemctl").chmod(0o755)
    env = {
        "PATH": f"{fake_bin}:{os.environ['PATH']}",
        "DATAPULSE_MCP_SOURCE_SHA": "a" * 40,
        "DATAPULSE_MCP_SOURCE_DATE": "2024-01-15",
    }
    return source, deployed, env


def _run_readiness_sync(
    source: Path,
    deployed: Path,
    endpoint: str,
    env: dict[str, str],
    budget: str,
    timeout: float,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            str(SYNC_SCRIPT),
            "--source",
            str(source),
            "--deployed-path",
            str(deployed),
            "--endpoint",
            endpoint,
            "--service",
            "sync-test.service",
            "--drop-in",
            str(deployed.parent / "drop-in.conf"),
        ],
        cwd=ROOT,
        env={**env, "DATAPULSE_MCP_READINESS_BUDGET_SECONDS": budget},
        capture_output=True,
        text=True,
        check=False,
        timeout=timeout,
    )


def test_sync_readiness_budget_outlasts_refused_port(tmp_path: Path) -> None:
    """A draining service keeps the port refused for longer than the retired
    poll's effective ~10s window; the budgeted deadline must wait it out,
    deploy, and report the measured wait so future resizes start from data."""
    source, deployed, env = _readiness_fixture(tmp_path)
    port = _free_scratch_port()
    stub = _DelayedMCPStub(port, delay=15.0)
    stub.start()
    try:
        result = _run_readiness_sync(
            source,
            deployed,
            f"http://127.0.0.1:{port}/mcp",
            env,
            budget="30",
            timeout=90,
        )
    finally:
        stub.close()

    assert result.returncode == 0, result.stderr
    waited = re.search(r"readiness wait=(\d+)s budget=(\d+)s", result.stdout)
    assert waited is not None, result.stdout
    assert waited.group(2) == "30"
    # The stub refused connections for 15s; the sync subprocess reaches the
    # poll ~1s in, so the deadline must have absorbed >= 12s of refusal —
    # beyond the old 10-attempt/1s window, which would have rolled back.
    assert int(waited.group(1)) >= 12
    assert deployed.read_text(encoding="utf-8") == (
        'import os\n'
        'FASTMCP_VERSION = "1.2.3"\n'
        'SOURCE_COMMIT_SHA = os.getenv("DATAPULSE_MCP_SOURCE_SHA", "'
        + "a" * 40
        + '")\n'
        'SOURCE_COMMIT_DATE = os.getenv("DATAPULSE_MCP_SOURCE_DATE", "2024-01-15")\n'
    )


def test_sync_dead_endpoint_rolls_back_within_budget(tmp_path: Path) -> None:
    """A bigger budget must not turn a genuinely dead endpoint into a success:
    the poll gives up at the deadline, rolls back, and reports the wait."""
    source, deployed, env = _readiness_fixture(tmp_path)
    port = _free_scratch_port()
    listener = _SilentListener(port)
    listener.start()
    try:
        result = _run_readiness_sync(
            source,
            deployed,
            f"http://127.0.0.1:{port}/mcp",
            env,
            budget="3",
            timeout=60,
        )
    finally:
        listener.close()

    assert result.returncode != 0
    assert "rolling back failed deployment" in result.stdout
    assert "local endpoint did not initialize after restart" in result.stderr
    waited = re.search(r"waited (\d+)s of 3s readiness budget", result.stderr)
    assert waited is not None, result.stderr
    assert int(waited.group(1)) >= 3
    assert "DATAPULSE_MCP_READINESS_BUDGET_SECONDS" in result.stderr
    assert deployed.read_text(encoding="utf-8") == "old deployed source\n"


def test_sync_rejects_malformed_readiness_budget(tmp_path: Path) -> None:
    source, deployed, env = _readiness_fixture(tmp_path)
    result = _run_readiness_sync(
        source,
        deployed,
        "http://127.0.0.1:1/mcp",
        env,
        budget="soon",
        timeout=30,
    )

    assert result.returncode != 0
    assert "DATAPULSE_MCP_READINESS_BUDGET_SECONDS" in result.stderr
    assert "positive integer" in result.stderr
    assert deployed.read_text(encoding="utf-8") == "old deployed source\n"
