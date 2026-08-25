"""Offline contract tests for the hand-authored operations runbook."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DOCS_PATH = ROOT / "docs/operations.md"
FIXTURE_PATH = Path(__file__).parent / "fixtures/operations_contract/canonical.json"


def load_contract() -> dict[str, dict[str, str]]:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def test_operations_runbook_matches_canonical_service_and_timer_fixture() -> None:
    document = DOCS_PATH.read_text(encoding="utf-8")
    contract = load_contract()
    service = contract["health_service"]
    timer = contract["health_timer"]

    assert f"`{service['user']}:{service['group']}`" in document
    assert f"`{service['working_directory']}`" in document
    assert f"`{timer['cadence']}`" in document
    assert f"`{timer['due_command']}`" in document
    assert "probes due datasets" in document
    assert "root-owned `/etc/systemd/system/datapulse-health.service`" not in document
    assert "owned by root" not in document


def test_operations_runbook_states_p6_stack_isolation_from_fixture() -> None:
    document = DOCS_PATH.read_text(encoding="utf-8")
    isolation = load_contract()["p6_isolation"]

    assert f"P6 production stack: **{isolation['production_stack']}**" in document
    assert f"P6 disposable lab stack: **{isolation['disposable_lab_stack']}**" in document
    assert (
        f"`{isolation['real_lab_marker_path']}`: **{isolation['real_lab_marker']}**"
        in document
    )
    assert "No P6 stack is active" in document
