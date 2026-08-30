"""Tests for deterministic per-dataset Sigstore receipt statements."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from scripts.gen_per_dataset_receipt import (
    PREDICATE_TYPE,
    StatementError,
    canonical_evidence_row,
    generate_receipts,
    statement_bytes,
)


def _inputs(tmp_path: Path) -> tuple[Path, Path, Path]:
    health = tmp_path / "health/latest.json"
    manifest = tmp_path / "datapulse.json"
    data = tmp_path / "data"
    health.parent.mkdir(parents=True)
    health.write_text(json.dumps({
        "schema": "datapulse/v0.4/dataset-health",
        "checked_at": "2026-08-30T02:16:30Z",
        "_trust_summary": {},
        "datasets": [
            {"dataset_id": identifier, "last_checked": "2026-08-30T02:16:30Z", "status": "fresh", "message": "HTTP 200", "request_url": "https://example.test/data", "access_method": "direct", "http_status": 200, "content_length": 1, "last_modified": None, "content_freshness_date": "2026-08-29", "first_record_timestamp": "2026-08-01", "record_count": 1, "record_count_within_tolerance": True, "freshness_signal": "content-date-parse", "freshness_signal_source": "content_date_parse"}
            for identifier in ("fuelprice", "cpi_3d", "dosm_lfs_month", "other")
        ],
    }), encoding="utf-8")
    manifest.write_text(json.dumps({"datasets": [
        {"id": identifier, "licence": "Open Government Licence (Malaysia)"}
        for identifier in ("fuelprice", "cpi_3d", "dosm_lfs_month", "other")
    ]}), encoding="utf-8")
    return health, manifest, data


def test_quick_receipts_bind_the_canonical_evidence_row(tmp_path: Path) -> None:
    health, manifest, data = _inputs(tmp_path)

    generated = generate_receipts(health, manifest, data, quick_test=True)

    assert generated == ["cpi_3d", "dosm_lfs_month", "fuelprice"]
    statement = json.loads((data / "fuelprice.receipt.statement.json").read_text())
    row = json.loads((data / "fuelprice.receipt.evidence.json").read_text())
    assert statement["predicateType"] == PREDICATE_TYPE
    assert statement["predicate"]["health"] == row
    assert statement["subject"] == [{
        "name": "data/fuelprice.receipt.evidence.json",
        "digest": {"sha256": hashlib.sha256(statement_bytes(row)).hexdigest()},
    }]
    assert row == canonical_evidence_row(
        json.loads(health.read_text())["datasets"][0],
        json.loads(manifest.read_text())["datasets"][0],
    )


def test_malformed_health_is_rejected(tmp_path: Path) -> None:
    health, manifest, data = _inputs(tmp_path)
    malformed = json.loads(health.read_text())
    malformed["datasets"][0].pop("status")
    health.write_text(json.dumps(malformed), encoding="utf-8")

    with pytest.raises(StatementError, match="status"):
        generate_receipts(health, manifest, data, quick_test=True)
