#!/usr/bin/env python3
"""Cross-document invariant: README taxonomy matches the schema status enum."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
README = ROOT / "README.md"
SCHEMA = ROOT / "health.schema.json"

CANONICAL_STATUSES = frozenset({
    "fresh",
    "aging",
    "stale",
    "discontinued",
    "degraded",
    "browser-dependent",
    "unreachable",
    "unknown",
    "unknown-freshness",
    "reference",
})


def _read_readme() -> str:
    return README.read_text(encoding="utf-8")


def _schema_status_enum() -> frozenset[str]:
    """Parse the live health.schema.json status enum."""
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    enum_values = schema["properties"]["datasets"]["items"]["properties"]["status"]["enum"]
    return frozenset(enum_values)


def _extract_status_mentions(text: str) -> frozenset[str]:
    """Extract backtick-quoted status names from the 'Health is reported as' sentence."""
    match = re.search(
        r"Health is reported as(.*?)\.",
        text,
        re.DOTALL,
    )
    if not match:
        return frozenset()
    sentence = match.group(1)
    names = re.findall(r"`([^`]+)`", sentence)
    return frozenset(names)


def _paragraph_containing(text: str, needle: str) -> str | None:
    """Return the paragraph (double-newline delimited block) containing *needle*."""
    for paragraph in text.split("\n\n"):
        if needle in paragraph:
            return paragraph
    return None


class TestReadmeTaxonomyMatchesSchema:
    """README status list must equal the schema enum exactly."""

    def test_status_mentions_equal_schema_enum(self) -> None:
        readme = _read_readme()
        mentioned = _extract_status_mentions(readme)
        schema_enum = _schema_status_enum()
        assert mentioned == schema_enum, (
            f"README mentions {mentioned!r}, schema defines {schema_enum!r}"
        )

    def test_schema_enum_is_canonical(self) -> None:
        """Guard: the parsed schema enum must match the known canonical set."""
        schema_enum = _schema_status_enum()
        assert schema_enum == CANONICAL_STATUSES


class TestReferenceSubtypesAreDataType:
    """policy-reference and reference-current must be presented as data_type values."""

    def test_policy_reference_near_data_type(self) -> None:
        readme = _read_readme()
        data_type_para = _paragraph_containing(readme, "data_type")
        assert data_type_para is not None, "README must mention data_type"
        assert "policy-reference" in data_type_para, (
            "policy-reference must appear in the data_type paragraph"
        )

    def test_reference_current_near_data_type(self) -> None:
        readme = _read_readme()
        data_type_para = _paragraph_containing(readme, "data_type")
        assert data_type_para is not None, "README must mention data_type"
        assert "reference-current" in data_type_para, (
            "reference-current must appear in the data_type paragraph"
        )

    def test_proximity_within_400_chars(self) -> None:
        readme = _read_readme()
        dt_pos = readme.find("data_type")
        assert dt_pos >= 0, "README must mention data_type"
        window = readme[dt_pos : dt_pos + 400]
        assert "policy-reference" in window, (
            "policy-reference must be within 400 chars of data_type"
        )
        assert "reference-current" in window, (
            "reference-current must be within 400 chars of data_type"
        )


class TestRegressionGuard:
    """Guard against re-introducing the old 'reference family splits into' framing."""

    def test_no_reference_family_splits_phrase(self) -> None:
        readme = _read_readme()
        assert "reference family splits into" not in readme, (
            "Old 'reference family splits into' phrasing must be removed"
        )

    def test_no_extra_statuses_in_health_sentence(self) -> None:
        readme = _read_readme()
        match = re.search(r"Health is reported as(.*?)\.", readme, re.DOTALL)
        assert match is not None
        health_sentence = match.group(0)
        backtick_names = set(re.findall(r"`([^`]+)`", health_sentence))
        extra = backtick_names & {"policy-reference", "reference-current"}
        assert not extra, (
            f"Health sentence must not present {extra} as statuses"
        )
