import json
from datetime import datetime
from pathlib import Path

import pytest

from scripts.health_policy import due_interval, frequency_to_tier, is_due


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
