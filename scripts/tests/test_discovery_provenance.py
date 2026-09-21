"""Guard the published discovery artefacts against source-identity drift."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

from scripts import gen_mcp_reference


ROOT = Path(__file__).resolve().parents[2]
DISCOVERY_ARTIFACTS = ("mcp.json", "agent.json")


def _agent_commit_sha(path: Path) -> str:
    document = json.loads(path.read_text(encoding="utf-8"))
    return document["source"]["commit_sha"]


def _assert_agent_identity(root: Path, agent_path: Path) -> None:
    """Reject an agent manifest whose source SHA differs from server.py."""
    expected_sha = gen_mcp_reference._checked_in_server_marker(root)
    actual_sha = _agent_commit_sha(agent_path)
    assert actual_sha == expected_sha, (
        f"agent.json source.commit_sha ({actual_sha}) differs from "
        f"mcp/server.py SOURCE_COMMIT_SHA ({expected_sha})"
    )


def test_agent_manifest_commit_sha_matches_server_marker() -> None:
    _assert_agent_identity(ROOT, ROOT / "agent.json")


def test_discovery_artifacts_are_byte_identical_to_regeneration(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Render in memory so this gate cannot modify the caller's worktree."""
    committed = {
        relative: (ROOT / relative).read_text(encoding="utf-8")
        for relative in DISCOVERY_ARTIFACTS
    }
    agent = json.loads(committed["agent.json"])
    rendered: dict[Path, str] = {}

    def capture_outputs(outputs: dict[Path, str], *, check: bool = False) -> bool:
        assert check is False
        rendered.update(outputs)
        return False

    monkeypatch.setattr(gen_mcp_reference, "publish_text_outputs", capture_outputs)

    asyncio.run(
        gen_mcp_reference.generate(
            ROOT,
            source_sha=gen_mcp_reference._checked_in_server_marker(ROOT),
            source_date=agent["source"]["commit_date"],
        )
    )

    for relative, content in committed.items():
        assert rendered[ROOT / relative] == content
        assert (ROOT / relative).read_text(encoding="utf-8") == content


def test_identity_guard_rejects_mismatched_agent_manifest(tmp_path: Path) -> None:
    mismatched_agent = tmp_path / "agent.json"
    mismatched_agent.write_text(
        json.dumps({"source": {"commit_sha": "d" * 40}}), encoding="utf-8"
    )

    with pytest.raises(AssertionError, match="agent.json source.commit_sha .* differs"):
        _assert_agent_identity(ROOT, mismatched_agent)
