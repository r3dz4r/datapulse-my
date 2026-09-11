"""Contract test: release automation authenticates with a GitHub App installation token.

Events created with the built-in ``GITHUB_TOKEN`` are held at ``action_required``
and never attach check runs, so the branch ruleset's required
``deterministic-safety-net`` context can never report and the release PR stays
unmergeable. These tests pin the App-token wiring so it cannot silently regress.

Both release-automation workflows are covered — ``release-please.yml`` and
``anchor-release-attestation.yml`` — because both push commits / edit PRs and
therefore both must authenticate as the App, not as ``github-actions[bot]``.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest
import yaml


ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github/workflows/release-please.yml"

# Pre-fix shape: builtin token, no token-minting step. Kept as a fixture so the
# assertions below are proven to bite (two-sided proof, not vacuous green).
OLD_BUILTIN_TOKEN_WORKFLOW = """\
name: Release Please

on:
  push:
    branches:
      - main

permissions:
  contents: write
  pull-requests: write

jobs:
  release-please:
    runs-on: ubuntu-latest
    steps:
      - id: release
        uses: googleapis/release-please-action@v4
        with:
          token: ${{ secrets.GITHUB_TOKEN }}
          config-file: release-please-config.json
          manifest-file: .release-please-manifest.json
      - name: Assert and publish attestation anchor
        env:
          GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}
          TAG: ${{ steps.release.outputs.tag_name }}
        run: echo anchor
"""

# Partial-fix shape: mint step exists but the release step still uses the
# builtin token. Proves the reference checks bite even when the step is present.
MINT_STEP_BUT_BUILTIN_RELEASE_TOKEN_WORKFLOW = """\
name: Release Please

on:
  push:
    branches:
      - main

permissions:
  contents: write
  pull-requests: write

jobs:
  release-please:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/create-github-app-token@v1
        id: app-token
        with:
          app-id: ${{ secrets.RELEASE_APP_ID }}
          private-key: ${{ secrets.RELEASE_APP_PRIVATE_KEY }}
      - id: release
        uses: googleapis/release-please-action@v4
        with:
          token: ${{ secrets.GITHUB_TOKEN }}
          config-file: release-please-config.json
          manifest-file: .release-please-manifest.json
      - name: Assert and publish attestation anchor
        env:
          GH_TOKEN: ${{ steps.app-token.outputs.token }}
          TAG: ${{ steps.release.outputs.tag_name }}
        run: echo anchor
"""

# Pre-fix shape of the anchor workflow: the checkout that later ``git push``es
# the PR head authenticated with the builtin token, so the anchor commit landed
# as a github-actions[bot] push whose check runs are held at action_required —
# leaving the release PR with zero attached checks.
OLD_BUILTIN_TOKEN_ANCHOR_WORKFLOW = """\
name: Anchor release attestation

on:
  pull_request:
    types: [opened, synchronize, labeled, reopened]

permissions:
  contents: write
  pull-requests: write

jobs:
  anchor:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          ref: ${{ github.event.pull_request.head.ref }}
          token: ${{ secrets.GITHUB_TOKEN }}
          fetch-depth: 0
      - name: Commit anchor to release PR branch
        run: git push origin HEAD:${{ github.event.pull_request.head.ref }}
      - name: Add anchor trailer to PR body
        env:
          GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}
        run: echo trailer
"""


@dataclass(frozen=True)
class AppTokenContract:
    """One workflow whose automation must push as the GitHub App installation.

    ``old_fixture`` holds the pre-fix shape (builtin token, no minting step) so
    the negative-side tests prove the assertions bite for this workflow too.
    Pinning a third workflow is a one-line addition to ``APP_TOKEN_CONTRACTS``.
    """

    workflow: Path
    job: str
    old_fixture: str
    checkout_consumes_token: bool = False


APP_TOKEN_CONTRACTS: tuple[AppTokenContract, ...] = (
    AppTokenContract(
        workflow=ROOT / ".github/workflows/release-please.yml",
        job="release-please",
        old_fixture=OLD_BUILTIN_TOKEN_WORKFLOW,
    ),
    AppTokenContract(
        workflow=ROOT / ".github/workflows/anchor-release-attestation.yml",
        job="anchor",
        old_fixture=OLD_BUILTIN_TOKEN_ANCHOR_WORKFLOW,
        checkout_consumes_token=True,
    ),
)


def _find_mint_step(steps: list[Any]) -> Any:
    return next(
        (step for step in steps if str(step.get("uses", "")).startswith("actions/create-github-app-token")),
        None,
    )


def _assert_app_token_wiring(
    workflow_text: str, *, job: str, checkout_consumes_token: bool = False
) -> str:
    """Assert the App-token contract shared by every workflow in the table.

    Returns the minted reference (parsed from the step id in the file) so
    workflow-specific callers can reuse it without hardcoding the string.
    """
    parsed: Any = yaml.safe_load(workflow_text)
    steps: list[Any] = parsed["jobs"][job]["steps"]

    mint = _find_mint_step(steps)
    assert mint is not None, f"{job} job must mint a GitHub App installation token"

    mint_id = mint.get("id")
    assert isinstance(mint_id, str) and mint_id, "app-token step must declare an id"
    assert mint["with"]["app-id"] == "${{ secrets.RELEASE_APP_ID }}"
    assert mint["with"]["private-key"] == "${{ secrets.RELEASE_APP_PRIVATE_KEY }}"

    expected_reference = "${{ steps." + mint_id + ".outputs.token }}"

    # Every step that authenticates (a `with.token` mapping or a GH_TOKEN env)
    # must reference the minted output, and must run after the minting step —
    # a forward reference resolves empty at runtime and fails auth.
    consumers = [
        step
        for step in steps
        if "token" in (step.get("with") or {}) or "GH_TOKEN" in (step.get("env") or {})
    ]
    assert consumers, f"{job} job must consume the minted token (step token or GH_TOKEN)"
    mint_index = steps.index(mint)
    for step in consumers:
        assert mint_index < steps.index(step), (
            "app-token step must run before the steps that consume it"
        )
        if "token" in (step.get("with") or {}):
            assert step["with"]["token"] == expected_reference, (
                "authenticating step token must reference the minted app-token output"
            )
        if "GH_TOKEN" in (step.get("env") or {}):
            assert step["env"]["GH_TOKEN"] == expected_reference, (
                "GH_TOKEN must reference the same minted app-token output"
            )

    if checkout_consumes_token:
        checkout = next(
            (
                step
                for step in steps
                if str(step.get("uses", "")).startswith("actions/checkout")
                and (step.get("with") or {}).get("token") == expected_reference
            ),
            None,
        )
        assert checkout is not None, (
            "checkout step must authenticate with the minted app-token (its push must not be a builtin-token push)"
        )

    assert "secrets.GITHUB_TOKEN" not in workflow_text, (
        "builtin GITHUB_TOKEN must not remain anywhere in the workflow"
    )
    return expected_reference


def _assert_release_please_app_token_wiring(workflow_text: str) -> None:
    """Full release-please proof: the shared contract plus step adjacency."""
    expected_reference = _assert_app_token_wiring(workflow_text, job="release-please")

    parsed: Any = yaml.safe_load(workflow_text)
    steps: list[Any] = parsed["jobs"]["release-please"]["steps"]
    mint = _find_mint_step(steps)

    release = next((step for step in steps if step.get("id") == "release"), None)
    assert release is not None, "release step must exist"
    assert steps.index(mint) == steps.index(release) - 1, (
        "app-token step must run immediately before the release step"
    )
    assert release["with"]["token"] == expected_reference, (
        "release step token must reference the minted app-token output"
    )

    anchor = next(
        (step for step in steps if step.get("name") == "Assert and publish attestation anchor"),
        None,
    )
    assert anchor is not None, "attestation anchor step must exist"
    assert anchor["env"]["GH_TOKEN"] == expected_reference, (
        "anchor step GH_TOKEN must reference the same minted app-token output"
    )


@pytest.mark.parametrize(
    "contract",
    APP_TOKEN_CONTRACTS,
    ids=lambda contract: contract.workflow.name,
)
def test_workflow_authenticates_with_app_installation_token(contract: AppTokenContract) -> None:
    _assert_app_token_wiring(
        contract.workflow.read_text(encoding="utf-8"),
        job=contract.job,
        checkout_consumes_token=contract.checkout_consumes_token,
    )


def test_release_please_authenticates_with_app_installation_token() -> None:
    _assert_release_please_app_token_wiring(WORKFLOW.read_text(encoding="utf-8"))


@pytest.mark.parametrize(
    "contract",
    APP_TOKEN_CONTRACTS,
    ids=lambda contract: contract.workflow.name,
)
def test_assertions_reject_the_old_builtin_token_workflow(contract: AppTokenContract) -> None:
    with pytest.raises(AssertionError):
        _assert_app_token_wiring(contract.old_fixture, job=contract.job)


def test_assertions_reject_a_partially_rewired_workflow() -> None:
    with pytest.raises(AssertionError):
        _assert_release_please_app_token_wiring(MINT_STEP_BUT_BUILTIN_RELEASE_TOKEN_WORKFLOW)
