"""Read-only retention measurements against synthetic observation stores."""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
from observation_store import (  # noqa: E402
    blob_path,
    canonical_json,
    put_blob,
    put_envelope,
    put_normalized,
)

SCRIPT = ROOT / "scripts" / "observation_retention_dry_run.py"


def _snapshot(root: Path) -> dict[str, tuple[int, int, str]]:
    return {
        path.relative_to(root).as_posix(): (
            path.stat().st_size,
            path.stat().st_mtime_ns,
            hashlib.sha256(path.read_bytes()).hexdigest(),
        )
        for path in sorted(root.rglob("*")) if path.is_file()
    }


def _snapshot_hash(snapshot: dict[str, tuple[int, int, str]]) -> str:
    return hashlib.sha256(canonical_json(snapshot)).hexdigest()


def _run(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--store", str(root), *args],
        text=True, capture_output=True, check=False,
    )


def _file_envelope(
    root: Path, dataset: str, observation_id: str, observed_at: str,
    source_digest: str | None, normalized_digest: str | None = None,
) -> Path:
    projection = {"state": "retained" if normalized_digest else "not_retained",
                  "format": "json-array-of-objects" if normalized_digest else None,
                  "record_count": 1 if normalized_digest else None}
    provenance = {"normalized_projection": {
        "transform": f"observation_normalize profile x/v1; projection_digest {normalized_digest}"
        if normalized_digest else None,
    }}
    envelope: dict[str, Any] = {
        "schema": "historical-observation/v2",
        "dataset_id": dataset,
        "observation_id": observation_id,
        "observed_at": observed_at,
        "source_digest": source_digest,
        "normalized_projection": projection,
        "field_provenance": provenance,
        "replay_state": "replayable" if source_digest else "metadata_only",
    }
    return put_envelope(dataset, observation_id, envelope, root=root)


def test_report_is_read_only_deterministic_and_envelope_authoritative(tmp_path: Path) -> None:
    shared = put_blob(b"same raw source across vintages", root=tmp_path)
    old_only = put_blob(b"old raw source", root=tmp_path)
    orphan = put_blob(b"orphan raw object", root=tmp_path)
    normalized = put_normalized({"records": [1]}, root=tmp_path)
    _file_envelope(tmp_path, "fuelprice", "obs-old-shared", "2025-01-01T00:00:00Z",
                   shared, normalized)
    _file_envelope(tmp_path, "fuelprice", "obs-old-only", "2025-02-01T00:00:00Z",
                   old_only)
    _file_envelope(tmp_path, "fuelprice", "obs-new-shared", "2026-09-01T00:00:00Z",
                   shared, normalized)
    # The index is deliberately incomplete and must never be queried or rebuilt.
    index = tmp_path / "indexes" / "observations.sqlite"
    index.parent.mkdir()
    index.write_text("stale cache, deliberately not a SQLite database", encoding="utf-8")
    before = _snapshot(tmp_path)
    first = _run(tmp_path, "--cutoffs", "12", "--json")
    after = _snapshot(tmp_path)
    print(f"snapshot_hash_before={_snapshot_hash(before)}")
    print(f"snapshot_hash_after={_snapshot_hash(after)}")
    assert before == after
    assert first.returncode == 0, first.stderr
    assert first.stdout == _run(tmp_path, "--cutoffs", "12", "--json").stdout
    report = json.loads(first.stdout)
    assert report["valid_envelopes"] == 3
    assert report["integrity_defect_count"] == 0
    assert report["orphan_raw_digests"] == [orphan]
    candidate = report["candidates"][0]
    assert candidate["newly_unreferenced_raw_digests"] == [old_only]
    assert candidate["never_prunable_shared_raw_digests"] == [shared]
    assert candidate["never_prunable_shared_normalized_digests"] == [normalized]
    fuel = candidate["datasets"]["fuelprice"]
    assert fuel["vintages_pruned"] == 2
    assert fuel["vintages_retained"] == fuel["envelopes_left"] == 1
    assert fuel["pruned_observation_ids"] == ["obs-old-shared", "obs-old-only"]
    assert fuel["raw_bytes_freed"] == blob_path(old_only, root=tmp_path).stat().st_size
    assert fuel["normalized_bytes_freed"] == 0
    assert fuel["oldest_pruned_observed_at"] == "2025-01-01T00:00:00Z"
    assert fuel["newest_retained_observed_at"] == "2026-09-01T00:00:00Z"
    assert fuel["policy"]["retention_months"] == 24
    assert fuel["candidate_shorter_than_policy"] is True


def test_policy_absence_false_raw_and_raw_expiry_are_explicit(tmp_path: Path) -> None:
    no_policy = put_blob(b"unconfigured dataset source", root=tmp_path)
    old_raw = put_blob(b"expiry source", root=tmp_path)
    _file_envelope(tmp_path, "unconfigured", "obs-unknown-old", "2025-01-01T00:00:00Z",
                   no_policy)
    _file_envelope(tmp_path, "exchangerates_daily_1700", "obs-no-raw", "2025-01-01T00:00:00Z",
                   None)
    _file_envelope(tmp_path, "mbpp_weather_stations", "obs-expiring", "2026-01-01T00:00:00Z",
                   old_raw)
    _file_envelope(tmp_path, "mbpp_weather_stations", "obs-latest", "2026-09-01T00:00:00Z",
                   None)
    result = _run(tmp_path, "--cutoffs", "12", "--json")
    assert result.returncode == 0, result.stderr
    datasets = json.loads(result.stdout)["candidates"][0]["datasets"]
    assert datasets["unconfigured"]["policy"]["status"] == (
        "no policy — not permitted to archive"
    )
    assert datasets["exchangerates_daily_1700"]["raw_bytes_freed"] is None
    assert datasets["exchangerates_daily_1700"]["policy"]["capture_raw_bytes"] is False
    assert datasets["mbpp_weather_stations"]["policy"]["raw_bytes_expire_days"] == 90
    assert datasets["mbpp_weather_stations"]["retained_raw_refs_past_policy_expiry"] == 1
    assert datasets["mbpp_weather_stations"]["raw_expiry_conflicts_with_invariant"] is True


def test_normalized_digest_from_provenance_and_missing_digest_is_unknown(tmp_path: Path) -> None:
    old_projection = put_normalized({"old": True}, root=tmp_path)
    orphan_projection = put_normalized({"orphan": True}, root=tmp_path)
    _file_envelope(tmp_path, "fuelprice", "obs-old", "2025-01-01T00:00:00Z",
                   None, old_projection)
    _file_envelope(tmp_path, "fuelprice", "obs-new", "2026-09-01T00:00:00Z", None)
    result = _run(tmp_path, "--cutoffs", "12", "--json")
    assert result.returncode == 0, result.stderr
    report = json.loads(result.stdout)
    candidate = report["candidates"][0]
    assert candidate["newly_unreferenced_normalized_digests"] == [old_projection]
    assert candidate["datasets"]["fuelprice"]["normalized_bytes_freed"] > 0
    assert report["orphan_normalized_digests"] == [orphan_projection]
    old_path = tmp_path / "envelopes" / "fuelprice" / "2025" / "01" / "obs-old.json"
    envelope = json.loads(old_path.read_text(encoding="utf-8"))
    envelope["field_provenance"]["normalized_projection"]["transform"] = None
    old_path.write_text(json.dumps(envelope), encoding="utf-8")
    unknown = _run(tmp_path, "--cutoffs", "12", "--json")
    assert unknown.returncode == 0, unknown.stderr
    dataset = json.loads(unknown.stdout)["candidates"][0]["datasets"]["fuelprice"]
    assert dataset["normalized_bytes_unknown"] is True
    assert dataset["normalized_bytes_freed"] is None


def test_shared_pruned_bytes_are_counted_once_globally(tmp_path: Path) -> None:
    shared = put_blob(b"two datasets cite this source", root=tmp_path)
    _file_envelope(tmp_path, "fuelprice", "obs-old", "2025-01-01T00:00:00Z", shared)
    _file_envelope(tmp_path, "mbpp_weather_stations", "obs-other-old",
                   "2025-01-01T00:00:00Z", shared)
    _file_envelope(tmp_path, "fuelprice", "obs-new", "2026-09-01T00:00:00Z", None)
    result = _run(tmp_path, "--cutoffs", "12", "--json")
    assert result.returncode == 0, result.stderr
    candidate = json.loads(result.stdout)["candidates"][0]
    assert candidate["raw_bytes_freed_all_datasets"] == blob_path(
        shared, root=tmp_path
    ).stat().st_size
    assert candidate["datasets"]["fuelprice"]["raw_bytes_freed"] == 0
    assert candidate["datasets"]["mbpp_weather_stations"]["raw_bytes_freed"] == 0


@pytest.mark.parametrize("args,reason", [
    (["--store", "relative"], "absolute path"),
    (["--store", "/definitely/missing/observation/store"], "does not exist"),
])
def test_invalid_root_is_refused(args: list[str], reason: str) -> None:
    result = subprocess.run(
        [sys.executable, str(SCRIPT), *args], text=True, capture_output=True, check=False,
    )
    assert result.returncode == 2
    assert reason in result.stderr


def test_missing_envelopes_directory_and_invalid_cutoffs_are_refused(tmp_path: Path) -> None:
    missing = _run(tmp_path)
    assert missing.returncode == 2
    assert "no envelopes/ directory" in missing.stderr
    (tmp_path / "envelopes").mkdir()
    invalid = _run(tmp_path, "--cutoffs", "12,zero")
    assert invalid.returncode == 2
    assert "positive integer months" in invalid.stderr


@pytest.mark.parametrize("defect", ["missing_id", "misfiled_date", "malformed_digest",
                                    "malformed_projection_digest", "unreadable_json",
                                    "missing_blob"])
def test_integrity_defect_is_named_and_exits_three(tmp_path: Path, defect: str) -> None:
    raw = put_blob(b"old source", root=tmp_path)
    path = _file_envelope(tmp_path, "fuelprice", "obs-old", "2025-01-01T00:00:00Z", raw)
    _file_envelope(tmp_path, "fuelprice", "obs-new", "2026-09-01T00:00:00Z", None)
    if defect == "missing_blob":
        blob_path(raw, root=tmp_path).unlink()
    else:
        envelope = json.loads(path.read_text(encoding="utf-8"))
        if defect == "missing_id":
            del envelope["observation_id"]
        elif defect == "misfiled_date":
            envelope["observed_at"] = "2026-01-01T00:00:00Z"
        elif defect == "malformed_digest":
            envelope["source_digest"] = "sha256:NOT-LOWERCASE"
        elif defect == "malformed_projection_digest":
            envelope["normalized_projection"]["state"] = "retained"
            envelope["field_provenance"]["normalized_projection"]["transform"] = (
                "observation_normalize profile x/v1; projection_digest sha256:BAD"
            )
        if defect == "unreadable_json":
            path.write_text("{broken", encoding="utf-8")
        else:
            path.write_text(json.dumps(envelope), encoding="utf-8")
    result = _run(tmp_path, "--cutoffs", "12", "--json")
    assert result.returncode == 3, result.stderr
    report = json.loads(result.stdout)
    assert report["integrity_defect_count"] == 1
    assert "obs-old.json" in report["integrity_defects"][0]
    assert report["candidates"][0]["safe_to_consider_removal"] is False
    assert report["candidates"][0]["newly_unreferenced_raw_digests"] == []


def test_text_output_and_default_cutoffs(tmp_path: Path) -> None:
    (tmp_path / "envelopes").mkdir()
    result = _run(tmp_path)
    assert result.returncode == 0, result.stderr
    assert "Safety invariant: A blob may never be removed" in result.stdout
    for months in (24, 12, 6, 3):
        assert f"Cutoff {months} months:" in result.stdout
