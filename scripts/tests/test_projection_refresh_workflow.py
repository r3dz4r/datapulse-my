from __future__ import annotations

from pathlib import Path


WORKFLOW = Path(__file__).resolve().parents[2] / ".github/workflows/projection-refresh.yml"


def test_projection_refresh_workflow_contract() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    push_at = text.index("push --set-upstream origin")
    close_at = text.index("- name: Close superseded projection pull requests")
    create_at = text.index("- name: Create and push refresh branch")
    diff_line = next(line for line in text.splitlines() if "if git diff --quiet --" in line)
    add_line = next(line for line in text.splitlines() if "git add --" in line)
    checks = [
        ("creates a pull request", "gh pr create" in text),
        ("enables auto-merge", "gh pr merge" in text and "--auto" in text),
        ("never pushes to main", "git push origin main" not in text
         and "git push origin HEAD:main" not in text),
        ("declares schedule trigger", "  schedule:" in text),
        ("declares workflow_dispatch trigger", "  workflow_dispatch:" in text),
        ("runs --check before branch push", text.index("gen_attestation_projections.py --check") < push_at),
        ("detects binding and scores refresh", all(
            path in diff_line for path in ("attestations/latest/binding.json", "attestations/latest/scores.json"))),
        ("stages binding and scores", all(
            path in add_line for path in ("attestations/latest/binding.json", "attestations/latest/scores.json"))),
        ("does not copy latest scores outside the writer", "frozen_scores" not in text and "cp --" not in text),
        ("mints and uses App token for push and PR",
         "uses: actions/create-github-app-token@v1" in text
         and text.count("steps.app-token.outputs.token") >= 2),
        ("keeps concurrency runs active", "cancel-in-progress: false" in text),
        ("closes prior refresh pull requests before creating a new one",
         close_at < create_at and 'startswith("projection/refresh-")' in text[close_at:create_at]
         and '"projection/refresh-${GITHUB_RUN_ID}"' in text[close_at:create_at]
         and "gh pr close" in text[close_at:create_at] and "GITHUB_RUN_ID" in text[close_at:create_at]),
    ]
    failed = False
    for description, passed in checks:
        print(f"{'PASS' if passed else 'FAIL'}: {description}")
        failed |= not passed
    assert not failed, "projection refresh workflow contract failed"
