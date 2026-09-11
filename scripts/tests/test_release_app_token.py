"""Contract test: release automation authenticates with a GitHub App installation token.

Events created with the built-in ``GITHUB_TOKEN`` are held at ``action_required``
and never attach check runs, so the branch ruleset's required
``deterministic-safety-net`` context can never report and the release PR stays
unmergeable. These tests pin the App-token wiring so it cannot silently regress.
"""

from __future__ import annotations

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


def _assert_app_token_wiring(workflow_text: str) -> None:
    parsed: Any = yaml.safe_load(workflow_text)
    steps: list[Any] = parsed["jobs"]["release-please"]["steps"]

    mint = next(
        (step for step in steps if str(step.get("uses", "")).startswith("actions/create-github-app-token")),
        None,
    )
    assert mint is not None, "release-please job must mint a GitHub App installation token"

    mint_id = mint.get("id")
    assert isinstance(mint_id, str) and mint_id, "app-token step must declare an id"

    release = next((step for step in steps if step.get("id") == "release"), None)
    assert release is not None, "release step must exist"
    assert steps.index(mint) == steps.index(release) - 1, (
        "app-token step must run immediately before the release step"
    )
    expected_reference = "${{ steps." + mint_id + ".outputs.token }}"
    assert release["with"]["token"] == expected_reference, (
        "release step token must reference the minted app-token output"
    )
    assert mint["with"]["app-id"] == "${{ secrets.RELEASE_APP_ID }}"
    assert mint["with"]["private-key"] == "${{ secrets.RELEASE_APP_PRIVATE_KEY }}"

    anchor = next(
        (step for step in steps if step.get("name") == "Assert and publish attestation anchor"),
        None,
    )
    assert anchor is not None, "attestation anchor step must exist"
    assert anchor["env"]["GH_TOKEN"] == expected_reference, (
        "anchor step GH_TOKEN must reference the same minted app-token output"
    )

    assert "secrets.GITHUB_TOKEN" not in workflow_text, (
        "builtin GITHUB_TOKEN must not remain anywhere in the workflow"
    )


def test_release_please_authenticates_with_app_installation_token() -> None:
    _assert_app_token_wiring(WORKFLOW.read_text(encoding="utf-8"))


def test_assertions_reject_the_old_builtin_token_workflow() -> None:
    with pytest.raises(AssertionError):
        _assert_app_token_wiring(OLD_BUILTIN_TOKEN_WORKFLOW)


def test_assertions_reject_a_partially_rewired_workflow() -> None:
    with pytest.raises(AssertionError):
        _assert_app_token_wiring(MINT_STEP_BUT_BUILTIN_RELEASE_TOKEN_WORKFLOW)
