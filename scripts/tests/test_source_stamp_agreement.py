"""Every published MCP discovery artefact must carry one source stamp.

``mcp.json`` and ``agent.json`` come from ``gen_mcp_reference`` and the
per-tool cards from ``gen_ai_catalog``. Both must resolve the stamp through the
same derivation, honour the same injected identity, and stay independent of
whatever ``refs/remotes/origin/HEAD`` a given machine points at. Fixtures are
local clones only; nothing here touches the network.
"""

from __future__ import annotations

import asyncio
import json
import logging
import shutil
import subprocess
from pathlib import Path

import pytest

from scripts import gen_ai_catalog, gen_mcp_reference
from scripts.verify_mcp_deployment import (
    SOURCE_COMMIT_DATE_ENV,
    SOURCE_COMMIT_SHA_ENV,
    newest_mcp_sha,
    resolve_source_identity,
)


ROOT = Path(__file__).resolve().parents[2]
INJECTED_SHA = "0123456789abcdef0123456789abcdef01234567"
INJECTED_DATE = "2026-01-02"
FIXTURE_FILES = (
    "mcp.json",
    "datapulse.json",
    "scripts/mcp-representative-queries.json",
    "mcp/server.py",
)


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        [
            "git", "-C", str(repo),
            "-c", "user.email=test@example.invalid", "-c", "user.name=Test User",
            "-c", "commit.gpgsign=false", "-c", "core.hooksPath=/dev/null",
            *args,
        ],
        capture_output=True, check=True, text=True,
    ).stdout.strip()


@pytest.fixture
def clone(tmp_path: Path) -> tuple[Path, str, str]:
    """Return a clone whose ``main`` and ``feature`` tips differ in MCP history."""
    upstream = tmp_path / "upstream"
    for relative in FIXTURE_FILES:
        (upstream / relative).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / relative, upstream / relative)
    _git(upstream.parent, "init", "--quiet", "--initial-branch=main", str(upstream))
    _git(upstream, "add", ".")
    _git(upstream, "commit", "--quiet", "-m", "main mcp")
    main_sha = _git(upstream, "rev-parse", "HEAD")
    _git(upstream, "switch", "--quiet", "-c", "feature")
    with (upstream / "mcp/server.py").open("a", encoding="utf-8") as handle:
        handle.write("\n# feature-only MCP change\n")
    _git(upstream, "commit", "--quiet", "-am", "feature mcp")
    feature_sha = _git(upstream, "rev-parse", "HEAD")
    _git(upstream, "switch", "--quiet", "main")

    checkout = tmp_path / "checkout"
    _git(tmp_path, "clone", "--quiet", str(upstream), str(checkout))
    return checkout, main_sha, feature_sha


def _point_origin_head(checkout: Path, branch: str) -> None:
    _git(checkout, "remote", "set-head", "origin", branch)


def _card_stamps(cards: dict[str, bytes]) -> set[str]:
    return {json.loads(content)["source"]["commit_sha"] for content in cards.values()}


@pytest.fixture
def no_injection(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(SOURCE_COMMIT_SHA_ENV, raising=False)
    monkeypatch.delenv(SOURCE_COMMIT_DATE_ENV, raising=False)


def test_fixture_reproduces_the_ambient_ref_divergence(
    clone: tuple[Path, str, str], no_injection: None,
) -> None:
    """Guard the fixture: the raw lookup really does follow origin/HEAD."""
    checkout, main_sha, feature_sha = clone
    assert main_sha != feature_sha
    _point_origin_head(checkout, "main")
    assert newest_mcp_sha(checkout) == main_sha
    _point_origin_head(checkout, "feature")
    assert newest_mcp_sha(checkout) == feature_sha


@pytest.mark.parametrize("ambient", ["main", "feature"])
def test_injected_argument_wins_in_both_generators_whatever_origin_head(
    clone: tuple[Path, str, str], no_injection: None, ambient: str,
) -> None:
    checkout, _, _ = clone
    _point_origin_head(checkout, ambient)

    reference_stamp = gen_mcp_reference._source_identity(
        checkout, INJECTED_SHA, INJECTED_DATE,
    )
    _, cards = gen_ai_catalog.build_outputs(
        checkout, source_sha=INJECTED_SHA, source_date=INJECTED_DATE,
    )

    assert reference_stamp == (INJECTED_SHA, INJECTED_DATE)
    assert _card_stamps(cards) == {INJECTED_SHA}


@pytest.mark.parametrize("ambient", ["main", "feature"])
def test_injected_environment_wins_in_both_generators_whatever_origin_head(
    clone: tuple[Path, str, str], monkeypatch: pytest.MonkeyPatch, ambient: str,
) -> None:
    checkout, _, _ = clone
    _point_origin_head(checkout, ambient)
    monkeypatch.setenv(SOURCE_COMMIT_SHA_ENV, INJECTED_SHA)
    monkeypatch.setenv(SOURCE_COMMIT_DATE_ENV, INJECTED_DATE)

    reference_stamp = gen_mcp_reference._source_identity(checkout, None, None)
    _, cards = gen_ai_catalog.build_outputs(checkout)

    assert reference_stamp == (INJECTED_SHA, INJECTED_DATE)
    assert _card_stamps(cards) == {INJECTED_SHA}


def test_cards_are_byte_identical_under_either_origin_head_when_injected(
    clone: tuple[Path, str, str], no_injection: None,
) -> None:
    checkout, _, _ = clone
    rendered = []
    for ambient in ("main", "feature"):
        _point_origin_head(checkout, ambient)
        rendered.append(gen_ai_catalog.build_outputs(
            checkout, source_sha=INJECTED_SHA, source_date=INJECTED_DATE,
        ))
    assert rendered[0] == rendered[1]


def test_stated_branch_derives_the_same_stamp_whatever_origin_head(
    clone: tuple[Path, str, str], no_injection: None,
) -> None:
    checkout, main_sha, _ = clone
    for ambient in ("main", "feature"):
        _point_origin_head(checkout, ambient)
        sha, _ = gen_mcp_reference._source_identity(checkout, None, None, branch="main")
        _, cards = gen_ai_catalog.build_outputs(checkout, source_branch="main")
        assert sha == main_sha
        assert _card_stamps(cards) == {main_sha}


def test_ambient_fallback_is_logged_with_the_ref_it_used(
    clone: tuple[Path, str, str], no_injection: None, caplog: pytest.LogCaptureFixture,
) -> None:
    checkout, _, feature_sha = clone
    _point_origin_head(checkout, "feature")
    with caplog.at_level(logging.WARNING):
        sha, _ = resolve_source_identity(checkout)
    assert sha == feature_sha
    assert "ambient origin default ref refs/remotes/origin/feature" in caplog.text
    assert feature_sha in caplog.text


def test_injection_and_stated_branch_are_not_logged_as_ambient(
    clone: tuple[Path, str, str], no_injection: None, caplog: pytest.LogCaptureFixture,
) -> None:
    checkout, _, _ = clone
    with caplog.at_level(logging.WARNING):
        resolve_source_identity(checkout, INJECTED_SHA, INJECTED_DATE)
        resolve_source_identity(checkout, branch="main")
    assert "ambient" not in caplog.text


def test_repository_generators_publish_one_injected_stamp(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Full renders of mcp.json, agent.json and every card agree on injection."""
    monkeypatch.setenv(SOURCE_COMMIT_SHA_ENV, INJECTED_SHA)
    monkeypatch.setenv(SOURCE_COMMIT_DATE_ENV, INJECTED_DATE)
    rendered: dict[Path, str] = {}

    def capture_outputs(outputs: dict[Path, str], *, check: bool = False) -> bool:
        rendered.update(outputs)
        return False

    monkeypatch.setattr(gen_mcp_reference, "publish_text_outputs", capture_outputs)
    asyncio.run(gen_mcp_reference.generate(ROOT))
    _, cards = gen_ai_catalog.build_outputs(ROOT)

    mcp_server = json.loads(rendered[ROOT / "mcp.json"])["server"]
    agent_source = json.loads(rendered[ROOT / "agent.json"])["source"]
    assert mcp_server["source_commit_sha"] == INJECTED_SHA
    assert mcp_server["source_commit_date"] == INJECTED_DATE
    assert agent_source == {"commit_sha": INJECTED_SHA, "commit_date": INJECTED_DATE}
    assert _card_stamps(cards) == {INJECTED_SHA}


def test_committed_artefacts_carry_one_stamp() -> None:
    mcp_sha = json.loads((ROOT / "mcp.json").read_text(encoding="utf-8"))["server"]["source_commit_sha"]
    agent_sha = json.loads((ROOT / "agent.json").read_text(encoding="utf-8"))["source"]["commit_sha"]
    card_shas = {
        json.loads(path.read_text(encoding="utf-8"))["source"]["commit_sha"]
        for path in sorted((ROOT / "docs/mcp/cards").glob("*.json"))
    }
    assert card_shas
    assert {mcp_sha, agent_sha} | card_shas == {mcp_sha}
