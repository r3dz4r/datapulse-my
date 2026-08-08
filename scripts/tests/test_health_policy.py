import json
from datetime import datetime
from pathlib import Path

import pytest

from scripts.health_policy import (
    age_in_days,
    classify_status,
    due_interval,
    frequency_to_tier,
    is_due,
    select_freshness_signal,
)


FIXTURE_PATH = Path(__file__).parent / "fixtures/health-policy-cases.json"
CASES = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
NOW = datetime.fromisoformat(CASES["now"].replace("Z", "+00:00"))


@pytest.mark.parametrize("case", CASES["frequency_cases"], ids=lambda case: case["name"])
def test_frequency_schedule(case: dict[str, object]) -> None:
    expected = case["expected"]
    frequency = case["frequency"]

    tier = frequency_to_tier(frequency)

    assert tier == expected["tier"]
    assert due_interval(tier, frequency) == expected["due_interval_seconds"]


@pytest.mark.parametrize("case", CASES["due_cases"], ids=lambda case: case["name"])
def test_due_boundaries(case: dict[str, object]) -> None:
    row = case["row"]

    assert is_due(row.get("last_checked"), NOW, row["refresh_frequency"]) is case["expected"]["is_due"]


def test_never_checked_dataset_is_due() -> None:
    assert is_due(None, NOW, "monthly") is True


def test_unsupported_frequency_reports_manifest_id_and_value() -> None:
    with pytest.raises(
        ValueError,
        match="manifest ID 'bad-frequency'.*refresh_frequency 'fortnightly'",
    ):
        frequency_to_tier("fortnightly", manifest_id="bad-frequency")


def test_unapproved_weekday_frequency_is_rejected() -> None:
    with pytest.raises(ValueError, match="refresh_frequency 'daily \\(weekdays, 1300 MYT\\)'"):
        frequency_to_tier("daily (weekdays, 1300 MYT)")


@pytest.mark.parametrize("case", CASES["signal_cases"], ids=lambda case: case["name"])
def test_freshness_signal_selection(case: dict[str, object]) -> None:
    row = case["row"]
    expected = case["expected"]

    assert select_freshness_signal(row) == (
        expected["signal"],
        expected["signal_reason"],
    )
    if expected["age_days"] is None:
        assert age_in_days(row, NOW) is None
    else:
        assert age_in_days(row, NOW) == pytest.approx(expected["age_days"])


POLICY_STATUS_CASES = CASES["freshness_cases"] + CASES["status_cases"]


@pytest.mark.parametrize("case", POLICY_STATUS_CASES, ids=lambda case: case["name"])
def test_status_classification(case: dict[str, object]) -> None:
    expected = case["expected"]

    assert classify_status(case["row"], NOW) == (
        expected["status"],
        expected["status_reason"],
    )


def test_representative_expected_status_mutation_is_detected() -> None:
    case = next(case for case in POLICY_STATUS_CASES if case["name"] == "transport-failure-beats-freshness")

    actual = classify_status(case["row"], NOW)
    mutated_expected = ("fresh", case["expected"]["status_reason"])

    assert actual != mutated_expected


@pytest.mark.parametrize(
    ("last_checked", "reason"),
    [
        ("not-a-date", "invalid-last-checked"),
        ("2026-08-08T12:00:01Z", "future-last-checked"),
    ],
)
def test_invalid_observation_dates_cannot_create_fresh(last_checked: str, reason: str) -> None:
    row = {
        "dataset_id": "invalid-observation",
        "refresh_frequency": "biennial to triennial (survey years)",
        "last_checked": last_checked,
        "http_status": 200,
    }

    assert classify_status(row, NOW) == ("degraded", reason)
