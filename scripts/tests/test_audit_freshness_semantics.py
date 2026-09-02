"""Tests for the read-only catalogue freshness-semantics audit."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
AUDIT_SCRIPT = ROOT / "scripts/audit_freshness_semantics.py"


def _policy(family: str, **overrides: object) -> dict[str, object]:
    policy: dict[str, object] = {
        "family": family,
        "content_date_field": "date",
        "interpretation": "observation_period",
        "discontinued_on_404": True,
        "reference_table": False,
        "notes": "fixture",
    }
    policy.update(overrides)
    return policy


def _write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value) + "\n", encoding="utf-8")


def _run(manifest_path: Path, health_path: Path) -> dict[str, object]:
    completed = subprocess.run(
        [
            sys.executable,
            str(AUDIT_SCRIPT),
            "--manifest",
            str(manifest_path),
            "--health",
            str(health_path),
            "--json",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    return json.loads(completed.stdout)


def test_audit_reports_source_policy_aware_and_remaining_counts(tmp_path: Path) -> None:
    manifest = {
        "datasets": [
            {
                "id": "openapi_retired",
                "refresh_frequency": "annual",
                "freshness_policy": _policy("data_gov_my_openapi"),
            },
            {
                "id": "dosm_obs",
                "refresh_frequency": "annual",
                "freshness_policy": _policy("dosm_via_data_gov_my"),
            },
            {
                "id": "lookup_tbl",
                "refresh_frequency": "as-required",
                "freshness_policy": _policy("data_gov_my_archive", reference_table=True),
            },
            {"id": "ref_row", "data_type": "reference", "refresh_frequency": "annual"},
            {"id": "plain", "refresh_frequency": "annual"},
        ]
    }
    health = {
        "checked_at": "2026-09-02T00:00:00Z",
        "datasets": [
            {
                "dataset_id": "openapi_retired",
                "status": "stale",
                "http_status": 200,
                "content_freshness_date": "2020-01-01",
            },
            {
                "dataset_id": "dosm_obs",
                "status": "stale",
                "http_status": 200,
                "content_freshness_date": "2024-01-01",
            },
            {"dataset_id": "lookup_tbl", "status": "stale", "http_status": 200},
            {"dataset_id": "ref_row", "status": "stale", "http_status": 200},
            {"dataset_id": "plain", "status": "stale", "http_status": 200},
        ],
    }
    manifest_path = tmp_path / "manifest.json"
    health_path = tmp_path / "health.json"
    _write_json(manifest_path, manifest)
    _write_json(health_path, health)

    report = _run(manifest_path, health_path)

    assert report["schema"] == "datapulse/freshness-semantics-audit/v1"
    assert report["datasets_total"] == 5
    assert report["typed_datasets"] == 2
    assert report["untyped_datasets"] == 3
    assert report["untyped_stale_candidates"]["count"] == 3
    assert report["untyped_stale_candidates"]["dataset_ids"] == [
        "dosm_obs",
        "openapi_retired",
        "plain",
    ]
    aware = report["source_policy_aware_candidates"]
    assert aware["count"] == 2
    reasons = {entry["dataset_id"]: entry["reason"] for entry in aware["entries"]}
    assert reasons == {
        "openapi_retired": "publisher-likely-retired",
        "dosm_obs": "observation-period-staleness",
    }
    assert report["remaining_unambiguous_candidates"] == {
        "count": 1,
        "dataset_ids": ["plain"],
    }


def test_audit_discontinued_on_404_reason(tmp_path: Path) -> None:
    manifest = {
        "datasets": [
            {
                "id": "gone",
                "refresh_frequency": "annual",
                "freshness_policy": _policy("data_gov_my_openapi"),
            }
        ]
    }
    health = {
        "checked_at": "2026-09-02T00:00:00Z",
        "datasets": [
            {"dataset_id": "gone", "status": "stale", "http_status": 404},
        ],
    }
    manifest_path = tmp_path / "manifest.json"
    health_path = tmp_path / "health.json"
    _write_json(manifest_path, manifest)
    _write_json(health_path, health)

    report = _run(manifest_path, health_path)

    aware = report["source_policy_aware_candidates"]
    assert aware["count"] == 1
    assert aware["entries"][0] == {
        "dataset_id": "gone",
        "family": "data_gov_my_openapi",
        "reason": "discontinued-on-404",
    }


def test_audit_rejects_manifest_health_id_mismatch(tmp_path: Path) -> None:
    manifest_path = tmp_path / "manifest.json"
    health_path = tmp_path / "health.json"
    _write_json(manifest_path, {"datasets": [{"id": "manifest-only"}]})
    _write_json(health_path, {"datasets": [{"dataset_id": "health-only", "status": "fresh"}]})

    completed = subprocess.run(
        [
            sys.executable,
            str(AUDIT_SCRIPT),
            "--manifest",
            str(manifest_path),
            "--health",
            str(health_path),
            "--json",
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 1
    assert "dataset ID mismatch" in completed.stderr


def test_audit_excludes_as_required_and_reference_from_candidates(tmp_path: Path) -> None:
    manifest = {
        "datasets": [
            {"id": "ref", "data_type": "reference", "refresh_frequency": "annual"},
            {"id": "asreq", "refresh_frequency": "as-required"},
            {"id": "candidate", "refresh_frequency": "annual"},
        ]
    }
    health = {
        "datasets": [
            {"dataset_id": "ref", "status": "stale"},
            {"dataset_id": "asreq", "status": "stale"},
            {"dataset_id": "candidate", "status": "stale"},
        ]
    }
    manifest_path = tmp_path / "manifest.json"
    health_path = tmp_path / "health.json"
    _write_json(manifest_path, manifest)
    _write_json(health_path, health)

    report = _run(manifest_path, health_path)

    assert report["untyped_stale_candidates"] == {
        "count": 1,
        "dataset_ids": ["candidate"],
    }
