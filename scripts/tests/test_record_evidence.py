"""Contract tests for the generic record-evidence generator and NPRA pilot."""

from __future__ import annotations

import copy
import json
from datetime import UTC, date, datetime
from pathlib import Path

import pytest

from scripts.gen_record_evidence import (
    STATUSES,
    build_record_evidence,
    validate_record_evidence,
    write_record_evidence,
)

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "scripts/tests/fixtures/record_evidence_npra.csv"
DATASET = {
    "id": "pharmaceutical_products",
    "record_source_url": (
        "https://storage.data.gov.my/healthcare/pharmaceutical_products.csv"
    ),
    "refresh_frequency": "monthly",
    "vertical": True,
    "record_evidence_schema": "record-evidence/v1",
}
RUN_DATE = date(2026, 8, 12)
OBSERVED_AT = datetime(2026, 8, 12, 12, 14, 7, tzinfo=UTC)
LAST_MODIFIED = datetime(2026, 8, 8, 9, 55, 45, tzinfo=UTC)


def _envelope() -> dict[str, object]:
    return build_record_evidence(
        DATASET,
        FIXTURE.read_bytes(),
        run_date=RUN_DATE,
        observed_at=OBSERVED_AT,
        source_last_modified=LAST_MODIFIED,
    )


def test_record_evidence_envelope_shape() -> None:
    envelope = _envelope()

    assert set(envelope) == {
        "schema",
        "dataset_id",
        "observed_at",
        "run_date",
        "source_url",
        "source_sha256",
        "record_count",
        "schema_valid_count",
        "freshness",
        "status_distribution",
        "records",
    }
    assert envelope["schema"] == "record-evidence/v1"
    assert envelope["dataset_id"] == "pharmaceutical_products"
    assert envelope["record_count"] == 3
    assert envelope["schema_valid_count"] == 3
    assert len(envelope["records"]) == 3


def test_record_evidence_digest_stable() -> None:
    first = _envelope()
    second = build_record_evidence(
        DATASET,
        FIXTURE.read_bytes(),
        run_date=RUN_DATE,
        observed_at=datetime(2026, 8, 12, 23, 59, tzinfo=UTC),
        source_last_modified=LAST_MODIFIED,
    )

    assert [row["evidence_digest"] for row in first["records"]] == [
        row["evidence_digest"] for row in second["records"]
    ]


def test_record_evidence_status_distribution_sums() -> None:
    envelope = _envelope()

    assert tuple(envelope["status_distribution"]) == STATUSES
    assert sum(envelope["status_distribution"].values()) == envelope["record_count"]


def test_record_evidence_freshness_age_matches_last_modified() -> None:
    envelope = _envelope()

    assert envelope["freshness"] == {
        "source_last_modified": "2026-08-08T09:55:45Z",
        "age_days": 4,
        "status": "stale",
    }
    assert {row["status"] for row in envelope["records"]} == {"stale"}


def test_record_evidence_records_subset_in_latest(tmp_path: Path) -> None:
    envelope = _envelope()
    paths = write_record_evidence(envelope, tmp_path, excerpt_size=2)

    full = json.loads(paths.full.read_text(encoding="utf-8"))
    latest = json.loads(paths.latest.read_text(encoding="utf-8"))
    assert len(full["records"]) == full["record_count"] == 3
    assert 0 < len(latest["records"]) == 2 < latest["record_count"]
    assert latest["status_distribution"] == full["status_distribution"]
    assert {row["record_id"] for row in latest["records"]} <= {
        row["record_id"] for row in full["records"]
    }


def test_record_evidence_strict_envelope() -> None:
    assert validate_record_evidence(_envelope(), full=True) == []

    invalid = copy.deepcopy(_envelope())
    invalid["status_distribution"]["stale"] -= 1
    errors = validate_record_evidence(invalid, full=True)
    assert any("status_distribution" in error for error in errors)


def test_record_evidence_rejects_future_last_modified() -> None:
    with pytest.raises(ValueError, match="future"):
        build_record_evidence(
            DATASET,
            FIXTURE.read_bytes(),
            run_date=RUN_DATE,
            observed_at=OBSERVED_AT,
            source_last_modified=datetime(2026, 8, 13, tzinfo=UTC),
        )


def test_record_evidence_degrades_structurally_invalid_row() -> None:
    content = b"id,name\n,missing id\nvalid,Valid row\n"
    dataset = {
        "id": "generic_table",
        "record_source_url": "https://example.invalid/table.csv",
        "refresh_frequency": "daily",
        "vertical": True,
        "record_evidence_schema": "record-evidence/v1",
    }

    envelope = build_record_evidence(
        dataset,
        content,
        run_date=RUN_DATE,
        observed_at=OBSERVED_AT,
        source_last_modified=datetime(2026, 8, 12, tzinfo=UTC),
    )

    assert envelope["schema_valid_count"] == 1
    assert envelope["status_distribution"]["degraded"] == 1
    assert envelope["records"][0]["explanation"]["structural"] == {
        "schema_ok": False,
        "missing_required_fields": ["id"],
    }
