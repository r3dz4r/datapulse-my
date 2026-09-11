"""Tests for the daily attestation commit-back decision."""

from __future__ import annotations

from scripts.attestation_commit_back import commit_message_for_changed_paths


def test_returns_commit_message_when_a_dated_envelope_changed() -> None:
    message = commit_message_for_changed_paths(
        (
            "attestations/2026-09-07/dataset-123.json",
            "attestations/latest/index.json",
            "attestations/chain-index.json",
            ".attestations/chain_head.json",
            "datapulse.json",
        ),
        "2026-09-07",
    )

    assert message == "chore(attestations): commit signed envelopes for 2026-09-07"


def test_returns_none_when_only_refreshed_aliases_changed() -> None:
    message = commit_message_for_changed_paths(
        (
            "attestations/latest/index.json",
            "attestations/chain-index.json",
            ".attestations/chain_head.json",
            "datapulse.json",
        ),
        "2026-09-07",
    )

    assert message is None


def test_returns_none_when_no_attestation_path_changed() -> None:
    assert commit_message_for_changed_paths(("README.md",), "2026-09-07") is None
