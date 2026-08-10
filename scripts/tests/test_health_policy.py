import json
from datetime import datetime
from pathlib import Path

import pytest

from scripts.health_policy import (
    age_in_days,
    classify_status,
    derive_trust_summary,
    due_interval,
    frequency_to_tier,
    is_due,
    merge_due_updates,
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


def test_reachable_reference_data_has_no_freshness_clock() -> None:
    row = {
        "dataset_id": "lookup",
        "data_type": "reference",
        "refresh_frequency": "daily",
        "last_checked": "2026-08-08T12:00:00Z",
        "http_status": 200,
        "probe_status": "degraded",
    }

    assert classify_status(row, NOW) == ("reference", "versioned-reference-data")


def test_unreachable_reference_data_remains_unreachable() -> None:
    row = {
        "dataset_id": "lookup",
        "data_type": "reference",
        "refresh_frequency": "daily",
        "last_checked": "2026-08-08T12:00:00Z",
        "http_status": 503,
    }

    assert classify_status(row, NOW) == ("unreachable", "transport-failure")


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


MERGE_CASES = [
    pytest.param(
        [
            {
                "dataset_id": "alpha",
                "status": "fresh",
                "freshness_signal_source": "last_modified_header",
                "last_modified": "2026-08-01T00:00:00Z",
                "record_count": 10,
                "staleness_days": 7,
            },
            {
                "dataset_id": "beta",
                "status": "stale",
                "freshness_signal_source": "none",
                "last_modified": None,
                "record_count": None,
                "staleness_days": 40,
            },
        ],
        [],
        ["alpha", "beta"],
        {"fresh": 1, "stale": 1},
        id="zero-selection",
    ),
    pytest.param(
        [
            {
                "dataset_id": "alpha",
                "status": "aging",
                "freshness_signal_source": "last_modified_header",
                "last_modified": "2026-07-01T00:00:00Z",
                "record_count": 10,
                "staleness_days": 38,
            },
            {
                "dataset_id": "beta",
                "status": "stale",
                "freshness_signal_source": "none",
                "last_modified": None,
                "record_count": None,
                "staleness_days": 40,
            },
            {
                "dataset_id": "gamma",
                "status": "fresh",
                "freshness_signal_source": "content_date_parse",
                "last_modified": "2026-08-02T00:00:00Z",
                "record_count": 30,
                "staleness_days": 6,
            },
        ],
        [
            {
                "dataset_id": "beta",
                "status": "fresh",
                "freshness_signal_source": "content_date_parse",
                "last_modified": "2026-08-03T00:00:00Z",
                "record_count": 20,
                "staleness_days": 5,
            }
        ],
        ["gamma", "beta", "alpha"],
        {"fresh": 2, "aging": 1},
        id="partial-selection",
    ),
    pytest.param(
        [
            {"dataset_id": "alpha", "status": "stale"},
            {"dataset_id": "beta", "status": "stale"},
        ],
        [
            {
                "dataset_id": "beta",
                "status": "browser-dependent",
                "freshness_signal_source": "none",
                "last_modified": None,
                "record_count": None,
                "staleness_days": None,
            },
            {
                "dataset_id": "alpha",
                "status": "unreachable",
                "freshness_signal_source": "none",
                "last_modified": None,
                "record_count": None,
                "staleness_days": None,
            },
        ],
        ["alpha", "beta"],
        {"browser_dependent": 1, "unreachable": 1},
        id="full-selection",
    ),
]


@pytest.mark.parametrize(
    ("prior_rows", "updates", "manifest_ids", "nonzero_statuses"),
    MERGE_CASES,
)
def test_due_merge_and_summary(
    prior_rows: list[dict[str, object]],
    updates: list[dict[str, object]],
    manifest_ids: list[str],
    nonzero_statuses: dict[str, int],
) -> None:
    merged = merge_due_updates(prior_rows, updates, manifest_ids)
    summary = derive_trust_summary(merged)

    assert [row["dataset_id"] for row in merged] == manifest_ids
    assert set(row["dataset_id"] for row in merged) == set(manifest_ids)
    assert summary["datasets_total"] == len(manifest_ids)
    assert sum(summary["by_status"].values()) == len(manifest_ids)
    assert {key: value for key, value in summary["by_status"].items() if value} == nonzero_statuses
    assert [row["dataset_id"] for row in summary["stale_datasets"]] == [
        row["dataset_id"] for row in merged if row.get("status") == "stale"
    ]


def test_due_merge_preserves_unprobed_row_objects() -> None:
    alpha = {"dataset_id": "alpha", "status": "fresh", "evidence": {"approved": True}}
    beta = {"dataset_id": "beta", "status": "stale"}
    beta_update = {"dataset_id": "beta", "status": "fresh"}

    merged = merge_due_updates([alpha, beta], [beta_update], ["alpha", "beta"])

    assert merged[0] is alpha
    assert merged[1] is beta_update


@pytest.mark.parametrize(
    ("prior_rows", "updates", "manifest_ids", "message"),
    [
        ([{"dataset_id": "alpha"}], [], ["alpha", "beta"], "missing"),
        ([{"dataset_id": "alpha"}], [{"dataset_id": "beta"}], ["alpha"], "unknown"),
        ([{"dataset_id": "alpha"}], [{"dataset_id": "alpha"}, {"dataset_id": "alpha"}], ["alpha"], "duplicate"),
    ],
)
def test_due_merge_rejects_id_loss_or_duplication(
    prior_rows: list[dict[str, object]],
    updates: list[dict[str, object]],
    manifest_ids: list[str],
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        merge_due_updates(prior_rows, updates, manifest_ids)
