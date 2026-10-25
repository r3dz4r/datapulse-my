#!/usr/bin/env python3
"""Check evidence immutability and signed-parent CAS against an accepted Git base."""
from __future__ import annotations

import argparse
import base64
from collections.abc import Iterator
from datetime import date
import fnmatch
import hashlib
import json
import logging
import os
from pathlib import Path, PurePosixPath
import subprocess
import sys
import time

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.attestation_fetch_refs import SNAPSHOT_FILES
from scripts.attestation_sets import (
    FILES,
    SET_REF,
    assert_head_extends_base,
    correction_record,
    descriptor,
    discovery,
    external_rekor_paths,
    first_parent_order,
    set_directory,
    verify_legacy_mirror,
    verify_set,
    selected_directory,
)
from scripts.verify_attestation_binding import (
    ContractError, _load, _parse_time, _verify_legacy_plane, _verify_signature,
)

PROJECTIONS = {
    "attestations/chain-index.json",
    "attestations/latest/index.json",
    "attestations/latest/chain_head.json",
    ".attestations/chain_head.json",
}
logger = logging.getLogger(__name__)


class AcceptancePending(ValueError):
    """Valid candidate has not yet appeared in authoritative Git."""


def wait_for_acceptance(root: Path, source: str, timeout: int, poll_seconds: int = 15) -> None:
    """Keep the sign-time tree frozen until its exact evidence is accepted on main.

    Submission creates a local commit, so HEAD is no longer an acceptance
    authority. Only a freshly fetched main containing the original source can
    accept this candidate. Never check out newer health or regenerate its head.
    """
    if timeout < 0 or poll_seconds <= 0:
        raise ValueError("acceptance timeout must be nonnegative and poll interval positive")
    source = subprocess.run(["git", "rev-parse", "--verify", f"{source}^{{commit}}"],
                            cwd=root, check=True, capture_output=True, text=True).stdout.strip()
    verify_append(root, source)
    directory = selected_directory(root)
    candidate_path = directory + "/chain_head.json"
    candidate_bytes = (root / candidate_path).read_bytes()
    deadline = time.monotonic() + timeout
    while True:
        try:
            subprocess.run(["git", "fetch", "origin", "refs/heads/main:refs/remotes/origin/main"],
                           cwd=root, check=True, capture_output=True, timeout=30)
        except subprocess.TimeoutExpired as error:
            raise AcceptancePending("append-deferred: authoritative Git fetch timed out") from error
        accepted = subprocess.run(["git", "rev-parse", "refs/remotes/origin/main"],
                                  cwd=root, check=True, capture_output=True, text=True).stdout.strip()
        subprocess.run(["git", "merge-base", "--is-ancestor", source, accepted],
                       cwd=root, check=True, capture_output=True)
        # Avoid re-verifying the full historical ledger on every pending probe.
        probe = subprocess.run(["git", "cat-file", "-e", f"{accepted}:{candidate_path}"],
                               cwd=root, capture_output=True)
        if probe.returncode == 0:
            if git_bytes(root, accepted, candidate_path) != candidate_bytes:
                raise ValueError("authoritative candidate head bytes disagree")
            # Presence, PR state and a local submission commit are insufficient:
            # verify all accepted immutable bytes, lineage and current projections.
            verify_append(root, accepted, require_committed=True)
            return
        if probe.returncode not in {1, 128}:
            probe.check_returncode()
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise AcceptancePending("append-deferred: candidate must be accepted in authoritative Git before publication; acceptance wait timed out")
        time.sleep(min(poll_seconds, remaining))


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


def _tree_entries(root: Path, *args: str) -> Iterator[tuple[str, str, str, str]]:
    """Stream NUL-delimited tree metadata, retaining at most one pipe chunk."""
    command = ["git", "ls-tree", "-z", *args]
    with subprocess.Popen(command, cwd=root, stdout=subprocess.PIPE) as process:
        pending = b""
        try:
            while chunk := process.stdout.read(65536):
                entries = (pending + chunk).split(b"\0")
                pending = entries.pop()
                for entry in entries:
                    metadata, path = entry.split(b"\t", 1)
                    mode, kind, digest = metadata.decode("ascii").split()
                    yield mode, kind, digest, path.decode("utf-8")
            if pending:
                raise ContractError("accepted Git tree entry is incomplete")
            if process.wait():
                raise subprocess.CalledProcessError(process.returncode, command)
        finally:
            # Closing a partially consumed iterator must not leave ls-tree
            # blocked on a full pipe (including on a validation failure).
            if process.poll() is None:
                process.terminate()


def accepted_files(root: Path, revision: str) -> Iterator[tuple[str, str]]:
    """Yield accepted paths and Git object IDs, never all historical blob bytes."""
    for mode, kind, digest, path in _tree_entries(
            root, "-r", revision, "--", "attestations",
            "docs/.well-known/datapulse-probe-keys.json"):
        if kind != "blob" or mode not in {"100644", "100755"}:
            raise ContractError("accepted attestation evidence must be regular files")
        yield path, digest


class _GitPath:
    """Read-only subset of Path used by discovery, backed by one Git tree.

    Blob requests are synchronous: cat-file never queues the whole ledger.
    Only the most recently listed directory is retained, not a file inventory.
    """

    def __init__(self, tree: _GitTree, path: PurePosixPath = PurePosixPath(".")) -> None:
        self.tree, self.path = tree, path

    def __truediv__(self, path: str) -> _GitPath:
        relative = PurePosixPath(path)
        if relative.is_absolute() or ".." in relative.parts or "\n" in path or "\r" in path:
            raise ContractError("unsafe accepted Git path")
        return _GitPath(self.tree, self.path / relative)

    def __lt__(self, other: _GitPath) -> bool:
        return self.path < other.path

    @property
    def name(self) -> str:
        return self.path.name

    def relative_to(self, root: _GitPath) -> PurePosixPath:
        return self.path.relative_to(root.path)

    def read_bytes(self) -> bytes:
        return self.tree.read(self.path)

    def read_text(self, encoding: str = "utf-8") -> str:
        return self.read_bytes().decode(encoding)

    def is_file(self) -> bool:
        return self.tree.entries(self.path.parent).get(self.name) == "blob"

    def is_dir(self) -> bool:
        return self.path == PurePosixPath(".") or self.tree.entries(self.path.parent).get(self.name) == "tree"

    def exists(self) -> bool:
        return self.is_file() or self.is_dir()

    def iterdir(self) -> Iterator[_GitPath]:
        for name in self.tree.entries(self.path):
            yield self / name

    def glob(self, pattern: str) -> Iterator[_GitPath]:
        first, separator, rest = pattern.partition("/")
        for child in self.iterdir():
            if fnmatch.fnmatchcase(child.name, first):
                if not separator:
                    yield child
                elif child.is_dir():
                    yield from child.glob(rest)


class _GitTree:
    """Bounded directory metadata and per-blob access for the signed verifier."""

    def __init__(self, root: Path, revision: str, process: subprocess.Popen) -> None:
        self.root, self.revision, self.process = root, revision, process
        self.cached_path: PurePosixPath | None = None
        self.cached_entries: dict[str, str] = {}

    def entries(self, path: PurePosixPath) -> dict[str, str]:
        if self.cached_path != path:
            if path != PurePosixPath(".") and self.entries(path.parent).get(path.name) != "tree":
                return {}
            tree = self.revision if path == PurePosixPath(".") else f"{self.revision}:{path}"
            entries = {}
            for _, kind, _, name in _tree_entries(self.root, tree):
                entries[name] = kind
            self.cached_path, self.cached_entries = path, entries
        return self.cached_entries

    def read(self, path: PurePosixPath) -> bytes:
        self.process.stdin.write(f"{self.revision}:{path}\n".encode("utf-8"))
        self.process.stdin.flush()
        header = self.process.stdout.readline().split()
        if len(header) == 2 and header[1] == b"missing":
            raise FileNotFoundError(str(path))
        if len(header) != 3 or header[1] != b"blob":
            raise ContractError("accepted Git blob is missing or invalid")
        size = int(header[2])
        data = self.process.stdout.read(size)
        if len(data) != size or self.process.stdout.read(1) != b"\n":
            raise ContractError("accepted Git blob bytes are incomplete")
        return data


def _spine_discovery(root: _GitPath | Path, references: set[str], order: dict[str, int],
                     *, delta: set[str] | None = None) -> dict:
    """Derive maps from the signed spine, fully verifying only delta sets.

    With no delta this reads an accepted Git tree. In a checkout, the caller
    must first protect accepted bytes with the Git-level immutable-file check.
    """
    checkpoint = "attestations/chain-index.json"
    document = (_load(root / checkpoint, "chain index") if checkpoint in references else
                {"schema": "datapulse/v2/chain-index", "heads": {}, "anchors": {},
                 "envelopes": {}, "days": {}, "current_head": None})
    if document.get("schema") == "datapulse/v1/chain-index":
        # The legacy migration resolves gaps by verifying sets, not by following
        # parents. Keep that one-time path until a v2 boundary has been pinned.
        return discovery(root, fork_order=order)
    if document.get("schema") != "datapulse/v2/chain-index":
        raise ContractError("unknown chain index schema")
    heads = document.get("heads")
    if not isinstance(heads, dict) or len(set(heads.values())) != len(heads):
        raise ContractError("duplicate or invalid chain head mapping")
    registry = None
    verified = {}
    bindings = {}

    def head_at(reference: str) -> dict:
        nonlocal registry
        if reference in verified:
            return verified[reference]
        directory = set_directory(reference)
        if delta is not None and reference in delta:
            verified[reference] = verify_set(root, reference)
            bindings[reference] = _load(root / directory / "binding.json", "immutable binding")["payload"]
            return verified[reference]
        head = _load(root / reference, "immutable chain head")
        index = _load(root / directory / "index.json", "immutable index")
        binding = _load(root / directory / "binding.json", "immutable binding")
        payload = binding.get("payload", {})
        if delta is not None:
            bindings[reference] = payload
        if registry is None:
            registry = _load(root / "docs/.well-known/datapulse-probe-keys.json", "key registry")
        matches = [row for row in registry.get("keys", [])
                   if row.get("key_id") == payload.get("ed25519", {}).get("key_id")]
        if registry.get("schema") != "datapulse/v2/probe-key-registry" or len(matches) != 1:
            raise ContractError("historical attestation key missing or ambiguous")
        row = matches[0]
        published = _parse_time(payload.get("published_at"), "publication time")
        if (row.get("purpose") != "attestation-chain-signing" or row.get("status") == "compromised"
                or row.get("compromised_at") or not (
                    _parse_time(row.get("not_before"), "key start") <= published
                    <= _parse_time(row.get("not_after"), "key end"))):
            raise ContractError("historical signer is unauthorized")
        public = Ed25519PublicKey.from_public_bytes(base64.b64decode(row["public_key_base64"], validate=True))
        _verify_signature(public, payload, binding.get("signature_base64"), "immutable binding")
        _verify_legacy_plane(root, index, head, public, row, verify_datasets=False)
        if (binding.get("schema") != "datapulse/v1/attestation-binding-envelope"
                or payload.get("schema") != "datapulse/v1/attestation-binding"
                or payload.get("date") != head["payload"]["date"]
                or payload.get("ed25519", {}).get("chain_head_ref") != reference
                or payload.get("ed25519", {}).get("chain_head") != head["chain_head"]
                or index.get("binding_ref") != directory + "/binding.json"):
            raise ContractError("immutable binding/index/head disagree")
        match = SET_REF.fullmatch(reference)
        if match[1] != head["payload"]["date"] or (match[2] and match[2] != head["chain_head"]):
            raise ContractError("immutable head path identity mismatch")
        # Accepted evidence bytes are protected by verify_append's Git-level
        # immutable-file check; delta sets take the full verify_set path above.
        # Only the spine and day indexes are needed to derive accepted structure.
        # Membership checks use tree metadata, never one cat-file read per dataset.
        for did, ref in index["attestations"].items():
            if ref != directory + "/" + did + ".json":
                raise ContractError("dataset attestation reference is invalid")
            if ref not in references:
                raise ContractError(f"dataset attestation {did} is missing")
        for filename in FILES:
            if directory + "/" + filename not in references:
                raise ContractError("immutable set evidence is missing")
        verified[reference] = head
        return head

    def validate() -> None:
        envelopes, days = document.get("envelopes", {}), document.get("days", {})
        seen = set()
        for day, run in days.items():
            date.fromisoformat(day)
            if not isinstance(run, list) or not run:
                raise ContractError("invalid day list")
            for sequence, digest in enumerate(run, 1):
                if digest in seen or digest not in envelopes or digest not in heads:
                    raise ContractError("repeated or unresolved discovery head")
                seen.add(digest)
                head = head_at(heads[digest])
                if (head["chain_head"] != digest or head["payload"]["date"] != day
                        or envelopes[digest] != descriptor(head, heads[digest], sequence)):
                    raise ContractError("discovery descriptor disagrees with signed set")
                if sequence > 1 and head["payload"]["previous_chain_head"] != run[sequence - 2]:
                    raise ContractError("same-day fork or missing parent")
                if delta is not None:
                    # Correction provenance is spine data too. Recheck every
                    # day run using already read bindings, including history.
                    payload = bindings[heads[digest]]
                    record = payload.get("correction")
                    if sequence == 1:
                        if record is not None:
                            raise ContractError("original attestation cannot be a correction")
                    else:
                        previous = bindings[heads[run[sequence - 2]]]
                        expected = correction_record(day, run[0], run[sequence - 2],
                                                     previous["health"]["artifact_sha256"],
                                                     payload["health"]["artifact_sha256"])
                        if isinstance(record, dict) and record.get("health_snapshot_ref") == expected["health_snapshot_ref"].removesuffix(".gz"):
                            expected["health_snapshot_ref"] = expected["health_snapshot_ref"].removesuffix(".gz")
                        if record != expected or head["payload"].get("correction") != record:
                            raise ContractError("signed correction provenance disagrees with the append lineage")
        if set(heads) - seen != set(document.get("unresolved_heads", [])):
            raise ContractError("unresolved head mappings changed without reconciliation")
        if seen != set(envelopes):
            raise ContractError("day lists and descriptors disagree")
        current = document.get("current_head")
        if not seen and current is None:
            return
        if current not in seen or current != days[max(days)][-1]:
            raise ContractError("current selector is not the terminal accepted head")
        boundary = document.get("migration_head")
        # Follow signed parents backwards to the migration/fork boundary. Older
        # disconnected history remains pinned by the checkpoint's day indexes.
        visited = assert_head_extends_base(document, boundary)
        forward = {h for h, entry in envelopes.items()
                   if boundary is None or entry["date"] >= envelopes[boundary]["date"]}
        if forward != visited | ({boundary} if boundary else set()):
            raise ContractError("fork or disconnected accepted forward head")

    validate()
    pending = {}
    for reference in sorted(references):
        match = SET_REF.fullmatch(reference)
        if delta is not None and match is None and reference.endswith("/chain_head.json"):
            parts = PurePosixPath(reference).parts
            if len(parts) == 5 and parts[2] == "revisions":
                # Full discovery's glob also sees malformed date/hash names.
                # Do not let filtering by SET_REF hide a broken candidate.
                raw = _load(root / reference, "append head")
                if "append_content_sha256" in raw.get("payload", {}):
                    raise ContractError("unsafe immutable attestation reference")
        if match is None or match[2] is None or match[3] != "chain_head":
            continue
        raw = _load(root / reference, "append head")
        if "append_content_sha256" not in raw.get("payload", {}):
            continue
        if delta is not None and reference in delta:
            head_at(reference)  # Aliases and rejected siblings need full verification too.
        digest = raw["chain_head"]
        if digest in heads:
            if heads[digest] not in {reference, f"attestations/{raw['payload']['date']}/chain_head.json"}:
                raise ContractError("duplicate append head identity")
        else:
            pending[digest] = (reference, head_at(reference))
    document.pop("rejected_heads", None)
    rejected = {}

    def select(children: list[tuple[str, str]]) -> tuple[str, str] | None:
        if len(children) == 1:
            return children[0]
        ranks = [order.get(reference) for _, reference in children]
        if not children or None in ranks or len(set(ranks)) != len(ranks):
            return None
        return min(children, key=lambda child: order[child[1]])

    def refuse() -> None:
        predecessors = {digest: head["payload"]["previous_chain_head"]
                        for digest, (_, head) in sorted(pending.items())}
        raise ContractError(
            "fork or disconnected accepted forward head: candidate does not append to accepted parent; "
            f"accepted_parent={document['current_head'] or '0' * 64}; "
            f"pending_parents={json.dumps(predecessors, sort_keys=True)}")

    for accepted, entry in document["envelopes"].items():
        siblings = [(digest, reference) for digest, (reference, head) in pending.items()
                    if head["payload"]["previous_chain_head"] == entry["parent_head"]]
        if siblings:
            selected = select(siblings + [(accepted, heads[accepted])])
            if selected is None or selected[0] != accepted:
                refuse()
            for digest, _ in siblings:
                rejected[digest] = accepted
                del pending[digest]
    while pending:
        parent = document["current_head"] or "0" * 64
        children = [(digest, reference) for digest, (reference, head) in pending.items()
                    if head["payload"]["previous_chain_head"] == parent]
        selected = select(children)
        if selected is None:
            refuse()
        digest, reference = selected
        for sibling, _ in children:
            if sibling != digest:
                rejected[sibling] = digest
                del pending[sibling]
        head = pending[digest][1]
        run = document["days"].setdefault(head["payload"]["date"], [])
        heads[digest] = reference
        document["envelopes"][digest] = descriptor(head, reference, len(run) + 1)
        run.append(digest)
        document["current_head"] = digest
        del pending[digest]
    validate()
    if rejected:
        document["rejected_heads"] = dict(sorted(rejected.items()))
    return document


def accepted_discovery(root: Path, revision: str) -> dict:
    """Derive accepted structure directly from Git without exporting the ledger."""
    revision = subprocess.run(["git", "rev-parse", "--verify", f"{revision}^{{commit}}"],
                              cwd=root, check=True, capture_output=True, text=True).stdout.strip()
    order = first_parent_order(root, revision)
    # Preserve the original rejection of nonregular evidence, including files
    # not referenced by a signed set. This scans metadata only.
    references = {path for path, _ in accepted_files(root, revision)}
    with subprocess.Popen(["git", "cat-file", "--batch"], cwd=root,
                          stdin=subprocess.PIPE, stdout=subprocess.PIPE) as process:
        try:
            document = _spine_discovery(_GitPath(_GitTree(root, revision, process)), references, order)
        except BaseException:
            # An invalid object header can leave unread output in the pipe.
            # Do not wait for a writer blocked on that output after rejection.
            process.terminate()
            process.wait()
            raise
        finally:
            process.stdin.close()
        if process.wait():
            raise subprocess.CalledProcessError(process.returncode, process.args)
        return document


def _file_object_id(path: Path, algorithm: str) -> str:
    """Hash exact on-disk bytes as a Git blob, including its length header."""
    digest = hashlib.new(algorithm)
    with path.open("rb") as source:
        size = os.fstat(source.fileno()).st_size
        digest.update(f"blob {size}\0".encode("ascii"))
        while chunk := source.read(65536):
            digest.update(chunk)
    return digest.hexdigest()


def append_paths(root: Path, base: str) -> list[str]:
    """Return only immutable files belonging to new, verified append sets."""
    return _verified_append_paths(root, base, check_delta_index=False)


def _candidate_discovery(root: Path, base: str, accepted_references: set[str]) -> dict:
    """Read the checkout's spine and delta; accepted payload bytes stay in Git.

    Include ignored and untracked paths: a new set or an unexpected addition to
    an accepted set must not escape validation by staying out of the index.
    """
    listed = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--directory", "-z", "--", "attestations"],
        cwd=root, check=True, capture_output=True).stdout
    references = set()
    for raw_path in listed.split(b"\0"):
        if not raw_path:
            continue
        path = os.fsdecode(raw_path)
        references.add(path.rstrip("/"))
        if path.endswith("/"):
            # Git collapses new directories, including empty ones. Walk only
            # these delta directories; never recurse through tracked history.
            for directory, subdirs, files in os.walk(root / path):
                references.update((Path(directory) / name).relative_to(root).as_posix()
                                  for name in subdirs + files)
    additions = references - accepted_references
    for path in additions:
        target = root / path
        if target.is_symlink() or not (target.is_file() or target.is_dir()):
            raise ContractError("candidate attestation evidence must be regular files")
    # An addition to a closed historical set also requires full validation,
    # including its exact directory membership. New revisions under a legacy
    # date alias are independent sets rather than changes to that alias.
    directories = set()
    for path in additions:
        parts = PurePosixPath(path).parts
        if len(parts) >= 3:
            if parts[2] == "revisions":
                if len(parts) >= 5:
                    directories.add("/".join(parts[:4]))
            else:
                directories.add("/".join(parts[:2]))
    delta = {reference for reference in references
             if (match := SET_REF.fullmatch(reference)) is not None
             and match[3] == "chain_head" and set_directory(reference) in directories}
    return _spine_discovery(root, references, first_parent_order(root, base), delta=delta)


def _append_paths(root: Path, old: dict, new: dict) -> list[str]:
    paths = set()
    for digest in set(new["heads"]) - set(old["heads"]):
        directory = set_directory(new["heads"][digest])
        revision = root / directory / "revisions" / digest / "chain_head.json"
        if revision.is_file():
            directory = revision.parent.relative_to(root).as_posix()
        head = _load(root / new["heads"][digest], "append head")
        if "append_content_sha256" not in head["payload"]:
            raise ContractError("append submission requires a content-addressed set")
        paths.update(p.relative_to(root).as_posix() for p in (root / directory).iterdir() if p.is_file())
        # This branch stores the snapshot compressed and keeps the plain name
        # only as a legacy alias. Enumerate whichever encoding this set carries
        # so the preserved copy is submitted, mirroring the served-plane refs.
        paths.update(directory + "/" + name for name in SNAPSHOT_FILES
                     if (root / directory / name).is_file())
        binding = _load(root / directory / "binding.json", "append binding")
        external_rekor = external_rekor_paths(binding.get("rekor"), head["payload"]["date"])
        if external_rekor is not None:
            paths.update(external_rekor)
        record = binding["payload"].get("correction")
        if record is not None:
            paths.add(record["health_snapshot_ref"])
    return sorted(paths)


def _checkout_changes(root: Path, base: str) -> tuple[set[str], dict[str, str]]:
    """Use Git's stat cache without refreshing away raw-byte differences.

    Unlike porcelain diff, diff-index's raw output retains stat-dirty paths
    even when a clean filter would normalize their bytes back to the base.
    Explicitly inspect index flags too: sparse/assume-unchanged entries must
    never exempt accepted evidence from verification.
    """
    command = ["git", "-c", "core.fsmonitor=false", "-c", "core.ignorestat=false",
               "-c", "core.trustctime=true", "-c", "core.checkstat=default"]
    changed = subprocess.run(
        [*command, "diff-index", "--name-only", "-z", "--no-renames",
         "--ignore-submodules=none", base, "--", "attestations"],
        cwd=root, check=True, capture_output=True).stdout
    paths = {os.fsdecode(path) for path in changed.split(b"\0") if path}
    entries = subprocess.run(
        ["git", "ls-files", "-v", "--stage", "-z", "--", "attestations"],
        cwd=root, check=True, capture_output=True).stdout
    indexed = {}
    for entry in entries.split(b"\0"):
        if not entry:
            continue
        metadata, raw_path = entry.split(b"\t", 1)
        flag, mode, digest, stage = metadata.split()
        path = os.fsdecode(raw_path)
        if flag != b"H" or stage != b"0" or mode not in {b"100644", b"100755"}:
            paths.add(path)
        indexed[path] = digest.decode("ascii")
    return paths, indexed


def _evidence_paths_changed(root: Path, base: str) -> bool:
    """Treat an unreadable base diff as evidence-bearing, never as an exemption."""
    commands = (
        ["git", "diff", "--no-ext-diff", "--no-textconv", "--no-renames",
         "--ignore-submodules=none", "--name-only", "-z", base, "--", "attestations", ".attestations"],
        ["git", "ls-files", "--others", "--exclude-standard", "-z", "--", "attestations", ".attestations"],
        ["git", "ls-files", "--others", "--ignored", "--exclude-standard", "-z", "--",
         "attestations", ".attestations"],
    )
    try:
        for command in commands:
            output = subprocess.run(command, cwd=root, check=True, capture_output=True).stdout
            if any(os.fsdecode(path) not in PROJECTIONS for path in output.split(b"\0") if path):
                return True
    except (OSError, subprocess.SubprocessError):
        return True
    return False


def _accepted_object_sizes(root: Path, indexed: dict[str, str]) -> dict[str, int]:
    """Read blob headers only; normalized index bytes may differ in size on disk."""
    digests = sorted(set(indexed.values()))
    result = subprocess.run(
        ["git", "cat-file", "--batch-check=%(objectname) %(objectsize)"],
        input="".join(digest + "\n" for digest in digests), cwd=root,
        check=True, capture_output=True, text=True)
    return {digest: int(size) for digest, size in (line.split() for line in result.stdout.splitlines())}


def _filtered_paths(root: Path, indexed: dict[str, str]) -> set[str]:
    """Arbitrary clean filters/encodings can change bytes without changing size."""
    result = subprocess.run(
        ["git", "check-attr", "-z", "--stdin", "filter", "working-tree-encoding", "ident"],
        input=b"".join(os.fsencode(path) + b"\0" for path in indexed),
        cwd=root, check=True, capture_output=True).stdout.split(b"\0")
    return {os.fsdecode(result[i]) for i in range(0, len(result) - 1, 3)
            if result[i + 2] not in {b"unspecified", b"unset"}}


def verify_append(root: Path, base: str, require_committed: bool = False) -> None:
    """Reject rewritten ledger bytes, remaps, lost entries, forks and stale parents."""
    _verified_append_paths(root, base, require_committed)


def _verified_append_paths(root: Path, base: str, require_committed: bool = False,
                           *, check_delta_index: bool = True) -> list[str]:
    algorithm = subprocess.run(["git", "rev-parse", "--show-object-format"], cwd=root,
                               check=True, capture_output=True, text=True).stdout.strip()
    changed, indexed = _checkout_changes(root, base)
    changed.update(_filtered_paths(root, indexed))
    sizes = _accepted_object_sizes(root, indexed)
    accepted_references = set()
    for path, digest in accepted_files(root, base):
        accepted_references.add(path)
        if not path.startswith("attestations/") or path in PROJECTIONS or path.startswith("attestations/latest/"):
            continue
        target = root / path
        if target.is_symlink() or not target.is_file():
            raise ValueError(f"immutable evidence changed or deleted: {path}")
        # Even a stat-clean index can contain normalized LF while the checkout
        # contains CRLF. Size catches that case without reading historical bytes.
        needs_hash = (path in changed or indexed.get(path) != digest
                      or target.stat().st_size != sizes[digest])
        if needs_hash and _file_object_id(target, algorithm) != digest:
            raise ValueError(f"immutable evidence changed or deleted: {path}")
    old = accepted_discovery(root, base)
    new = _candidate_discovery(root, base, accepted_references)
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
    parent = old.get("current_head")
    cursor, seen = new["current_head"], set()
    while cursor != parent:
        if cursor in seen or cursor in old["heads"] or cursor not in new["envelopes"]:
            raise ValueError("candidate does not append to accepted parent")
        seen.add(cursor)
        cursor = new["envelopes"][cursor]["parent_head"]
        if cursor == "0" * 64 and parent is None:
            cursor = None
    if set(new["heads"]) - set(old["heads"]) != seen:
        raise ValueError("candidate contains a sibling or unaccepted head")
    # Check staged candidate bytes before projection comparisons so tampering
    # is reported as immutable evidence failure, even when it also breaks a
    # projection that includes the same file.
    paths = _append_paths(root, old, new)
    if check_delta_index:
        for path in paths:
            digest = _file_object_id(root / path, algorithm)
            if path in indexed and digest != indexed[path]:
                raise ValueError(f"immutable evidence changed or deleted: {path}")
    head = _load(root / new["heads"][new["current_head"]], "current head")
    projection_matches_current = False
    if "append_content_sha256" not in head["payload"]:
        selected_directory(root)
        projection_matches_current = True
    else:
        projection = root / "attestations/latest/chain_head.json"
        projection_only = not _evidence_paths_changed(root, base)
        inherited_projections = False
        if not projection_only:
            # An immutable-only submission carries the accepted base's exact
            # projections; changed projections belong to the candidate head.
            inherited_paths = ("attestations/chain-index.json", ".attestations/chain_head.json",
                               *("attestations/latest/" + filename for filename in FILES))
            try:
                inherited_projections = all(
                    (root / path).is_file() and (root / path).read_bytes() == git_bytes(root, base, path)
                    for path in inherited_paths
                )
            except subprocess.CalledProcessError:
                inherited_projections = False
        if not projection_only and not inherited_projections:
            # Evidence-bearing candidates must project their own signed head.
            candidate_directory = accepted_day_directory(root, new)
            candidate_revision = root / candidate_directory / "revisions" / new["current_head"] / "chain_head.json"
            if candidate_revision.is_file():
                candidate_directory = candidate_revision.parent.relative_to(root).as_posix()
            if not (root / candidate_directory).is_dir():
                raise ContractError("latest projection is stale or mixed")
            for filename in FILES:
                latest = root / "attestations/latest" / filename
                frozen = root / candidate_directory / filename
                if not latest.is_file() or not frozen.is_file():
                    raise ContractError("latest projection is stale or mixed")
                if latest.read_bytes() != frozen.read_bytes():
                    raise ContractError("latest projection is stale or mixed")
            verify_legacy_mirror(root, new, candidate_directory)
            projection_matches_current = True
            logger.warning("append judged against its own head")
        elif projection.exists():
            # An evidence-free refresh may project an accepted head that is
            # absent from this tree; an immutable-only submission may carry
            # the exact base projections while awaiting publication.
            projected = _load(projection, "projected head")["chain_head"]
            if inherited_projections and projected not in new["envelopes"]:
                raise ContractError("latest projection is stale or mixed")
            base_projected = json.loads(git_bytes(root, base, "attestations/latest/chain_head.json"))["chain_head"]
            if projected in new["envelopes"]:
                try:
                    assert_head_extends_base({**new, "current_head": projected}, base_projected)
                except ContractError as error:
                    raise ContractError("latest projection is stale or mixed") from error
            if projected not in new["envelopes"]:
                # This head may already be accepted on main but absent from a
                # projection-only PR tree. The mirror must still agree locally.
                verify_legacy_mirror(root, new, "attestations/latest")
            else:
                projected_document = {**new, "current_head": projected}
                projected_directory = accepted_day_directory(root, projected_document)
                projected_revision = root / projected_directory / "revisions" / projected / "chain_head.json"
                if projected_revision.is_file():
                    projected_directory = projected_revision.parent.relative_to(root).as_posix()
                verify_legacy_mirror(root, projected_document, projected_directory)
                projection_matches_current = projected == new["current_head"]
                # An evidence-free refresh can inherit stale latest files until
                # publication; committed checks still require frozen agreement.
                if inherited_projections or require_committed:
                    for filename in FILES:
                        latest = root / "attestations/latest" / filename
                        frozen = root / projected_directory / filename
                        if latest.read_bytes() != frozen.read_bytes():
                            raise ContractError("latest projection is stale or mixed")
    if require_committed:
        for digest in seen:
            raise ValueError(f"candidate head {digest} must be accepted in authoritative Git before publication")
        if not projection_matches_current:
            raise ContractError("latest projection is stale or mixed")
    # Untracked candidates still receive signed discovery checks.
    return paths


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--base", default="HEAD")
    parser.add_argument("--require-committed", action="store_true")
    parser.add_argument("--print-paths", action="store_true")
    parser.add_argument("--wait-for-acceptance", type=int, metavar="SECONDS",
                        help="wait for fetched main to accept the frozen candidate; --base is its source commit")
    args = parser.parse_args()
    try:
        if args.wait_for_acceptance is not None:
            if args.print_paths:
                raise ValueError("acceptance waiting cannot print submission paths")
            wait_for_acceptance(args.root, args.base, args.wait_for_acceptance)
        else:
            paths = _verified_append_paths(args.root, args.base, args.require_committed)
        if args.print_paths:
            for path in paths:
                print(path)
    except AcceptancePending as error:
        sys.stderr.write(f"attestation append: {error}\n")
        return 75
    except (ValueError, OSError, KeyError, subprocess.SubprocessError) as error:
        raise SystemExit(f"attestation append: {error}") from error
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
