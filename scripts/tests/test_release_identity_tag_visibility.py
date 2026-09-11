"""Contract test: CI must clone git tags for the release-identity gate to see them.

``scripts/release_identity.py --check`` compares the release-please manifest
against ``VERSION.txt``, ``server.json``, and the newest ``v*`` git tag.
``actions/checkout`` defaults (``fetch-depth: 1``, ``fetch-tags: false``) clone
no tags, so in CI the tag comparison was silently skipped while the job stayed
green -- locally tags exist, hiding the gap. This test pins the checkout step
of the job that runs the check to fetch tags (or full history), so a
tag-vs-manifest disagreement can no longer publish unnoticed.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml


ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github/workflows/ci.yml"
STEP_NAME = "Verify release identity consistency"

# Mirrors the shipped bug: a bare actions/checkout step (defaults: fetch-depth 1,
# fetch-tags false) feeding the release-identity check.
FIXTURE_WITHOUT_KEY = """\
jobs:
  deterministic-safety-net:
    steps:
      - name: Check out repository
        uses: actions/checkout@v4
      - name: Verify release identity consistency
        run: python3 scripts/release_identity.py --check
"""

# The same shape with the key present: tags are fetched even in a shallow clone.
FIXTURE_WITH_KEY = """\
jobs:
  deterministic-safety-net:
    steps:
      - name: Check out repository
        uses: actions/checkout@v4
        with:
          fetch-tags: true
      - name: Verify release identity consistency
        run: python3 scripts/release_identity.py --check
"""


def _release_identity_job(
    workflow: dict[object, object],
    source: str,
) -> tuple[str, dict[object, object]]:
    jobs = workflow.get("jobs") or {}
    if not isinstance(jobs, dict):
        raise AssertionError(f"{source}: 'jobs' is not a mapping")
    for job_name, job in jobs.items():
        steps = (job or {}).get("steps") or []
        if any((step or {}).get("name") == STEP_NAME for step in steps):
            return str(job_name), job
    raise AssertionError(f"{source}: no job contains a step named {STEP_NAME!r}")


def _repo_checkout_step(job: dict[object, object]) -> dict[object, object] | None:
    """Return the job's own repository checkout, ignoring cross-repo checkouts."""
    for step in job.get("steps") or []:
        uses = str((step or {}).get("uses") or "")
        with_block = (step or {}).get("with") or {}
        if uses.startswith("actions/checkout") and "repository" not in with_block:
            return step
    return None


def _assert_checkout_fetches_tags(workflow_text: str, source: str) -> None:
    workflow = yaml.safe_load(workflow_text)
    job_name, job = _release_identity_job(workflow, source)
    step = _repo_checkout_step(job)
    if step is None:
        raise AssertionError(
            f"{source}: job {job_name!r} has no actions/checkout step for the "
            f"repository itself feeding {STEP_NAME!r}"
        )
    with_block = step.get("with") or {}
    fetch_tags = with_block.get("fetch-tags")
    fetch_depth = with_block.get("fetch-depth")
    if fetch_tags is not True and fetch_depth != 0:
        raise AssertionError(
            f"{source}: job {job_name!r} checks out the repository without git tags "
            f"(fetch-tags={fetch_tags!r}, fetch-depth={fetch_depth!r}); the checkout "
            f"feeding {STEP_NAME!r} must set 'fetch-tags: true' (or 'fetch-depth: 0') "
            f"so the tag-vs-manifest comparison in scripts/release_identity.py "
            f"actually runs in CI"
        )


def test_ci_checkout_for_release_identity_fetches_tags() -> None:
    _assert_checkout_fetches_tags(WORKFLOW.read_text(encoding="utf-8"), str(WORKFLOW))


def test_positive_control_fixture_with_key_passes() -> None:
    _assert_checkout_fetches_tags(FIXTURE_WITH_KEY, "fixture-with-key")


def test_negative_control_fixture_with_key_removed_fails() -> None:
    with pytest.raises(AssertionError, match=r"deterministic-safety-net.*fetch-tags"):
        _assert_checkout_fetches_tags(FIXTURE_WITHOUT_KEY, "fixture-without-key")


def test_negative_control_real_workflow_without_with_block_fails() -> None:
    workflow = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    _job_name, job = _release_identity_job(workflow, str(WORKFLOW))
    step = _repo_checkout_step(job)
    assert step is not None
    step.pop("with", None)
    mutated = yaml.safe_dump(workflow)

    with pytest.raises(AssertionError, match=r"deterministic-safety-net.*fetch-tags"):
        _assert_checkout_fetches_tags(mutated, "mutated-ci.yml")
