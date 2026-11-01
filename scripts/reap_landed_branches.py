#!/usr/bin/env python3
"""Identify the landed-branch backlog and detect drift, conservatively.

Repository auto-delete remains disabled because it removed the health publish
branch on 2026-10-06. This is a backlog reaper and weekly drift detector.
A multi-commit branch squashed into a single base commit is not detectable by
patch-id; it is reported unmerged and never deleted. The tool errs toward
keeping.

Apply requires a nonempty, successful open-PR query and a flushed JSON manifest.
GitHub's DELETE ref API has no SHA precondition: immediate rechecks reduce, but
cannot eliminate, a concurrent push or PR opening between the check and DELETE.
Coordinate apply with branch writers. Report mode never deletes a remote ref.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
from pathlib import Path
import re
import subprocess
import sys
from typing import Any, Sequence
from urllib.parse import quote, urlsplit

logger = logging.getLogger(__name__)


class ReaperError(RuntimeError):
    """A safety gate or required tool failed."""


def run_command(root: Path, args: Sequence[str]) -> str:
    """Run a required command without leaking credential-bearing arguments."""
    try:
        result = subprocess.run(args, cwd=root, text=True, capture_output=True)
    except OSError as error:
        raise ReaperError(f"{args[0]} unavailable: {error.strerror}") from error
    if result.returncode:
        raise ReaperError(f"{args[0]} {args[1]} failed (exit {result.returncode})")
    return result.stdout.strip()


def remote_heads(root: Path, remote: str) -> dict[str, str]:
    """Read and validate the live remote head snapshot."""
    heads: dict[str, str] = {}
    for line in run_command(root, ["git", "ls-remote", "--heads", remote]).splitlines():
        fields = line.split()
        if (len(fields) != 2 or not re.fullmatch(r"[0-9a-f]{40}", fields[0])
                or not fields[1].startswith("refs/heads/")):
            raise ReaperError("Malformed remote head listing")
        branch = fields[1].removeprefix("refs/heads/")
        if branch in heads:
            raise ReaperError("Duplicate remote head")
        heads[branch] = fields[0]
    return heads


def repository_slug(root: Path, remote: str) -> str:
    """Derive owner/repository from HTTPS, SSH URLs, or an SSH host alias."""
    url = run_command(root, ["git", "remote", "get-url", remote])
    if "://" in url:
        parsed = urlsplit(url)
        if parsed.scheme not in {"https", "ssh"} or not parsed.hostname:
            raise ReaperError("Remote URL is not a GitHub HTTPS or SSH URL")
        path = parsed.path.lstrip("/")
    elif re.fullmatch(r"git@[^/:]+:[^\s]+", url):
        path = url.split(":", 1)[1]
    else:
        raise ReaperError("Cannot derive owner/repository from remote URL")
    slug = path.removesuffix(".git")
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", slug):
        raise ReaperError("Invalid owner/repository in remote URL")
    return slug


def open_pr_branches(root: Path, slug: str) -> set[str]:
    """Query the selected repository; refuse a potentially truncated keep set."""
    output = run_command(root, ["gh", "pr", "list", "--repo", slug, "--state", "open",
                                "--limit", "1000", "--json", "headRefName",
                                "--jq", ".[].headRefName"])
    lines = output.splitlines()
    if len(lines) >= 1000:
        raise ReaperError("Open-PR query reached its limit; keep set may be incomplete")
    for branch in lines:
        if not branch:
            raise ReaperError("Malformed open-PR branch result")
        run_command(root, ["git", "check-ref-format", f"refs/heads/{branch}"])
    return set(lines)


def classify_branches(
    root: Path, remote: str, base: str, heads: dict[str, str],
    open_prs: set[str], extra_keep: set[str] | None = None, mode: str = "report",
) -> dict[str, Any]:
    """Classify exact advertised SHAs, with an injected trustworthy PR keep set."""
    base_ref = f"{remote}/{base}"
    base_sha = run_command(root, ["git", "rev-parse", "--verify",
                                  f"refs/remotes/{base_ref}^{{commit}}"])
    if heads.get(base) != base_sha:
        raise ReaperError("Remote base differs from tracking ref; fetch before classifying")
    report: dict[str, Any] = {
        "base": base_ref, "base_sha": base_sha, "mode": mode, "total": len(heads),
        "landed": [], "keep": [], "unmerged": [],
    }
    for branch, sha in sorted(heads.items()):
        reason = None
        if branch == base:
            reason = "base"
        elif branch in open_prs:
            reason = "open-pr"
        elif branch == "health-automation" or branch.startswith("release-please--"):
            reason = "builtin"
        elif branch in (extra_keep or set()):
            reason = "keep-file"
        if reason:
            report["keep"].append({"branch": branch, "reason": reason})
            continue
        count = run_command(root, ["git", "rev-list", "--count", f"{base_sha}..{sha}"])
        if not count.isdecimal():
            raise ReaperError(f"Invalid ahead count for {branch}")
        ahead = int(count)
        rule = "zero-ahead" if ahead == 0 else None
        if ahead:
            lines = run_command(root, ["git", "cherry", base_sha, sha]).splitlines()
            # cherry omits merge commits; never treat omitted unique commits as landed.
            if len(lines) == ahead and all(re.fullmatch(r"- [0-9a-f]{40}", s) for s in lines):
                rule = "patch-equivalent"
        if rule:
            report["landed"].append({"branch": branch, "sha": sha, "rule": rule})
        else:
            report["unmerged"].append({"branch": branch, "sha": sha, "ahead": ahead})
    return report


def checked_out_branches(root: Path) -> set[str]:
    """Read all worktree branches, including the current checkout."""
    prefix = "branch refs/heads/"
    return {line.removeprefix(prefix) for line in
            run_command(root, ["git", "worktree", "list", "--porcelain"]).splitlines()
            if line.startswith(prefix)}


def write_report(report: dict[str, Any], path: Path | None) -> None:
    """Write deterministic JSON atomically, flushing before any deletion."""
    payload = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if path is None:
        sys.stdout.write(payload)
        sys.stdout.flush()
        return
    temporary = path.with_name(path.name + ".tmp")
    try:
        with temporary.open("x", encoding="utf-8") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        temporary.replace(path)
        # The rename must survive a crash before a remote branch is deleted.
        directory_fd = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    except OSError as error:
        raise ReaperError(f"Manifest write failed: {error.strerror}") from error


def apply_report(
    root: Path, remote: str, base: str, slug: str, report: dict[str, Any], path: Path,
) -> None:
    """Persist the plan, recheck safety gates, and stop at the first failure."""
    occupied = checked_out_branches(root)
    report["deleted"] = []
    report["not_deleted"] = [dict(item) for item in report["landed"]]
    report["skipped"] = [dict(item, reason="checked-out") for item in report["landed"]
                         if item["branch"] in occupied]
    write_report(report, path)
    try:
        for item in report["landed"]:
            branch = item["branch"]
            if branch in occupied:
                continue
            # Revalidate near DELETE: never delete a branch that moved or gained a PR.
            prs = open_pr_branches(root, slug)
            if not prs:
                raise ReaperError("Apply refuses an empty open-PR result")
            heads = remote_heads(root, remote)
            if heads.get(base) != report["base_sha"] or heads.get(branch) != item["sha"]:
                raise ReaperError(f"Remote changed before deletion of {branch}")
            if branch in prs or branch in checked_out_branches(root):
                report["skipped"].append(dict(item, reason="open-pr" if branch in prs
                                             else "checked-out"))
                report["skipped"].sort(key=lambda entry: entry["branch"])
                write_report(report, path)
                continue
            try:
                run_command(root, ["gh", "api", "--method", "DELETE",
                                   f"repos/{slug}/git/refs/heads/{quote(branch, safe='')}"])
            except ReaperError as error:
                raise ReaperError(f"Deletion failed for {branch}: {error}") from error
            report["deleted"].append(item)
            report["not_deleted"].remove(item)
            write_report(report, path)
    except ReaperError as error:
        logger.error("Apply stopped: %s; deleted=%s; not_deleted=%s", error,
                     [item["branch"] for item in report["deleted"]],
                     [item["branch"] for item in report["not_deleted"]])
        raise
    logger.info("Deleted=%s; not_deleted=%s", [i["branch"] for i in report["deleted"]],
                [i["branch"] for i in report["not_deleted"]])


def main(argv: Sequence[str] | None = None) -> int:
    """Run the report or explicitly requested apply, returning a stable exit code."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--remote", default="origin")
    parser.add_argument("--base", default="main")
    parser.add_argument("--mode", choices=("report", "apply"), default="report")
    parser.add_argument("--json", type=Path)
    parser.add_argument("--no-fetch", action="store_true")
    parser.add_argument("--keep-file", type=Path)
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    try:
        root = args.repo_root.resolve()
        run_command(root, ["git", "rev-parse", "--git-dir"])
        if args.remote.startswith("-") or args.base.startswith("-"):
            raise ReaperError("Remote and base cannot begin with a dash")
        if args.mode == "apply" and args.json is None:
            raise ReaperError("Apply requires --json for its deletion manifest")
        if not args.no_fetch:
            run_command(root, ["git", "fetch", "--no-prune", args.remote])
        slug = repository_slug(root, args.remote)
        prs = open_pr_branches(root, slug)
        if args.mode == "apply" and not prs:
            raise ReaperError("Apply refuses an empty open-PR result")
        keep = set(args.keep_file.read_text(encoding="utf-8").splitlines()) if args.keep_file else set()
        report = classify_branches(root, args.remote, args.base,
                                   remote_heads(root, args.remote), prs, keep, args.mode)
        if args.mode == "apply":
            apply_report(root, args.remote, args.base, slug, report, args.json)
        else:
            write_report(report, args.json)
        logger.info("total=%s landed=%s keep=%s unmerged=%s", report["total"],
                    len(report["landed"]), len(report["keep"]), len(report["unmerged"]))
        return 0
    except (ReaperError, OSError, UnicodeError) as error:
        logger.error("%s", error)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
