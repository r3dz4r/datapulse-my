"""Static contracts for the paid OpenWiki workflow boundary."""

from __future__ import annotations

from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[2]
OPENWIKI_WORKFLOW = ROOT / ".github/workflows/openwiki-update.yml"
PRODUCTION_WORKFLOW = ROOT / ".github/workflows/deploy-cloudflare-pages.yml"


def _workflow_on(workflow: dict[object, object]) -> dict[str, object]:
    """Read the YAML 1.1 boolean form PyYAML uses for the ``on`` key."""
    return workflow.get("on", workflow.get(True, {}))  # type: ignore[return-value]


def test_openwiki_triggers_are_manual_or_weekly_and_exclude_health_cycles() -> None:
    workflow = yaml.safe_load(OPENWIKI_WORKFLOW.read_text(encoding="utf-8"))
    triggers = _workflow_on(workflow)
    push = triggers.get("push", {})
    paths = push.get("paths", []) if isinstance(push, dict) else []

    assert "health/latest.json" not in paths
    assert "workflow_dispatch" in triggers
    assert triggers.get("schedule") == [{"cron": "0 8 * * 1"}]


def test_openwiki_generation_is_not_a_production_workflow_dependency() -> None:
    openwiki = yaml.safe_load(OPENWIKI_WORKFLOW.read_text(encoding="utf-8"))
    production = yaml.safe_load(PRODUCTION_WORKFLOW.read_text(encoding="utf-8"))

    assert "openwiki" not in str(production).lower()
    assert "workflow_run" not in _workflow_on(openwiki)
    assert "needs" not in openwiki.get("jobs", {}).get("update", {})


def test_source_validation_remains_a_separate_deterministic_ci_check() -> None:
    ci = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
    openwiki = OPENWIKI_WORKFLOW.read_text(encoding="utf-8")

    assert "run: python3 scripts/verify_openwiki.py" in ci
    assert "verify_openwiki.py --generated --changed-from HEAD" in openwiki
