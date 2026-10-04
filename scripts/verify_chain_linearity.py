#!/bin/sh
""":"
exec python3 "$0" "$@"
":"""
# Fail closed unless the latest chain head mirrors the newest dated head.
# 
# This verifies the forward-linearity seed only.  It intentionally does not
# retroactively require the historical dated envelopes to form one chain.

from __future__ import annotations

import argparse
import json
import logging
import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path


LOGGER = logging.getLogger(__name__)
ROOT = Path(__file__).resolve().parents[1]
DATE_DIRECTORY = re.compile(r"\d{4}-\d{2}-\d{2}")
DIGEST = re.compile(r"[0-9a-f]{64}")


class ChainLinearityError(Exception):
    """Raised when the latest chain-head pointer cannot seed a linear next day."""


@dataclass(frozen=True)
class ChainLinearityReport:
    """The newest dated head confirmed as the next day's predecessor."""

    latest_date: str
    chain_head: str


def _load_head(path: Path, label: str) -> str:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ChainLinearityError(f"{label} is missing or invalid") from error
    if not isinstance(value, dict):
        raise ChainLinearityError(f"{label} must be a JSON object")
    chain_head = value.get("chain_head")
    if not isinstance(chain_head, str) or DIGEST.fullmatch(chain_head) is None:
        raise ChainLinearityError(f"{label} has an invalid chain_head")
    return chain_head


def _dated_heads(root: Path) -> list[tuple[date, str]]:
    base = root / "attestations"
    try:
        children = list(base.iterdir())
    except OSError as error:
        raise ChainLinearityError("attestations directory is missing or unreadable") from error

    dated_heads: list[tuple[date, str]] = []
    for directory in children:
        if not directory.is_dir() or DATE_DIRECTORY.fullmatch(directory.name) is None:
            continue
        try:
            day = date.fromisoformat(directory.name)
        except ValueError as error:
            raise ChainLinearityError(f"dated attestation directory is invalid: {directory.name}") from error
        head_path = directory / "chain_head.json"
        if head_path.is_file():
            if (directory / "revisions").is_dir():
                try:
                    from scripts.verify_attestation_binding import ContractError, verified_day_tip
                except ModuleNotFoundError:
                    from verify_attestation_binding import ContractError, verified_day_tip
                try:
                    head_path = root / verified_day_tip(root, directory.name)
                except ContractError as error:
                    raise ChainLinearityError(f"correction history is invalid: {error}") from error
            dated_heads.append(
                (day, _load_head(head_path, f"dated chain head for {directory.name}"))
            )
    if not dated_heads:
        raise ChainLinearityError("no dated attestation chain heads found")
    return dated_heads


def verify_chain_linearity(root: Path) -> ChainLinearityReport:
    """Require latest/chain_head.json to equal the newest dated chain head."""
    index_path = root / "attestations/chain-index.json"
    if index_path.exists() and json.loads(index_path.read_text()).get("schema") == "datapulse/v2/chain-index":
        try:
            import sys
            sys.path.insert(0, str(ROOT))
            from scripts.attestation_sets import discovery, selected_directory
            document = discovery(root)
            selected_directory(root)
            newest_head = document["current_head"]
            return ChainLinearityReport(document["envelopes"][newest_head]["date"], newest_head)
        except (ValueError, OSError, KeyError, TypeError) as error:
            raise ChainLinearityError(str(error)) from error
    newest_day, newest_head = max(_dated_heads(root), key=lambda item: item[0])
    latest_head = _load_head(
        root / "attestations/latest/chain_head.json", "latest chain head"
    )
    if latest_head != newest_head:
        raise ChainLinearityError(
            "latest chain head does not match newest dated head "
            f"({newest_day.isoformat()})"
        )
    return ChainLinearityReport(newest_day.isoformat(), newest_head)


def main() -> int:
    """Run the forward-linearity seed invariant."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args()
    try:
        report = verify_chain_linearity(args.root)
    except ChainLinearityError as error:
        LOGGER.error("verify_chain_linearity.py: %s", error)
        return 1
    LOGGER.info(
        "latest chain head mirrors newest dated head %s: %s",
        report.latest_date,
        report.chain_head,
    )
    return 0


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    raise SystemExit(main())
