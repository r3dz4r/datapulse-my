"""Focused tests for the shared daily and Pages Sigstore workflow contract."""

from __future__ import annotations

from pathlib import Path

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
    daily.write_text(original.replace("attestation_commit_back.py", "commit_back.py", 1), encoding="utf-8")

    with pytest.raises(ContractError, match="attestation_commit_back.py"):
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
