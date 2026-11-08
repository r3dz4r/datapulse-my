#!/usr/bin/env python3
"""Missing profiles emit no passport; present profiles retain strict validation."""

from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path
from typing import Any

import pytest

from scripts.gen_dataset_passports import PassportError, generate
from scripts.gen_quality_profile import derive_snapshot


ROOT = Path(__file__).resolve().parents[2]
NOW = "2026-11-08T00:00:00Z"
# Captured from the unmodified generator using the fixed inputs below.
VALID_PASSPORT_SHA256 = "a11236e43a533108ab139e0ac3e31512890cd28a2836097175a563229439eaa1"


def _write(root: Path, path: str, value: dict[str, Any]) -> None:
    destination = root / path
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(value) + "\n", encoding="utf-8")


def _inputs(root: Path) -> dict[str, Any]:
    for schema in ("datapulse.schema.json", "health.schema.json", "passport.schema.json"):
        shutil.copyfile(ROOT / schema, root / schema)
    manifest = {
        "$schema": "https://www.data-pulse.my/datapulse.schema.json",
        "datasets": [
            {
                "id": dataset_id, "name": dataset_id,
                "source": "Example catalogue", "steward": "Example Steward",
                "custodian": "example-custodian",
                "url": f"https://example.test/{dataset_id}",
                "licence": "Creative Commons Attribution 4.0",
                "attribution": "Example Steward", "refresh_frequency": "daily",
                "expected_record_count": 12, "geo_coverage": "Malaysia",
                "health_report": f"data/{dataset_id}.md", "namespace": "other",
            }
            for dataset_id in ("air_pollution", "fuelprice")
        ],
    }
    snapshot = {
        "schema": "datapulse/v0.4/dataset-health", "checked_at": NOW,
        "_trust_summary": {
            "checked_at": NOW, "datasets_total": 2,
            "by_status": {
                "fresh": 2, "aging": 0, "stale": 0, "discontinued": 0,
                "degraded": 0, "browser_dependent": 0, "unreachable": 0,
                "unknown": 0, "unknown_freshness": 0, "reference": 0,
            },
        },
        "datasets": [
            {
                "dataset_id": row["id"], "last_checked": NOW,
                "url": row["url"], "status": "fresh", "http_status": 200,
                "record_count": 12,
            }
            for row in manifest["datasets"]
        ],
    }
    snapshot = derive_snapshot(manifest, snapshot)
    _write(root, "datapulse.json", manifest)
    _write(root, "health/latest.json", snapshot)
    _write(root, "catalog-graph.json", {"node_count": 2, "edges": []})
    _write(root, "attestations/latest/index.json", {"attestations": {}})
    return snapshot


@pytest.mark.parametrize("quick_test", [False, True])
def test_missing_profile_emits_no_passport_or_index_entry(tmp_path: Path, quick_test: bool) -> None:
    snapshot = _inputs(tmp_path)
    del snapshot["datasets"][0]["quality_profile"]
    _write(tmp_path, "health/latest.json", snapshot)

    output = tmp_path / "passports"
    assert generate(tmp_path, output, quick_test=quick_test) == 1
    assert sorted(path.name for path in output.iterdir()) == ["fuelprice.json", "index.json"]
    assert json.loads((output / "index.json").read_text(encoding="utf-8")) == {
        "schema": "datapulse/v1/dataset-passport-index",
        "dataset_count": 1, "dataset_ids": ["fuelprice"],
    }
    assert hashlib.sha256((output / "fuelprice.json").read_bytes()).hexdigest() == VALID_PASSPORT_SHA256


@pytest.mark.parametrize("profile", [None, False, "invalid", [], {}, {"profile_version": "wrong"}])
def test_present_malformed_profile_still_refuses(tmp_path: Path, profile: object) -> None:
    snapshot = _inputs(tmp_path)
    # An absent profile must not hide a malformed profile on another row.
    del snapshot["datasets"][0]["quality_profile"]
    snapshot["datasets"][1]["quality_profile"] = profile
    _write(tmp_path, "health/latest.json", snapshot)

    output = tmp_path / "passports"
    with pytest.raises(PassportError, match="health schema validation failed:"):
        generate(tmp_path, output)
    assert not output.exists()


def test_valid_profile_passport_bytes_match_base(tmp_path: Path) -> None:
    _inputs(tmp_path)
    output = tmp_path / "passports"
    assert generate(tmp_path, output) == 2
    expected = (output / "fuelprice.json").read_bytes()
    assert hashlib.sha256(expected).hexdigest() == VALID_PASSPORT_SHA256
    assert generate(tmp_path, output) == 2
    assert (output / "fuelprice.json").read_bytes() == expected
