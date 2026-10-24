#!/usr/bin/env python3
"""Offline decision contract for the read-only Pages arrival preflight."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

import pytest


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/deploy_preflight.py"
CANDIDATE = "a" * 40
OTHER = "b" * 40


@pytest.fixture
def served_proof(tmp_path: Path) -> Path:
    proof = tmp_path / "release-verification.md"
    proof.write_text(
        "# Release reproducibility verification\n\n"
        "<!-- generated: scripts/verify_release_reproducible.py; do not hand-edit -->\n"
        "- Status: `current generated release proof`\n"
        f"- Source SHA: `{CANDIDATE}`\n"
        "- Protocol result: `byte-identical isolated release-build runs`\n",
        encoding="utf-8",
    )
    return proof


def invoke(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=ROOT, text=True, capture_output=True, check=False,
    )


def decision(proof: Path, candidate: str = CANDIDATE) -> dict:
    result = invoke("--promotion-source-sha", candidate, "--served-proof", str(proof), "--mode", "json")
    assert result.returncode == 0, result.stderr
    assert not result.stderr
    return json.loads(result.stdout)


def test_identical_served_and_candidate_identities_skip(served_proof: Path) -> None:
    result = decision(served_proof)
    assert result["decision"] == "skip"
    assert result["reason_code"] == "identities_equal"
    assert result["candidate_identity"] == result["served_identity"] == CANDIDATE
    assert f"candidate={CANDIDATE}" in result["reason"]
    assert f"served={CANDIDATE}" in result["reason"]


def test_different_identity_publishes(served_proof: Path) -> None:
    result = decision(served_proof, OTHER)
    assert result["decision"] == "publish"
    assert result["reason_code"] == "identities_differ"
    assert result["candidate_identity"] == OTHER
    assert result["served_identity"] == CANDIDATE


def test_missing_served_proof_publishes(tmp_path: Path) -> None:
    result = decision(tmp_path / "missing.md")
    assert result["decision"] == "publish"
    assert result["reason_code"] == "comparison_unavailable"
    assert result["served_identity"] is None


@pytest.mark.parametrize("contents", [
    "{invalid JSON", "{}", "", "[]", "null", "- Source SHA: `" + CANDIDATE + "`\n",
])
def test_malformed_proof_publishes(served_proof: Path, contents: str) -> None:
    served_proof.write_text(contents, encoding="utf-8")
    result = decision(served_proof)
    assert result["decision"] == "publish"
    assert result["reason_code"] == "comparison_unavailable"


def test_unreadable_proof_publishes(tmp_path: Path) -> None:
    # A directory is unreadable as a proof even when the tests run as root.
    result = decision(tmp_path)
    assert result["decision"] == "publish"
    assert result["reason_code"] == "comparison_unavailable"


@pytest.mark.parametrize("candidate", ["", "abc123", "A" * 40, "a" * 41])
def test_absent_or_invalid_candidate_stamp_publishes(served_proof: Path, candidate: str) -> None:
    result = decision(served_proof, candidate)
    assert result["decision"] == "publish"
    assert result["reason_code"] == "comparison_unavailable"
    assert result["candidate_identity"] is None


def test_absent_inputs_publish() -> None:
    result = invoke("--mode", "json")
    assert result.returncode == 0
    assert json.loads(result.stdout)["decision"] == "publish"


@pytest.mark.parametrize("args", [("--promotion-source-sha",), ("--mode", "bad"), ("--unknown",)])
def test_invalid_invocation_publishes(args: tuple[str, ...]) -> None:
    result = invoke(*args)
    assert result.returncode == 0
    decision = json.loads(result.stdout)
    assert decision["decision"] == "publish"
    assert decision["reason_code"] == "comparison_unavailable"


def test_decisions_have_one_output_shape(served_proof: Path, tmp_path: Path) -> None:
    results = [decision(served_proof), decision(served_proof, OTHER), decision(tmp_path / "absent")]
    keys = {"decision", "reason", "reason_code", "candidate_identity", "served_identity"}
    assert all(set(result) == keys for result in results)


def test_conflicting_served_identities_publish(served_proof: Path) -> None:
    with served_proof.open("a", encoding="utf-8") as proof:
        proof.write(f"- Source SHA: `{OTHER}`\n")
    assert decision(served_proof)["decision"] == "publish"


def test_invalid_utf8_proof_publishes(served_proof: Path) -> None:
    served_proof.write_bytes(b"\xff")
    assert decision(served_proof)["decision"] == "publish"


def test_human_output_names_both_identities(served_proof: Path) -> None:
    result = invoke("--promotion-source-sha", CANDIDATE, "--served-proof", str(served_proof), "--mode", "human")
    assert result.returncode == 0
    assert "skip" in result.stdout
    assert "identities_equal" in result.stdout
    assert f"candidate={CANDIDATE}" in result.stdout
    assert f"served={CANDIDATE}" in result.stdout
