#!/usr/bin/env python3
"""Compute a snapshot publish commit without changing repository state."""

from __future__ import annotations

import argparse
import json
import logging
import os
import re
import subprocess
import sys
import tempfile
from collections.abc import Iterator, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

LOGGER = logging.getLogger(__name__)

# Source: /home/redza/dotfiles/scripts/datapulse-pipeline.sh:63. That file is
# outside this repository and unavailable in Actions, so this is the one local
# declaration until the producer's path list has a shared source.
ARTIFACT_PATHS = (
    "health", "badges", "feed.xml", "changelog.json", "catalog-snapshot.json",
    "catalog-graph.json", "datapulse_summary.json", "README.md", "record-evidence",
    "deltas", "data/passports", "docs/okf", "docs/datasets",
    "observation-receipts", "datapulse.json", "data/json", "data/jsonld",
    "docs/index.html",
)
WATERMARK = "health/snapshot.json"
PUBLISH_SUBJECT = "chore(health): publish snapshot"
IDENTITY_NAME = "DataPulse Snapshot Publisher"
IDENTITY_EMAIL = "snapshot-publisher@data-pulse.my"
SHA_RE = re.compile(r"[0-9a-f]{40}|[0-9a-f]{64}")


class PublisherError(Exception):
    """Invalid snapshot or repository input."""


@dataclass(frozen=True)
class Decision:
    line: str
    tree: str | None = None
    sha: str | None = None


@dataclass(frozen=True)
class Overlay:
    tree: str
    sha: str
    changed: int


@dataclass(frozen=True)
class OverlayObjects:
    env: Mapping[str, str]


def git(
    repo: Path, *args: str, env: Mapping[str, str] | None = None,
    input_data: bytes | None = None,
) -> bytes:
    """Run Git with argument boundaries preserved and return raw output."""
    process = subprocess.run(
        ["git", "-C", str(repo), *args], input=input_data,
        capture_output=True,
        env=dict(env) if env is not None else None, check=False,
    )
    if process.returncode:
        reason = process.stderr.decode("utf-8", "replace").strip()
        raise PublisherError(f"git {args[0]} failed: {reason}")
    return process.stdout


def _try_git(repo: Path, *args: str) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True, check=False,
    )


def _sha(value: bytes) -> str:
    result = value.decode("ascii").strip()
    if SHA_RE.fullmatch(result) is None:
        raise PublisherError(f"invalid Git object ID: {result}")
    return result


def _ref(repo: Path, local: str, remote: str) -> str:
    for ref in (local, remote):
        result = _try_git(repo, "rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}")
        if result.returncode == 0:
            return _sha(result.stdout)
    raise PublisherError(f"missing {local} and {remote}")


def _managed(path: str) -> bool:
    return path != WATERMARK and any(
        path == root or path.startswith(root + "/") for root in ARTIFACT_PATHS
    )


def _tree_entries(repo: Path, revision: str) -> list[tuple[str, str, str]]:
    entries = []
    for record in git(repo, "ls-tree", "-rz", revision).split(b"\0"):
        if not record:
            continue
        metadata, raw_path = record.split(b"\t", 1)
        mode, kind, oid = metadata.decode("ascii").split()
        if kind not in ("blob", "commit"):
            raise PublisherError(f"unexpected tree entry: {raw_path!r}")
        path = raw_path.decode("utf-8", "surrogateescape")
        entries.append((mode, oid, path))
    return entries


def _snapshot(repo: Path, tip: str) -> tuple[int, str, str]:
    parents = git(repo, "rev-list", "--parents", tip).decode("ascii").splitlines()
    if any(len(row.split()) != 2 for row in parents[:-1]) or len(parents[-1].split()) > 2:
        raise PublisherError("snapshot history is not a single-parent linear chain")
    message = git(repo, "show", "-s", "--format=%B", tip).decode("utf-8", "replace")
    trailers = {}
    for line in message.splitlines():
        for key in ("Snapshot-Seq", "Snapshot-Source"):
            if line.startswith(key + ":"):
                trailers[key] = line[len(key) + 1:].strip()
    raw_seq = trailers.get("Snapshot-Seq", "")
    if not raw_seq.isdecimal() or int(raw_seq) < 1:
        raise PublisherError("missing or invalid Snapshot-Seq trailer")
    source = trailers.get("Snapshot-Source", "")
    if SHA_RE.fullmatch(source) is None or _try_git(repo, "cat-file", "-e", f"{source}^{{commit}}").returncode:
        raise PublisherError("missing or invalid Snapshot-Source trailer")
    tree = _sha(git(repo, "rev-parse", f"{tip}^{{tree}}"))
    for _, _, path in _tree_entries(repo, tip):
        if not _managed(path):
            raise PublisherError(f"snapshot contains unmanaged path: {path}")
    return int(raw_seq), source, tree


def _watermark(repo: Path, main: str) -> tuple[int, str | None]:
    if _try_git(repo, "cat-file", "-e", f"{main}:{WATERMARK}").returncode:
        return 0, None
    try:
        raw = json.loads(git(repo, "show", f"{main}:{WATERMARK}"))
        seq, tree, snapshot = raw["seq"], raw["tree"], raw["snapshot"]
    except (ValueError, KeyError, TypeError) as error:
        raise PublisherError(f"invalid {WATERMARK}: {error}") from error
    if type(seq) is not int or seq < 0 or not isinstance(tree, str) or not isinstance(snapshot, str):
        raise PublisherError(f"invalid {WATERMARK} fields")
    if SHA_RE.fullmatch(tree) is None or SHA_RE.fullmatch(snapshot) is None:
        raise PublisherError(f"invalid {WATERMARK} object IDs")
    return seq, tree


def decide(seq: int, published_seq: int, in_flight_pr: int | None, foreign: str | None) -> str | None:
    """Apply the publisher's ordered, side-effect-free skip rules."""
    if seq <= published_seq:
        return f"would-skip already-published seq={seq}"
    if in_flight_pr is not None:
        return f"would-skip in-flight pr={in_flight_pr}"
    if foreign is not None:
        return f"would-skip superseded-by {foreign}"
    return None


@contextmanager
def overlay_objects(repo: Path) -> Iterator[OverlayObjects]:
    """Keep Git's index and new objects outside the checkout and object store."""
    object_dir = Path(git(repo, "rev-parse", "--path-format=absolute", "--git-path", "objects").decode().strip())
    with tempfile.TemporaryDirectory(prefix="snapshot-publisher-") as scratch:
        temp = Path(scratch)
        (temp / "objects").mkdir()
        env = os.environ.copy()
        env.update({
            "GIT_INDEX_FILE": str(temp / "index"),
            "GIT_OBJECT_DIRECTORY": str(temp / "objects"),
            "GIT_ALTERNATE_OBJECT_DIRECTORIES": str(object_dir),
        })
        yield OverlayObjects(env)


def _replace_index(repo: Path, revision: str, objects: OverlayObjects, *, managed_only: bool) -> None:
    env = objects.env
    git(repo, "read-tree", revision, env=env)
    paths = [entry[2] for entry in _tree_entries(repo, revision)]
    removed = [path for path in paths if (not _managed(path) if managed_only else _managed(path) or path == WATERMARK)]
    if removed:
        git(repo, "update-index", "--force-remove", "--", *removed, env=env)


def _managed_tree(repo: Path, main: str, objects: OverlayObjects) -> str:
    _replace_index(repo, main, objects, managed_only=True)
    return _sha(git(repo, "write-tree", env=objects.env))


def _foreign_write(repo: Path, main: str, source: str, watermark_tree: str | None, objects: OverlayObjects) -> str | None:
    if watermark_tree is None or _managed_tree(repo, main, objects) == watermark_tree:
        return None
    history = git(repo, "log", "--format=%H%x09%s", main, "--", *ARTIFACT_PATHS)
    for row in history.decode("utf-8", "replace").splitlines():
        sha, subject = row.split("\t", 1)
        if subject.startswith(PUBLISH_SUBJECT):
            continue
        ancestor = _try_git(repo, "merge-base", "--is-ancestor", sha, source)
        if ancestor.returncode == 0:
            return None
        if ancestor.returncode == 1:
            return sha
        raise PublisherError("could not check foreign-write ancestry")
    return None


def build_overlay(repo: Path, main: str, tip: str, seq: int, objects: OverlayObjects) -> Overlay:
    """Build a deterministic commit in scratch objects without updating refs."""
    env = dict(objects.env)
    _replace_index(repo, main, objects, managed_only=False)
    entries = []
    for mode, oid, path in _tree_entries(repo, tip):
        if not _managed(path):
            raise PublisherError(f"snapshot contains unmanaged path: {path}")
        entries.append(f"{mode} {oid} 0\t".encode("ascii") + path.encode("utf-8", "surrogateescape") + b"\0")
    snapshot_tree = _sha(git(repo, "rev-parse", f"{tip}^{{tree}}"))
    watermark = json.dumps({"seq": seq, "snapshot": tip, "tree": snapshot_tree}, separators=(",", ":")) + "\n"
    blob = _sha(git(repo, "hash-object", "-w", "--stdin", env=env, input_data=watermark.encode()))
    entries.append(f"100644 {blob} 0\t{WATERMARK}".encode("ascii") + b"\0")
    git(repo, "update-index", "-z", "--index-info", env=env, input_data=b"".join(entries))
    tree = _sha(git(repo, "write-tree", env=env))
    date = git(repo, "show", "-s", "--format=%cI", tip).decode("ascii").strip()
    env.update({
        "GIT_AUTHOR_NAME": IDENTITY_NAME,
        "GIT_AUTHOR_EMAIL": IDENTITY_EMAIL,
        "GIT_COMMITTER_NAME": IDENTITY_NAME,
        "GIT_COMMITTER_EMAIL": IDENTITY_EMAIL,
        "GIT_AUTHOR_DATE": date,
        "GIT_COMMITTER_DATE": date,
    })
    message = f"{PUBLISH_SUBJECT}\n\nSnapshot-Seq: {seq}\nSnapshot-Source: {tip}\n"
    sha = _sha(git(repo, "commit-tree", tree, "-p", main, env=env, input_data=message.encode()))
    changed = len([path for path in git(repo, "diff", "--name-only", "-z", main, tree, env=env).split(b"\0") if path])
    return Overlay(tree, sha, changed)


def evaluate(repo: Path, in_flight_pr: int | None = None) -> Decision:
    """Return exactly one dry-run decision from local refs."""
    if in_flight_pr is not None and in_flight_pr < 1:
        raise PublisherError("in-flight PR number must be positive")
    tip = _ref(repo, "refs/heads/health-snapshots", "refs/remotes/origin/health-snapshots")
    main = _ref(repo, "refs/heads/main", "refs/remotes/origin/main")
    seq, source, _ = _snapshot(repo, tip)
    published_seq, watermark_tree = _watermark(repo, main)
    early = decide(seq, published_seq, in_flight_pr, None)
    if early is not None:
        return Decision(early)
    with overlay_objects(repo) as objects:
        foreign = _foreign_write(repo, main, source, watermark_tree, objects)
        skip = decide(seq, published_seq, in_flight_pr, foreign)
        if skip is not None:
            return Decision(skip)
        overlay = build_overlay(repo, main, tip, seq, objects)
    return Decision(
        f"would-apply" f" seq={seq} tree={overlay.tree} sha={overlay.sha} changed={overlay.changed}",
        overlay.tree, overlay.sha,
    )


def main(argv: Sequence[str] | None = None) -> int:
    """Read local refs and emit one machine-readable dry-run line."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path("."))
    parser.add_argument("--dry-run", action="store_true", required=True)
    parser.add_argument("--in-flight-pr", type=int)
    args = parser.parse_args(argv)
    try:
        decision = evaluate(args.repo, args.in_flight_pr)
    except PublisherError as error:
        LOGGER.error("snapshot publisher: %s", error)
        return 2
    sys.stdout.write(decision.line + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
