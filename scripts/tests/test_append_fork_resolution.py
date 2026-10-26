#!/usr/bin/env python3
"""Ratify first-parent merge order without rewriting signed fork evidence."""
from __future__ import annotations

import hashlib
import shutil
from datetime import timedelta
from pathlib import Path

import pytest

from scripts import gen_attestations as ga
from scripts import verify_attestation_append as verifier
from scripts.attestation_sets import assert_head_extends_base, discovery, first_parent_order, verify_set
from scripts.tests.test_append_set_isolation import NOW, accept, git, staged_bytes
from scripts.tests.test_attestations import fixture_root, write
from scripts.verify_attestation_binding import ContractError

ROOT = Path(__file__).resolve().parents[2]
INCIDENT = "origin/main"
PARENT = "efdc505c7d31e8d07136194918bce1f6a8e4e8222037631f798cfa5c0330944f"
SIBLINGS = (
    "063aa71d64e2dd9f96ef85a7ee7cadcbf6248b27a4232ac031e0ba46b39f8423",
    "8730c6aa944bdb88fbe1b1fafe08549e9a8951f8754a0124450d923dd147d4cf",
)


def _disable_git(root: Path) -> None:
    git_dir = root / ".git"
    if git_dir.exists():
        git_dir.rename(root / ".git-disabled")


def test_disable_git_is_idempotent_and_leaves_no_git_directory(tmp_path: Path) -> None:
    root, _ = fixture_root(tmp_path)
    _disable_git(root)
    _disable_git(root)
    assert not (root / ".git").exists()


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


def merged_fork(tmp_path: Path, *, extension: str | None = None,
                tie: bool = False) -> tuple[Path, str, str, str]:
    """Merge immutable siblings; the earlier signed set enters main second."""
    root, key = fixture_root(tmp_path / "left")
    ga.generate(root, key, NOW)
    base = accept(root)
    right = tmp_path / "right"
    shutil.copytree(root, right)
    ga.generate(root, key, NOW + timedelta(days=2))
    winner = discovery(root)["current_head"]
    if extension == "accepted":
        ga.generate(root, key, NOW + timedelta(days=3))
    terminal = discovery(root)["current_head"]
    left_paths = staged_bytes(root, base)
    ga.generate(right, right / key.name, NOW + timedelta(days=1))
    loser = discovery(right)["current_head"]
    if extension == "rejected":
        ga.generate(right, right / key.name, NOW + timedelta(days=3))
    right_paths = staged_bytes(right, base)
    git(root, "restore", ".")
    git(root, "switch", "-c", "left")
    git(root, "add", "--", *left_paths)
    git(root, "commit", "-m", "left append")
    git(root, "switch", "-c", "right", base)
    for path, raw in right_paths.items():
        target = root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(raw)
    git(root, "add", "--", *right_paths)
    git(root, "commit", "-m", "right append")
    git(root, "switch", "main")
    if tie:
        git(root, "merge", "--no-ff", "-m", "both siblings", "left", "right")
    else:
        git(root, "merge", "--no-ff", "-m", "first accepted", "left")
        git(root, "merge", "--no-ff", "-m", "second accepted", "right")
    return root, winner, loser, terminal


@pytest.mark.parametrize("extension", [None, "accepted"])
def test_first_merged_child_and_accepted_extension_agree(
    tmp_path: Path, extension: str | None,
) -> None:
    root, winner, loser, terminal = merged_fork(tmp_path, extension=extension)
    for document in (discovery(root), verifier.accepted_discovery(root, "HEAD")):
        assert document["current_head"] == terminal
        assert document["rejected_heads"] == {loser: winner}
        assert loser not in document["heads"]
    verifier.verify_append(root, "HEAD")


@pytest.mark.parametrize("mutation", ("signature", "dataset", "scores"))
def test_rejected_sibling_integrity_is_still_checked(
    tmp_path: Path, mutation: str,
) -> None:
    root, _, loser, _ = merged_fork(tmp_path)
    directory = root / "attestations/2026-08-16/revisions" / loser
    filename = {"signature": "binding.json", "dataset": "sample.json",
                "scores": "scores.json"}[mutation]
    target = directory / filename
    document = ga.load(target)
    if mutation == "signature":
        document["signature_base64"] = "invalid"
        expected = "immutable binding signature is invalid"
    elif mutation == "dataset":
        document["chain_link"] = "0" * 64
        expected = "dataset attestation chain link is invalid"
    else:
        document["datasets"][0]["score"] = 0
        expected = "append content digest disagrees"
    write(target, document)
    with pytest.raises(ContractError, match=expected):
        discovery(root)


def test_extension_of_rejected_child_fails(tmp_path: Path) -> None:
    root, _, _, _ = merged_fork(tmp_path, extension="rejected")
    with pytest.raises(ContractError, match="fork or disconnected accepted forward head"):
        discovery(root)
    with pytest.raises(ContractError, match="fork or disconnected accepted forward head"):
        verifier.verify_append(root, "HEAD")


def test_generator_appends_to_accepted_child_after_reconciliation(tmp_path: Path) -> None:
    root, winner, loser, _ = merged_fork(tmp_path)
    base = git(root, "rev-parse", "HEAD")
    ga.generate(root, root / "private.json", NOW + timedelta(days=3))
    document = discovery(root)
    terminal = document["current_head"]
    assert document["envelopes"][terminal]["parent_head"] == winner
    assert document["rejected_heads"] == {loser: winner}
    paths = verifier.append_paths(root, base)
    assert any(path.endswith(f"/{terminal}/chain_head.json") for path in paths)
    assert not any(loser in path for path in paths)
    verifier.verify_append(root, base)


def test_checkpoint_recomputes_rejection_from_accepted_history(tmp_path: Path) -> None:
    root, winner, loser, _ = merged_fork(tmp_path)
    document = discovery(root)
    document.pop("rejected_heads")
    ga.dump(root / "attestations/chain-index.json", document)
    accept(root)
    for result in (discovery(root), verifier.accepted_discovery(root, "HEAD")):
        assert result["current_head"] == winner
        assert result["rejected_heads"] == {loser: winner}


def test_candidate_cannot_use_history_beyond_accepted_base(tmp_path: Path) -> None:
    root, _, _, _ = merged_fork(tmp_path)
    assert discovery(root)["current_head"]
    with pytest.raises(ContractError, match="fork or disconnected accepted forward head"):
        verifier.verify_append(root, "HEAD~1")
    with pytest.raises(ContractError, match="fork or disconnected accepted forward head"):
        discovery(root, fork_order={})


@pytest.mark.parametrize("unavailable", ["tie", "missing_merge", "shallow", "no_git"])
def test_undecidable_fork_fails_closed(tmp_path: Path, unavailable: str) -> None:
    root, _, _, _ = merged_fork(tmp_path, tie=unavailable == "tie")
    if unavailable == "missing_merge":
        git(root, "reset", "--soft", "HEAD~1")
        git(root, "commit", "-m", "direct introduction has no introducing merge")
    elif unavailable == "shallow":
        clone = tmp_path / "shallow"
        git(tmp_path, "clone", "--depth=1", root.as_uri(), str(clone))
        root = clone
    elif unavailable == "no_git":
        _disable_git(root)
    with pytest.raises(ContractError, match="fork or disconnected accepted forward head"):
        discovery(root)
    if unavailable != "no_git":
        with pytest.raises(ContractError, match="fork or disconnected accepted forward head"):
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


def test_on_disk_fork_selects_first_merged_child_without_evidence_changes() -> None:
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
    order = first_parent_order(ROOT, INCIDENT)
    refs = [f"attestations/2026-10-17/revisions/{sibling}/chain_head.json"
            for sibling in SIBLINGS]
    assert order[refs[1]] < order[refs[0]]
    generator = discovery(ROOT)
    accepted = verifier.accepted_discovery(ROOT, INCIDENT)
    for document in (generator, accepted):
        lineage = assert_head_extends_base(document, PARENT)
        assert SIBLINGS[1] in lineage
        assert SIBLINGS[0] not in lineage
        assert document["rejected_heads"].get(SIBLINGS[0]) == SIBLINGS[1]
        assert SIBLINGS[0] not in document["heads"]
    assert before == revision_digests()
    assert git(ROOT, "diff", INCIDENT, "--", *[
        f"attestations/2026-10-17/revisions/{sibling}" for sibling in SIBLINGS]) == ""
