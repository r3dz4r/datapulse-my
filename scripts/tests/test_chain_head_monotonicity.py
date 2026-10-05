#!/usr/bin/env python3
"""Fail if the signed observation chain head ever moves backwards.

``observation-receipts/chain_head.json`` carries a monotonic
``sequence_number``. A checkout that predates the newest receipts can
regenerate a lower head and republish it, silently rewinding the signed
chain. Nothing checked ordering across the commits that touched that file
until now, so this test walks the recent history and rejects any decrease.

Measured on 2026-10-05: a production checkout reset to a ``main`` that
predated the newest receipts and regenerated a chain head of 2096 while
``main`` already read 2098. Only the ordering of an unrelated push kept the
signed chain from going backwards.
"""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import pytest


ROOT = Path(__file__).resolve().parents[2]
CHAIN_HEAD_PATH = "observation-receipts/chain_head.json"

# chain_head.json is rewritten on nearly every pipeline push, so the 50 most
# recent commits that touched it are ample to catch a regression without
# making the gate walk the full repository history (1,600+ commits).
MAX_COMMITS = 50


class ChainHeadMonotonicityError(AssertionError):
    """Raised when the observation chain head's sequence number decreases."""


@dataclass(frozen=True)
class ChainHeadCommit:
    """One commit that touched the chain head, with its sequence number."""

    sha: str
    sequence_number: int


def verify_sequence_monotonic(commits: Iterable[ChainHeadCommit]) -> None:
    """Raise unless sequence numbers are non-decreasing, oldest commit first."""
    previous: ChainHeadCommit | None = None
    for commit in commits:
        if previous is not None and commit.sequence_number < previous.sequence_number:
            raise ChainHeadMonotonicityError(
                "observation chain head went backwards: "
                f"{previous.sha} has sequence_number {previous.sequence_number}, "
                f"then {commit.sha} has sequence_number {commit.sequence_number}"
            )
        previous = commit


def _read_sequence_number(sha: str) -> int | None:
    """Return the chain head's sequence_number at one commit, if readable."""
    result = subprocess.run(
        ["git", "show", f"{sha}:{CHAIN_HEAD_PATH}"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        return None
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError:
        return None
    if not isinstance(payload, dict):
        return None
    value = payload.get("sequence_number")
    # bool is a subclass of int; a boolean sequence number is not a real stamp.
    if not isinstance(value, int) or isinstance(value, bool):
        return None
    return value


def read_chain_head_history(limit: int = MAX_COMMITS) -> list[ChainHeadCommit]:
    """Return chain-head commits that touched the file, oldest commit first."""
    result = subprocess.run(
        [
            "git",
            "log",
            f"--max-count={limit}",
            "--format=%H",
            "--",
            CHAIN_HEAD_PATH,
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    shas = [line for line in result.stdout.splitlines() if line.strip()]
    commits: list[ChainHeadCommit] = []
    for sha in reversed(shas):  # git log is newest-first; walk oldest-first
        sequence_number = _read_sequence_number(sha)
        if sequence_number is None:
            continue
        commits.append(ChainHeadCommit(sha=sha, sequence_number=sequence_number))
    return commits


def test_chain_head_sequence_never_decreases() -> None:
    commits = read_chain_head_history()

    assert commits, "no chain-head history could be read; the walk is vacuous"

    verify_sequence_monotonic(commits)


def test_control_decreasing_pair_is_rejected() -> None:
    """The gate can go red: a synthetic decrease must be rejected."""
    older_sha = "a" * 40
    newer_sha = "b" * 40
    commits = [
        ChainHeadCommit(sha=older_sha, sequence_number=2096),
        ChainHeadCommit(sha=newer_sha, sequence_number=2095),
    ]

    with pytest.raises(ChainHeadMonotonicityError) as error:
        verify_sequence_monotonic(commits)

    message = str(error.value)
    assert older_sha in message and "2096" in message
    assert newer_sha in message and "2095" in message
