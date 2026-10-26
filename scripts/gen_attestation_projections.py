#!/usr/bin/env python3
"""Refresh unsigned selectors from evidence already accepted on main."""
from __future__ import annotations

import argparse
import json
import logging
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.attestation_sets import assert_head_extends_base, set_directory
from scripts.verify_attestation_append import accepted_discovery, git_bytes
from scripts.verify_attestation_binding import ContractError

logger = logging.getLogger(__name__)
SCORES_PROJECTION = "attestations/latest/" + "scores.json"
PROJECTIONS = (
    "attestations/latest/index.json",
    "attestations/latest/chain_head.json",
    "attestations/chain-index.json",
    ".attestations/chain_head.json",
    "attestations/latest/binding.json",
    SCORES_PROJECTION,
)
REGISTRY = "docs/.well-known/datapulse-probe-keys.json"


class ProjectionError(Exception):
    """The checkout or accepted lineage cannot safely produce projections."""


def _git(root: Path, *args: str) -> str:
    result = subprocess.run(["git", *args], cwd=root, capture_output=True, text=True, check=False)
    if result.returncode:
        raise ProjectionError(f"git {' '.join(args)} failed: {result.stderr.strip()}")
    return result.stdout


def _check_evidence(root: Path, *, require_main: bool) -> None:
    if require_main:
        branch = subprocess.run(["git", "symbolic-ref", "--quiet", "--short", "HEAD"],
                                cwd=root, capture_output=True, text=True, check=False)
        if branch.returncode or branch.stdout.strip() != "main":
            raise ProjectionError("HEAD must be on branch main")
    status = _git(root, "status", "--porcelain", "--untracked-files=all")
    for line in status.splitlines():
        path = line[3:]
        if path not in PROJECTIONS:
            raise ProjectionError(f"working tree must be clean: {path}")
    tracked_projections = set(_git(root, "ls-files", "--", *PROJECTIONS).splitlines())
    for path in PROJECTIONS:
        if path not in tracked_projections:
            raise ProjectionError(f"projection file is not tracked at HEAD: {path}")

    # Discovery verifies files throughout each immutable set, including signed
    # datasets and snapshots. Check the entire evidence tree before it reads any.
    listed = _git(root, "ls-files", "--error-unmatch", "-z", "--", "attestations", REGISTRY)
    tracked = set(listed.split("\0")) - {""}
    evidence = {path.relative_to(root).as_posix()
                for path in (root / "attestations").rglob("*") if path.is_file() or path.is_symlink()}
    evidence.add(REGISTRY)
    for path in sorted(evidence):
        if path not in tracked:
            raise ProjectionError(f"evidence file is not tracked at HEAD: {path}")
        if (root / path).is_symlink():
            raise ProjectionError(f"evidence file is not regular: {path}")


def _derive(root: Path, *, require_main: bool) -> dict[str, bytes]:
    _check_evidence(root, require_main=require_main)
    accepted = json.loads(git_bytes(root, "HEAD", "attestations/chain-index.json"))
    previous = accepted["current_head"]
    document = accepted_discovery(root, "HEAD")
    current = document["current_head"]
    try:
        assert_head_extends_base(document, previous)
    except ContractError as error:
        raise ProjectionError(f"derived head {current} does not extend accepted head {previous}: {error}") from error
    reference = document["heads"][current]
    directory = set_directory(reference)
    revision = root / directory / "revisions" / current
    if (revision / "chain_head.json").is_file():
        directory = revision.relative_to(root).as_posix()
    return {
        PROJECTIONS[0]: (root / directory / "index.json").read_bytes(),
        PROJECTIONS[1]: (root / directory / "chain_head.json").read_bytes(),
        PROJECTIONS[2]: (json.dumps(document, ensure_ascii=False, indent=2) + "\n").encode("utf-8"),
        PROJECTIONS[3]: (root / directory / "chain_head.json").read_bytes(),
        PROJECTIONS[4]: (root / directory / "binding.json").read_bytes(),
        PROJECTIONS[5]: (root / directory / "scores.json").read_bytes(),
    }


def derive_projections(root: Path) -> dict[str, bytes]:
    """Derive five projections only from a clean accepted main checkout."""
    return _derive(root.resolve(), require_main=True)


def _value(path: str, raw: bytes | None) -> str:
    if raw is None:
        return "missing"
    document = json.loads(raw)
    if path == PROJECTIONS[0]:
        return f"date={document['date']} chain_head_ref={document['chain_head_ref']}"
    if path in {PROJECTIONS[1], PROJECTIONS[3]}:
        return f"chain_head={document['chain_head']}"
    if path == PROJECTIONS[4]:
        return f"chain_head={document['payload']['ed25519']['chain_head']}"
    if path == PROJECTIONS[5]:
        return f"generated_at={document['generated_at']}"
    return f"current_head={document['current_head']} days={len(document['days'])}"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--check", action="store_true", help="report stale projections without writing")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(message)s", stream=sys.stdout)
    root = args.root.resolve()
    try:
        # PR checkouts are detached or on a candidate branch. They may be
        # checked read-only; only main is allowed to write accepted selectors.
        derived = _derive(root, require_main=not args.check)
        stale = []
        for path, content in derived.items():
            target = root / path
            committed = target.read_bytes() if target.is_file() else None
            if committed != content:
                stale.append((path, committed, content))
        if args.check:
            for path, committed, content in stale:
                logger.info("STALE %s committed=%s derived=%s", path,
                            _value(path, committed), _value(path, content))
            if not stale:
                logger.info("OK: accepted attestation projections match evidence")
            return 1 if stale else 0
        for path, _, content in stale:
            target = root / path
            pending = target.with_name(target.name + ".tmp")
            pending.write_bytes(content)
            os.replace(pending, target)
            logger.info("UPDATED %s: %s", path, _value(path, content))
        if not stale:
            logger.info("UNCHANGED: accepted attestation projections match evidence")
        return 0
    except (ContractError, ProjectionError, OSError, KeyError, ValueError) as error:
        logger.error("REFUSED: %s", error)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
