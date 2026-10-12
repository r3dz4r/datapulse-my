"""Focused tests for the shared daily and Pages Sigstore workflow contract."""

from __future__ import annotations

from pathlib import Path
from datetime import timedelta
import os
import re
import subprocess
import sys

import pytest

from scripts.verify_attestation_workflow_contract import ContractError, verify_workflows
from scripts import gen_attestations as ga
from scripts.tests.test_append_set_isolation import NOW, accept, git
from scripts.tests.test_attestations import fixture_root
from scripts.verify_attestation_append import append_paths, verify_append


ROOT = Path(__file__).resolve().parents[2]
DAILY = ROOT / ".github/workflows/datapulse-attest-daily.yml"
PAGES = ROOT / ".github/workflows/deploy-cloudflare-pages.yml"


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
    assert producer.split("        run: |\n", 1)[1] == _step(daily, "produce_rekor_witness").split("        run: |\n", 1)[1]
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
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    verifier = ROOT / "scripts/verify_attestation_append.py"
    (bin_dir / "python3").write_text(
        '#!/bin/bash\nset -Eeuo pipefail\nshift\nargs=("$@")\n'
        # Bound a non-acceptance test to one real remote probe, without sleeping.
        'for i in "${!args[@]}"; do [[ "${args[$i]}" != 1500 ]] || args[$i]=0; done\n'
        f'exec "{sys.executable}" "{verifier}" --root "{root}" "${{args[@]}}"\n'
    )
    (bin_dir / "gh").write_text(
        '#!/bin/bash\n'
        'case "$1 $2" in\n'
        '  "pr list") printf "[]\\n" ;;\n'
        '  "pr view")\n'
        '    if [[ "$*" == *statusCheckRollup* ]]; then printf "IN_PROGRESS/\\n";\n'
        '    else printf "{\\"number\\":99,\\"headRefName\\":\\"%s\\",'
        '\\"headRefOid\\":\\"%s\\",\\"baseRefName\\":\\"main\\",\\"state\\":\\"OPEN\\"}\\n" '
        '"$(git branch --show-current)" "$(git rev-parse HEAD)"; fi ;;\n'
        '  "pr merge") : ;;\n'
        '  *) exit 2 ;;\n'
        'esac\n'
    )
    for path in bin_dir.iterdir():
        path.chmod(0o755)
    pages = PAGES.read_text(encoding="utf-8")
    guard = next(step for step in re.split(r"(?=^      - )", pages, flags=re.MULTILINE)
                 if "- name: Require authoritative acceptance before signing publication\n" in step)
    result = subprocess.run(
        ["bash", "-c", guard.split("        run: |\n", 1)[1]], cwd=root,
        env={**os.environ, "PATH": f"{bin_dir}:{os.environ['PATH']}",
             "GITHUB_SHA": source, "GITHUB_REPOSITORY": "fixture/datapulse"},
        text=True, capture_output=True,
    )
    assert (result.returncode == 0) is accepted, result.stdout + result.stderr
    assert git(root, "branch", "--show-current") == "attestation/append-contract"
    assert (root / "health/latest.json").read_bytes() == health
    assert (root / ".attestations/chain_head.json").read_bytes() == head
    assert {path: (root / path).read_bytes() for path in paths} == frozen
    if accepted:
        verify_append(root, "origin/main", require_committed=True)
        assert git(root, "rev-parse", "origin/main") != source
    else:
        assert "must be accepted" in result.stderr
