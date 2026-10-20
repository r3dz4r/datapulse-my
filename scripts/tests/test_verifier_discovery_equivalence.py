#!/usr/bin/env python3
"""Compare accepted spine maps with full discovery, including real Git history."""
from __future__ import annotations

from datetime import timedelta
import json
from pathlib import Path, PurePosixPath
import shutil
import subprocess

import pytest

from scripts import gen_attestations as ga
from scripts import verify_attestation_append as verifier
from scripts.attestation_sets import discovery, first_parent_order
from scripts.tests.test_append_fork_resolution import merged_fork
from scripts.tests.test_append_set_isolation import NOW, accept, git
from scripts.tests.test_attestations import fixture_root, write
from scripts.verify_attestation_binding import ContractError

ROOT = Path(__file__).resolve().parents[2]
FIELDS = ("heads", "anchors", "envelopes", "days", "current_head",
          "migration_head", "unresolved_heads")


def maps(document: dict) -> str:
    return json.dumps({field: document.get(field) for field in FIELDS}, sort_keys=True)


def full_git_discovery(root: Path, revision: str) -> dict:
    with subprocess.Popen(["git", "cat-file", "--batch"], cwd=root,
                          stdin=subprocess.PIPE, stdout=subprocess.PIPE) as process:
        try:
            return discovery(verifier._GitPath(verifier._GitTree(root, revision, process)),
                             fork_order=first_parent_order(root, revision))
        finally:
            process.stdin.close()


@pytest.mark.parametrize("revision", ["HEAD", "origin/main"])
def test_real_history_maps_equal_full_discovery(revision: str) -> None:
    probe = subprocess.run(["git", "cat-file", "-e",
                            f"{revision}:attestations/chain-index.json"],
                           cwd=ROOT, capture_output=True)
    if probe.returncode:
        pytest.skip(f"real attestation history absent: {revision} lacks chain index")
    if git(ROOT, "rev-parse", "--is-shallow-repository") == "true":
        pytest.skip("real first-parent attestation history absent: shallow checkout")
    revision = git(ROOT, "rev-parse", "--verify", f"{revision}^{{commit}}")
    assert maps(verifier.accepted_discovery(ROOT, revision)) == maps(full_git_discovery(ROOT, revision))


@pytest.mark.parametrize("fork", [False, True])
def test_fixture_maps_equal_full_discovery(tmp_path: Path, fork: bool) -> None:
    if fork:
        root, _, _, _ = merged_fork(tmp_path)
    else:
        root, key = fixture_root(tmp_path)
        ga.generate(root, key, NOW)
        accept(root)
        ga.generate(root, key, NOW + timedelta(days=1))
        accept(root)
    assert maps(verifier.accepted_discovery(root, "HEAD")) == maps(full_git_discovery(root, "HEAD"))


def test_accepted_discovery_does_not_read_dataset_envelopes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    root, key = fixture_root(tmp_path)
    ga.generate(root, key, NOW)
    base = accept(root)
    read = verifier._GitTree.read

    def structural_only(tree: verifier._GitTree, path: PurePosixPath) -> bytes:
        assert path.name != "sample.json", "accepted discovery read a dataset envelope"
        return read(tree, path)

    monkeypatch.setattr(verifier._GitTree, "read", structural_only)
    assert verifier.accepted_discovery(root, base)["current_head"] == discovery(root)["current_head"]


@pytest.mark.parametrize("mutation,expected", [
    ("envelope-delete", "immutable evidence changed or deleted"),
    ("day-remove", "repeated or unresolved|day lists and descriptors|unresolved head mappings|invalid day list"),
    ("anchor-change", "accepted anchors entry replaced or deleted"),
    ("parent", "candidate does not append to accepted parent"),
    ("sibling", "candidate contains a sibling or unaccepted head|candidate does not append to accepted parent"),
    ("evidence-bytes", "immutable evidence changed or deleted"),
    ("migration", "historical migration boundary changed"),
    ("nonregular", "must be regular files"),
])
def test_refusals_survive_spine_derivation(tmp_path: Path, mutation: str, expected: str) -> None:
    root, key = fixture_root(tmp_path / "candidate")
    ga.generate(root, key, NOW)
    initial = discovery(root)
    # Pin a real migration boundary and anchor in the accepted checkpoint.
    initial["migration_head"] = initial["current_head"]
    initial["unresolved_heads"] = []
    initial["anchors"] = {initial["current_head"]: {"tag": "v1", "commit": "a" * 40}}
    write(root / "attestations/chain-index.json", initial)
    base = accept(root)
    reference = initial["heads"][initial["current_head"]]
    if mutation == "envelope-delete":
        (root / reference).unlink()
    elif mutation == "evidence-bytes":
        path = root / Path(reference).parent / "sample.json"
        path.write_bytes(path.read_bytes() + b" ")
    elif mutation == "nonregular":
        (root / "attestations/nonregular").symlink_to("chain-index.json")
        git(root, "add", "attestations/nonregular")
        git(root, "commit", "-m", "invalid accepted entry")
        base = "HEAD"
    elif mutation in {"day-remove", "anchor-change", "migration"}:
        changed = json.loads(json.dumps(initial))
        if mutation == "day-remove":
            changed["days"][NOW.date().isoformat()] = []
        elif mutation == "anchor-change":
            changed["anchors"][initial["current_head"]]["commit"] = "b" * 40
        else:
            changed.pop("migration_head")
        write(root / "attestations/chain-index.json", changed)
    else:
        fork = tmp_path / "fork"
        shutil.copytree(root, fork)
        ga.generate(root, key, NOW + timedelta(days=1))
        if mutation == "parent":
            base = accept(root)
        ga.generate(fork, fork / key.name, NOW + timedelta(days=2))
        source = fork / "attestations/2026-08-17"
        shutil.copytree(source, root / source.relative_to(fork))
    with pytest.raises((ValueError, ContractError), match=expected):
        verifier.verify_append(root, base)


@pytest.mark.parametrize("filename", ["chain_head.json", "index.json", "sample.json"])
def test_missing_accepted_revision_evidence_is_refused(tmp_path: Path, filename: str) -> None:
    root, key = fixture_root(tmp_path)
    ga.generate(root, key, NOW)
    accept(root)
    ga.generate(root, key, NOW + timedelta(days=1))
    document = discovery(root)
    reference = document["heads"][document["current_head"]]
    accept(root)
    git(root, "rm", str(Path(reference).parent / filename))
    git(root, "commit", "-m", "delete accepted revision evidence")
    with pytest.raises(ContractError, match="missing|unreadable|invalid"):
        verifier.accepted_discovery(root, "HEAD")


@pytest.mark.parametrize("legacy", [False, True])
def test_same_day_and_legacy_maps_equal_full_discovery(tmp_path: Path, legacy: bool) -> None:
    root, key = fixture_root(tmp_path)
    ga.generate(root, key, NOW)
    if legacy:
        checkpoint = ga.load(root / "attestations/chain-index.json")
        checkpoint["schema"] = "datapulse/v1/chain-index"
        for field in ("envelopes", "days", "current_head"):
            checkpoint.pop(field, None)
        write(root / "attestations/chain-index.json", checkpoint)
    else:
        accept(root)
        ga.generate(root, key, NOW + timedelta(hours=1), force_append=True)
    accept(root)
    assert maps(verifier.accepted_discovery(root, "HEAD")) == maps(full_git_discovery(root, "HEAD"))


@pytest.mark.parametrize("authorization", ["compromised", "wrong-purpose", "expired"])
def test_accepted_signer_authority_cannot_be_replaced_by_checkout(
    tmp_path: Path, authorization: str,
) -> None:
    root, key = fixture_root(tmp_path)
    ga.generate(root, key, NOW)
    registry_path = root / "docs/.well-known/datapulse-probe-keys.json"
    trusted_bytes = registry_path.read_bytes()
    registry = ga.load(registry_path)
    row = registry["keys"][0]
    if authorization == "compromised":
        row["status"] = "compromised"
    elif authorization == "wrong-purpose":
        row["purpose"] = "unrelated"
    else:
        row["not_after"] = "2026-01-02T00:00:00Z"
    write(registry_path, registry)
    base = accept(root)
    registry_path.write_bytes(trusted_bytes)
    with pytest.raises(ContractError, match="historical signer is unauthorized"):
        verifier.verify_append(root, base)
