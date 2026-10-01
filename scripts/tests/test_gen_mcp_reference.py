"""Tests for MCP public-surface source identity generation."""

from __future__ import annotations

import asyncio
import json
import os
import shutil
import subprocess
import textwrap
from pathlib import Path

import pytest

from scripts import gen_mcp_reference
from scripts.verify_mcp_deployment import newest_mcp_sha


ROOT = gen_mcp_reference.ROOT
SERVER_DATE = "2026-09-07"
OTHER_SHA = "f" * 40


def _capture_generation(
    monkeypatch: pytest.MonkeyPatch,
) -> dict[Path, str]:
    """Capture generated public surfaces without writing to the checkout."""
    rendered: dict[Path, str] = {}

    def capture_outputs(outputs: dict[Path, str], *, check: bool = False) -> bool:
        assert check is False
        rendered.update(outputs)
        return False

    monkeypatch.setattr(gen_mcp_reference, "publish_text_outputs", capture_outputs)
    return rendered


def test_direct_generation_publishes_identity_derived_from_mcp_history(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """No injected identity publishes the newest revision that changed ``mcp/``."""
    monkeypatch.delenv("DATAPULSE_SOURCE_COMMIT_SHA", raising=False)
    monkeypatch.delenv("DATAPULSE_SOURCE_COMMIT_DATE", raising=False)
    rendered = _capture_generation(monkeypatch)

    changed = asyncio.run(gen_mcp_reference.generate(ROOT))

    expected_sha = newest_mcp_sha(ROOT)
    expected_date = gen_mcp_reference._source_commit_date(ROOT, expected_sha)
    assert changed is False
    mcp_server = json.loads(rendered[ROOT / "mcp.json"])["server"]
    assert mcp_server["source_commit_sha"] == expected_sha
    assert mcp_server["source_commit_date"] == expected_date
    assert json.loads(rendered[ROOT / "agent.json"])["source"] == {
        "commit_sha": expected_sha,
        "commit_date": expected_date,
    }


def test_direct_generation_publishes_explicitly_injected_identity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An explicit source identity overrides the revision derived from history."""
    rendered = _capture_generation(monkeypatch)

    changed = asyncio.run(
        gen_mcp_reference.generate(
            ROOT,
            source_sha=OTHER_SHA,
            source_date=SERVER_DATE,
        )
    )

    assert changed is False
    assert json.loads(rendered[ROOT / "mcp.json"])["server"]["source_commit_sha"] == OTHER_SHA
    assert json.loads(rendered[ROOT / "agent.json"])["source"] == {
        "commit_sha": OTHER_SHA,
        "commit_date": SERVER_DATE,
    }


def test_environment_injection_supplies_the_source_identity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Environment injection remains a supported explicit identity source."""
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
