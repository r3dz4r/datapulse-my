"""Contract for the revision the MCP sync verifies against the served endpoint.

Every case builds a throwaway git repository and a loopback stub serving a
chosen revision. Nothing here contacts the live MCP service or the observer's
breaker state.
"""

from __future__ import annotations

import json
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any, Iterator

import pytest

from scripts.verify_mcp_deployment import (
    EXIT_MISMATCH,
    EXIT_UNREACHABLE,
    EXIT_UNRESOLVED,
    RepositoryHistoryError,
    newest_mcp_sha,
)


ROOT = Path(__file__).resolve().parents[2]
VERIFY_SCRIPT = ROOT / "scripts/verify_mcp_deployment.py"


def _git(repo: Path, *args: str) -> str:
    return subprocess.check_output(["git", "-C", str(repo), *args], text=True).strip()


def _commit(repo: Path, path: str, text: str, message: str) -> str:
    target = repo / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")
    _git(repo, "add", path)
    _git(repo, "commit", "-qm", message)
    return _git(repo, "rev-parse", "HEAD")


@pytest.fixture
def checkout(tmp_path: Path) -> tuple[Path, str]:
    """A clone whose origin/main tip is not the newest deployed-code commit.

    Returns the clone and the commit that must be resolved: the newest
    origin/main commit touching deployed MCP code. Newer non-runtime commits on
    main, and a newer server.py change only on a side branch, must not win.
    """
    upstream = tmp_path / "upstream"
    upstream.mkdir()
    _git(upstream, "init", "-q", "-b", "main")
    _git(upstream, "config", "user.email", "test@example.invalid")
    _git(upstream, "config", "user.name", "Test")
    _commit(upstream, "mcp/server.py", "first\n", "mcp: first")
    expected = _commit(upstream, "mcp/server.py", "stateless\n", "mcp: stateless")
    _commit(upstream, "mcp/README.md", "docs\n", "docs: not runtime")
    _commit(upstream, "health/latest.json", "{}\n", "chore(health): tip")
    _git(upstream, "checkout", "-qb", "side")
    _commit(upstream, "mcp/server.py", "unmerged\n", "mcp: unmerged")
    _git(upstream, "checkout", "-q", "main")

    clone = tmp_path / "clone"
    _git(tmp_path, "clone", "-q", str(upstream), str(clone))
    # The served checkout runs detached on a health commit, never on main.
    _git(clone, "checkout", "-q", "--detach", "origin/side")
    return clone, expected


class _Stub(BaseHTTPRequestHandler):
    """Stateless MCP: no Mcp-Session-Id, tools/list answers without a session."""

    version = "v4.0.0b3+0000000"
    tools: Any = [{"name": "probe"}]
    calls: list[str] = []

    def do_POST(self) -> None:  # noqa: N802
        request = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        type(self).calls.append(request["method"])
        if request["method"] == "initialize":
            result: dict[str, Any] = {
                "protocolVersion": "2025-03-26",
                "capabilities": {},
                "serverInfo": {"name": "DataPulse", "version": type(self).version},
            }
        else:
            result = {"tools": type(self).tools}
        body = f"event: message\ndata: {json.dumps({'jsonrpc': '2.0', 'id': request.get('id'), 'result': result})}\n\n"
        encoded = body.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def log_message(self, format: str, *args: object) -> None:
        return


@pytest.fixture
def served() -> Iterator[tuple[str, type[_Stub]]]:
    handler = type("Stub", (_Stub,), {"calls": [], "tools": [{"name": "probe"}]})
    server = HTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}/mcp", handler
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def _verify(endpoint: str, repo: Path, *, cwd: Path, branch: str | None = "main") -> subprocess.CompletedProcess[str]:
    args = [sys.executable, str(VERIFY_SCRIPT), "--endpoint", endpoint, "--repo-path", str(repo)]
    if branch is not None:
        args += ["--default-branch", branch]
    return subprocess.run(args, cwd=cwd, capture_output=True, text=True, check=False, timeout=20)


# --- the resolver -----------------------------------------------------------


def test_resolver_returns_newest_deployed_code_commit_on_default_branch(
    checkout: tuple[Path, str],
) -> None:
    clone, expected = checkout
    assert _git(clone, "rev-parse", "origin/main") != expected
    assert newest_mcp_sha(clone) == expected
    assert newest_mcp_sha(clone, "main") == expected


@pytest.mark.parametrize("subdir", ["mcp", "scripts"])
def test_resolver_answers_the_same_from_a_subdirectory(
    checkout: tuple[Path, str], subdir: str,
) -> None:
    """The live failure: the pipeline-side run resolved pathspecs from its cwd."""
    clone, expected = checkout
    (clone / subdir).mkdir(exist_ok=True)
    assert newest_mcp_sha(clone / subdir, "main") == expected


def test_resolver_refuses_a_requested_branch_the_checkout_lacks(
    checkout: tuple[Path, str],
) -> None:
    clone, _ = checkout
    with pytest.raises(RepositoryHistoryError, match="differs from requested"):
        newest_mcp_sha(clone, "trunk")


def test_resolver_refuses_rather_than_guessing_head_when_origin_ref_is_absent(
    checkout: tuple[Path, str], tmp_path: Path,
) -> None:
    clone, _ = checkout
    _git(clone, "update-ref", "--no-deref", "-d", "refs/remotes/origin/HEAD")
    _git(clone, "update-ref", "-d", "refs/remotes/origin/main")
    _git(clone, "remote", "set-url", "origin", str(tmp_path / "gone"))
    # HEAD still has deployed-code history, so a guess would look plausible.
    assert _git(clone, "log", "-1", "--format=%H", "HEAD", "--", "mcp/server.py")

    with pytest.raises(RepositoryHistoryError):
        newest_mcp_sha(clone)
    with pytest.raises(RepositoryHistoryError):
        newest_mcp_sha(clone, "main")


# --- the comparison ---------------------------------------------------------


def test_matching_served_revision_passes_over_stateless_transport(
    checkout: tuple[Path, str], served: tuple[str, type[_Stub]],
) -> None:
    clone, expected = checkout
    endpoint, stub = served
    stub.version = f"v4.0.0b3+{expected[:7]}"

    result = _verify(endpoint, clone, cwd=clone / "mcp")

    assert result.returncode == 0, result.stdout
    assert result.stdout.startswith(f"OK: deployed {expected[:7]}")
    assert stub.calls == ["initialize", "tools/list"]


def test_stale_served_revision_is_a_mismatch_failure_not_a_skip(
    checkout: tuple[Path, str], served: tuple[str, type[_Stub]],
) -> None:
    clone, expected = checkout
    endpoint, stub = served
    stale = _git(clone, "rev-parse", "origin/main~3")  # mcp: first
    stub.version = f"v4.0.0b3+{stale[:7]}"

    result = _verify(endpoint, clone, cwd=clone)

    assert result.returncode == EXIT_MISMATCH
    assert result.stdout.startswith(f"MISMATCH: deployed={stale[:7]} ")
    assert expected in result.stdout
    assert "skip" not in result.stdout.lower()


def test_stateless_endpoint_must_still_list_tools(
    checkout: tuple[Path, str], served: tuple[str, type[_Stub]],
) -> None:
    clone, expected = checkout
    endpoint, stub = served
    stub.version = f"v4.0.0b3+{expected[:7]}"
    stub.tools = None

    result = _verify(endpoint, clone, cwd=clone)

    assert result.returncode == EXIT_UNREACHABLE
    assert "tools/list response omitted the tools array" in result.stdout


def test_unresolvable_revision_is_distinguishable_from_a_mismatch(
    checkout: tuple[Path, str], served: tuple[str, type[_Stub]],
) -> None:
    clone, _ = checkout
    endpoint, stub = served

    unresolved = _verify(endpoint, clone, cwd=clone, branch="trunk")
    mismatch = _verify(endpoint, clone, cwd=clone)

    assert unresolved.returncode == EXIT_UNRESOLVED
    assert unresolved.stdout.startswith("UNRESOLVED: cannot establish expected deployed MCP code revision")
    assert mismatch.returncode == EXIT_MISMATCH
    assert len({EXIT_MISMATCH, EXIT_UNREACHABLE, EXIT_UNRESOLVED, 0}) == 4
    # No expected revision means no comparison: the endpoint is not consulted.
    assert stub.calls == ["initialize", "tools/list"]
