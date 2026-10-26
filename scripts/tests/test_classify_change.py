"""Tests for the fail-closed health-cycle changed-path classifier."""

from __future__ import annotations

import hashlib
import re
import subprocess
import sys
from pathlib import Path

import pytest

from scripts.classify_change import (
    is_append_only_change,
    is_health_cycle_output,
    is_health_only_change,
    is_release_only_change,
)
from scripts.gen_dynamic_manifest_urls import SURFACE_PATHS


ROOT = Path(__file__).resolve().parents[2]
CLASSIFIER = ROOT / "scripts/classify_change.py"
GENERATOR = ROOT / "scripts/generate.sh"
RECEIPT_FIXTURE = ROOT / "scripts/tests/fixtures/health-branch-receipt-paths.txt"
DYNAMIC_URL_SURFACES = "changed dataset JSON envelopes, JSON-LD, passports, and website pages"
DYNAMIC_URL_HEALTH_PATHS = {"data/passports/sample.json", "docs/datasets/sample.html"}
DYNAMIC_URL_RELEASE_PATHS = {
    "data/json/sample.json",
    "data/jsonld/sample.json",
    "docs/okf/datasets/sample.md",
}


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

RELEASE_PATHS = (
    ".release-please-manifest.json",
    "CHANGELOG.md",
    "VERSION.txt",
    "server.json",
)


def test_release_only_change_requires_all_markers_and_accepts_release_extra_file() -> None:
    assert is_release_only_change(RELEASE_PATHS)
    assert is_release_only_change(RELEASE_PATHS[:3])
    assert _classify_cli(list(RELEASE_PATHS), ("--release-only",)).returncode == 0


@pytest.mark.parametrize(
    "paths",
    [
        (),
        ("VERSION.txt",),
        ("server.json",),
        (".release-please-manifest.json", "CHANGELOG.md"),
        (".release-please-manifest.json", "VERSION.txt"),
        ("CHANGELOG.md", "VERSION.txt"),
        (*RELEASE_PATHS, "scripts/classify_change.py"),
        (*RELEASE_PATHS, "health/latest.json"),
        (*RELEASE_PATHS, "../VERSION.txt"),
    ],
)
def test_release_only_change_rejects_missing_markers_and_foreign_paths(paths: tuple[str, ...]) -> None:
    assert not is_release_only_change(paths)
    assert _classify_cli(list(paths), ("--release-only",)).returncode != 0


def test_append_only_change_accepts_immutable_revision_and_chain_heads() -> None:
    assert is_append_only_change(APPEND_PATHS)
    assert is_append_only_change((APPEND_PATHS[0], APPEND_PATHS[7]))
    assert not is_health_only_change(APPEND_PATHS)


def test_append_only_change_accepts_gzipped_revision_health() -> None:
    gzipped_health = (
        "attestations/2026-10-26/revisions/"
        "1e2e5f0df6466afb96b09fa372f0a518788e0690979c34f3917ca1b22c93b8bc/health.json.gz"
    )
    assert is_append_only_change((APPEND_PATHS[0], gzipped_health))


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
        "attestations/2026-10-09/health.json.gz",
        "attestations/2026-10-09/revisions/not-a-digest/health.json.gz",
        f"attestations/2026-10-09/revisions/{REVISION}/health.txt.gz",
        f"attestations/2026-13-09/revisions/{REVISION}/health.json.gz",
        "data/health.json.gz",
        "docs/health.json.gz",
        "health/health.json.gz",
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
            if item == DYNAMIC_URL_SURFACES:
                # A health-cycle invocation can also write release-owned surfaces.
                # Expand the grouped prose and check both classes explicitly.
                surfaces = {template.format(id="sample") for template in SURFACE_PATHS}
                assert surfaces == DYNAMIC_URL_HEALTH_PATHS | DYNAMIC_URL_RELEASE_PATHS
                paths.extend(sorted(DYNAMIC_URL_HEALTH_PATHS))
                excluded.extend(sorted(DYNAMIC_URL_RELEASE_PATHS))
                continue
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
    paths, excluded = _declared_health_cycle_outputs()
    assert paths, "health-cycle outputs declaration is empty"
    rejected = [path for path in paths if not is_health_cycle_output(path)]
    assert rejected == [], f"declared health-cycle outputs rejected: {rejected}"
    assert DYNAMIC_URL_HEALTH_PATHS.issubset(paths)
    assert DYNAMIC_URL_RELEASE_PATHS.issubset(excluded)
    # The producer also regenerates the catalogue and dashboard. Manifest and
    # release-surface changes must still select full verification in both modes.
    for path in DYNAMIC_URL_RELEASE_PATHS | {
        "datapulse.json", "data/jsonld/catalog.json", "docs/index.html",
    }:
        assert not is_health_cycle_output(path), path
        for ci_artifact_profile in (False, True):
            assert not is_health_only_change(
                ("health/latest.json", path), ci_artifact_profile=ci_artifact_profile
            ), path


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


def _receipt_fixture_paths() -> list[str]:
    captured = RECEIPT_FIXTURE.read_bytes()
    assert hashlib.sha256(captured).hexdigest() == (
        "a340e8ea4fc8c4d0325fd0f8a630c037aa2ce9f779aedc1ffbf5b17bb948cd00"
    )
    return captured.decode("utf-8").splitlines()


def _classify_cli(paths: list[str], flags: tuple[str, ...]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(CLASSIFIER), *flags],
        input="\n".join(paths) + "\n",
        capture_output=True,
        text=True,
        check=False,
    )


@pytest.mark.parametrize("flags, expected", [((), 1), (("--ci-artifact-profile",), 0)])
def test_real_receipt_health_cycle_selects_only_ci_artifact_profile(
    flags: tuple[str, ...], expected: int
) -> None:
    result = _classify_cli(_receipt_fixture_paths(), flags)
    assert result.returncode == expected, result.stderr
    assert result.stderr == ""


@pytest.mark.parametrize("flags", [(), ("--ci-artifact-profile",)])
@pytest.mark.parametrize(
    "receipt_path",
    [
        "observation-receipts/days/.json",
        "observation-receipts/days/2026-10-10.json.bak",
        "observation-receipts/days/nested/2026-10-10.json",
        "observation-receipts/other.json",
        "observation-receipts/days/2026-02-30.json",
        "observation-receipts/days/../2026-10-10.json",
        "observation-receipts//chain_head.json",
    ],
)
def test_malformed_receipt_paths_are_refused_in_both_profiles(
    flags: tuple[str, ...], receipt_path: str
) -> None:
    result = _classify_cli(["health/latest.json", receipt_path], flags)
    assert result.returncode == 1, result.stderr
    assert result.stderr == ""


@pytest.mark.parametrize("flags", [(), ("--ci-artifact-profile",)])
def test_code_only_change_is_refused_in_both_profiles(flags: tuple[str, ...]) -> None:
    result = _classify_cli([".github/workflows/ci.yml", "scripts/gen_drift.py"], flags)
    assert result.returncode == 1, result.stderr
    assert result.stderr == ""


@pytest.mark.parametrize("flags", [(), ("--ci-artifact-profile",)])
@pytest.mark.parametrize("source_path", [".github/workflows/ci.yml", "scripts/gen_drift.py"])
def test_receipt_fixture_with_source_path_is_refused_in_both_profiles(
    flags: tuple[str, ...], source_path: str
) -> None:
    result = _classify_cli([*_receipt_fixture_paths(), source_path], flags)
    assert result.returncode == 1, result.stderr
    assert result.stderr == ""


@pytest.mark.parametrize(
    "paths, expected",
    [
        (["health/latest.json", "observation-receipts/chain_head.json"], 0),
        (["health/latest.json", "observation-receipts/days/2026-10-15.json"], 0),
        (["observation-receipts/chain_head.json"], 1),
        ([], 1),
        (["health/latest.json", "README.md", "observation-receipts/chain_head.json"], 1),
    ],
)
def test_ci_artifact_profile_preserves_required_health_context(
    paths: list[str], expected: int
) -> None:
    result = _classify_cli(paths, ("--ci-artifact-profile",))
    assert result.returncode == expected, result.stderr
    assert result.stderr == ""
