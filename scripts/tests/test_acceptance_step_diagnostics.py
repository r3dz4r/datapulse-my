#!/usr/bin/env python3
"""Pin fail-closed accepted-head verification and the deploy concurrency lane."""
from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github/workflows/deploy-cloudflare-pages.yml"


def test_accepted_head_verification_fails_closed_and_deploy_concurrency_is_preserved() -> None:
    workflow = yaml.safe_load(WORKFLOW.read_text())
    signing = workflow["jobs"]["sign_health"]
    assert signing["timeout-minutes"] == 142
    guard = next(step for step in signing["steps"] if step.get("id") == "accepted_head")
    assert "timeout-minutes" not in guard
    assert 'python3 - "$accepted_main"' in guard["run"]
    assert "continue-on-error" not in guard
    assert "trap " not in guard["run"]
    # Replace superseded pending deploys while preserving the active promotion.
    assert workflow["concurrency"] == {
        "group": "cloudflare-pages-deploy",
        "cancel-in-progress": False,
        "queue": "single",
    }
