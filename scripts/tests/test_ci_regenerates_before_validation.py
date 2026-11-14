"""The required safety net regenerates derived artefacts before it validates them."""

from __future__ import annotations

import copy
from pathlib import Path
import re

import pytest
import yaml


ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github/workflows/ci.yml"
JOB = "deterministic-safety-net"
TEST_STEP = "Run repository-contract and MCP tests"
INVARIANT_STEP = "Verify local release invariants"
README_CHECK = "python3 scripts/gen_readme.py --check"
DERIVED_CLOCK_GENERATORS = ("gen_trends", "gen_drift", "gen_reconciliation")
CHAIN = (
    "gen_health_trust_summary", "gen_quality_profile", "gen_trends", "gen_drift",
    "gen_reconciliation", "gen_public_summary", "gen_catalog_snapshot", "gen_catalog_graph",
    # _invoked matches only `gen_*` scripts, so embed_dashboard_data.py is not visible to this
    # chain assertion. Its effect is covered by the parity and dashboard suites, which read the
    # register rows it writes; do not try to pin it here.
    "gen_public_discovery", "gen_dashboard_sections", "gen_dashboard_filters",
    "gen_readme", "gen_llms_summary", "gen_mcp_reference",
    "gen_ai_catalog", "gen_json_envelope", "gen_changelog",
)


def _workflow() -> dict:
    return yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))


def _invoked(step: dict) -> list[str]:
    return re.findall(r"^\s*python3 scripts/(gen_\w+)\.py\b", step.get("run") or "", re.MULTILINE)


def _regeneration_index(steps: list[dict]) -> int | None:
    matches = [index for index, step in enumerate(steps)
               if set(DERIVED_CLOCK_GENERATORS) <= set(_invoked(step))]
    return matches[0] if len(matches) == 1 else None


def _violations(workflow: dict) -> list[str]:
    job = workflow["jobs"][JOB]
    steps = job["steps"]
    names = [step.get("name") for step in steps]
    index = _regeneration_index(steps)
    if index is None:
        return ["no single step regenerates the derived-clock generators"]
    step = steps[index]
    problems = []
    for name in (TEST_STEP, INVARIANT_STEP):
        if name not in names:
            problems.append(f"validation step {name!r} is missing")
        elif names.index(name) < index:
            problems.append(f"regeneration runs after {name!r}")
    if _invoked(step) != list(CHAIN):
        problems.append(f"generator chain is {_invoked(step)}, not {list(CHAIN)}")
    if not (step.get("run") or "").lstrip().startswith("set -Eeuo pipefail"):
        problems.append("a failing generator would not fail the step")
    if step.get("continue-on-error"):
        problems.append("regeneration is allowed to fail")
    if step.get("if") != "env.FULL_VERIFICATION == 'true'":
        problems.append("regeneration is not bound to full verification")
    if "history_daily.json" not in str(step.get("name")):
        problems.append("step name does not disclose the history_daily.json substitution")
    # The committed README is still judged before any generator can rewrite it.
    runs = [candidate.get("run") for candidate in steps]
    if README_CHECK not in runs or runs.index(README_CHECK) > index:
        problems.append("README --check no longer precedes regeneration")
    return problems


def test_required_job_regenerates_before_it_validates() -> None:
    assert _violations(_workflow()) == []


def test_regeneration_never_assumes_the_gitignored_raw_history() -> None:
    steps = _workflow()["jobs"][JOB]["steps"]
    run = steps[_regeneration_index(steps)]["run"]
    for generator in ("gen_trends", "gen_drift"):
        line = next(line for line in run.splitlines() if f"scripts/{generator}.py" in line)
        assert "--history /dev/null" in line and "--daily health/history_daily.json" in line
    assert "secrets." not in run and "curl" not in run and "wget" not in run


def test_regeneration_step_documents_the_trade() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    step_at = text.index("- name: Regenerate derived artefacts before validation")
    comment = text[text.rindex("\n\n", 0, step_at):step_at]
    flat = " ".join(line.strip().lstrip("#").strip() for line in comment.splitlines())
    assert "validates generator self-consistency" in flat
    assert "committed artefacts are kept current by the health pipeline, not by this check" in flat


def _remove(workflow: dict) -> None:
    steps = workflow["jobs"][JOB]["steps"]
    del steps[_regeneration_index(steps)]


def _move_after(target: str):
    def mutate(workflow: dict) -> None:
        steps = workflow["jobs"][JOB]["steps"]
        step = steps.pop(_regeneration_index(steps))
        steps.insert([s.get("name") for s in steps].index(target) + 1, step)
    return mutate


def _drop(generator: str):
    def mutate(workflow: dict) -> None:
        steps = workflow["jobs"][JOB]["steps"]
        step = steps[_regeneration_index(steps)]
        step["run"] = "\n".join(line for line in step["run"].splitlines()
                                if f"scripts/{generator}.py" not in line)
    return mutate


def _disable(workflow: dict) -> None:
    steps = workflow["jobs"][JOB]["steps"]
    steps[_regeneration_index(steps)]["if"] = "false"


@pytest.mark.parametrize("mutate", [
    _remove, _move_after(TEST_STEP), _move_after(INVARIANT_STEP),
    _drop("gen_trends"), _drop("gen_drift"), _drop("gen_reconciliation"), _disable,
], ids=["removed", "after-tests", "after-invariants", "no-trends", "no-drift",
        "no-reconciliation", "disabled"])
def test_the_guard_rejects_a_retired_or_reordered_step(mutate) -> None:
    workflow = copy.deepcopy(_workflow())
    mutate(workflow)
    assert _violations(workflow) != []
