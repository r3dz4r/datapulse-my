"""Tests for the fail-closed health-cycle changed-path classifier."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from scripts.classify_change import is_health_only_change


ROOT = Path(__file__).resolve().parents[2]
CLASSIFIER = ROOT / "scripts/classify_change.py"


def test_exact_health_cycle_outputs_require_latest_snapshot() -> None:
    assert is_health_only_change(
        (
            "health/latest.json",
            "health/history.jsonl",
            "health/history_daily.json",
            "health/trends.json",
            "health/drift.json",
            "health/reconciliation.json",
            "health/evidence-coverage.json",
            "deltas/2026-09-09T000000Z.json",
            "record-evidence/pharmaceutical_products/latest.json",
            "attestations/latest/binding.json",
            "attestations/latest/chain_head.json",
            "attestations/latest/index.json",
            "attestations/latest/scores.json",
            ".attestations/latest/2026-09-09.json",
            ".attestations/chain_head.json",
            "catalog-graph.json",
            "catalog-snapshot.json",
            "changelog.json",
            "feed.xml",
        )
    )
    assert not is_health_only_change(("health/trends.json",))


def test_actual_health_cycle_commit_d4cae64e6_is_health_only() -> None:
    assert is_health_only_change(
        (
            "attestations/latest/scores.json",
            "badges/exchangerates_daily_0900.svg",
            "badges/gtfs_realtime_mybas_johor.svg",
            "badges/gtfs_realtime_mybas_melaka.svg",
            "badges/gtfs_realtime_mybas_seremban_a.svg",
            "badges/sg_datagov_weather_readings.svg",
            "badges/status-degraded.svg",
            "badges/status-fresh.svg",
            "badges/status-stale.svg",
            "catalog-graph.json",
            "catalog-snapshot.json",
            "changelog.json",
            "feed.xml",
            "health/drift.json",
            "health/evidence-coverage.json",
            "health/history_daily.json",
            "health/latest.json",
            "health/reconciliation.json",
            "health/trends.json",
            "record-evidence/pharmaceutical_products/latest.json",
        )
    )


@pytest.mark.parametrize(
    "path",
    (
        "README.md",
        "datapulse.json",
        "scripts/generate.sh",
        ".github/workflows/ci.yml",
        "docs/index.html",
        "unknown/generated-output.json",
        "health/unrecognized.json",
        "data/pharmaceutical_products.md",
        "data/passports/pharmaceutical_products.json",
        "badges/status-fresh.txt",
        "badges/.svg",
        "badges/nested/status.svg",
        "deltas/nested/change.json",
        "deltas/change.json.txt",
        "deltas/.json",
        "record-evidence/pharmaceutical_products/nested/latest.json",
        "record-evidence/pharmaceutical_products/archive.json",
        "record-evidence/pharmaceutical_products/dated.json",
        "record-evidence/pharmaceutical_products/arbitrary.json",
        "attestations/latest/unrecognized.txt",
        ".attestations/latest/unrecognized.txt",
        ".attestations/latest/.json",
        ".attestations/latest/dated.txt.json.bak",
        "health/latest.json.bak",
        "health/../latest.json",
        "../health/latest.json",
        "health//latest.json",
    ),
)
def test_source_unknown_and_nested_paths_fail_closed(path: str) -> None:
    assert not is_health_only_change(("health/latest.json", path))


def test_cli_reads_newline_separated_paths_from_standard_input() -> None:
    result = subprocess.run(
        [sys.executable, str(CLASSIFIER)],
        input="health/latest.json\nrecord-evidence/pharmaceutical_products/latest.json\n",
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr


def test_cli_returns_source_mode_for_mixed_changes() -> None:
    result = subprocess.run(
        [sys.executable, str(CLASSIFIER)],
        input="health/latest.json\nREADME.md\n",
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 1
