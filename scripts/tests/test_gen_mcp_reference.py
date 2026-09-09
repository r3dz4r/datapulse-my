"""Tests for MCP public-surface source identity generation."""

from __future__ import annotations

import asyncio
import os
import shutil
import subprocess
import textwrap
from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts import gen_mcp_reference
from scripts.public_surface_generation import GenerationError
from scripts.public_surface_generation import load_public_surfaces, replace_owned_block


ROOT = gen_mcp_reference.ROOT
SERVER_SHA = gen_mcp_reference._checked_in_server_marker(ROOT)
SERVER_DATE = "2026-09-07"
OTHER_SHA = "f" * 40


def test_direct_generation_accepts_the_checked_in_server_marker() -> None:
    changed = asyncio.run(
        gen_mcp_reference.generate(
            ROOT,
            source_sha=SERVER_SHA,
            source_date=SERVER_DATE,
            validate_only=True,
        )
    )

    assert changed is False


def test_direct_generation_rejects_a_different_source_marker() -> None:
    with pytest.raises(GenerationError, match="checked-in mcp/server.py marker"):
        asyncio.run(
            gen_mcp_reference.generate(
                ROOT,
                source_sha=OTHER_SHA,
                source_date=SERVER_DATE,
                validate_only=True,
            )
        )


def test_direct_generation_accepts_injected_sha_for_dev_fixture_marker(tmp_path: Path) -> None:
    server = tmp_path / "mcp" / "server.py"
    server.parent.mkdir()
    server.write_text(
        'import os\nSOURCE_COMMIT_SHA = os.getenv("DATAPULSE_MCP_SOURCE_SHA", "dev")\n',
        encoding="utf-8",
    )

    gen_mcp_reference._validate_server_marker(tmp_path, OTHER_SHA)


def test_release_build_accepts_an_injected_source_marker(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DATAPULSE_RELEASE_BUILD", "1")
    monkeypatch.setenv("DATAPULSE_SOURCE_COMMIT_SHA", OTHER_SHA)
    monkeypatch.setenv("DATAPULSE_SOURCE_COMMIT_DATE", SERVER_DATE)

    changed = asyncio.run(
        gen_mcp_reference.generate(
            ROOT,
            validate_only=True,
        )
    )

    assert changed is False


def test_release_build_profile_passes_the_explicit_override(tmp_path: Path) -> None:
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    shutil.copy2(ROOT / "scripts/generate.sh", scripts / "generate.sh")
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    marker = tmp_path / "release-build-context.txt"
    for command in ("python3", "bash"):
        executable = fake_bin / command
        executable.write_text(
            textwrap.dedent(
                """\
                #!/bin/sh
                printf '%s\\n' "${DATAPULSE_RELEASE_BUILD:-}" >> "$DATAPULSE_ENV_LOG"
                """
            ),
            encoding="utf-8",
        )
        executable.chmod(0o755)

    result = subprocess.run(
        ["/bin/bash", "scripts/generate.sh", "release-build"],
        cwd=tmp_path,
        env={
            **os.environ,
            "DATAPULSE_ENV_LOG": str(marker),
            "PATH": f"{fake_bin}:{os.environ['PATH']}",
        },
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert marker.read_text(encoding="utf-8").splitlines()
    assert set(marker.read_text(encoding="utf-8").splitlines()) == {"1"}


def test_agent_quickstart_blocks_use_canonical_config_and_live_tool_metadata() -> None:
    config = load_public_surfaces(ROOT)
    tools = [
        SimpleNamespace(name="first", description="First tool"),
        SimpleNamespace(name="second", description="Second tool"),
    ]

    identity, mcp = gen_mcp_reference._agent_quickstart_blocks(
        config, [{"id": "alpha"}, {"id": "beta"}], tools
    )

    assert f"# {config['product_name']} — Agent Quickstart" in identity
    assert "DataPulse MY" not in identity + mcp
    assert f"{config['origins']['mcp']}/mcp" in mcp
    assert "2 read-only tools over 2 datasets" in mcp
    assert mcp.index("`first`") < mcp.index("`second`")


def test_agent_quickstart_owned_markers_replace_once_and_are_idempotent() -> None:
    source = (ROOT / "docs/agent-quickstart.md").read_text(encoding="utf-8")
    config = load_public_surfaces(ROOT)
    identity, mcp = gen_mcp_reference._agent_quickstart_blocks(
        config, [{"id": "alpha"}], [SimpleNamespace(name="live_tool", description="Live tool")]
    )

    rendered = replace_owned_block(
        replace_owned_block(source, "agent-quickstart-identity", identity),
        "agent-quickstart-mcp", mcp,
    )
    rerendered = replace_owned_block(
        replace_owned_block(rendered, "agent-quickstart-identity", identity),
        "agent-quickstart-mcp", mcp,
    )

    assert rendered == rerendered
    assert rendered.count("<!-- BEGIN agent-quickstart-mcp -->") == 1
    assert "1 read-only tools over 1 datasets" in rendered
