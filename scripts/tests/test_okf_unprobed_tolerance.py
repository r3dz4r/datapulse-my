"""The OKF generator emits an explicitly unprobed dataset without inventing freshness."""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

import pytest
import yaml

from scripts.gen_okf_bundle import OkfBundleError, generate, render_bundle


ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "scripts/tests/fixtures/okf"
# The realtime row is the sharpest case: its cadence derives stale_after from
# last_checked, so any fallback would have to fabricate a probe time.
UNPROBED_ID = "realtime_sample"


def _load(name: str) -> dict[str, Any]:
    value = json.loads((FIXTURE / name).read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def _unprobed_health() -> dict[str, Any]:
    health = _load("health.json")
    for index, row in enumerate(health["datasets"]):
        if row["dataset_id"] == UNPROBED_ID:
            health["datasets"][index] = {
                "dataset_id": UNPROBED_ID,
                "last_checked": None,
                "url": row["url"],
                "status": "unknown-freshness",
                "message": "Not probed; provisional onboarding status.",
            }
            return health
    raise AssertionError(f"fixture has no {UNPROBED_ID} row")


def _frontmatter(text: str) -> dict[str, object]:
    _, raw, _ = text.split("---\n", 2)
    value = yaml.safe_load(raw)
    assert isinstance(value, dict)
    return value


def _row(health: dict[str, Any], identifier: str) -> dict[str, Any]:
    return next(row for row in health["datasets"] if row["dataset_id"] == identifier)


def test_generator_completes_and_emits_the_unprobed_dataset(tmp_path: Path) -> None:
    health_path = tmp_path / "health.json"
    health_path.write_text(json.dumps(_unprobed_health()), encoding="utf-8")
    output = tmp_path / "okf"

    files = generate(FIXTURE / "manifest.json", health_path, FIXTURE / "changelog.json", output)

    concept = output / "datasets" / f"{UNPROBED_ID}.md"
    assert concept.is_file()
    assert Path("datasets") / f"{UNPROBED_ID}.md" in files
    assert f"({UNPROBED_ID}.md)" in (output / "datasets/index.md").read_text(encoding="utf-8")


def test_unprobed_concept_carries_no_fabricated_freshness(tmp_path: Path) -> None:
    health = _unprobed_health()
    files = render_bundle(_load("manifest.json"), health, _load("changelog.json"))
    text = files[Path("datasets") / f"{UNPROBED_ID}.md"]
    frontmatter = _frontmatter(text)

    assert "stale_after" not in frontmatter
    assert "datapulse:stale_after_basis" not in frontmatter
    assert frontmatter["verified"] == []
    assert frontmatter["datapulse:real_status"] == "unknown-freshness"
    assert frontmatter["datapulse:probe_state"] == "unprobed"
    # generated.at may only come from an observed source: the manifest's
    # lifecycle verification date for this fixture entry.
    assert frontmatter["generated"] == {"by": "process:datapulse-pipeline", "at": "2026-09-01T00:00:00Z"}
    assert "last_modified" not in frontmatter["sources"][0]
    assert "onboarded but not yet probed" in text.split("# Health", 1)[1]


def test_unprobed_concept_without_manifest_verification_uses_the_snapshot_time() -> None:
    manifest = _load("manifest.json")
    for entry in manifest["datasets"]:
        if entry["id"] == UNPROBED_ID:
            entry.pop("verified_at", None)
    health = _unprobed_health()

    files = render_bundle(manifest, health, _load("changelog.json"))
    frontmatter = _frontmatter(files[Path("datasets") / f"{UNPROBED_ID}.md"])

    assert frontmatter["generated"]["at"] == health["checked_at"].replace("+00:00", "Z")
    assert "stale_after" not in frontmatter


def test_probed_rows_are_unchanged_by_the_unprobed_neighbour() -> None:
    baseline = render_bundle(_load("manifest.json"), _load("health.json"), _load("changelog.json"))
    tolerant = render_bundle(_load("manifest.json"), _unprobed_health(), _load("changelog.json"))

    for identifier in ("daily_sample", "stale_sample"):
        path = Path("datasets") / f"{identifier}.md"
        assert tolerant[path] == baseline[path]


def test_missing_last_checked_key_still_fails(tmp_path: Path) -> None:
    health = _unprobed_health()
    del _row(health, UNPROBED_ID)["last_checked"]

    with pytest.raises(OkfBundleError, match="missing last_checked"):
        render_bundle(_load("manifest.json"), health, _load("changelog.json"))

    health_path = tmp_path / "health.json"
    health_path.write_text(json.dumps(health), encoding="utf-8")
    with pytest.raises(OkfBundleError):
        generate(FIXTURE / "manifest.json", health_path, FIXTURE / "changelog.json", None)


@pytest.mark.parametrize("status", ["fresh", "stale", "reference", "discontinued"])
def test_null_last_checked_with_another_status_still_fails(tmp_path: Path, status: str) -> None:
    health = copy.deepcopy(_unprobed_health())
    _row(health, UNPROBED_ID)["status"] = status

    with pytest.raises(OkfBundleError, match=f"health last_checked for {UNPROBED_ID}"):
        render_bundle(_load("manifest.json"), health, _load("changelog.json"))

    health_path = tmp_path / "health.json"
    health_path.write_text(json.dumps(health), encoding="utf-8")
    with pytest.raises(OkfBundleError):
        generate(FIXTURE / "manifest.json", health_path, FIXTURE / "changelog.json", None)
