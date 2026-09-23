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

    assert "push" not in triggers
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


def test_openwiki_publishes_by_pull_request_and_never_pushes_main() -> None:
    """A direct push to main is refused by the ruleset's required check."""
    workflow = OPENWIKI_WORKFLOW.read_text(encoding="utf-8")

    assert "create-pull-request" in workflow
    assert "HEAD:main" not in workflow
    assert "git push" not in workflow


def test_openwiki_dispatches_the_required_check_on_its_branch() -> None:
    """A token-pushed branch never triggers ci.yml, so the check is dispatched."""
    workflow = OPENWIKI_WORKFLOW.read_text(encoding="utf-8")

    assert "gh workflow run ci.yml" in workflow
    assert "--ref openwiki/update" in workflow


def test_openwiki_enables_auto_merge_after_dispatching() -> None:
    """Auto-merge lets the run exit instead of holding the runner for CI."""
    workflow = OPENWIKI_WORKFLOW.read_text(encoding="utf-8")

    assert "gh pr merge openwiki/update --auto --squash" in workflow
    assert "--auto" in workflow


def test_openwiki_declares_the_permissions_publishing_needs() -> None:
    workflow = yaml.safe_load(OPENWIKI_WORKFLOW.read_text(encoding="utf-8"))
    permissions = workflow["permissions"]

    assert permissions["contents"] == "write"
    assert permissions["pull-requests"] == "write"
    assert permissions["actions"] == "write"


def test_openwiki_preflights_every_chatgpt_credential() -> None:
    """An unprovisioned secret must fail by name, not as a 401 from the provider."""
    workflow = OPENWIKI_WORKFLOW.read_text(encoding="utf-8")

    for name in (
        "OPENAI_CHATGPT_ACCESS_TOKEN",
        "OPENAI_CHATGPT_REFRESH_TOKEN",
        "OPENAI_CHATGPT_EXPIRES_AT",
        "OPENAI_CHATGPT_ACCOUNT_ID",
        "OPENAI_CHATGPT_EMAIL",
        "OPENAI_CHATGPT_PLAN",
    ):
        assert name in workflow, name
