from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.verify_licence_consistency import SPDX_IDS, licence_failures


def manifest(licence: object, **fields: object) -> dict:
    return {"datasets": [{"id": "sample", "custodian": "agency", "licence": licence, **fields}]}


@pytest.mark.parametrize("identifier", sorted(SPDX_IDS))
def test_entire_embedded_spdx_list_is_accepted(identifier: str) -> None:
    assert not licence_failures(manifest(identifier), {})


def test_custom_instrument_needs_a_source() -> None:
    value = "Malaysian Government Open Data License 1.0"
    failures = licence_failures(manifest(value), {})
    assert len(failures) == 1 and "sample:" in failures[0]
    assert "not an SPDX" in failures[0] and "source reference" in failures[0]
    assert not licence_failures(manifest(value, licence_ref="https://example.test/licence"), {})
    assert not licence_failures(manifest(value), {"custodians": {"agency": {"licence_references": {value: "https://example.test/licence"}}}})


@pytest.mark.parametrize("reference", [None, "", "file:///licence", "https://", "javascript:alert(1)", " https://example.test/licence", "https://user:password@example.test/licence"])
def test_invalid_references_cannot_authorize_custom_values(reference: object) -> None:
    assert licence_failures(manifest("custom", licence_ref=reference), {})


def test_dataset_url_and_unrelated_custodian_instrument_are_not_evidence() -> None:
    assert licence_failures(manifest("unverified", url="https://example.test/data"), {"custodians": {"agency": {"licence_references": {"another": "https://example.test/licence"}}}})


@pytest.mark.parametrize("value", [None, "", 123, [], {}])
def test_invalid_value_has_a_distinct_actionable_message(value: object) -> None:
    assert "missing or invalid" in licence_failures(manifest(value), {})[0]


def test_current_manifest_reports_every_unsourced_value() -> None:
    root = Path(__file__).resolve().parents[2]
    rows = json.loads((root / "datapulse.json").read_text())
    custodians = json.loads((root / "custodians.json").read_text())
    failures = licence_failures(rows, custodians)
    expected = [row["id"] for row in rows["datasets"] if row["licence"] not in SPDX_IDS and not row.get("licence_ref") and not custodians["custodians"][row["custodian"]].get("licence_references", {}).get(row["licence"])]
    assert [failure.split(":", 1)[0] for failure in failures] == expected
