#!/usr/bin/env python3
"""Prove that two isolated release-build runs produce identical artifacts."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import shlex
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
README_MARKER = "Current distribution (`_trust_summary`):"
CATEGORY_ORDER = (
    "data/<id>.md",
    "badges/",
    "feed.xml",
    "README.md (trust-summary)",
    "changelog.json",
    "data/json/",
    "data/jsonld/",
    "docs/mcp-reference.md",
    "mcp.json",
    "docs/.dashboard_filters.json",
)
STATUS_BADGE_COUNT = 8


class SetupFailure(RuntimeError):
    """The verifier could not prepare or record an isolated run."""


class VerificationFailure(RuntimeError):
    """A build failed or its owned outputs did not satisfy the contract."""


@dataclass(frozen=True)
class BuildCapture:
    hashes: dict[str, str]
    categories: dict[str, tuple[str, ...]]
    workdir: Path


def _run_git(*arguments: str) -> str:
    try:
        completed = subprocess.run(
            ["git", *arguments],
            cwd=ROOT,
            env={"PATH": os.environ.get("PATH", os.defpath)},
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
        )
    except OSError as error:
        raise SetupFailure(f"could not execute git: {error}") from error
    if completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip()
        raise SetupFailure(f"git {' '.join(arguments)} failed: {detail}")
    return completed.stdout.strip()


def _copy_ignore(directory: str, names: list[str]) -> set[str]:
    relative = Path(directory).resolve().relative_to(ROOT.resolve())
    ignored = {
        name
        for name in names
        if name in {".git", "__pycache__", ".pytest_cache", "_site"}
        or name.endswith(".pyc")
    }
    if relative == Path("data/health"):
        ignored.update(
            name
            for name in names
            if name.startswith(".latest.") and name.endswith(".json")
        )
    return ignored


def _copy_source(destination: Path) -> None:
    try:
        shutil.copytree(
            ROOT,
            destination,
            dirs_exist_ok=True,
            symlinks=True,
            ignore=_copy_ignore,
        )
    except (OSError, shutil.Error, ValueError) as error:
        raise SetupFailure(f"could not copy source into {destination}: {error}") from error


def _load_json(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise VerificationFailure(f"could not read required JSON {path}: {error}") from error
    if not isinstance(value, dict):
        raise VerificationFailure(f"required JSON must be an object: {path}")
    return value


def _canonical_ids(root: Path) -> tuple[str, ...]:
    rows = _load_json(root / "datapulse.json").get("datasets")
    if not isinstance(rows, list):
        raise VerificationFailure("datapulse.json: datasets must be an array")
    identifiers: list[str] = []
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get("id"), str):
            raise VerificationFailure("datapulse.json: every dataset needs a string id")
        identifiers.append(row["id"])
    if len(identifiers) != len(set(identifiers)):
        raise VerificationFailure("datapulse.json: duplicate dataset ids")
    return tuple(identifiers)


def _expected_badge_count(source: Path, identifiers: tuple[str, ...]) -> int:
    counts = (
        _load_json(source / "health/latest.json")
        .get("_trust_summary", {})
        .get("by_status", {})
    )
    if not isinstance(counts, dict):
        raise VerificationFailure("health/latest.json: invalid _trust_summary.by_status")
    identifiers_set = set(identifiers)
    auxiliary = 0
    badges = source / "badges"
    if badges.is_dir():
        for path in badges.rglob("*"):
            if not path.is_file():
                continue
            if path.parent == badges and path.suffix == ".svg":
                if path.stem in identifiers_set or path.name.startswith("status-"):
                    continue
            auxiliary += 1
    return len(identifiers) + STATUS_BADGE_COUNT + auxiliary


def _readme_summary(path: Path) -> bytes:
    try:
        lines = path.read_bytes().splitlines(keepends=True)
    except OSError as error:
        raise VerificationFailure(f"could not read {path}: {error}") from error
    marker = README_MARKER.encode("utf-8")
    matches = [index for index, line in enumerate(lines) if line.startswith(marker)]
    if len(matches) != 1:
        raise VerificationFailure(
            f"{path}: expected exactly one trust-summary marker, found {len(matches)}"
        )
    start = matches[0]
    end = next(
        (index for index in range(start + 1, len(lines)) if not lines[index].strip()),
        len(lines),
    )
    return b"".join(lines[start:end])


def _regular_files(directory: Path) -> tuple[Path, ...]:
    if not directory.is_dir():
        raise VerificationFailure(f"required output directory is missing: {directory}")
    return tuple(sorted(path for path in directory.rglob("*") if path.is_file()))


def _capture(root: Path, source: Path) -> BuildCapture:
    identifiers = _canonical_ids(root)
    non_gtfs = tuple(identifier for identifier in identifiers if "gtfs" not in identifier.lower())

    data_reports = tuple(root / "data" / f"{identifier}.md" for identifier in identifiers)
    badges = _regular_files(root / "badges")
    envelopes = _regular_files(root / "data/json")
    jsonld = _regular_files(root / "data/jsonld")
    singleton_paths = {
        "feed.xml": root / "feed.xml",
        "changelog.json": root / "changelog.json",
        "docs/mcp-reference.md": root / "docs/mcp-reference.md",
        "mcp.json": root / "mcp.json",
        "docs/.dashboard_filters.json": root / "docs/.dashboard_filters.json",
    }

    required = [
        *data_reports,
        *(root / "badges" / f"{identifier}.svg" for identifier in identifiers),
        *(root / "data/json" / f"{identifier}.json" for identifier in non_gtfs),
        *(root / "data/jsonld" / f"{identifier}.json" for identifier in identifiers),
        root / "data/jsonld/catalog.json",
        *singleton_paths.values(),
    ]
    missing = [path.relative_to(root).as_posix() for path in required if not path.is_file()]
    if missing:
        raise VerificationFailure("missing required output(s): " + ", ".join(missing))

    expected_counts = {
        "data/<id>.md": len(identifiers),
        "badges/": _expected_badge_count(source, identifiers),
        "feed.xml": 1,
        "README.md (trust-summary)": 1,
        "changelog.json": 1,
        "data/json/": len(non_gtfs),
        "data/jsonld/": len(identifiers) + 1,
        "docs/mcp-reference.md": 1,
        "mcp.json": 1,
        "docs/.dashboard_filters.json": 1,
    }

    category_paths: dict[str, tuple[Path, ...]] = {
        "data/<id>.md": data_reports,
        "badges/": badges,
        "feed.xml": (singleton_paths["feed.xml"],),
        "changelog.json": (singleton_paths["changelog.json"],),
        "data/json/": envelopes,
        "data/jsonld/": jsonld,
        "docs/mcp-reference.md": (singleton_paths["docs/mcp-reference.md"],),
        "mcp.json": (singleton_paths["mcp.json"],),
        "docs/.dashboard_filters.json": (
            singleton_paths["docs/.dashboard_filters.json"],
        ),
    }
    actual_counts = {
        category: len(paths) for category, paths in category_paths.items()
    }
    actual_counts["README.md (trust-summary)"] = 1
    count_errors = [
        f"{category}: expected {expected_counts[category]}, found {actual_counts[category]}"
        for category in CATEGORY_ORDER
        if actual_counts[category] != expected_counts[category]
    ]
    if count_errors:
        raise VerificationFailure("owned-path count mismatch: " + "; ".join(count_errors))

    hashes: dict[str, str] = {}
    categories: dict[str, tuple[str, ...]] = {}
    for category, paths in category_paths.items():
        names: list[str] = []
        for path in paths:
            relative = path.relative_to(root).as_posix()
            try:
                payload = path.read_bytes()
            except OSError as error:
                raise VerificationFailure(f"could not hash {path}: {error}") from error
            hashes[relative] = hashlib.sha256(payload).hexdigest()
            names.append(relative)
        categories[category] = tuple(names)

    readme_key = "README.md#trust-summary"
    hashes[readme_key] = hashlib.sha256(_readme_summary(root / "README.md")).hexdigest()
    categories["README.md (trust-summary)"] = (readme_key,)
    return BuildCapture(hashes=dict(sorted(hashes.items())), categories=categories, workdir=root)


def _write_hash_table(path: Path, hashes: dict[str, str]) -> None:
    try:
        path.write_text(json.dumps(hashes, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    except OSError as error:
        raise SetupFailure(f"could not write metadata {path}: {error}") from error


def _build(source: Path, workdir: Path, git_dir: str) -> BuildCapture:
    _copy_source(workdir)
    environment = {
        "PATH": os.environ.get("PATH", os.defpath),
        "GIT_DIR": git_dir,
    }
    try:
        completed = subprocess.run(
            ["bash", "scripts/generate.sh", "release-build"],
            cwd=workdir,
            env=environment,
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
        )
    except OSError as error:
        raise SetupFailure(f"could not execute release-build in {workdir}: {error}") from error
    if completed.returncode != 0:
        if completed.stdout:
            print(completed.stdout, file=sys.stderr, end="")
        if completed.stderr:
            print(completed.stderr, file=sys.stderr, end="")
        raise VerificationFailure(
            f"release-build failed in {workdir} with exit code {completed.returncode}"
        )
    return _capture(workdir, source)


def _aggregate(capture: BuildCapture, category: str) -> str:
    digest = hashlib.sha256()
    for relative in sorted(capture.categories[category]):
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update(bytes.fromhex(capture.hashes[relative]))
        digest.update(b"\n")
    return digest.hexdigest()


def _print_diff(first: dict[str, str], second: dict[str, str]) -> None:
    print("ERROR: release output hashes differ:", file=sys.stderr)
    for relative in sorted(first.keys() | second.keys()):
        first_hash = first.get(relative, "<missing>")
        second_hash = second.get(relative, "<missing>")
        if first_hash != second_hash:
            print(
                f"  {relative}: first={first_hash} second={second_hash}",
                file=sys.stderr,
            )


def _summary(
    source_sha: str,
    first: BuildCapture,
    second: BuildCapture,
    reproduction: str,
) -> str:
    timestamp = dt.datetime.now().astimezone().isoformat(timespec="seconds")
    total = len(first.hashes)
    lines = [
        "# Release reproducibility verification",
        "",
        f"- Verified at: `{timestamp}`",
        f"- Source SHA: `{source_sha}`",
        "- Profile result: `bash scripts/generate.sh release-build` exited 0 in both isolated runs",
        f"- Total files built: **{total}**",
        "",
        "| Path category | File count | First-run hash | Second-run hash | Match? |",
        "|---|---:|---|---|:---:|",
    ]
    for category in CATEGORY_ORDER:
        first_hash = _aggregate(first, category)
        second_hash = _aggregate(second, category)
        match = first_hash == second_hash
        lines.append(
            f"| {category} | {len(first.categories[category])} | `{first_hash}` | "
            f"`{second_hash}` | {'Yes' if match else 'No'} |"
        )
    lines.extend(
        [
            "",
            "## Reproduction",
            "",
            "```bash",
            reproduction,
            "```",
            "",
        ]
    )
    return "\n".join(lines)


def _workdir(root: Path, prefix: str) -> Path:
    try:
        return Path(tempfile.mkdtemp(prefix=prefix, dir=root))
    except OSError as error:
        raise SetupFailure(f"could not create temporary workdir under {root}: {error}") from error


def verify(workdir_root: Path, output: Path, reproduction: str) -> int:
    try:
        if workdir_root.resolve().is_relative_to(ROOT.resolve()):
            raise SetupFailure("--workdir-root must be outside the source tree")
        workdir_root.mkdir(parents=True, exist_ok=True)
        if not workdir_root.is_dir():
            raise SetupFailure(f"workdir root is not a directory: {workdir_root}")
    except OSError as error:
        raise SetupFailure(f"could not prepare workdir root {workdir_root}: {error}") from error

    source_sha = _run_git("rev-parse", "HEAD")
    git_dir = _run_git("rev-parse", "--absolute-git-dir")
    metadata = _workdir(workdir_root, "datapulse-release-meta-")
    first_workdir = _workdir(workdir_root, "datapulse-release-A-")
    first = _build(ROOT, first_workdir, git_dir)
    _write_hash_table(metadata / "first_run.json", first.hashes)

    try:
        shutil.rmtree(first_workdir)
    except OSError as error:
        raise SetupFailure(f"could not wipe first workdir {first_workdir}: {error}") from error

    second_workdir = _workdir(workdir_root, "datapulse-release-B-")
    second = _build(ROOT, second_workdir, git_dir)
    _write_hash_table(metadata / "second_run.json", second.hashes)

    summary = _summary(source_sha, first, second, reproduction)
    try:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(summary, encoding="utf-8")
    except OSError as error:
        raise SetupFailure(f"could not write verification summary {output}: {error}") from error

    if first.hashes != second.hashes:
        _print_diff(first.hashes, second.hashes)
        raise VerificationFailure("isolated release builds were not byte-identical")

    print(f"First-run hashes: {metadata / 'first_run.json'}")
    print(f"Second-run hashes: {metadata / 'second_run.json'}")
    print(f"Second build retained at: {second_workdir}")
    print(f"Verification summary: {output}")
    print(f"OK: both builds produced byte-identical outputs ({len(first.hashes)} files)")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workdir-root", type=Path, default=Path("/tmp"))
    parser.add_argument(
        "--output", type=Path, default=Path("docs/release-verification.md")
    )
    args = parser.parse_args()
    output = args.output if args.output.is_absolute() else ROOT / args.output
    reproduction = shlex.join(
        ["python3", "scripts/verify_release_reproducible.py", *sys.argv[1:]]
    )
    try:
        return verify(args.workdir_root.resolve(), output.resolve(), reproduction)
    except VerificationFailure as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1
    except SetupFailure as error:
        print(f"SETUP ERROR: {error}", file=sys.stderr)
        return 2
    except Exception as error:  # Defensive setup boundary for a command-line gate.
        print(f"SETUP ERROR: unexpected verifier failure: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
