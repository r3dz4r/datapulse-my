#!/usr/bin/env python3
"""Fail closed when daily and Pages Sigstore workflow contracts drift."""

from __future__ import annotations

import argparse
from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
COSIGN_INSTALLER = "sigstore/cosign-installer@faadad0cce49287aee09b3a48701e75088a2c6ad"
COSIGN_RELEASE = "cosign-release: v3.1.3"
OIDC_ISSUER = "https://token.actions.githubusercontent.com"
CANONICAL_HEALTH = "--health health/latest.json"
CANONICAL_MANIFEST = "--manifest datapulse.json"
CANONICAL_CHAIN_HEAD = "--legacy-chain-head .attestations/chain_head.json"


class ContractError(Exception):
    """Raised when a workflow no longer satisfies the attestation contract."""


def _read_workflow(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError as error:
        raise ContractError(f"could not read workflow {path}: {error}") from error


def _require(workflow: str, label: str, fragment: str) -> None:
    if fragment not in workflow:
        raise ContractError(f"{label}: missing required {fragment!r}")


def _command_block(workflow: str, command: str, ending: str, label: str) -> str:
    match = re.search(
        rf"{re.escape(command)}(?P<block>(?:[^\n]*\n)*?\s+{re.escape(ending)})",
        workflow,
    )
    if match is None:
        raise ContractError(f"{label}: could not find complete {command!r} command")
    return match.group("block")


def _require_command_arguments(block: str, label: str, command: str, arguments: tuple[str, ...]) -> None:
    for argument in arguments:
        if argument not in block:
            raise ContractError(f"{label}: {command} missing required {argument!r}")


def _require_dsse_flow(workflow: str, label: str, identity: str) -> None:
    for fragment in (
        "python3 scripts/gen_sigstore_bundle.py",
        CANONICAL_HEALTH,
        CANONICAL_MANIFEST,
        CANONICAL_CHAIN_HEAD,
        '--source-commit "$GITHUB_SHA"',
        "python3 scripts/verify_sigstore_bundle.py",
        "--certificate-identity \"$SIGSTORE_IDENTITY\"",
        "--certificate-oidc-issuer \"$SIGSTORE_ISSUER\"",
        COSIGN_INSTALLER,
        COSIGN_RELEASE,
        identity,
        OIDC_ISSUER,
    ):
        _require(workflow, label, fragment)

    if re.search(r"cosign\s+sign-blob\b", workflow) is not None:
        raise ContractError(f"{label}: must not use cosign sign-blob")
    if re.search(r"cosign\s+attest-blob\b[\s\\]*--yes[\s\\]*--statement\b", workflow) is None:
        raise ContractError(
            f"{label}: must use cosign attest-blob --statement for the canonical in-toto predicate"
        )

    canonical_inputs = (
        CANONICAL_HEALTH,
        CANONICAL_MANIFEST,
        CANONICAL_CHAIN_HEAD,
        '--source-commit "$GITHUB_SHA"',
    )
    _require_command_arguments(
        _command_block(workflow, "python3 scripts/gen_sigstore_bundle.py", "--out", label),
        label,
        "python3 scripts/gen_sigstore_bundle.py",
        canonical_inputs,
    )
    _require_command_arguments(
        _command_block(workflow, "python3 scripts/verify_sigstore_bundle.py", "--cosign", label),
        label,
        "python3 scripts/verify_sigstore_bundle.py",
        canonical_inputs,
    )


def _require_daily_guards(workflow: str) -> None:
    for fragment in (
        "id: rekor_guard",
        "id: produce_rekor_witness",
        "DATAPULSE_REKOR_REFERENCE",
        "python3 scripts/attestation_commit_back.py",
    ):
        _require(workflow, "daily workflow", fragment)


def _require_pages_boundaries(workflow: str) -> None:
    for fragment in (
        "signer_down",
        "Require signed attestation for full release",
        "health_only",
        "python3 scripts/verify_sigstore_bundle.py",
    ):
        _require(workflow, "Pages workflow", fragment)


def verify_workflows(daily_path: Path, pages_path: Path) -> None:
    """Verify both workflow files preserve the shared Sigstore signing contract."""
    daily = _read_workflow(daily_path)
    pages = _read_workflow(pages_path)

    _require_dsse_flow(
        daily,
        "daily workflow",
        "https://github.com/r3dz4r/datapulse-my/.github/workflows/datapulse-attest-daily.yml@refs/heads/main",
    )
    _require_dsse_flow(
        pages,
        "Pages workflow",
        "https://github.com/r3dz4r/datapulse-my/.github/workflows/deploy-cloudflare-pages.yml@refs/heads/main",
    )
    _require_daily_guards(daily)
    _require_pages_boundaries(pages)


def parse_args() -> argparse.Namespace:
    """Parse optional workflow paths for local contract testing."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--daily-workflow",
        type=Path,
        default=ROOT / ".github/workflows/datapulse-attest-daily.yml",
    )
    parser.add_argument(
        "--pages-workflow",
        type=Path,
        default=ROOT / ".github/workflows/deploy-cloudflare-pages.yml",
    )
    return parser.parse_args()


def main() -> None:
    """Run the workflow contract verifier as a command-line program."""
    args = parse_args()
    try:
        verify_workflows(args.daily_workflow, args.pages_workflow)
    except ContractError as error:
        raise SystemExit(f"attestation workflow contract: {error}") from error


if __name__ == "__main__":
    main()
