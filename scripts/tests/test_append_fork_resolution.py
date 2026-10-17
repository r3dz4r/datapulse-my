#!/usr/bin/env python3
"""Pin the incident's fail-closed boundary until authorized reconciliation exists.

There is no selected head on the 2026-10-17 fork: both consumers must refuse it.
A new signed child of either sibling alone cannot consume the other sibling.
These tests deliberately do not claim that passing tests unblocks publication.
"""
from __future__ import annotations

import hashlib
import shutil
from datetime import timedelta
from pathlib import Path

import pytest

from scripts import gen_attestations as ga
from scripts import verify_attestation_append as verifier
from scripts.attestation_sets import discovery, verify_set
from scripts.tests.test_append_set_isolation import NOW, accept, git, staged_bytes
from scripts.tests.test_attestations import fixture_root
from scripts.verify_attestation_binding import ContractError

ROOT = Path(__file__).resolve().parents[2]
INCIDENT = "12c6b966d343937a4fe9ac0adfe8c7f7746450b6"
PARENT = "efdc505c7d31e8d07136194918bce1f6a8e4e8222037631f798cfa5c0330944f"
SIBLINGS = (
    "063aa71d64e2dd9f96ef85a7ee7cadcbf6248b27a4232ac031e0ba46b39f8423",
    "8730c6aa944bdb88fbe1b1fafe08549e9a8951f8754a0124450d923dd147d4cf",
)


def test_accepted_files_stream_object_ids_instead_of_ledger_bytes(tmp_path: Path) -> None:
    root, key = fixture_root(tmp_path)
    ga.generate(root, key, NOW)
    base = accept(root)
    entries = verifier.accepted_files(root, base)
    assert iter(entries) is entries, "the ledger must not be materialized in a dict"
    path, digest = next(entries)
    raw = (root / path).read_bytes()
    assert digest == hashlib.sha1(f"blob {len(raw)}\0".encode() + raw).hexdigest()
    entries.close()


def test_generator_and_accepted_git_select_same_linear_head(tmp_path: Path) -> None:
    root, key = fixture_root(tmp_path)
    ga.generate(root, key, NOW)
    base = accept(root)
    ga.generate(root, key, NOW + timedelta(days=1))
    paths = verifier.append_paths(root, base)
    expected = discovery(root)["current_head"]
    # Exercise immutable-only acceptance with inherited projections.
    git(root, "restore", ".")
    git(root, "add", "--", *paths)
    git(root, "commit", "-m", "accept immutable append")
    assert discovery(root)["current_head"] == expected
    assert verifier.accepted_discovery(root, "HEAD")["current_head"] == expected
    verifier.verify_append(root, "HEAD")


def test_accepted_git_rejects_nonregular_unreferenced_evidence(tmp_path: Path) -> None:
    root, key = fixture_root(tmp_path)
    ga.generate(root, key, NOW)
    accept(root)
    (root / "attestations/unreferenced").symlink_to("chain-index.json")
    git(root, "add", "attestations/unreferenced")
    git(root, "commit", "-m", "invalid evidence fixture")
    with pytest.raises(ContractError, match="must be regular files"):
        verifier.accepted_discovery(root, "HEAD")


def test_signed_descendant_of_one_sibling_does_not_reconcile_fork(tmp_path: Path) -> None:
    root, key = fixture_root(tmp_path / "left")
    ga.generate(root, key, NOW)
    base = accept(root)
    right = tmp_path / "right"
    shutil.copytree(root, right)
    ga.generate(root, key, NOW + timedelta(days=1))
    ga.generate(right, right / key.name, NOW + timedelta(days=2))
    sibling = staged_bytes(right, base)
    accept(root)
    ga.generate(root, key, NOW + timedelta(days=3))
    accept(root)
    for path, raw in sibling.items():
        target = root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(raw)
    accept(root)
    with pytest.raises(ContractError, match="accepted parent"):
        discovery(root)
    with pytest.raises(ContractError, match="accepted parent"):
        verifier.accepted_discovery(root, "HEAD")


@pytest.mark.parametrize("mutation", ["edit", "delete"])
def test_streaming_verifier_preserves_raw_byte_immutability(
    tmp_path: Path, mutation: str,
) -> None:
    root, key = fixture_root(tmp_path)
    ga.generate(root, key, NOW)
    base = accept(root)
    document = discovery(root)
    target = root / document["heads"][document["current_head"]]
    if mutation == "edit":
        target.write_bytes(target.read_bytes() + b" ")
    else:
        target.unlink()
    # Accepted discovery must read Git, independently of the altered worktree.
    assert verifier.accepted_discovery(root, base)["current_head"] == document["current_head"]
    with pytest.raises(ValueError, match="immutable evidence changed or deleted"):
        verifier.verify_append(root, base)


def test_on_disk_fork_has_no_generator_or_accepted_head() -> None:
    revisions = ROOT / "attestations/2026-10-17/revisions"

    def revision_digests() -> dict[Path, str]:
        return {p: hashlib.sha256(p.read_bytes()).hexdigest()
                for sibling in SIBLINGS for p in (revisions / sibling).iterdir()}

    before = revision_digests()
    for sibling in SIBLINGS:
        reference = f"attestations/2026-10-17/revisions/{sibling}/chain_head.json"
        head = verify_set(ROOT, reference)
        assert head["chain_head"] == sibling
        assert head["payload"]["previous_chain_head"] == PARENT
    # The real differential: neither side returns a value, so no equality of
    # successful head selections may be asserted for this incident.
    with pytest.raises(ContractError, match="fork or disconnected accepted forward head") as generator:
        discovery(ROOT)
    with pytest.raises(ContractError, match="fork or disconnected accepted forward head") as accepted:
        verifier.accepted_discovery(ROOT, INCIDENT)
    assert str(generator.value) == str(accepted.value)
    assert f"accepted_parent={PARENT}" in str(accepted.value)
    assert all(sibling in str(accepted.value) for sibling in SIBLINGS)
    assert before == revision_digests()
    assert git(ROOT, "diff", INCIDENT, "--", "attestations") == ""
