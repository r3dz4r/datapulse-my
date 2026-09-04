"""Regression tests for source-card probe-history verification."""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "verify_source_cards.py"
HISTORY = ROOT / "health" / "history.jsonl"
SKIP_NO_HISTORY = pytest.mark.skipif(
    not HISTORY.exists() or HISTORY.stat().st_size == 0,
    reason="health/history.jsonl unavailable (CI or freshly cloned worktree)",
)
CARDS = ROOT / "notes" / "source-cards"


def _run(cards_dir: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--cards-dir", str(cards_dir), "--history-path", str(HISTORY)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


def _copy_cards(tmp_path: Path) -> Path:
    destination = tmp_path / "source-cards"
    shutil.copytree(CARDS, destination)
    return destination


@SKIP_NO_HISTORY
def test_clean_state_passes() -> None:
    completed = _run(CARDS)
    assert completed.returncode == 0, completed.stderr


@SKIP_NO_HISTORY
def test_bnm_card_lying_about_status_fails(tmp_path: Path) -> None:
    cards = _copy_cards(tmp_path)
    path = cards / "bnm-open-api.md"
    path.write_text(
        path.read_text(encoding="utf-8").replace(
            '"affected_datasets":["bnm_base_rate"',
            '"affected_datasets":["bnm_base_rate_fresh"',
        ),
        encoding="utf-8",
    )
    completed = _run(cards)
    assert completed.returncode != 0
    assert "must list exactly the two HTTP-200-but-stale datasets" in completed.stderr


@SKIP_NO_HISTORY
def test_gtfs_card_missing_offpeak_quirk_fails(tmp_path: Path) -> None:
    cards = _copy_cards(tmp_path)
    path = cards / "gtfs-api.md"
    path.write_text(path.read_text(encoding="utf-8").replace("zero vehicles", "no vehicle data", 1), encoding="utf-8")
    completed = _run(cards)
    assert completed.returncode != 0
    assert "off-peak zero-vehicle" in completed.stderr


@SKIP_NO_HISTORY
def test_bnm_card_wrong_dataset_count_fails(tmp_path: Path) -> None:
    cards = _copy_cards(tmp_path)
    path = cards / "bnm-open-api.md"
    path.write_text(path.read_text(encoding="utf-8").replace('"datasets_in_family":8', '"datasets_in_family":7'), encoding="utf-8")
    completed = _run(cards)
    assert completed.returncode != 0
    assert "datasets_in_family=7" in completed.stderr


@SKIP_NO_HISTORY
def test_hansard_card_wrong_dataset_count_fails(tmp_path: Path) -> None:
    cards = _copy_cards(tmp_path)
    path = cards / "malaysia-parliament-digital-hansard.md"
    path.write_text(
        path.read_text(encoding="utf-8").replace('"datasets_in_family":3', '"datasets_in_family":2'),
        encoding="utf-8",
    )
    completed = _run(cards)
    assert completed.returncode != 0
    assert "Hansard datasets_in_family=2" in completed.stderr


@SKIP_NO_HISTORY
def test_hansard_card_wrong_recess_claim_fails(tmp_path: Path) -> None:
    cards = _copy_cards(tmp_path)
    path = cards / "malaysia-parliament-digital-hansard.md"
    path.write_text(
        path.read_text(encoding="utf-8").replace(
            '"affected_datasets":["hansard_sittings"',
            '"affected_datasets":["hansard_sittings_typo"',
        ),
        encoding="utf-8",
    )
    completed = _run(cards)
    assert completed.returncode != 0
    assert "Hansard known_false_positives" in completed.stderr
