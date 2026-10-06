#!/usr/bin/env python3
"""Enumerate safe immutable metadata/proof URLs for fail-closed served checks."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.attestation_sets import FILES, SET_REF, set_directory


def _proof_pattern(day: str, *, revision: bool) -> re.Pattern[str]:
    """Mirror main's split: anchors are flat, revisions may nest under the day.

    A revision's Rekor evidence is grouped beneath the binding day (for example
    ``attestations/rekor/<day>/correction/reference.json``), while the anchor set
    may only reference a flat object. Both stay inside the binding day.
    """
    tail = r"[A-Za-z0-9_.-]+(?:/[A-Za-z0-9_.-]+)*" if revision else r"[A-Za-z0-9_.-]+"
    return re.compile(rf"attestations/(?:rekor/)?{re.escape(day)}/{tail}\.json")


def fetch_refs(root: Path, proofs: bool = False) -> list[str]:
    """Discovery proposes URLs; the binding verifier subsequently authenticates them."""
    index = json.loads((root / "attestations/latest/index.json").read_text())
    chain = json.loads((root / "attestations/chain-index.json").read_text())
    selected = set_directory(index["chain_head_ref"])
    directories = {selected}
    if chain.get("schema") == "datapulse/v2/chain-index":
        directories.update(set_directory(chain["heads"][h]) for h in chain["envelopes"])
    elif chain.get("schema") != "datapulse/v1/chain-index":
        raise ValueError("unknown chain index schema")
    references = set()
    for directory in directories:
        if not proofs:
            references.update(directory + "/" + filename for filename in FILES)
            continue
        binding = json.loads((root / directory / "binding.json").read_text())
        day = binding["payload"]["date"]
        match = SET_REF.fullmatch(directory + "/chain_head.json")
        revision = match is not None and match[2] is not None
        pattern = _proof_pattern(day, revision=revision)
        for reference in (binding.get("rekor") or {}).values():
            if (
                not isinstance(reference, str)
                or not pattern.fullmatch(reference)
                or any(segment in {".", ".."} for segment in reference.split("/"))
            ):
                raise ValueError("unsafe Rekor proof reference")
            references.add(reference)
    return sorted(references)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--proofs", action="store_true")
    args = parser.parse_args()
    for reference in fetch_refs(args.root, args.proofs):
        print(reference)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
