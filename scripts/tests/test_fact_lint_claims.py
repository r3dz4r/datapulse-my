#!/usr/bin/env python3
"""Regression tests for the opt-in claim-ledger checker."""

from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess
import sys

import pytest


ROOT = Path(__file__).resolve().parents[2]
FACT_LINT = ROOT / "scripts" / "fact_lint.py"
LEDGER = ROOT / "claims" / "claims.json"


def claim_tree(tmp_path: Path) -> Path:
    """Create the small repository copy needed by the claim checker."""
    shutil.copytree(ROOT / "claims", tmp_path / "claims")
    for relative_path in ("README.md", "llms.txt", "mcp.json"):
        shutil.copy2(ROOT / relative_path, tmp_path / relative_path)
    shutil.copytree(ROOT / "docs", tmp_path / "docs")
    return tmp_path


def run_claim_check(root: Path) -> subprocess.CompletedProcess[str]:
    """Run the CLI against one tree and retain its diagnostics."""
    return subprocess.run(
        [sys.executable, str(FACT_LINT), "--root", str(root), "--check-claims"],
        check=False,
        capture_output=True,
        text=True,
    )


def test_clean_state_passes() -> None:
    result = run_claim_check(ROOT)

    assert result.returncode == 0, result.stdout + result.stderr


def test_forbidden_phrase_detected(tmp_path: Path) -> None:
    root = claim_tree(tmp_path)
    readme = root / "README.md"
    readme.write_text(
        readme.read_text(encoding="utf-8") + "\nWe list verified datasets.\n",
        encoding="utf-8",
    )

    result = run_claim_check(root)

    assert result.returncode == 1
    assert "README.md" in result.stdout
    assert "verified datasets" in result.stdout


def test_ledger_field_missing_detected(tmp_path: Path) -> None:
    root = claim_tree(tmp_path)
    ledger = json.loads((root / "claims" / "claims.json").read_text(encoding="utf-8"))
    del ledger["claims"][0]["evidence_source"]
    (root / "claims" / "claims.json").write_text(
        json.dumps(ledger), encoding="utf-8"
    )

    result = run_claim_check(root)

    assert result.returncode == 1
    assert "missing required field 'evidence_source'" in result.stdout


def test_allowed_occurrence_outside_allowlist_detected(tmp_path: Path) -> None:
    root = claim_tree(tmp_path)
    learn = root / "docs" / "learn.html"
    learn.write_text(
        learn.read_text(encoding="utf-8") + "\n<p>authoritative</p>\n",
        encoding="utf-8",
    )

    result = run_claim_check(root)

    assert result.returncode == 1
    assert "docs/learn.html" in result.stdout
    assert "unscoped claim phrase 'authoritative'" in result.stdout


def test_forbidden_phrase_outside_scope_detected(tmp_path: Path) -> None:
    root = claim_tree(tmp_path)
    learn = root / "docs" / "learn.html"
    learn.write_text(
        learn.read_text(encoding="utf-8") + "\n<p>standard deviation</p>\n",
        encoding="utf-8",
    )

    result = run_claim_check(root)

    assert result.returncode == 1
    assert "docs/learn.html" in result.stdout
    assert "standard deviation" in result.stdout


@pytest.mark.parametrize(
    "field",
    (
        "claim_id",
        "phrase_pattern",
        "verification_mode",
        "scope_statement",
        "evidence_source",
        "last_audit_date",
        "re_audit_trigger",
    ),
)
def test_ledger_structure_validates_each_required_field(
    tmp_path: Path, field: str
) -> None:
    root = claim_tree(tmp_path)
    ledger_path = root / "claims" / "claims.json"
    ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
    del ledger["claims"][0][field]
    ledger_path.write_text(json.dumps(ledger), encoding="utf-8")

    result = run_claim_check(root)

    assert result.returncode == 1
    assert f"missing required field '{field}'" in result.stdout
