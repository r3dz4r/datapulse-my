import json
from pathlib import Path

import pytest

from scripts.shape_fingerprint import (
    fingerprint_csv_headers,
    fingerprint_json,
    fingerprint_untyped,
)


FIXTURE_PATH = Path(__file__).parent / "fixtures/shape-cases.json"
CASES = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


@pytest.mark.parametrize(
    "case",
    CASES["stable_values"]
    + CASES["nested_wrappers"]
    + CASES["rolling_feeds"],
    ids=lambda case: case["name"],
)
def test_json_value_changes_keep_the_same_fingerprint(case: dict[str, str]) -> None:
    fingerprint = fingerprint_json(case["left"])

    assert fingerprint.startswith("shape-v1:")
    assert fingerprint == fingerprint_json(case["right"])


@pytest.mark.parametrize(
    "case",
    CASES["field_drift"] + CASES["type_drift"],
    ids=lambda case: case["name"],
)
def test_json_structural_drift_changes_the_fingerprint(case: dict[str, str]) -> None:
    assert fingerprint_json(case["left"]) != fingerprint_json(case["right"])


@pytest.mark.parametrize(
    "case",
    CASES["quoted_csv_headers"],
    ids=lambda case: case["name"],
)
def test_csv_quoted_headers_ignore_row_values(case: dict[str, str]) -> None:
    assert fingerprint_csv_headers(case["left"]) == fingerprint_csv_headers(case["right"])


def test_csv_header_order_and_names_are_structural() -> None:
    baseline = 'id,"full,name",state\n1,"Alpha, One",Johor\n'

    assert fingerprint_csv_headers(baseline) != fingerprint_csv_headers(
        'state,"full,name",id\nJohor,"Alpha, One",1\n'
    )
    assert fingerprint_csv_headers(baseline) != fingerprint_csv_headers(
        'id,"display,name",state\n1,"Alpha, One",Johor\n'
    )


def test_untyped_and_binary_formats_have_no_fingerprint() -> None:
    assert fingerprint_untyped(b"PAR1\x00\x01") is None
