"""Focused tests for the shared daily and Pages Sigstore workflow contract."""

from __future__ import annotations

from pathlib import Path
import re

import pytest

from scripts.verify_attestation_workflow_contract import ContractError, verify_workflows


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
