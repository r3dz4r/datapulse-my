#!/usr/bin/env python3
"""Check evidence immutability and signed-parent CAS against an accepted Git base."""
from __future__ import annotations

import argparse
import io
from pathlib import Path
import subprocess
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.attestation_sets import (
    FILES,
    PIPELINE_OWNED_PROJECTIONS,
    discovery,
    set_directory,
    verify_legacy_mirror,
    selected_directory,
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


def accepted_files(root: Path, revision: str) -> dict[str, bytes]:
    """Read accepted evidence in one Git operation, preserving exact raw bytes."""
    entries = subprocess.run(["git", "ls-tree", "-rz", revision, "--", "attestations",
                              "docs/.well-known/datapulse-probe-keys.json"],
                             cwd=root, check=True, capture_output=True).stdout.split(b"\0")
    blobs = []
    for entry in filter(None, entries):
        metadata, path = entry.split(b"\t", 1)
        mode, kind, digest = metadata.split()
        if kind != b"blob" or mode not in {b"100644", b"100755"}:
            raise ContractError("accepted attestation evidence must be regular files")
        blobs.append((path.decode("utf-8"), digest))
    if not blobs:
        return {}
    batch = subprocess.run(["git", "cat-file", "--batch"], cwd=root, check=True,
                           input=b"".join(digest + b"\n" for _, digest in blobs), capture_output=True).stdout
    stream, result = io.BytesIO(batch), {}
    for path, digest in blobs:
        actual, kind, size = stream.readline().split()
        if actual != digest or kind != b"blob":
            raise ContractError("accepted Git blob is missing or invalid")
        result[path] = stream.read(int(size))
        if len(result[path]) != int(size) or stream.read(1) != b"\n":
            raise ContractError("accepted Git blob bytes are incomplete")
    return result


def accepted_discovery(root: Path, revision: str, files: dict[str, bytes] | None = None) -> dict:
    """Resolve the accepted tree, including sets absent from its legacy index."""
    files = accepted_files(root, revision) if files is None else files
    with tempfile.TemporaryDirectory(prefix="accepted-attestations-") as temporary:
        for path, data in files.items():
            target = Path(temporary) / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
        return discovery(Path(temporary))


def append_paths(root: Path, base: str) -> list[str]:
    """Return only immutable files belonging to new, verified append sets."""
    old, new = accepted_discovery(root, base), discovery(root)
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
        binding = _load(root / directory / "binding.json", "append binding")
        record = binding["payload"].get("correction")
        if record is not None:
            paths.add(record["health_snapshot_ref"])
    return sorted(paths)


def verify_append(root: Path, base: str, require_committed: bool = False) -> None:
    """Reject rewritten ledger bytes, remaps, lost entries, forks and stale parents."""
    files = accepted_files(root, base)
    for path, data in files.items():
        if not path.startswith("attestations/") or path in PROJECTIONS or path.startswith("attestations/latest/"):
            continue
        if not (root / path).is_file() or (root / path).read_bytes() != data:
            raise ValueError(f"immutable evidence changed or deleted: {path}")
    old = accepted_discovery(root, base, files)
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
    directory = accepted_day_directory(root, new)
    head = _load(root / new["heads"][new["current_head"]], "current head")
    if "append_content_sha256" not in head["payload"]:
        selected_directory(root)
    else:
        # Publication checks still require current projections. An append commit
        # carries immutable evidence only, so its inherited projections may
        # coherently describe an accepted ancestor. Reject mixtures and tampering.
        projection = root / "attestations/latest/chain_head.json"
        if projection.exists():
            projected = _load(projection, "projected head")["chain_head"]
            if projected not in new["envelopes"]:
                raise ContractError("latest projection is stale or mixed")
            projected_directory = set_directory(new["heads"][projected])
            projected_revision = root / projected_directory / "revisions" / projected
            if projected_revision.is_dir():
                projected_directory = projected_revision.relative_to(root).as_posix()
            projected_document = {**new, "current_head": projected}
            verify_legacy_mirror(root, projected_document, projected_directory)
            for filename in FILES:
                latest = root / "attestations/latest" / filename
                frozen = root / projected_directory / filename
                if filename in PIPELINE_OWNED_PROJECTIONS:
                    if _parse_time(_load(latest, "latest scores").get("generated_at"), "latest scores time") < _parse_time(
                            _load(frozen, "frozen scores").get("generated_at"), "frozen scores time"):
                        raise ContractError("latest projection is stale or mixed")
                elif latest.read_bytes() != frozen.read_bytes():
                    raise ContractError("latest projection is stale or mixed")
    if require_committed:
        for digest in seen:
            raise ValueError(f"candidate head {digest} must be accepted in authoritative Git before publication")
        selected_directory(root)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--base", default="HEAD")
    parser.add_argument("--require-committed", action="store_true")
    parser.add_argument("--print-paths", action="store_true")
    args = parser.parse_args()
    try:
        verify_append(args.root, args.base, args.require_committed)
        if args.print_paths:
            for path in append_paths(args.root, args.base):
                print(path)
    except (ValueError, OSError, KeyError, subprocess.CalledProcessError) as error:
        raise SystemExit(f"attestation append: {error}") from error
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
