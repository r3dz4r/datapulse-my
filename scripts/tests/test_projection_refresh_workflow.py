from __future__ import annotations

import json
from pathlib import Path


WORKFLOW = Path(__file__).resolve().parents[2] / ".github/workflows/projection-refresh.yml"
ROOT = WORKFLOW.parents[2]


def test_projection_refresh_workflow_contract() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    push_at = text.index("push --set-upstream origin")
    close_at = text.index("- name: Close superseded projection pull requests")
    create_at = text.index("- name: Create and push refresh branch")
    checks = [
        ("creates a pull request", "gh pr create" in text),
        ("enables auto-merge", "gh pr merge" in text and "--auto" in text),
        (
            "never pushes to main",
            "git push origin main" not in text and "git push origin HEAD:main" not in text,
        ),
        ("declares schedule trigger", "  schedule:" in text),
        ("declares workflow_dispatch trigger", "  workflow_dispatch:" in text),
        ("runs --check before branch push", text.index("gen_attestation_projections.py --check") < push_at),
        (
            "detects a binding-only refresh",
            "attestations/latest/binding.json" in next(
                line for line in text.splitlines() if "if git diff --quiet --" in line),
        ),
        (
            "stages the refreshed binding",
            "attestations/latest/binding.json" in next(
                line for line in text.splitlines() if "git add --" in line),
        ),
        (
            "mints and uses App token for push and PR",
            "uses: actions/create-github-app-token@v1" in text
            and text.count("steps.app-token.outputs.token") >= 2,
        ),
        ("keeps concurrency runs active", "cancel-in-progress: false" in text),
        (
            "closes previous projection refresh pull requests before creating a new one",
            close_at < create_at
            and 'startswith("projection/refresh-")' in text[close_at:create_at]
            and '"projection/refresh-${GITHUB_RUN_ID}"' in text[close_at:create_at]
            and "gh pr close" in text[close_at:create_at]
            and "GITHUB_RUN_ID" in text[close_at:create_at],
        ),
    ]
    failed = False
    for description, passed in checks:
        print(f"{'PASS' if passed else 'FAIL'}: {description}")
        failed |= not passed
    assert not failed, "projection refresh workflow contract failed"


def test_projection_refresh_carries_scores_from_projected_revision() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    copy_scores = next(
        (line for line in text.splitlines() if "cp -- \"$frozen_scores\"" in line),
        "",
    )
    add_line = next(line for line in text.splitlines() if "git add --" in line)
    diff_line = next(line for line in text.splitlines() if "if git diff --quiet --" in line)
    assert "binding_ref" in text and copy_scores, "refresh must copy frozen scores selected by binding_ref"
    assert "attestations/latest/scores.json" in add_line
    assert "attestations/latest/scores.json" in diff_line

    latest_scores = json.loads((ROOT / "attestations/latest/scores.json").read_text())
    latest_index = json.loads((ROOT / "attestations/latest/index.json").read_text())
    frozen_path = ROOT / Path(latest_index["binding_ref"]).with_name("scores.json")
    frozen_scores = json.loads(frozen_path.read_text())
    assert latest_scores["generated_at"] >= frozen_scores["generated_at"], (
        "latest scores must be at least as recent as the frozen scores of the projected head"
    )
