#!/usr/bin/env python3
"""Offline contracts for external citations and DataPulse's evidence boundary."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import pytest


ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / "config/scoring-standards.json"
DQAF = "IMF Data Quality Assessment Framework (DQAF)"
ODIN = "Open Data Inventory (ODIN)"
FIVE_STAR = "Tim Berners-Lee's 5-star scheme"
REFERENCES = {
    DQAF: (
        "primary", "spine", "International Monetary Fund",
        "https://dsbb.imf.org/content/pdfs/eGDDS_Guide_for_Participants_and_Users.pdf",
    ),
    ODIN: (
        "secondary", "context", "Open Data Watch",
        "https://docs.google.com/document/d/1q9QGI5svEY6RRmi7jkgQtX1Sjms3sznH/edit",
    ),
    FIVE_STAR: (
        "descriptor", "descriptor", "Tim Berners-Lee",
        "https://www.w3.org/DesignIssues/LinkedData.html",
    ),
}
ELEMENTS = {
    DQAF: {
        "3.5 Revision studies", "4.1 Periodicity and timeliness",
        "4.2 Consistency", "5.2 Metadata accessibility",
    },
    ODIN: {
        "machine readable format", "non-proprietary format", "reference metadata",
        "download options - bulk downloads, APIs, customisable export",
        "open data license or open data terms of use",
    },
    FIVE_STAR: {
        "1 = on the web under an open license", "2 = structured data",
        "3 = non-proprietary open format", "4 = URIs to denote things",
        "5 = linked to other data for context",
    },
}
UNEVIDENCED = {
    DQAF: {"3.5 Revision studies", "4.2 Consistency"},
    ODIN: {"machine readable format", "non-proprietary format"},
    FIVE_STAR: {
        "2 = structured data", "3 = non-proprietary open format",
        "4 = URIs to denote things", "5 = linked to other data for context",
    },
}


def _load() -> dict[str, Any]:
    return json.loads(CONFIG.read_text(encoding="utf-8"))


def _manifest_rows() -> list[dict[str, Any]]:
    return json.loads((ROOT / "datapulse.json").read_text(encoding="utf-8"))["datasets"]


def _assert_no_numbers(value: Any, path: str = "root") -> None:
    # All numbers are forbidden in this citation-only artifact, including nested
    # scores and numeric weights without an authority in the immediate key.
    assert not isinstance(value, (int, float)), f"Numeric authority value at {path}"
    if isinstance(value, dict):
        for key, child in value.items():
            _assert_no_numbers(child, f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _assert_no_numbers(child, f"{path}[{index}]")


def test_json_has_exactly_the_three_references_in_hierarchy_order() -> None:
    config = _load()
    assert config["schema"] == "datapulse/v1/scoring-standards"
    assert [entry["standard"] for entry in config["standards"]] == list(REFERENCES)
    for entry in config["standards"]:
        hierarchy, role, author, source_url = REFERENCES[entry["standard"]]
        assert entry["hierarchy"] == hierarchy
        assert entry["role"] == role
        assert author in entry["attribution"]
        assert entry["source_url"] == source_url
        assert entry["assessment_boundary"]


def test_every_element_has_its_own_standard_attribution_and_source() -> None:
    for reference in _load()["standards"]:
        entries = reference["elements"]
        names = [entry["element"] for entry in entries]
        assert len(names) == len(set(names))
        assert set(names) == ELEMENTS[reference["standard"]]
        for entry in entries:
            assert entry["standard"] == reference["standard"]
            assert entry["element"]
            assert REFERENCES[entry["standard"]][2] in entry["attribution"]
            assert entry["source_url"] == reference["source_url"]
            parsed = urlsplit(entry["source_url"])
            assert parsed.scheme == "https" and parsed.netloc
            assert entry["evidence_note"]


def test_dqaf_dimension_names_and_revision_definition_are_preserved() -> None:
    entries = _load()["standards"][0]["elements"]
    assert {entry["element"]: entry["dimension"] for entry in entries} == {
        "3.5 Revision studies": "3 Accuracy and reliability",
        "4.1 Periodicity and timeliness": "4 Serviceability",
        "4.2 Consistency": "4 Serviceability",
        "5.2 Metadata accessibility": "5 Accessibility",
    }
    assert entries[0]["definition"] == (
        "Revisions, as a gauge of reliability, are tracked and mined for the "
        "information they may provide."
    )


def test_no_numeric_scores_weights_ratings_or_external_verdicts() -> None:
    _assert_no_numbers(_load())


@pytest.mark.parametrize("borrowed_value", [0, 0.5, 1, 5, True])
@pytest.mark.parametrize("authority", list(REFERENCES))
@pytest.mark.parametrize("shape", ["named_key", "attributed", "nested", "list"])
def test_numeric_guard_rejects_borrowed_scores(
    borrowed_value: int | float | bool, authority: str, shape: str,
) -> None:
    candidates = {
        "named_key": {f"{authority} score": borrowed_value},
        "attributed": {"attribution": authority, "score": borrowed_value},
        "nested": {"standard": authority, "assessment": {"value": borrowed_value}},
        "list": {"standard": authority, "marks": [borrowed_value]},
    }
    with pytest.raises(AssertionError, match="Numeric authority value"):
        _assert_no_numbers(candidates[shape])


def test_numeric_guard_allows_cited_element_identifiers_and_nulls() -> None:
    _assert_no_numbers({"element": "3.5 Revision studies", "local_fields": None})
    _assert_no_numbers({"element": "1 = on the web under an open license"})


def test_mappings_use_actual_manifest_row_fields_with_real_values() -> None:
    rows = _manifest_rows()
    keys = {key for row in rows for key in row}
    mapped_fields = set()
    for reference in _load()["standards"]:
        for entry in reference["elements"]:
            fields = entry["local_fields"]
            assert entry["evidence_status"] in {"partial", "unknown"}
            if fields is None:
                assert entry["evidence_status"] == "unknown"
                continue
            assert isinstance(fields, list) and fields
            assert len(fields) == len(set(fields))
            assert entry["evidence_status"] == "partial"
            for field in fields:
                assert isinstance(field, str) and field in keys
                assert any(row.get(field) not in (None, "", [], {}) for row in rows)
                mapped_fields.add(field)
    assert mapped_fields


def test_unevidenced_elements_remain_null_with_an_explanation() -> None:
    for reference in _load()["standards"]:
        actual = {
            entry["element"] for entry in reference["elements"]
            if entry["local_fields"] is None
        }
        assert actual == UNEVIDENCED[reference["standard"]]
        for entry in reference["elements"]:
            if entry["element"] in actual:
                assert entry["evidence_status"] == "unknown"
                assert entry["evidence_note"].startswith("No manifest field")


def test_crosswalk_applies_per_dataset_without_materialising_scores() -> None:
    application = _load()["application"]
    assert application["manifest"] == "datapulse.json"
    assert application["dataset_key"] == "id"
    rows = _manifest_rows()
    assert len(rows) == 425
    assert len({row[application["dataset_key"]] for row in rows}) == len(rows)
    assert "independently to every manifest dataset" in application["scope"]
    assert "missing, null, empty or insufficient" in application["missing_evidence"]
    assert "unknown" in application["missing_evidence"]
    assert "not blended or weighted" in application["hierarchy"]
    assert "DataPulse owns" in application["attribution_boundary"]


def test_local_probe_evidence_is_owned_by_datapulse_and_not_relabelled() -> None:
    config = _load()
    local = config["local_evidence"]
    keys = {key for row in _manifest_rows() for key in row}
    assert local["owner"] == "DataPulse"
    assert set(local["fields"]) <= keys
    assert "not a content freshness" in local["fields"]["verified_at"]
    assert "not an observed count" in local["fields"]["expected_record_count"]
    for reference in config["standards"]:
        for entry in reference["elements"]:
            assert "verified_at" not in (entry["local_fields"] or [])
            assert "expected_record_count" not in (entry["local_fields"] or [])
