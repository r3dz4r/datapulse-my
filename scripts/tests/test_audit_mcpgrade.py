"""Hermetic tests for scripts/audit_mcpgrade.sh and audit_mcpgrade_parse.py."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

import pytest

from scripts.audit_mcpgrade_parse import parse_file, parse_mcpgrade_output

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "audit_mcpgrade.sh"
PARSE_HELPER = ROOT / "scripts" / "audit_mcpgrade_parse.py"
FIXTURES = ROOT / "scripts" / "tests" / "fixtures"


class TestScriptExistsAndValid:
    """Assert the bash script exists, is valid, and is executable."""

    def test_script_exists(self) -> None:
        assert SCRIPT.exists(), f"{SCRIPT} does not exist"

    def test_script_syntax(self) -> None:
        result = subprocess.run(["bash", "-n", str(SCRIPT)], capture_output=True, text=True)
        assert result.returncode == 0, f"bash -n failed: {result.stderr}"

    def test_script_executable(self) -> None:
        assert SCRIPT.stat().st_mode & 0o111, f"{SCRIPT} is not executable"

    def test_pins_mcpgrade_version(self) -> None:
        content = SCRIPT.read_text()
        assert 'MCPGRADE_VERSION="${MCPGRADE_VERSION:-' in content, (
            "Script must pin a default MCPGRADE_VERSION"
        )


class TestScriptArtifactPath:
    """Assert the script writes into artifacts/mcpgrade/ inside the repo."""

    def test_artifact_dir_inside_repo(self) -> None:
        content = SCRIPT.read_text()
        assert "artifacts/mcpgrade" in content, (
            "Script must reference artifacts/mcpgrade/ directory"
        )

    def test_no_writes_outside_repo(self) -> None:
        content = SCRIPT.read_text()
        # Should not contain absolute paths outside the repo
        assert "/tmp/mcpgrade" not in content
        assert "/var/mcpgrade" not in content
        assert "/home/" not in content.split("REPO_ROOT")[0]


class TestParseHelperValid:
    """Test the parse helper with a valid mcpgrade fixture."""

    def test_parse_valid_fixture(self) -> None:
        fixture = FIXTURES / "mcpgrade-valid.json"
        result = parse_file(fixture)
        assert result is not None
        assert result["grade"] == "A"
        assert result["total_score"] == 100
        assert result["tools"] == 18

    def test_parse_mcpgrade_output_dict(self) -> None:
        data: dict[str, Any] = {
            "snapshot": {"source": "https://example.com", "toolCount": 10},
            "totalScore": 85,
            "grade": "B",
        }
        result = parse_mcpgrade_output(data)
        assert result is not None
        assert result["grade"] == "B"
        assert result["total_score"] == 85
        assert result["tools"] == 10


class TestParseHelperUnknown:
    """Test the UNKNOWN exit path with malformed or incomplete fixtures."""

    def test_malformed_json(self) -> None:
        fixture = FIXTURES / "mcpgrade-malformed.json"
        result = parse_file(fixture)
        assert result is None

    def test_missing_fields(self) -> None:
        fixture = FIXTURES / "mcpgrade-missing-fields.json"
        result = parse_file(fixture)
        assert result is None

    def test_empty_dict(self) -> None:
        result = parse_mcpgrade_output({})
        assert result is None

    def test_missing_snapshot(self) -> None:
        result = parse_mcpgrade_output({"grade": "A", "totalScore": 100})
        assert result is None

    def test_null_grade(self) -> None:
        result = parse_mcpgrade_output({
            "grade": None,
            "totalScore": 100,
            "snapshot": {"toolCount": 18},
        })
        assert result is None


class TestParseHelperCLI:
    """Test the parse helper CLI interface."""

    def test_cli_valid(self) -> None:
        fixture = FIXTURES / "mcpgrade-valid.json"
        result = subprocess.run(
            ["python3", str(PARSE_HELPER), str(fixture)],
            capture_output=True, text=True,
        )
        assert result.returncode == 0
        assert "OK:" in result.stdout
        assert "grade=A" in result.stdout
        assert "score=100" in result.stdout
        assert "tools=18" in result.stdout

    def test_cli_malformed(self) -> None:
        fixture = FIXTURES / "mcpgrade-malformed.json"
        result = subprocess.run(
            ["python3", str(PARSE_HELPER), str(fixture)],
            capture_output=True, text=True,
        )
        assert result.returncode == 3
        assert "UNKNOWN" in result.stderr

    def test_cli_json_format(self) -> None:
        fixture = FIXTURES / "mcpgrade-valid.json"
        result = subprocess.run(
            ["python3", str(PARSE_HELPER), str(fixture), "--format", "json"],
            capture_output=True, text=True,
        )
        assert result.returncode == 0
        parsed = json.loads(result.stdout)
        assert parsed["grade"] == "A"
        assert parsed["total_score"] == 100
        assert parsed["tools"] == 18
