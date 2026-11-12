"""Contract tests for the generic record-evidence generator and NPRA pilot."""

from __future__ import annotations

import copy
import json
from datetime import UTC, date, datetime
from pathlib import Path

import httpx
import pytest

from scripts import gen_record_evidence
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


def test_record_evidence_exhausted_503_degrades_and_continues(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    unavailable = {**DATASET, "id": "unavailable"}
    manifest = tmp_path / "datapulse.json"
    manifest.write_text(json.dumps({"datasets": [unavailable, DATASET]}))
    attempts = 0

    def respond(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        if attempts <= gen_record_evidence.MAX_ATTEMPTS:
            return httpx.Response(503)
        return httpx.Response(200, content=FIXTURE.read_bytes())

    client = httpx.Client
    monkeypatch.setattr(
        gen_record_evidence.httpx, "Client",
        lambda **kwargs: client(transport=httpx.MockTransport(respond), **kwargs),
    )
    monkeypatch.setattr(gen_record_evidence.time, "sleep", lambda _: None)
    argv = [
        "--root", str(tmp_path), "--run-date", RUN_DATE.isoformat(),
        "--observed-at", OBSERVED_AT.isoformat(),
    ]
    assert gen_record_evidence.main(argv) == 0
    assert attempts == gen_record_evidence.MAX_ATTEMPTS + 1
    directory = tmp_path / "record-evidence" / unavailable["id"]
    latest_path = directory / "latest.json"
    serialized = latest_path.read_bytes()
    envelope = json.loads(serialized)
    assert envelope["source_unavailable"] == "http-503"
    assert envelope.get("source_sha256") is None
    assert envelope.get("record_count") is None
    assert envelope.get("schema_valid_count") is None
    assert envelope.get("status_distribution") is None
    assert envelope["records"] == []
    assert envelope["freshness"]["status"] == "unreachable"
    assert validate_record_evidence(envelope, full=True) == []
    assert (directory / f"{RUN_DATE}.json").read_bytes() == serialized
    healthy = json.loads(
        (tmp_path / "record-evidence" / DATASET["id"] / "latest.json").read_text()
    )
    assert healthy["record_count"] == 3
    assert "source_unavailable" not in healthy
    invalid = {**envelope, "record_count": 0}
    assert validate_record_evidence(invalid, full=True)
    invalid = {**envelope, "source_unavailable": "http-404"}
    assert validate_record_evidence(invalid, full=True)
    invalid = {**envelope, "records": _envelope()["records"]}
    assert validate_record_evidence(invalid, full=True)
    invalid = {**envelope, "freshness": _envelope()["freshness"]}
    assert validate_record_evidence(invalid, full=True)
    invalid = {**envelope, "dataset_id": ""}
    assert validate_record_evidence(invalid, full=True)
    invalid = {**envelope, "source_unavailable": "http-503?query=private"}
    assert validate_record_evidence(invalid, full=True)
    attempts = 0
    assert gen_record_evidence.main(argv) == 0
    assert latest_path.read_bytes() == serialized


def test_record_evidence_404_still_raises(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    manifest = tmp_path / "datapulse.json"
    manifest.write_text(json.dumps({"datasets": [DATASET]}))
    attempts = 0

    def respond(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        return httpx.Response(404)

    client = httpx.Client
    monkeypatch.setattr(
        gen_record_evidence.httpx, "Client",
        lambda **kwargs: client(transport=httpx.MockTransport(respond), **kwargs),
    )
    with pytest.raises(httpx.HTTPStatusError) as failure:
        gen_record_evidence.main(["--root", str(tmp_path)])
    assert failure.value.response.status_code == 404
    assert attempts == 1
    assert not (tmp_path / "record-evidence").exists()
