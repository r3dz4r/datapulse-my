"""Tests for the fail-closed health-cycle changed-path classifier."""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import pytest

from scripts.classify_change import is_append_only_change, is_health_cycle_output, is_health_only_change


ROOT = Path(__file__).resolve().parents[2]
CLASSIFIER = ROOT / "scripts/classify_change.py"
GENERATOR = ROOT / "scripts/generate.sh"


REVISION = "a" * 64
APPEND_PATHS = (
    ".attestations/chain_head.json",
    "attestations/chain-index.json",
    "attestations/latest/binding.json",
    "attestations/latest/chain_head.json",
    "attestations/latest/index.json",
    "attestations/latest/scores.json",
    "attestations/2026-10-09/chain_head.json",
    f"attestations/2026-10-09/revisions/{REVISION}/chain_head.json",
    f"attestations/2026-10-09/revisions/{REVISION}/binding.json",
    f"attestations/rekor/2026-10-09/health.{REVISION}.sigstore.bundle.json",
    f"attestations/rekor/2026-10-09/health.{REVISION}.statement.json",
    f"attestations/rekor/2026-10-09/reference.{REVISION}.json",
)


def test_append_only_change_accepts_immutable_revision_and_chain_heads() -> None:
    assert is_append_only_change(APPEND_PATHS)
    assert is_append_only_change((APPEND_PATHS[0], APPEND_PATHS[7]))
    assert not is_health_only_change(APPEND_PATHS)


@pytest.mark.parametrize(
    "outside_path",
    (
        "README.md",
        "health/latest.json",
        "attestations/2026-10-09/index.json",
        "attestations/2026-13-09/chain_head.json",
        f"attestations/2026-10-09/revisions/{REVISION}/nested/binding.json",
        "attestations/2026-10-09/revisions/not-a-digest/binding.json",
        "attestations/2026-10-09/revisions/../binding.json",
        "attestations/rekor/2026-10-09/reference.json",
        f"attestations/rekor/2026-10-09/arbitrary.{REVISION}.json",
    ),
)
def test_append_only_change_rejects_any_path_outside_append_class(outside_path: str) -> None:
    assert not is_append_only_change((APPEND_PATHS[0], outside_path))


def test_append_only_change_rejects_empty_input() -> None:
    assert not is_append_only_change(())


def test_append_only_cli_preserves_default_health_classifier() -> None:
    paths = ".attestations/chain_head.json\n" + APPEND_PATHS[2] + "\n"
    append = subprocess.run(
        [sys.executable, str(CLASSIFIER), "--append-only"],
        input=paths,
        text=True,
        capture_output=True,
    )
    health = subprocess.run(
        [sys.executable, str(CLASSIFIER)],
        input=paths,
        text=True,
        capture_output=True,
    )
    assert append.returncode == 0, append.stderr
    assert health.returncode == 1


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


def test_actual_health_cycle_commit_6efbf606b_is_health_only() -> None:
    assert is_health_only_change(
        (
            "attestations/latest/scores.json",
            "badges/gtfs_realtime_mybas_ipoh.svg",
            "badges/gtfs_realtime_mybas_johor.svg",
            "badges/gtfs_realtime_mybas_melaka.svg",
            "badges/gtfs_realtime_prasarana_bus_kl.svg",
            "badges/status-aging.svg",
            "badges/status-stale.svg",
            "catalog-graph.json",
            "catalog-snapshot.json",
            "changelog.json",
            "data/passports/doe_apims.json",
            "data/passports/doe_rqims.json",
            "data/passports/eperolehan-diklankan.json",
            "data/passports/gtfs_realtime_ktmb.json",
            "data/passports/gtfs_realtime_mybas_alor_setar.json",
            "data/passports/gtfs_realtime_mybas_ipoh.json",
            "data/passports/gtfs_realtime_mybas_johor.json",
            "data/passports/gtfs_realtime_mybas_kangar.json",
            "data/passports/gtfs_realtime_mybas_kota_bharu.json",
            "data/passports/gtfs_realtime_mybas_kuala_terengganu.json",
            "data/passports/gtfs_realtime_mybas_kuching.json",
            "data/passports/gtfs_realtime_mybas_melaka.json",
            "data/passports/gtfs_realtime_mybas_seremban_a.json",
            "data/passports/gtfs_realtime_mybas_seremban_b.json",
            "data/passports/gtfs_realtime_prasarana_bus_kl.json",
            "data/passports/gtfs_realtime_prasarana_bus_mrtfeeder.json",
            "data/passports/gtfs_realtime_prasarana_bus_penang.json",
            "data/passports/mbpp_weather_stations.json",
            "datapulse_summary.json",
            "feed.xml",
            "health/drift.json",
            "health/evidence-coverage.json",
            "health/latest.json",
            "health/reconciliation.json",
            "health/trends.json",
            "record-evidence/pharmaceutical_products/latest.json",
        )
    )


def test_dataset_passports_are_health_cycle_outputs() -> None:
    assert is_health_only_change(("health/latest.json", "data/passports/x.json"))


def test_dataset_page_with_latest_snapshot_is_health_only() -> None:
    assert is_health_only_change(
        ("docs/datasets/cosmetic_notifications.html", "health/latest.json")
    )


def test_dataset_page_without_latest_snapshot_is_not_health_only() -> None:
    assert not is_health_only_change(("docs/datasets/cosmetic_notifications.html",))


def test_generated_outputs_without_latest_snapshot_are_not_health_only() -> None:
    assert not is_health_only_change(("datapulse_summary.json",))
    assert not is_health_only_change(("data/passports/x.json",))


def test_mixed_source_and_passport_outputs_fail_closed() -> None:
    assert not is_health_only_change(
        ("datapulse.json", "health/latest.json", "data/passports/x.json")
    )


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


def _declared_health_cycle_outputs() -> tuple[list[str], list[str]]:
    script = GENERATOR.read_text(encoding="utf-8")
    health_cycle = script.split('case "$profile" in', 1)[1].split("  release-build)", 1)[0]
    match = re.search(r"(?ms)^\s*outputs=\(\s*\n(.*?)^\s*\)", health_cycle)
    assert match is not None, "health-cycle outputs declaration missing"

    paths: list[str] = []
    excluded: list[str] = []
    placeholder_values = {
        "id": "sample",
        "cycle": "cycle",
        "vertical-id": "sample",
        "run-date": "2026-10-10",
        "date": "2026-10-10",
    }
    for line in match.group(1).splitlines():
        declaration = re.fullmatch(r'\s*"([^"]+)"\s*', line)
        assert declaration is not None, f"unparsed health-cycle output: {line}"
        for item in declaration.group(1).split("; "):
            item = re.sub(r" \([^)]*\)$", "", item)
            # These are release-profile paths, append-only artifacts, or a broad wildcard.
            if (
                item in {"data/<id>.md", "README.md", "attestations/latest/*"}
                or item.startswith("attestations/<date>/")
                or item.startswith("append-only chain-index entries")
                or item.startswith("datapulse.json ")
            ):
                excluded.append(item)
                continue
            path = re.sub(
                r"<([^>]+)>", lambda match: placeholder_values[match.group(1)], item
            ).replace("*", "sample")
            paths.append(path)

    return paths, excluded


def test_declared_health_cycle_outputs_are_classified() -> None:
    paths, _ = _declared_health_cycle_outputs()
    assert paths, "health-cycle outputs declaration is empty"
    rejected = [path for path in paths if not is_health_cycle_output(path)]
    assert rejected == [], f"declared health-cycle outputs rejected: {rejected}"


@pytest.mark.parametrize(
    "path",
    (
        "README.md",
        "datapulse.json",
        "scripts/generate.sh",
        ".github/workflows/ci.yml",
        "docs/index.html",
        "docs/datasets/x.json",
        "docs/datasets/x/cosmetic_notifications.html",
        "docs/datasets/.html",
        "docs/datasets/x.bad.html",
        "unknown/generated-output.json",
        "health/unrecognized.json",
        "data/pharmaceutical_products.md",
        "data/passports/nested/deep.json",
        "data/passports/index.txt",
        "data/passports",
        "data/other/x.json",
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
        "record-evidence/pharmaceutical_products/2026-10-10.json.bak",
        "record-evidence/pharmaceutical_products/nested/2026-10-10.json",
        "observation-receipts/days/.json",
        "observation-receipts/days/2026-10-10.json.bak",
        "observation-receipts/days/nested/2026-10-10.json",
        "observation-receipts/other.json",
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
