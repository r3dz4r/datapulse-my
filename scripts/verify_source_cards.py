#!/usr/bin/env python3
"""Verify source-card claims against the latest local health probes."""

from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path
from typing import Any


LOGGER = logging.getLogger(__name__)
ROOT = Path(__file__).resolve().parents[1]
BNM_STALE_200 = {"bnm_base_rate", "bnm_kijang_emas", "bnm_opr"}
KUANTAN_DATASET = "gtfs_static_prasarana_bus_kuantan"


def load_card(path: Path) -> dict[str, Any]:
    """Load JSON-form YAML frontmatter from a source-card Markdown file."""
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        raise ValueError(f"{path}: missing opening frontmatter delimiter")
    closing = text.find("\n---\n", 4)
    if closing == -1:
        raise ValueError(f"{path}: missing closing frontmatter delimiter")
    frontmatter = text[4:closing]
    card = json.loads(frontmatter)
    if not isinstance(card, dict):
        raise ValueError(f"{path}: frontmatter must be a mapping")
    return card


def latest_probe_per_dataset(history_path: Path, prefix: str) -> dict[str, dict[str, Any]]:
    """Return the latest observed record for each dataset with ``prefix``."""
    latest: dict[str, dict[str, Any]] = {}
    with history_path.open(encoding="utf-8") as history:
        for line_number, line in enumerate(history, start=1):
            if not line.strip():
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{history_path}:{line_number}: invalid JSONL") from exc
            dataset_id = record.get("dataset_id")
            observed_at = record.get("observed_at")
            if not isinstance(dataset_id, str) or not dataset_id.startswith(prefix):
                continue
            if not isinstance(observed_at, str):
                raise ValueError(f"{history_path}:{line_number}: missing observed_at")
            previous = latest.get(dataset_id)
            if previous is None or observed_at >= previous["observed_at"]:
                latest[dataset_id] = record
    return latest


def _affected_datasets(card: dict[str, Any], phrase: str) -> set[str]:
    claims: set[str] = set()
    for false_positive in card.get("known_false_positives", []):
        if phrase in false_positive.get("description", ""):
            claims.update(false_positive.get("affected_datasets", []))
    return claims


def verify_bnm_open_api_card(card: dict[str, Any], history_path: Path) -> list[str]:
    """Validate BNM source-card claims against the most recent BNM probes."""
    errors: list[str] = []
    latest = latest_probe_per_dataset(history_path, prefix="bnm_")
    stale_200 = sorted(
        dataset_id
        for dataset_id, record in latest.items()
        if record.get("status") == "stale"
        and record.get("http_status") == 200
        and dataset_id in BNM_STALE_200
    )
    card_claims = _affected_datasets(card, "HTTP 200")
    if set(stale_200) != card_claims:
        errors.append(
            f"BNM stale-200 dataset mismatch: history shows {stale_200}, "
            f"card claims {sorted(card_claims)}"
        )
    if card.get("data_type_mix", {}).get("reference", 0) < 1:
        errors.append("BNM data_type_mix.reference must be >= 1")
    if card.get("datasets_in_family") != 8:
        errors.append(f"BNM datasets_in_family={card.get('datasets_in_family')}, expected 8")
    if card_claims != BNM_STALE_200:
        errors.append(
            "BNM known_false_positives must list exactly the three HTTP-200-but-stale "
            f"datasets; got {sorted(card_claims)}, expected {sorted(BNM_STALE_200)}"
        )
    return errors


def verify_gtfs_api_card(card: dict[str, Any], history_path: Path) -> list[str]:
    """Validate GTFS source-card claims against the most recent GTFS probes."""
    errors: list[str] = []
    latest = latest_probe_per_dataset(history_path, prefix="gtfs_")
    discontinued = sorted(
        dataset_id for dataset_id, record in latest.items() if record.get("status") == "discontinued"
    )
    failure_datasets = {example.get("dataset_id") for example in card.get("failure_examples", [])}
    quirks = card.get("freshness_signals", {}).get("known_quirks", [])
    if card.get("datasets_in_family") != 30:
        errors.append(f"GTFS datasets_in_family={card.get('datasets_in_family')}, expected 30")
    if discontinued != [KUANTAN_DATASET]:
        errors.append(f"GTFS discontinued dataset mismatch: history shows {discontinued}")
    if KUANTAN_DATASET not in failure_datasets:
        errors.append(f"GTFS failure_examples must list {KUANTAN_DATASET}")
    if not any("zero vehicles" in quirk and "off-peak" in quirk for quirk in quirks):
        errors.append("GTFS known_quirks must mention the off-peak zero-vehicle pattern")
    if "protobuf" not in card.get("access_method", "").lower():
        errors.append("GTFS access_method must mention protobuf for realtime")
    return errors


def verify_source_cards(cards_dir: Path, history_path: Path) -> list[str]:
    """Verify both source cards and return deterministic error messages."""
    bnm_card = load_card(cards_dir / "bnm-open-api.md")
    gtfs_card = load_card(cards_dir / "gtfs-api.md")
    return verify_bnm_open_api_card(bnm_card, history_path) + verify_gtfs_api_card(gtfs_card, history_path)


def parse_args() -> argparse.Namespace:
    """Parse local input paths without changing probe or deployment state."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cards-dir", type=Path, default=ROOT / "notes" / "source-cards")
    parser.add_argument("--history-path", type=Path, default=ROOT / "health" / "history.jsonl")
    return parser.parse_args()


def main() -> int:
    """Run verification and return a conventional process status."""
    args = parse_args()
    try:
        errors = verify_source_cards(args.cards_dir, args.history_path)
    except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
        LOGGER.error("source-card verification failed: %s", exc)
        return 1
    if errors:
        for error in errors:
            LOGGER.error("%s", error)
        return 1
    LOGGER.info("source cards agree with latest local probe history")
    return 0


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    raise SystemExit(main())
