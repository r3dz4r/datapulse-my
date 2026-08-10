"""Focused tests for GTFS realtime freshness timestamp selection."""

from __future__ import annotations

from datetime import datetime, timezone

from scripts.probe_gtfs import select_realtime_timestamp


def test_feed_header_timestamp_wins_over_future_vehicle_timestamp() -> None:
    now = datetime(2026, 8, 10, 4, 0, tzinfo=timezone.utc)
    header_timestamp = int(datetime(2026, 8, 10, 3, 59, tzinfo=timezone.utc).timestamp())
    future_vehicle_timestamp = int(
        datetime(2029, 10, 7, 4, 25, tzinfo=timezone.utc).timestamp()
    )

    selected = select_realtime_timestamp(
        header_timestamp,
        [future_vehicle_timestamp],
        now=now,
    )

    assert selected == header_timestamp


def test_newest_non_future_vehicle_timestamp_is_used_without_header() -> None:
    now = datetime(2026, 8, 10, 4, 0, tzinfo=timezone.utc)
    older_timestamp = int(datetime(2026, 8, 10, 3, 55, tzinfo=timezone.utc).timestamp())
    newest_timestamp = int(datetime(2026, 8, 10, 3, 59, tzinfo=timezone.utc).timestamp())
    future_timestamp = int(datetime(2029, 10, 7, 4, 25, tzinfo=timezone.utc).timestamp())

    selected = select_realtime_timestamp(
        0,
        [older_timestamp, newest_timestamp, future_timestamp],
        now=now,
    )

    assert selected == newest_timestamp
