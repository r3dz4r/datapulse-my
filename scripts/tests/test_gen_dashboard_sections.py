from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

import pytest

from scripts import gen_dashboard_sections as sections


def test_readme_parser_collects_dataset_ids_until_next_heading() -> None:
    readme = """\
### Daily reference data

#### Bank Negara Malaysia (BNM)

- [Morning rates](data/exchangerates_daily_0900.md) — sample
  continuation text
- [Noon rates](data/exchangerates_daily_1200.md)

#### MET Malaysia

- [Weather](data/met_weather.md)

### GTFS transit feeds
- [Ignored](data/not_part_of_met.md)
"""

    assert sections.parse_readme_categories(readme) == {
        "Bank Negara Malaysia (BNM)": [
            "exchangerates_daily_0900",
            "exchangerates_daily_1200",
        ],
        "MET Malaysia": ["met_weather"],
    }


def test_popular_ids_use_supported_engagement_fields_and_manifest_membership() -> None:
    metrics = [
        {"id": "csv-heavy", "views": 2, "download_csv": 8, "download_parquet": 1},
        {"id": "not-tracked", "views": 9999},
        {"id": "viewed", "views": 9, "download_png": 5000},
        {"id": "parquet", "views": "3", "download_parquet": "5"},
    ]

    assert sections.select_popular_ids(
        metrics, {"csv-heavy", "viewed", "parquet"}, limit=2
    ) == ["csv-heavy", "viewed"]


def test_section_assembly_uses_canonical_order_and_assigns_every_dataset_once() -> None:
    manifest = {
        "datasets": [
            {"id": "bnm", "data_type": "dataset"},
            {"id": "met", "data_type": "dataset"},
            {"id": "gtfs_static_demo", "data_type": "dataset"},
            {"id": "hansard_sittings", "data_type": "dataset"},
            {"id": "hansard_parliamentary_terms", "data_type": "dataset"},
            {"id": "hansard_mps", "data_type": "dataset"},
            {"id": "reference", "data_type": "reference"},
            {"id": "other", "data_type": "dataset"},
        ]
    }
    parsed = {
        "Bank Negara Malaysia (BNM)": ["bnm", "reference"],
        "MET Malaysia": ["met"],
    }

    result = sections.build_sections(manifest, parsed, ["other", "bnm"])

    assert [section["key"] for section in result] == [
        "top_visited",
        "bnm",
        "met",
        "doe",
        "kkm",
        "opendosm",
        "data_gov_my",
        "gtfs",
        "hansard",
        "reference",
        "other_government_open_data",
    ]
    assert result[0] == {
        "name": "Most-Consumed Malaysian Data",
        "key": "top_visited",
        "type": "popular",
        "datasets": ["other", "bnm"],
    }
    category_ids = [
        dataset_id
        for section in result[1:]
        for dataset_id in section["datasets"]
    ]
    assert category_ids == [
        "bnm",
        "met",
        "gtfs_static_demo",
        "hansard_sittings",
        "hansard_parliamentary_terms",
        "hansard_mps",
        "reference",
        "other",
    ]
    assert len(category_ids) == len(set(category_ids)) == len(manifest["datasets"])


def test_fresh_metrics_cache_avoids_network(tmp_path: Path) -> None:
    cache = tmp_path / "metrics.json"
    now = dt.datetime(2026, 8, 10, 8, 30, tzinfo=dt.UTC)
    cache.write_text(
        json.dumps(
            {
                "fetched_at": "2026-08-10T08:00:00Z",
                "datasets": [{"id": "cached", "views": 10}],
            }
        ),
        encoding="utf-8",
    )

    def unexpected_network(_request: object, timeout: int) -> object:
        pytest.fail(f"network called with timeout={timeout}")

    metrics, fetched_at = sections.load_metrics(
        cache, now=now, opener=unexpected_network
    )

    assert metrics == [{"id": "cached", "views": 10}]
    assert fetched_at == "2026-08-10T08:00:00Z"


def test_stale_cache_is_used_when_refresh_fails(tmp_path: Path) -> None:
    cache = tmp_path / "metrics.json"
    now = dt.datetime(2026, 8, 10, 10, 30, tzinfo=dt.UTC)
    cache.write_text(
        json.dumps(
            {
                "fetched_at": "2026-08-10T08:00:00Z",
                "datasets": [{"id": "stale", "views": 10}],
            }
        ),
        encoding="utf-8",
    )

    def failed_network(_request: object, timeout: int) -> object:
        raise OSError(f"offline after {timeout}s")

    metrics, fetched_at = sections.load_metrics(
        cache, now=now, opener=failed_network
    )

    assert metrics == [{"id": "stale", "views": 10}]
    assert fetched_at == "2026-08-10T08:00:00Z"
