"""Tests for deterministic per-dataset Sigstore receipt statements."""

from __future__ import annotations

import hashlib
import json
import logging
from pathlib import Path

import pytest

from scripts.gen_per_dataset_receipt import (
    PREDICATE_TYPE,
    StatementError,
    canonical_evidence_row,
    generate_receipts,
    main,
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


def _unprobed_row() -> dict[str, object]:
    return {
        "dataset_id": "other", "last_checked": None, "status": "unknown-freshness",
        "message": "Not probed; provisional onboarding status.",
    }


@pytest.mark.parametrize("quick_test", [False, True])
def test_unprobed_row_is_skipped_without_changing_probed_receipts(
    tmp_path: Path, caplog: pytest.LogCaptureFixture, quick_test: bool,
) -> None:
    health, manifest, data = _inputs(tmp_path)
    baseline = tmp_path / "baseline"
    generate_receipts(health, manifest, baseline)
    snapshot = json.loads(health.read_text())
    snapshot["datasets"][-1] = _unprobed_row()
    health.write_text(json.dumps(snapshot), encoding="utf-8")

    with caplog.at_level(logging.INFO, logger="scripts.gen_per_dataset_receipt"):
        generated = generate_receipts(health, manifest, data, quick_test=quick_test)

    assert generated == ["cpi_3d", "dosm_lfs_month", "fuelprice"]
    assert len(list(data.iterdir())) == 2 * len(generated)
    assert not list(data.glob("other.receipt.*.json"))
    for path in data.iterdir():
        assert path.read_bytes() == (baseline / path.name).read_bytes()
    assert caplog.record_tuples == [(
        "scripts.gen_per_dataset_receipt", logging.INFO,
        "Skipping receipt for health dataset other: unprobed "
        "(last_checked is null and status is unknown-freshness)",
    )]


def test_only_unprobed_row_writes_nothing_and_cli_succeeds(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str],
) -> None:
    health, manifest, data = _inputs(tmp_path)
    snapshot = json.loads(health.read_text())
    snapshot["datasets"] = [_unprobed_row()]
    health.write_text(json.dumps(snapshot), encoding="utf-8")
    manifest.write_text(json.dumps({"datasets": [{"id": "other", "licence": "OGL"}]}), encoding="utf-8")

    assert generate_receipts(health, manifest, data) == []
    assert not data.exists()
    monkeypatch.setattr("sys.argv", [
        "gen_per_dataset_receipt.py", "--health", str(health),
        "--manifest", str(manifest), "--data-dir", str(data),
    ])
    main()
    assert capsys.readouterr().out == "Generated 0 per-dataset receipts.\n"
    assert not data.exists()


@pytest.mark.parametrize("last_checked,status", [
    ("2026-08-30T02:16:30Z", "fresh"),
    ("2026-08-30T02:16:30Z", "unknown-freshness"),
    (None, "fresh"),
])
def test_missing_request_url_is_rejected_unless_explicitly_unprobed(
    tmp_path: Path, last_checked: str | None, status: str,
) -> None:
    health, manifest, data = _inputs(tmp_path)
    snapshot = json.loads(health.read_text())
    row = snapshot["datasets"][-1]
    row.update(last_checked=last_checked, status=status)
    row.pop("request_url")
    health.write_text(json.dumps(snapshot), encoding="utf-8")

    with pytest.raises(StatementError, match="^health dataset other is missing request_url$"):
        generate_receipts(health, manifest, data)
    assert not data.exists()


def test_missing_last_checked_does_not_declare_an_unprobed_row(tmp_path: Path) -> None:
    health, manifest, data = _inputs(tmp_path)
    snapshot = json.loads(health.read_text())
    snapshot["datasets"][-1] = _unprobed_row()
    snapshot["datasets"][-1].pop("last_checked")
    health.write_text(json.dumps(snapshot), encoding="utf-8")

    with pytest.raises(StatementError, match="^health dataset other is missing last_checked$"):
        generate_receipts(health, manifest, data)


@pytest.mark.parametrize("invalid,reason", [
    ("absent", "health dataset other is absent from the manifest"),
    ("missing_health", "manifest and health dataset identities must match"),
    ("duplicate_health", "health datasets must have unique dataset_id strings"),
    ("duplicate_manifest", "manifest datasets must have unique id strings"),
    ("licence", "manifest dataset other must have a licence"),
])
def test_unprobed_row_cannot_bypass_identity_or_licence_checks(
    tmp_path: Path, caplog: pytest.LogCaptureFixture, invalid: str, reason: str,
) -> None:
    health, manifest, data = _inputs(tmp_path)
    snapshot = json.loads(health.read_text())
    snapshot["datasets"][-1] = _unprobed_row()
    catalog = json.loads(manifest.read_text())
    if invalid == "absent":
        catalog["datasets"].pop()
    elif invalid == "missing_health":
        snapshot["datasets"].pop(0)
    elif invalid == "duplicate_health":
        snapshot["datasets"].append(_unprobed_row())
    elif invalid == "duplicate_manifest":
        catalog["datasets"].append(catalog["datasets"][-1])
    else:
        catalog["datasets"][-1].pop("licence")
    health.write_text(json.dumps(snapshot), encoding="utf-8")
    manifest.write_text(json.dumps(catalog), encoding="utf-8")

    with caplog.at_level(logging.INFO, logger="scripts.gen_per_dataset_receipt"):
        with pytest.raises(StatementError, match=f"^{reason}$"):
            generate_receipts(health, manifest, data)
    assert not data.exists()
    assert not caplog.records
