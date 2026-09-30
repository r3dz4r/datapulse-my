#!/usr/bin/env python3
"""Compare a deployed MCP server's source marker with default-branch history."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


DEFAULT_ENDPOINT = "https://mcp.data-pulse.my/mcp"
ACCEPT = "application/json, text/event-stream"
PROTOCOL_VERSION = "2025-03-26"
VERSION_SHA_RE = re.compile(r"\+([0-9a-f]{7,40})$")
SHA_RE = re.compile(r"^[0-9a-f]{40}$")


class RepositoryHistoryError(ValueError):
    """The checkout cannot provide an authoritative default-branch revision."""


def extract_deployed_sha(server_info: dict[str, Any]) -> str:
    sha = server_info.get("source_commit_sha")
    if isinstance(sha, str) and sha:
        return sha
    version = server_info.get("version", "")
    m = VERSION_SHA_RE.search(version)
    if m:
        return m.group(1)
    return "<missing>"


def _git(repo_path: Path, *args: str) -> str:
    """Run a read-only Git query and return its stripped standard output."""
    try:
        result = subprocess.run(
            ["git", "-C", str(repo_path), *args],
            capture_output=True,
            check=False,
            text=True,
        )
    except OSError as error:
        raise RepositoryHistoryError(f"unable to run git: {error}") from error
    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip() or "git command failed"
        raise RepositoryHistoryError(detail)
    return result.stdout.strip()


def default_branch_ref(repo_path: Path, default_branch: str | None = None) -> str:
    """Return the default branch ref without guessing from the current HEAD."""
    if default_branch is not None:
        ref = f"refs/remotes/origin/{default_branch}"
        try:
            _git(repo_path, "rev-parse", "--verify", f"{ref}^{{commit}}")
        except RepositoryHistoryError:
            return _remote_default_branch_revision(repo_path, expected_ref=ref)
        return ref
    try:
        ref = _git(repo_path, "symbolic-ref", "--quiet", "refs/remotes/origin/HEAD")
    except RepositoryHistoryError:
        return _remote_default_branch_revision(repo_path)
    if not ref.startswith("refs/remotes/origin/"):
        raise RepositoryHistoryError(f"origin default branch has unexpected ref {ref!r}")
    try:
        _git(repo_path, "rev-parse", "--verify", f"{ref}^{{commit}}")
    except RepositoryHistoryError:
        return _remote_default_branch_revision(repo_path, expected_ref=ref)
    return ref


def _remote_default_branch_revision(
    repo_path: Path, *, expected_ref: str | None = None,
) -> str:
    """Resolve the remote's advertised default branch when its local symref is absent."""
    advertised = _git(repo_path, "ls-remote", "--symref", "origin", "HEAD").splitlines()
    try:
        symbolic, revision = advertised[:2]
        advertised_ref, symbolic_name = symbolic.removeprefix("ref: ").split("\t", 1)
        advertised_sha, revision_name = revision.split("\t", 1)
    except ValueError as error:
        raise RepositoryHistoryError("origin did not advertise a default branch") from error
    if symbolic_name != "HEAD" or revision_name != "HEAD":
        raise RepositoryHistoryError("origin default branch advertisement is malformed")
    branch = advertised_ref.split("/", 2)[-1]
    ref = f"refs/remotes/origin/{branch}"
    if expected_ref is not None and ref != expected_ref:
        raise RepositoryHistoryError(
            f"origin default branch {ref!r} differs from requested {expected_ref!r}"
        )
    try:
        _git(repo_path, "rev-parse", "--verify", f"{ref}^{{commit}}")
        return ref
    except RepositoryHistoryError:
        _git(repo_path, "rev-parse", "--verify", f"{advertised_sha}^{{commit}}")
        return advertised_sha


def newest_mcp_sha(repo_path: Path, default_branch: str | None = None) -> str:
    """Return the newest default-branch commit that changes ``mcp/``.

    A shallow checkout can omit an older ``mcp/`` commit and would therefore
    manufacture a false match. Refuse it rather than treating its tip as proof.
    """
    if _git(repo_path, "rev-parse", "--is-shallow-repository") == "true":
        raise RepositoryHistoryError(
            "repository history is shallow; cannot derive newest mcp/ revision"
        )
    ref = default_branch_ref(repo_path, default_branch)
    sha = _git(repo_path, "log", "-1", "--format=%H", ref, "--", "mcp/")
    if not SHA_RE.fullmatch(sha):
        raise RepositoryHistoryError(
            f"default branch {ref} has no resolvable commit touching mcp/"
        )
    return sha


def _decode_response(payload: bytes) -> dict[str, Any]:
    text = payload.decode("utf-8")
    if not text.strip():
        return {}
    if text.lstrip().startswith("{"):
        return json.loads(text)
    for line in text.splitlines():
        if line.startswith("data: "):
            message = json.loads(line.removeprefix("data: "))
            if isinstance(message, dict):
                return message
    raise ValueError("MCP endpoint returned neither JSON nor a JSON SSE event")


def _post(
    endpoint: str,
    message: dict[str, Any],
    *,
    session_id: str | None = None,
) -> tuple[dict[str, Any], str | None]:
    headers = {
        "Accept": ACCEPT,
        "Content-Type": "application/json",
        "User-Agent": "DataPulse-MCP-Deployment-Verify/1.0",
    }
    if session_id is not None:
        headers["Mcp-Session-Id"] = session_id
    request = Request(
        endpoint,
        data=json.dumps(message, separators=(",", ":")).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    with urlopen(request, timeout=15) as response:
        return _decode_response(response.read()), response.headers.get("Mcp-Session-Id")


def deployed_source_sha(endpoint: str) -> str:
    initialized, session_id = _post(
        endpoint,
        {
            "jsonrpc": "2.0",
            "method": "initialize",
            "params": {
                "protocolVersion": PROTOCOL_VERSION,
                "capabilities": {},
                "clientInfo": {"name": "verify-mcp-deployment", "version": "1"},
            },
            "id": 1,
        },
    )
    if not session_id:
        raise ValueError("initialize response omitted Mcp-Session-Id")
    server_info = initialized.get("result", {}).get("serverInfo", {})

    _post(
        endpoint,
        {"jsonrpc": "2.0", "method": "notifications/initialized"},
        session_id=session_id,
    )
    tools, _ = _post(
        endpoint,
        {"jsonrpc": "2.0", "method": "tools/list", "id": 2},
        session_id=session_id,
    )
    if not isinstance(tools.get("result", {}).get("tools"), list):
        raise ValueError("tools/list response omitted the tools array")
    return extract_deployed_sha(server_info)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--endpoint", default=DEFAULT_ENDPOINT)
    parser.add_argument("--repo-path", type=Path, default=Path.cwd())
    parser.add_argument(
        "--default-branch",
        help="Default branch checked out by the caller; avoids inferring from detached HEAD.",
    )
    parser.add_argument(
        "--deployed-path",
        type=Path,
        help="Accepted for deployment-tool compatibility; endpoint introspection is authoritative.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        expected_sha = newest_mcp_sha(args.repo_path, args.default_branch)
        deployed_sha = deployed_source_sha(args.endpoint)
    except RepositoryHistoryError as error:
        print(f"UNREACHABLE: cannot establish expected newest mcp/ revision: {error}")
        return 2
    except (HTTPError, URLError, TimeoutError, OSError, ValueError) as error:
        print(f"UNREACHABLE: {error}")
        return 2

    if deployed_sha[:7] == expected_sha[:7]:
        print(
            f"OK: deployed {deployed_sha[:7]} matches newest mcp/ revision "
            f"{expected_sha} on default branch, rather than matches recorded stamp "
            "in mcp.json"
        )
        return 0
    print(
        f"MISMATCH: deployed={deployed_sha} newest mcp/ revision={expected_sha} "
        "on default branch"
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
