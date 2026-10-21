from __future__ import annotations

from pathlib import Path


WORKFLOW = Path(__file__).resolve().parents[2] / ".github/workflows/projection-refresh.yml"


def test_projection_refresh_workflow_contract() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    push_at = text.index("push --set-upstream origin")
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
            "mints and uses App token for push and PR",
            "uses: actions/create-github-app-token@v1" in text
            and text.count("steps.app-token.outputs.token") >= 2,
        ),
        ("keeps concurrency runs active", "cancel-in-progress: false" in text),
    ]
    failed = False
    for description, passed in checks:
        print(f"{'PASS' if passed else 'FAIL'}: {description}")
        failed |= not passed
    assert not failed, "projection refresh workflow contract failed"
