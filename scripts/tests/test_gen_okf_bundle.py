"""Regression tests for the deterministic OKF v0.2 bundle generator."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime
from pathlib import Path

import pytest
import yaml

from scripts.gen_okf_bundle import cadence_stale_after, generate


ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "scripts/tests/fixtures/okf"


def _files(root: Path) -> dict[Path, bytes]:
    return {path.relative_to(root): path.read_bytes() for path in sorted(root.rglob("*")) if path.is_file()}


def _generate(output: Path) -> None:
    generate(
        FIXTURE / "manifest.json",
        FIXTURE / "health.json",
        FIXTURE / "changelog.json",
        output,
    )


def _frontmatter(path: Path) -> dict[str, object] | None:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        return None
    _, raw, _ = text.split("---\n", 2)
    value = yaml.safe_load(raw)
    assert isinstance(value, dict)
    return value


def _timestamps(value: object, key: str = "") -> list[str]:
    if isinstance(value, dict):
        return [timestamp for child_key, child_value in value.items() for timestamp in _timestamps(child_value, str(child_key))]
    if isinstance(value, list):
        return [timestamp for child in value for timestamp in _timestamps(child, key)]
    return [value] if key in {"at", "stale_after", "last_modified"} and isinstance(value, str) else []


def test_matches_golden_fixture(tmp_path: Path) -> None:
    output = tmp_path / "okf"
    _generate(output)

    assert _files(output) == _files(FIXTURE / "expected")


def test_every_concept_is_conformant_and_indexes_follow_okf_rules(tmp_path: Path) -> None:
    output = tmp_path / "okf"
    _generate(output)
    manifest = json.loads((FIXTURE / "manifest.json").read_text(encoding="utf-8"))

    root_index = _frontmatter(output / "index.md")
    assert root_index == {"okf_version": "0.2"}
    for path in (output / "agencies").rglob("index.md"):
        assert _frontmatter(path) is None
    assert _frontmatter(output / "datasets/index.md") is None
    assert _frontmatter(output / "computations/index.md") is None

    concepts = [*sorted((output / "datasets").glob("*.md")), *sorted((output / "computations").glob("*.md"))]
    assert len(list((output / "datasets").glob("*.md"))) - 1 == len(manifest["datasets"])
    for path in concepts:
        if path.name == "index.md":
            continue
        frontmatter = _frontmatter(path)
        assert frontmatter is not None
        assert frontmatter["type"] in {"Dataset", "Attested Computation"}
        assert isinstance(frontmatter.get("verified"), list)
        for timestamp in _timestamps(frontmatter):
            assert timestamp.endswith("Z")


def test_two_runs_are_byte_identical(tmp_path: Path) -> None:
    first = tmp_path / "first"
    second = tmp_path / "second"
    _generate(first)
    _generate(second)

    assert _files(first) == _files(second)


def test_fixed_reference_staleness_direction_matches_health_status(tmp_path: Path) -> None:
    output = tmp_path / "okf"
    _generate(output)
    fixed_reference = datetime.fromisoformat("2026-09-01T12:00:00+00:00")
    health = {row["dataset_id"]: row for row in json.loads((FIXTURE / "health.json").read_text(encoding="utf-8"))["datasets"]}
    for path in (output / "datasets").glob("*.md"):
        if path.name == "index.md":
            continue
        frontmatter = _frontmatter(path)
        assert frontmatter is not None
        stale_after = frontmatter.get("stale_after")
        if stale_after is None:
            continue
        status = health[path.stem]["status"]
        instant = datetime.fromisoformat(str(stale_after).replace("Z", "+00:00"))
        if status in {"fresh", "aging"}:
            assert instant > fixed_reference
        elif status == "stale":
            assert instant <= fixed_reference


def test_computation_sources_are_pinned_by_content_digest(tmp_path: Path) -> None:
    output = tmp_path / "okf"
    _generate(output)

    concepts = [path for path in sorted((output / "computations").glob("*.md")) if path.name != "index.md"]
    assert len(concepts) >= 2
    for path in concepts:
        frontmatter = _frontmatter(path)
        assert frontmatter is not None
        sources = frontmatter["sources"]
        assert isinstance(sources, list)
        assert len(sources) == 3
        digests: list[str] = []
        for entry in sources:
            assert isinstance(entry, dict)
            digest = entry.get("digest")
            resource = entry.get("resource")
            assert isinstance(digest, str)
            assert isinstance(resource, str)
            assert re.fullmatch(r"sha256:[0-9a-f]{64}", digest)
            # Independent recomputation catches hashing the wrong file,
            # hashing the resource string instead of its bytes, or switching
            # algorithm. Sensitivity -- the digest actually moving when a
            # closure script changes -- is gated by the golden fixture
            # comparison in test_matches_golden_fixture, not by this
            # recomputation, which is why both gates exist.
            expected = "sha256:" + hashlib.sha256((ROOT / resource).read_bytes()).hexdigest()
            assert digest == expected
            digests.append(digest)
        # A copy-paste that stamps one file's digest onto all three entries
        # would otherwise pass recomputation.
        assert len(set(digests)) > 1


@pytest.mark.parametrize(
    ("frequency", "expected", "basis"),
    [
        ("30 seconds", "2026-01-01T00:10:00Z", "realtime"),
        ("hourly", "2026-01-02T12:00:00Z", "cadence"),
        ("daily", "2026-01-02T12:00:00Z", "cadence"),
        ("daily (weekdays)", "2026-01-02T00:00:00Z", "weekday_cadence"),
        ("daily (weekdays, 0900 MYT)", "2026-01-02T00:00:00Z", "weekday_cadence"),
        ("daily (weekdays, 1130 MYT)", "2026-01-02T00:00:00Z", "weekday_cadence"),
        ("daily (weekdays, 1200 MYT)", "2026-01-02T00:00:00Z", "weekday_cadence"),
        ("daily (weekdays, 1700 MYT)", "2026-01-02T00:00:00Z", "weekday_cadence"),
        ("weekly", "2026-01-11T12:00:00Z", "cadence"),
        ("monthly", "2026-02-16T12:00:00Z", "cadence"),
        ("quarterly", "2026-05-19T00:00:00Z", "cadence"),
        ("annual", "2027-07-02T12:00:00Z", "cadence"),
        ("biennial to triennial (survey years)", "2030-07-01T12:00:00Z", "cadence"),
        ("as-required", "2026-05-16T00:00:00Z", "default_90d"),
        (None, "2026-05-16T00:00:00Z", "default_90d"),
        ("unknown", "2026-05-16T00:00:00Z", "default_90d"),
    ],
)
def test_cadence_normalization_table(frequency: str | None, expected: str, basis: str) -> None:
    stale_after, actual_basis = cadence_stale_after(frequency, "2026-01-01", "2026-01-01T00:00:00Z")

    assert (stale_after, actual_basis) == (expected, basis)


def test_weekday_daily_rolls_a_weekend_deadline_to_monday() -> None:
    stale_after, basis = cadence_stale_after("daily (weekdays)", "2026-01-02", "2026-01-02T00:00:00Z")

    assert (stale_after, basis) == ("2026-01-05T00:00:00Z", "weekday_cadence")
