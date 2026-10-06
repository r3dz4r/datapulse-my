#!/usr/bin/env python3
"""Require an SPDX identifier or a licence-specific source reference."""
from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
# SPDX's generated licence list, pinned to v3.29.0 (including deprecated IDs).
# Provenance URL and list version are retained in the embedded data file.
SPDX_IDS = frozenset(json.loads(Path(__file__).with_name("spdx_licence_ids.json").read_text())["licence_ids"])
LOGGER = logging.getLogger(__name__)


def source_reference(value: object) -> bool:
    """A reference must identify the licence source, not merely a dataset URL."""
    if not isinstance(value, str) or not value or value != value.strip():
        return False
    parsed = urlparse(value)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc) and not parsed.username and not parsed.password


def licence_failures(manifest: dict, custodians: dict) -> list[str]:
    """Name every row lacking either recognized identity or sourced evidence."""
    failures = []
    entries = custodians.get("custodians", {})
    for row in manifest["datasets"]:
        identifier, licence = row.get("id"), row.get("licence")
        if isinstance(licence, str) and licence in SPDX_IDS:
            continue
        custodian = entries.get(row.get("custodian"), {})
        # Custodian evidence is keyed by the exact licence value so a reference
        # for one instrument cannot authorize every instrument its rows declare.
        references = custodian.get("licence_references", {})
        reference = references.get(licence) if isinstance(licence, str) and isinstance(references, dict) else None
        if source_reference(row.get("licence_ref")) or source_reference(reference):
            continue
        if not isinstance(licence, str) or not licence.strip():
            failures.append(f"{identifier}: licence is missing or invalid; declare an SPDX identifier or a non-SPDX licence with licence_ref")
        else:
            failures.append(f"{identifier}: {licence!r} is not an SPDX licence identifier and has no valid licence source reference; record licence_ref on this row or custodian.licence_references[{licence!r}]")
    return failures


def main() -> int:
    """Check repository inputs without changing their declared licence values."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args()
    try:
        manifest = json.loads((args.root / "datapulse.json").read_text())
        custodians = json.loads((args.root / "custodians.json").read_text())
        failures = licence_failures(manifest, custodians)
    except (OSError, ValueError, KeyError, TypeError) as error:
        LOGGER.error("licence consistency: invalid repository inputs: %s", error)
        return 1
    for failure in failures:
        LOGGER.error("licence consistency: %s", failure)
    if not failures:
        LOGGER.info("licence consistency: %d datasets accepted", len(manifest["datasets"]))
    return int(bool(failures))


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    raise SystemExit(main())
