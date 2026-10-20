#!/usr/bin/env python3
"""Bound payload I/O by the append, allowing only metadata and the chain spine to grow."""
from __future__ import annotations

from collections import Counter
from datetime import timedelta
from pathlib import Path

import pytest

from scripts import gen_attestations as ga
from scripts import verify_attestation_append as verifier
from scripts.attestation_sets import discovery, first_parent_order
from scripts.tests.test_append_set_isolation import NOW, accept, git
from scripts.tests.test_attestations import fixture_root
from scripts.tests.test_verifier_discovery_equivalence import maps
from scripts.verify_attestation_binding import ContractError

HISTORY_SIZES = (10, 100)
MAX_PAYLOAD_READ_RATIO = 1.25
FIXED_PROJECTION_READS = 2  # Latest scores and the selected ancestor's frozen scores.
MAX_READS_PER_DELTA_FILE = 3  # Signature/content verification plus exact Git hashing.
MAX_HISTORICAL_PAYLOAD_READS = 1  # Only the projected ancestor's frozen scores.
SPINE_FILES = {"chain-index.json", "chain_head.json", "index.json", "binding.json"}


@pytest.mark.parametrize("same_day", [False, True])
@pytest.mark.parametrize("inherited_checkpoint", [False, True])
def test_candidate_maps_match_full_discovery(
    tmp_path: Path, same_day: bool, inherited_checkpoint: bool,
) -> None:
    root, key = fixture_root(tmp_path)
    ga.generate(root, key, NOW)
    ga.generate(root, key, NOW + timedelta(hours=1), force_append=True)
    base = accept(root)
    references = {path for path, _ in verifier.accepted_files(root, base)}
    ga.generate(root, key, NOW + (timedelta(hours=2) if same_day else timedelta(days=1)),
                force_append=True)
    if inherited_checkpoint:
        git(root, "restore", ".")
    expected = discovery(root, fork_order=first_parent_order(root, base))
    assert maps(verifier._candidate_discovery(root, base, references)) == maps(expected)
    verifier.verify_append(root, base)


@pytest.mark.parametrize("entry", ["file", "ignored-file", "empty-directory", "symlink"])
def test_additions_cannot_hide_inside_an_accepted_set(tmp_path: Path, entry: str) -> None:
    root, key = fixture_root(tmp_path)
    ga.generate(root, key, NOW)
    base = accept(root)
    document = discovery(root)
    extra = root / Path(document["heads"][document["current_head"]]).parent / "unexpected"
    if entry == "empty-directory":
        extra.mkdir()
    elif entry == "symlink":
        extra.symlink_to("scores.json")
    else:
        extra.write_text("unexpected evidence\n")
        if entry == "ignored-file":
            (root / ".gitignore").write_text("unexpected\n")
    with pytest.raises(ContractError, match="unexpected files"):
        discovery(root)
    with pytest.raises((ContractError, ValueError), match="unexpected files|must be regular files"):
        verifier.verify_append(root, base)


@pytest.mark.parametrize("malformation", ["date", "hash", "json"])
def test_malformed_candidate_is_not_hidden_by_reference_filter(
    tmp_path: Path, malformation: str,
) -> None:
    root, key = fixture_root(tmp_path)
    ga.generate(root, key, NOW)
    base = accept(root)
    document = discovery(root)
    head = root / document["heads"][document["current_head"]]
    day = "not-a-day" if malformation == "date" else "2026-08-16"
    digest = "bad" if malformation in {"hash", "json"} else "a" * 64
    candidate = root / "attestations" / day / "revisions" / digest / "chain_head.json"
    candidate.parent.mkdir(parents=True)
    candidate.write_bytes(b"{" if malformation == "json" else head.read_bytes())
    for check in (lambda: discovery(root), lambda: verifier.verify_append(root, base)):
        with pytest.raises(ContractError, match="unsafe|missing or invalid"):
            check()


def test_one_append_payload_work_is_independent_of_history(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    measurements = []
    for size in HISTORY_SIZES:
        root, key = fixture_root(tmp_path / str(size))
        for revision in range(size):
            ga.generate(root, key, NOW + timedelta(days=revision))
        base = accept(root)
        accepted_paths = {path for path, _ in verifier.accepted_files(root, base)}
        ga.generate(root, key, NOW + timedelta(days=size))
        # An immutable-only append inherits the accepted projection and index.
        git(root, "restore", ".")
        delta_paths = {p.relative_to(root).as_posix()
                       for p in (root / "attestations").rglob("*") if p.is_file()}
        delta_paths -= accepted_paths
        assert delta_paths
        counts: Counter[str] = Counter()
        original_open = Path.open
        original_read = verifier._GitTree.read

        def counted_open(path: Path, *args: object, **kwargs: object):
            relative = path.relative_to(root).as_posix() if path.is_relative_to(root) else ""
            if relative.startswith("attestations/"):
                if path.name in SPINE_FILES:
                    counts["spine"] += 1
                else:
                    counts["payload"] += 1
                    if relative in accepted_paths and not relative.startswith("attestations/latest/"):
                        counts["historical_payload"] += 1
            return original_open(path, *args, **kwargs)

        def counted_read(tree: verifier._GitTree, path) -> bytes:
            counts["git_spine" if path.name in SPINE_FILES else "git_payload"] += 1
            return original_read(tree, path)

        with monkeypatch.context() as patch:
            patch.setattr(Path, "open", counted_open)
            patch.setattr(verifier._GitTree, "read", counted_read)
            verifier.verify_append(root, base)
        measurement = {"history": size, "delta_files": len(delta_paths), **counts}
        measurements.append(measurement)
        print(measurement)

    small, large = measurements
    assert large["payload"] / small["payload"] <= MAX_PAYLOAD_READ_RATIO, measurements
    for measured in measurements:
        assert measured["payload"] <= (
            FIXED_PROJECTION_READS + MAX_READS_PER_DELTA_FILE * measured["delta_files"]
        ), measurements
        assert measured.get("historical_payload", 0) <= MAX_HISTORICAL_PAYLOAD_READS, measurements
        assert measured.get("git_payload", 0) <= 1, measurements  # Public key registry only.
