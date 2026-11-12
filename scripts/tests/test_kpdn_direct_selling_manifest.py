#!/usr/bin/env python3
from __future__ import annotations

import copy
import json
import shutil
from pathlib import Path

import pytest

from scripts import gen_kpdn_direct_selling as kpdn


ROOT = Path(__file__).resolve().parents[2]
FIXTURES = Path(__file__).parent / "fixtures/kpdn_direct_selling"
FETCHED_AT = "2026-11-12T11:20:00Z"


def observation() -> dict:
    pages = []
    for source in kpdn.SOURCES:
        body = (FIXTURES / f"{source}.html").read_bytes()
        pages.append(kpdn.parse_page(source, body, FETCHED_AT))
    return kpdn.combine(pages)


def test_manifest_parser_covers_every_section_without_inventing_fields() -> None:
    result = observation()
    assert result["counts"] == {"active": 1, "expired": 1, "cancelled": 9}
    assert len(result["sections"]) == 11
    assert sum(s["skipped_rows"] for s in result["sections"]) == 11
    assert all(s["skipped_reasons"] == {"header": 1} for s in result["sections"])
    active = result["records"][0]
    assert active["company_name"] == "AVON COSMETIC (M) SDN. BHD."
    assert active["licence_start"] == "2022-05-17"
    assert active["raw"]["TARIKH MULA"] == "17/05/2022"
    assert active["status_raw"] == "AKTIF"
    assert active["fetched_at"] == FETCHED_AT
    assert active["sector"] is active["address_operations"] is None
    expired = result["records"][1]
    assert expired["registration_no"] is expired["licence_expiry"] is None
    assert expired["raw"]["TARIKH TAMAT LESEN"] == "-"
    historic = result["records"][3]
    assert historic["ajl_no"] == "AJL931900"
    assert historic["raw"]["NO. LESEN"] == "AJL 931900"
    assert historic["raw"]["TARIKH BATAL"] == "03.02.2012"
    assert historic["status"] == "cancelled"
    assert historic["status_raw"] is None
    assert historic["source_section"] == "2012"
    assert historic["sector"] is None  # PELAN is not a sector.
    numeric_only = next(r for r in result["records"] if r["source_section"] == "2009")
    assert numeric_only["ajl_no"] == numeric_only["raw"]["NO. LESEN"] == "931699"
    assert numeric_only["issues"] == []


def test_manifest_parser_retains_bad_dates_short_rows_and_unknown_status() -> None:
    body = (FIXTURES / "active_expired.html").read_text()
    body = body.replace("17/05/2022", "31.02.2022").replace("AKTIF</td>", "UNRECOGNISED</td>")
    body = body.replace("<td>SELANGOR</td>", "", 1)
    result = kpdn.parse_page("active_expired", body.encode(), FETCHED_AT)
    record = result["records"][0]
    assert record["licence_start"] is record["status"] is None
    assert record["raw"]["TARIKH MULA"] == "31.02.2022"
    assert record["status_raw"] == "UNRECOGNISED"
    assert {"invalid_licence_start", "unknown_status", "column_count_mismatch"} <= set(record["issues"])
    assert len(result["records"]) == 3
    assert result["sections"][0]["malformed_rows"] == 1


@pytest.mark.parametrize("value, expected", [("19.5.2011", "2011-05-19"), ("17/05/2022", "2022-05-17"), ("-", None)])
def test_manifest_date_formats(value: str, expected: str | None) -> None:
    assert kpdn.normalise_date(value) == expected


def test_manifest_parser_stops_on_block_or_missing_section() -> None:
    with pytest.raises(kpdn.SourceError, match="missing register tables"):
        kpdn.parse_page("active_expired", b"<html>Access denied</html>", FETCHED_AT)
    with pytest.raises(kpdn.SourceError, match="missing register tables"):
        kpdn.parse_page("active_expired", (FIXTURES / "active_expired.html").read_bytes().replace(b"myTable-batal", b"missing"), FETCHED_AT)


@pytest.mark.parametrize("field, value", [("counts", {}), ("pages", [])])
def test_manifest_replay_rejects_incomplete_observation(field: str, value: object) -> None:
    result = observation()
    original = copy.deepcopy(result)
    kpdn.validate_observation(result)
    assert result == original
    result[field] = value
    with pytest.raises(kpdn.SourceError, match="invalid pinned observation"):
        kpdn.validate_observation(result)


@pytest.mark.parametrize("status, location", [(403, ""), (302, "https://example.test/other"), (200, "")])
def test_manifest_fetch_stops_on_block_redirect_or_non_register(monkeypatch: pytest.MonkeyPatch, status: int, location: str) -> None:
    class Response:
        status_code = status
        headers = {"Content-Type": "text/html", "Location": location}

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def iter_content(self, _size):
            yield b"<html>Access denied</html>"

    calls = []

    def get(url, **kwargs):
        calls.append((url, kwargs))
        return Response()

    monkeypatch.setattr(kpdn.requests, "get", get)
    with pytest.raises(kpdn.SourceError):
        kpdn.fetch_page("active_expired")
    assert len(calls) == 1
    assert calls[0][0] == kpdn.SOURCES["active_expired"]
    assert calls[0][1]["allow_redirects"] is False


def test_manifest_registration_is_scoped_and_byte_idempotent(tmp_path: Path) -> None:
    for relative in ("datapulse.json", "datapulse.schema.json", "health/latest.json", "health.schema.json", "scripts/probe-policy.json", "scripts/probe-policy.schema.json", "scripts/contract-scope.json", "config/public-surfaces.json", "config/public-surfaces.schema.json"):
        target = tmp_path / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / relative, target)
    config = json.loads((ROOT / "config/kpdn-direct-selling.json").read_text())
    before = json.loads((tmp_path / "datapulse.json").read_text())["datasets"]
    result = observation()
    paths = kpdn.register(tmp_path, config, result)
    first = {path: path.read_bytes() for path in paths}
    kpdn.register(tmp_path, config, result)
    assert first == {path: path.read_bytes() for path in paths}
    rows = json.loads((tmp_path / "datapulse.json").read_text())["datasets"]
    assert [r for r in rows if r["id"] != kpdn.DATASET_ID] == [r for r in before if r["id"] != kpdn.DATASET_ID]
    assert len([r for r in rows if r["id"] == kpdn.DATASET_ID]) == 1
    assert "Open Government Licence" not in config["dataset"]["licence"]
    report = (tmp_path / f"data/{kpdn.DATASET_ID}.md").read_text()
    assert "not stated" in report
    assert "DD/MM/YYYY" in report
    assert (tmp_path / f"data/jsonld/{kpdn.DATASET_ID}.json").is_file()
    assert (tmp_path / f"docs/datasets/{kpdn.DATASET_ID}.html").is_file()
    assert f"/datasets/{kpdn.DATASET_ID}" in (tmp_path / "sitemap.xml").read_text()


def test_manifest_checked_in_registration_has_observation_and_safe_policy() -> None:
    rows = json.loads((ROOT / "datapulse.json").read_text())["datasets"]
    row = next(r for r in rows if r["id"] == kpdn.DATASET_ID)
    assert row["canonical_id"] == kpdn.DATASET_ID
    assert row["refresh_frequency"] == "daily"
    assert row["custodian"] == "kpdn"
    assert row["licence"] == "Reuse licence not stated on the KPDN source pages; permission unverified"
    references = json.loads((ROOT / "custodians.json").read_text())["custodians"]["kpdn"]["licence_references"]
    assert references[row["licence"]].endswith(f"data/{kpdn.DATASET_ID}.md#licence-and-attribution")
    assert row["url"] == kpdn.SOURCES["active_expired"]
    observed = json.loads((ROOT / f"data/observations/{kpdn.DATASET_ID}.json").read_text())
    assert set(observed["counts"]) == {"active", "expired", "cancelled"}
    assert len(observed["records"]) == sum(observed["counts"].values())
    policy = json.loads((ROOT / "scripts/probe-policy.json").read_text())["datasets"][kpdn.DATASET_ID]
    assert policy["adapter"] == "direct"
    assert policy["freshness"]["fallback"] == "unknown-freshness"
    assert (ROOT / row["health_report"]).is_file()
