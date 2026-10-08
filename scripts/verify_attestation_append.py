#!/usr/bin/env python3
"""Check evidence immutability and signed-parent CAS against an accepted Git base."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.attestation_sets import (
    FILES,
    PIPELINE_OWNED_PROJECTIONS,
    discovery,
    set_directory,
    verify_legacy_mirror,
)
from scripts.verify_attestation_binding import ContractError, _load, _parse_time

PROJECTIONS = {"attestations/chain-index.json", ".attestations/chain_head.json"}


def accepted_day_directory(root: Path, document: dict) -> str:
    """Resolve the candidate's day from its current head mapping."""
    digest = document.get("current_head")
    if digest is None:
        raise ContractError("chain index missing key: current_head")
    heads = document.get("heads")
    if not isinstance(heads, dict) or digest not in heads:
        raise ContractError(f"chain index heads missing key: {digest}")
    return set_directory(heads[digest])


def git_bytes(root: Path, revision: str, path: str) -> bytes:
    """Read accepted source bytes, never consult a mutable date alias."""
    return subprocess.run(["git", "show", f"{revision}:{path}"], cwd=root, check=True, capture_output=True).stdout


def verify_append(root: Path, base: str, require_committed: bool = False) -> None:
    """Reject rewritten ledger bytes, remaps, lost entries, forks and stale parents."""
    files = subprocess.run(["git", "ls-tree", "-r", "--name-only", base, "attestations"], cwd=root, check=True, capture_output=True, text=True).stdout.splitlines()
    for path in files:
        if path in PROJECTIONS or path.startswith("attestations/latest/"):
            continue
        if not (root / path).is_file() or (root / path).read_bytes() != git_bytes(root, base, path):
            raise ValueError(f"immutable evidence changed or deleted: {path}")
    old = json.loads(git_bytes(root, base, "attestations/chain-index.json"))
    new = discovery(root)
    for field in ("heads", "anchors", "envelopes"):
        if any(new.get(field, {}).get(k) != v for k, v in old.get(field, {}).items()):
            raise ValueError(f"accepted {field} entry replaced or deleted")
    for day, run in old.get("days", {}).items():
        if new["days"].get(day, [])[:len(run)] != run:
            raise ValueError("accepted day run replaced or reordered")
    if old.get("schema") == "datapulse/v2/chain-index":
        for field in ("migration_head", "unresolved_heads"):
            if new.get(field) != old.get(field):
                raise ValueError("historical migration boundary changed")
    parent = old.get("current_head") or json.loads(git_bytes(root, base, "attestations/latest/chain_head.json"))["chain_head"]
    cursor, seen = new["current_head"], set()
    while cursor != parent:
        if cursor in seen or cursor in old["heads"] or cursor not in new["envelopes"]:
            raise ValueError("candidate does not append to accepted parent")
        seen.add(cursor)
        cursor = new["envelopes"][cursor]["parent_head"]
    if set(new["heads"]) - set(old["heads"]) != seen:
        raise ValueError("candidate contains a sibling or unaccepted head")
    directory = accepted_day_directory(root, new)
    verify_legacy_mirror(root, new, directory)
    for filename in FILES:
        projection = root / "attestations/latest" / filename
        if not projection.is_file():
            raise ContractError("latest projection is stale or mixed")
        frozen = root / directory / filename
        if filename in PIPELINE_OWNED_PROJECTIONS:
            latest_scores = _load(projection, "latest scores projection")
            frozen_scores = _load(frozen, "immutable scores")
            if _parse_time(latest_scores.get("generated_at"), "latest scores generated_at") < _parse_time(
                frozen_scores.get("generated_at"), "immutable scores generated_at"
            ):
                raise ContractError("latest projection is stale or mixed")
        elif projection.read_bytes() != frozen.read_bytes():
            raise ContractError("latest projection is stale or mixed")
    if require_committed:
        for digest in seen:
            raise ValueError(f"candidate head {digest} must be accepted in authoritative Git before publication")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--base", default="HEAD")
    parser.add_argument("--require-committed", action="store_true")
    args = parser.parse_args()
    try:
        verify_append(args.root, args.base, args.require_committed)
    except (ValueError, OSError, KeyError, subprocess.CalledProcessError) as error:
        raise SystemExit(f"attestation append: {error}") from error
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
