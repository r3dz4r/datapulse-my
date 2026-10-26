"""Focused tests for attestation signing and CI acceptance workflow contracts."""

from __future__ import annotations

from pathlib import Path
from datetime import timedelta
import os
import re
import subprocess
import sys
import textwrap

import pytest
import yaml

from scripts.verify_attestation_workflow_contract import ContractError, verify_workflows
from scripts import gen_attestations as ga
from scripts.tests.test_append_set_isolation import NOW, accept, git
from scripts.tests.test_attestations import fixture_root
from scripts.verify_attestation_append import append_paths, verify_append


ROOT = Path(__file__).resolve().parents[2]
DAILY = ROOT / ".github/workflows/datapulse-attest-daily.yml"
PAGES = ROOT / ".github/workflows/deploy-cloudflare-pages.yml"
CI = ROOT / ".github/workflows/ci.yml"


def _ci_workflow() -> dict:
    # BaseLoader preserves the Actions `on` key instead of treating it as a boolean.
    return yaml.load(CI.read_text(encoding="utf-8"), Loader=yaml.BaseLoader)


def _ci_step(job: str) -> dict:
    steps = _ci_workflow()["jobs"][job]["steps"]
    if job == "classify":
        return next(step for step in steps if step.get("id") == "classify")
    return next(step for step in steps if step.get("name") ==
                "Verify immutable attestation append against accepted base")


def test_ci_jobs_do_not_derive_bases_from_event_payloads() -> None:
    for name, job in _ci_workflow()["jobs"].items():
        contents = yaml.dump(job)
        for frozen_base in ("github.event.pull_request.base.sha", "github.event.merge_group.base_sha"):
            assert frozen_base not in contents, f"{name} uses a frozen event base"


def test_ci_push_trigger_accepts_only_main() -> None:
    triggers = _ci_workflow()["on"]
    assert {"pull_request", "merge_group", "workflow_dispatch"} <= triggers.keys()
    assert triggers["push"] == {"branches": ["main"]}, "branch and tag pushes must not duplicate PR CI"


@pytest.fixture
def ci_merge_checkout(tmp_path: Path) -> tuple[Path, str, str, str]:
    root = tmp_path / "checkout"
    (root / "scripts").mkdir(parents=True)
    (root / "scripts/classify_change.py").write_text(
        (ROOT / "scripts/classify_change.py").read_text(encoding="utf-8"), encoding="utf-8",
    )
    # Record the workflow's verifier argument; verifier semantics have separate tests.
    (root / "scripts/verify_attestation_append.py").write_text(
        'import os, sys\nfrom pathlib import Path\n'
        'assert sys.argv[1] == "--base"\n'
        'Path(os.environ["BASE_RECORD"]).write_text(sys.argv[2])\n', encoding="utf-8",
    )
    git(root, "init", "-b", "main")
    git(root, "config", "user.name", "Test")
    git(root, "config", "user.email", "test@example.test")
    git(root, "add", ".")
    git(root, "commit", "-m", "event base")
    event_base = git(root, "rev-parse", "HEAD")
    git(root, "switch", "-c", "candidate")
    (root / "health").mkdir()
    (root / "health/latest.json").write_text("{}\n", encoding="utf-8")
    git(root, "add", ".")
    git(root, "commit", "-m", "candidate")
    candidate = git(root, "rev-parse", "HEAD")
    git(root, "switch", "main")
    (root / "scripts/base-only.py").write_text("# base advanced\n", encoding="utf-8")
    git(root, "add", ".")
    git(root, "commit", "-m", "base advanced after event")
    checkout_base = git(root, "rev-parse", "HEAD")
    git(root, "merge", "--no-ff", "--no-commit", "candidate")
    # A merge-only path proves classification reads the merge tree, not the PR head.
    (root / "health/trends.json").write_text("{}\n", encoding="utf-8")
    git(root, "add", ".")
    git(root, "commit", "-m", "merge ref")
    return root, event_base, checkout_base, candidate


def _run_ci_step(job: str, root: Path, event: str, event_base: str, candidate: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["bash", "-e", "-o", "pipefail", "-c", _ci_step(job)["run"]], cwd=root,
        env={**os.environ, "PATH": f"{Path(sys.executable).parent}:{os.environ['PATH']}",
             "GITHUB_EVENT_NAME": event, "GITHUB_OUTPUT": str(root / "step-output"),
             "BASE_RECORD": str(root / "base-record"),
             "BASE_SHA": event_base, "ACCEPTED_BASE": event_base, "HEAD_SHA": candidate},
        text=True, capture_output=True,
    )


@pytest.mark.parametrize("event", ["pull_request", "merge_group"])
def test_ci_append_verification_passes_base_derived_from_checkout(
    ci_merge_checkout: tuple[Path, str, str, str], event: str,
) -> None:
    root, event_base, checkout_base, candidate = ci_merge_checkout
    step = _ci_step("deterministic-safety-net")
    assert "pull_request" in step["if"] and "merge_group" in step["if"]
    assert "continue-on-error" not in step
    result = _run_ci_step("deterministic-safety-net", root, event, event_base, candidate)
    assert result.returncode == 0, result.stdout + result.stderr
    assert (root / "base-record").read_text() == checkout_base


@pytest.mark.parametrize("event", ["pull_request", "merge_group"])
def test_ci_classify_uses_checkout_base_and_merge_tree(
    ci_merge_checkout: tuple[Path, str, str, str], event: str,
) -> None:
    root, event_base, _, candidate = ci_merge_checkout
    result = _run_ci_step("classify", root, event, event_base, candidate)
    assert result.returncode == 0, result.stdout + result.stderr
    outputs = (root / "step-output").read_text().splitlines()
    assert "changed_paths=health/latest.json, health/trends.json" in outputs
    assert "health_only=true" in outputs


@pytest.mark.parametrize("job", ["classify", "deterministic-safety-net"])
@pytest.mark.parametrize("event", ["pull_request", "merge_group"])
@pytest.mark.parametrize("missing_parent", ["root", "shallow"])
def test_ci_missing_checkout_base_fails_loudly(
    ci_merge_checkout: tuple[Path, str, str, str], job: str, event: str, missing_parent: str,
) -> None:
    root, event_base, _, candidate = ci_merge_checkout
    if missing_parent == "root":
        git(root, "switch", "--detach", event_base)
    else:
        shallow = root.parent / "shallow"
        git(root, "clone", "--depth=1", root.as_uri(), str(shallow))
        root = shallow
    result = _run_ci_step(job, root, event, event_base, candidate)
    assert result.returncode != 0, "missing checkout parent must break the gate"
    assert "::error::" in result.stderr and "base" in result.stderr.lower()
    assert not (root / "base-record").exists(), "verifier must not run with a fallback base"


def _workflow_pair(tmp_path: Path) -> tuple[Path, Path]:
    daily = tmp_path / "daily.yml"
    pages = tmp_path / "pages.yml"
    daily.write_text(DAILY.read_text(encoding="utf-8"), encoding="utf-8")
    pages.write_text(PAGES.read_text(encoding="utf-8"), encoding="utf-8")
    return daily, pages


def test_repository_workflows_satisfy_shared_attestation_contract() -> None:
    verify_workflows(DAILY, PAGES)


def _step(workflow: str, step_id: str) -> str:
    return next(
        step for step in re.split(r"(?=^      - )", workflow, flags=re.MULTILINE)
        if f"        id: {step_id}\n" in step
    )


def test_pages_reuses_daily_witness_mechanism_before_submission() -> None:
    daily = DAILY.read_text(encoding="utf-8")
    pages = re.split(r"^  [a-z_]+:\n", PAGES.read_text(encoding="utf-8").split("  sign_health:\n", 1)[1], maxsplit=1, flags=re.MULTILINE)[0]
    guard = _step(pages, "rekor_guard")
    producer = _step(pages, "produce_rekor_witness")
    assert guard.split("        run: |\n", 1)[1] == _step(daily, "rekor_guard").split("        run: |\n", 1)[1]
    # Pages promotes its settled main revision; daily signs its triggering revision.
    assert producer.split("        run: |\n", 1)[1].replace(
        '"$PROMOTION_SOURCE_SHA"', '"$GITHUB_SHA"'
    ) == _step(daily, "produce_rekor_witness").split("        run: |\n", 1)[1]
    assert "continue-on-error:" not in producer
    assert "deploy-cloudflare-pages.yml@refs/heads/main" in producer
    assert "id-token: write" in pages
    installer_id = re.search(r"steps\.([a-z_]+)\.outcome == 'success'", producer)[1]
    installer = _step(pages, installer_id)
    assert "continue-on-error:" not in installer
    assert "cosign-release: v3.1.3" in installer
    assert pages.index(f"id: {installer_id}") < pages.index("id: produce_rekor_witness")
    assert pages.index("id: produce_rekor_witness") < pages.index("python3 scripts/bind_candidate_witness.py") < pages.index("bash scripts/submit_attestation_append.sh")
    assert '--rekor-reference "$DATAPULSE_REKOR_REFERENCE"' in pages
    assert 'DATAPULSE_ATTESTATION_PRIVATE_KEY_FILE=%s\\n' in pages
    assert "DATAPULSE_ALLOW_UNWITNESSED_PUBLICATION" not in pages


@pytest.mark.parametrize(
    ("target", "old", "new", "message"),
    (
        ("daily", "--statement \"$statement\"", "--predicate \"$statement\"", "--statement"),
        ("pages", "--manifest datapulse.json", "--manifest altered.json", "--manifest datapulse.json"),
        ("pages", "cosign attest-blob", "cosign sign-blob", "must not use cosign sign-blob"),
        ("pages", '--source-commit "$PROMOTION_SOURCE_SHA"', '--source-commit "$GITHUB_SHA"', "PROMOTION_SOURCE_SHA"),
        ("pages", "PROMOTION_SOURCE_SHA: ${{ needs.classify.outputs.settled_sha }}", "PROMOTION_SOURCE_SHA: ${{ github.sha }}", "PROMOTION_SOURCE_SHA"),
        ("pages", "PROMOTION_SOURCE_SHA: ${{ needs.sign_health.outputs.settled_sha }}", "PROMOTION_SOURCE_SHA: ${{ needs.classify.outputs.settled_sha }}", "PROMOTION_SOURCE_SHA"),
        ("pages", "ref: ${{ needs.sign_health.outputs.settled_sha }}", "ref: ${{ needs.classify.outputs.settled_sha }}", "ref:"),
        ("pages", 'export PROMOTION_SOURCE_SHA="$settled_sha"', 'export PROMOTION_SOURCE_SHA="$initial_sha"', "PROMOTION_SOURCE_SHA"),
        ("pages", 'echo "settled_sha=$PROMOTION_SOURCE_SHA" >> "$GITHUB_OUTPUT"', 'echo "settled_sha=$initial_sha" >> "$GITHUB_OUTPUT"', "settled_sha="),
        (
            "daily",
            "https://token.actions.githubusercontent.com",
            "https://issuer.example.invalid",
            "https://token.actions.githubusercontent.com",
        ),
    ),
)
def test_contract_rejects_synthetic_shared_flow_drift(
    tmp_path: Path, target: str, old: str, new: str, message: str
) -> None:
    daily, pages = _workflow_pair(tmp_path)
    path = daily if target == "daily" else pages
    original = path.read_text(encoding="utf-8")
    assert old in original
    path.write_text(original.replace(old, new, 1), encoding="utf-8")

    with pytest.raises(ContractError, match=message):
        verify_workflows(daily, pages)


def test_contract_rejects_missing_daily_commit_back_guard(tmp_path: Path) -> None:
    daily, pages = _workflow_pair(tmp_path)
    original = daily.read_text(encoding="utf-8")
    daily.write_text(original.replace("submit_attestation_append.sh", "submit_replacement.sh", 1), encoding="utf-8")

    with pytest.raises(ContractError, match="submit_attestation_append.sh"):
        verify_workflows(daily, pages)


def test_contract_rejects_missing_pages_full_release_gate(tmp_path: Path) -> None:
    daily, pages = _workflow_pair(tmp_path)
    original = pages.read_text(encoding="utf-8")
    pages.write_text(
        original.replace("Require signed attestation for full release", "Require attestation", 1),
        encoding="utf-8",
    )

    with pytest.raises(ContractError, match="Require signed attestation for full release"):
        verify_workflows(daily, pages)


@pytest.mark.parametrize(
    ("target", "old", "new", "message"),
    (
        ("pages", "group: cloudflare-pages-deploy", "group: CLOUDFLARE-PAGES-PRODUCTION", "separate concurrency groups"),
        ("daily", "queue: max", "queue: single", "queue: max"),
        ("pages", "queue: single", "queue: max", "queue: single"),
        ("daily", "cancel-in-progress: false", "cancel-in-progress: true", "cancel-in-progress: false"),
        ("pages", "cancel-in-progress: false", "cancel-in-progress: true", "cancel-in-progress: false"),
    ),
)
def test_contract_rejects_concurrency_lane_regressions(
    tmp_path: Path, target: str, old: str, new: str, message: str
) -> None:
    daily, pages = _workflow_pair(tmp_path)
    path = daily if target == "daily" else pages
    original = path.read_text(encoding="utf-8")
    assert old in original
    path.write_text(original.replace(old, new, 1), encoding="utf-8")

    with pytest.raises(ContractError, match=message):
        verify_workflows(daily, pages)


@pytest.mark.parametrize("accepted", [True, False])
def test_pages_publishes_frozen_candidate_only_after_authoritative_acceptance(
    tmp_path: Path, accepted: bool,
) -> None:
    """Execute the real guard across an immutable-only merge and health drift."""
    root, key = fixture_root(tmp_path / "candidate")
    ga.generate(root, key, NOW)
    source = accept(root)
    origin = tmp_path / "origin.git"
    git(root, "clone", "--bare", str(root), str(origin))
    git(root, "remote", "add", "origin", str(origin))
    authority = tmp_path / "authority"
    git(root, "clone", str(origin), str(authority))
    git(authority, "config", "user.name", "Test")
    git(authority, "config", "user.email", "test@example.test")
    ga.generate(root, key, NOW + timedelta(hours=1), force_append=True)
    paths = append_paths(root, source)
    frozen = {path: (root / path).read_bytes() for path in paths}
    health = (root / "health/latest.json").read_bytes()
    head = (root / ".attestations/chain_head.json").read_bytes()
    scripts = root / "scripts"
    scripts.mkdir()
    # Submission commits locally in both cases. That commit is never acceptance.
    submission = 'set -Eeuo pipefail\ngit switch -c attestation/append-contract\n'
    submission += 'git add -- ' + ' '.join(paths) + '\ngit commit -m "append contract"\n'
    if accepted:
        for path, data in frozen.items():
            target = authority / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
        submission += f'git -C "{authority}" add attestations\n'
        submission += f'git -C "{authority}" commit -m "accept immutable append"\n'
        # A newer health push must not replace the bytes this run witnessed.
        submission += f'printf "\\n" >> "{authority}/health/latest.json"\n'
        submission += f'git -C "{authority}" commit -am "new health observation"\n'
        submission += f'git --git-dir="{origin}" fetch "{authority}" main:main\n'
    (scripts / "submit_attestation_append.sh").write_text(submission)
    (scripts / "close_superseded_appends.sh").write_text("#!/bin/bash\nexit 0\n")
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    verifier = ROOT / "scripts/verify_attestation_append.py"
    (bin_dir / "python3").write_text(
        '#!/bin/bash\nset -Eeuo pipefail\nshift\nargs=("$@")\n'
        # Bound a non-acceptance test to one real remote probe, without sleeping.
        'for i in "${!args[@]}"; do\n'
        '  [[ "${args[$i]}" != --wait-for-acceptance ]] || args[$((i + 1))]=0\n'
        'done\n'
        f'exec "{sys.executable}" "{verifier}" --root "{root}" "${{args[@]}}"\n'
    )
    (bin_dir / "gh").write_text(
        '#!/bin/bash\n'
        'case "$1 $2" in\n'
        '  "pr list") printf "[]\\n" ;;\n'
        '  "pr view")\n'
        '    printf \'{"number":99,"headRefName":"%s","headRefOid":"%s",'
        '"baseRefName":"main","isCrossRepository":false,"state":"%s",'
        '"createdAt":"2026-08-15T00:00:00Z","autoMergeRequest":{},'
        '"statusCheckRollup":[{"name":"deterministic-safety-net",'
        '"status":"COMPLETED","conclusion":"SUCCESS"}]}\\n\' '
        '"$(git branch --show-current)" "$(git rev-parse HEAD)" "$PR_STATE" ;;\n'
        '  "pr merge") : ;;\n'
        '  *) exit 2 ;;\n'
        'esac\n'
    )
    for path in bin_dir.iterdir():
        path.chmod(0o755)
    pages = PAGES.read_text(encoding="utf-8")
    guard = next(step for step in re.split(r"(?=^      - )", pages, flags=re.MULTILINE)
                 if "- name: Require authoritative acceptance before signing publication\n" in step)
    output = tmp_path / "guard-output"
    summary = tmp_path / "guard-summary"
    guard_run = textwrap.dedent(guard.split("        run: |\n", 1)[1])
    if not accepted:
        guard_run = re.sub(r"^\s*sleep .*$", "              SECONDS=$deadline", guard_run, flags=re.MULTILINE)
    result = subprocess.run(
        ["bash", "-c", guard_run], cwd=root,
        env={**os.environ, "PATH": f"{bin_dir}:{os.environ['PATH']}",
             **{key: str(value) for key, value in yaml.safe_load(pages)["env"].items()},
             "GITHUB_SHA": "b" * 40, "PROMOTION_SOURCE_SHA": source, "GITHUB_REPOSITORY": "fixture/datapulse",
             "APPEND_PREP_STATE": "ready", "APPEND_BRANCH": "attestation/append-contract",
             "APPEND_HEAD_SHA": git(root, "rev-parse", "HEAD"),
             "PR_STATE": "MERGED" if accepted else "OPEN", "GITHUB_OUTPUT": str(output),
             "GITHUB_STEP_SUMMARY": str(summary)},
        text=True, capture_output=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert output.read_text() == ("state=accepted\n" if accepted else "state=append-deferred\n")
    assert git(root, "branch", "--show-current") == "attestation/append-contract"
    assert (root / "health/latest.json").read_bytes() == health
    assert (root / ".attestations/chain_head.json").read_bytes() == head
    assert {path: (root / path).read_bytes() for path in paths} == frozen
    if accepted:
        verify_append(root, "origin/main", require_committed=True)
        assert git(root, "rev-parse", "origin/main") != source
    else:
        assert "append-deferred" in summary.read_text()
