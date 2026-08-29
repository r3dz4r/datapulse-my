#!/usr/bin/env python3
"""Classify a served attestation plane without weakening fail-closed checks."""

from __future__ import annotations

import argparse
import json
import logging
import re
import sys
from dataclasses import dataclass
from datetime import date, datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

if __package__:
    from scripts.verify_attestation_binding import (
        ContractError,
        verify_contract,
        verify_unbound_legacy_plane,
    )
else:
    from verify_attestation_binding import (  # type: ignore[no-redef]
        ContractError,
        verify_contract,
        verify_unbound_legacy_plane,
    )


LOGGER = logging.getLogger(__name__)
DIGEST = re.compile(r"[0-9a-f]{64}")
FALSE_CLAIMS = {
    "artifact_signed": False,
    "rekor_witnessed": False,
    "source_truth_verified": False,
}
SIGNER_DOWN_REASONS = {
    "Ed25519 binding does not match the latest daily head",
    "health digest/count/time binding does not match served health",
    "served attestation is stale",
}


class PlaneState(str, Enum):
    """Release-relevant attestation plane states."""

    HEALTHY = "healthy"
    SIGNER_DOWN = "signer_down"
    CORRUPT = "corrupt"


@dataclass(frozen=True)
class Classification:
    """Attestation plane state plus its verification diagnostic."""

    state: PlaneState
    reason: str


def _load(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ContractError(f"{label} is missing or invalid") from error
    if not isinstance(value, dict):
        raise ContractError(f"{label} must be an object")
    return value


def _parse_date(value: object, label: str) -> date:
    if not isinstance(value, str):
        raise ContractError(f"{label} is invalid")
    try:
        parsed = date.fromisoformat(value)
    except ValueError as error:
        raise ContractError(f"{label} is invalid") from error
    if parsed.isoformat() != value:
        raise ContractError(f"{label} is invalid")
    return parsed


def _validate_fail_closed_binding(root: Path) -> dict[str, Any]:
    binding_path = root / "attestations/latest/binding.json"
    binding = _load(binding_path, "latest binding")
    payload = binding.get("payload")
    if (
        binding.get("schema") != "datapulse/v1/attestation-binding-envelope"
        or not isinstance(payload, dict)
        or payload.get("schema") != "datapulse/v1/attestation-binding"
        or binding.get("claims") != FALSE_CLAIMS
        or binding.get("rekor") is not None
    ):
        raise ContractError("published trust claims do not match verified evidence")

    binding_date = _parse_date(payload.get("date"), "binding date").isoformat()
    dated_binding = root / f"attestations/{binding_date}/binding.json"
    if not dated_binding.is_file() or dated_binding.read_bytes() != binding_path.read_bytes():
        raise ContractError("latest binding is stale or not the dated binding")

    ed25519 = payload.get("ed25519")
    if not isinstance(ed25519, dict):
        raise ContractError("attestation binding payload is incomplete")
    dated_head = _load(
        root / f"attestations/{binding_date}/chain_head.json", "dated chain head"
    )
    head_payload = dated_head.get("payload")
    if (
        dated_head.get("schema") != "datapulse/v1/daily-chain-head-envelope"
        or not isinstance(head_payload, dict)
        or head_payload.get("schema") != "datapulse/v1/daily-chain-head"
        or head_payload.get("date") != binding_date
        or not isinstance(dated_head.get("chain_head"), str)
        or DIGEST.fullmatch(dated_head["chain_head"]) is None
        or dated_head.get("chain_head") != ed25519.get("chain_head")
    ):
        raise ContractError("dated chain head is invalid")
    return binding


def classify_plane(
    root: Path,
    *,
    now: datetime | None = None,
    max_stale_days: int = 3,
    verify_datasets: bool = True,
) -> Classification:
    """Return healthy, signer_down, or corrupt for the served plane."""
    current = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    try:
        result = verify_contract(
            root, now=current, require_rekor=False, verify_datasets=verify_datasets
        )
    except ContractError as strict_error:
        if str(strict_error) not in SIGNER_DOWN_REASONS:
            return Classification(PlaneState.CORRUPT, str(strict_error))
        try:
            index = _load(
                root / "attestations/latest/index.json", "latest attestation index"
            )
            index_date = _parse_date(index.get("date"), "attestation index date")
            if (current.date() - index_date).days <= max_stale_days:
                raise ContractError("unsigned attestation plane is not stale")
            _validate_fail_closed_binding(root)
            verify_unbound_legacy_plane(
                root, now=current, verify_datasets=verify_datasets
            )
        except ContractError as fail_closed_error:
            return Classification(PlaneState.CORRUPT, str(fail_closed_error))
        return Classification(PlaneState.SIGNER_DOWN, str(strict_error))

    claims = result.get("claims")
    if claims != {
        "artifact_signed": True,
        "rekor_witnessed": True,
        "source_truth_verified": False,
    }:
        return Classification(
            PlaneState.CORRUPT,
            "current attestation plane does not carry verified signing evidence",
        )
    return Classification(PlaneState.HEALTHY, "binding and signing evidence verified")


def _parse_time(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise argparse.ArgumentTypeError("--now must be an ISO-8601 timestamp") from error
    if parsed.tzinfo is None:
        raise argparse.ArgumentTypeError("--now must include a UTC offset")
    return parsed.astimezone(timezone.utc)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--planedir", type=Path, required=True)
    parser.add_argument("--now", type=_parse_time)
    parser.add_argument("--max-stale-days", type=int, default=3)
    parser.add_argument("--head-only", action="store_true")
    args = parser.parse_args()
    result = classify_plane(
        args.planedir,
        now=args.now,
        max_stale_days=args.max_stale_days,
        verify_datasets=not args.head_only,
    )
    if result.state is PlaneState.CORRUPT:
        LOGGER.error("verify_attestation_binding.py: %s", result.reason)
        return 1
    sys.stdout.write(f"{result.state.value}\n")
    return 0


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    raise SystemExit(main())
