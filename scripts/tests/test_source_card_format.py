"""Format and completeness tests for local source-card fixtures."""

from __future__ import annotations

from datetime import date
import json
from pathlib import Path

from scripts.verify_source_cards import load_card


ROOT = Path(__file__).resolve().parents[2]
CARDS = ROOT / "notes" / "source-cards"
FIXTURES = ROOT / "scripts" / "tests" / "fixtures" / "source-cards"
REQUIRED_FIELDS = {
    "family", "display_name", "publisher", "publisher_short", "authoritative_url",
    "alternate_urls", "license", "declared_cadence", "datasets_in_family", "data_type_mix",
    "access_method", "browser_dependency", "schema_kind", "expected_record_count_band",
    "freshness_signals", "known_false_positives", "known_false_negatives", "rate_limit_or_robots",
    "failure_examples", "current_probe_rule", "regression_fixture", "last_reviewed",
    "next_review_date", "contract_version",
}


def _card(name: str) -> dict[str, object]:
    return load_card(CARDS / name)


def test_bnm_card_has_required_frontmatter_fields() -> None:
    assert REQUIRED_FIELDS <= _card("bnm-open-api.md").keys()


def test_gtfs_card_has_required_frontmatter_fields() -> None:
    assert REQUIRED_FIELDS <= _card("gtfs-api.md").keys()


def test_bnm_card_yaml_parses() -> None:
    assert _card("bnm-open-api.md")["family"] == "bnm_open_api"


def test_gtfs_card_yaml_parses() -> None:
    assert _card("gtfs-api.md")["family"] == "gtfs_api"


def test_card_body_has_narrative() -> None:
    for name in ("bnm-open-api.md", "gtfs-api.md"):
        parts = (CARDS / name).read_text(encoding="utf-8").split("---\n", 2)
        assert len(parts) == 3
        assert parts[2].strip()


def test_card_dates_are_iso8601() -> None:
    for name in ("bnm-open-api.md", "gtfs-api.md"):
        card = _card(name)
        date.fromisoformat(str(card["last_reviewed"]))
        date.fromisoformat(str(card["next_review_date"]))


def test_card_known_false_positives_non_empty_bnm() -> None:
    assert _card("bnm-open-api.md")["known_false_positives"]


def test_card_known_false_positives_non_empty_gtfs() -> None:
    assert _card("gtfs-api.md")["known_false_positives"]


def test_json_fixtures_mirror_card_frontmatter_shape() -> None:
    for card_name, fixture_name in (("bnm-open-api.md", "bnm-open-api.json"), ("gtfs-api.md", "gtfs-api.json")):
        fixture = json.loads((FIXTURES / fixture_name).read_text(encoding="utf-8"))
        assert fixture.keys() == _card(card_name).keys()
