"""Focused tests for GTFS realtime freshness timestamp selection."""

from __future__ import annotations

from datetime import datetime, timezone
from io import BytesIO
import zipfile

from scripts.probe_gtfs import _archive_member_headers, select_realtime_timestamp
from scripts.shape_fingerprint import fingerprint_archive_member_headers


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


def test_gtfs_archive_fingerprint_ignores_zip_metadata_and_member_order() -> None:
    def fingerprint(
        entries: list[tuple[str, str]], compression: int, timestamp: tuple[int, int, int, int, int, int]
    ) -> str:
        payload = BytesIO()
        with zipfile.ZipFile(payload, "w", compression=compression) as archive:
            for name, text in entries:
                info = zipfile.ZipInfo(name, date_time=timestamp)
                info.compress_type = compression
                archive.writestr(info, text)
        with zipfile.ZipFile(BytesIO(payload.getvalue())) as archive:
            return fingerprint_archive_member_headers(_archive_member_headers(archive))

    first = fingerprint(
        [("stops.txt", "stop_id,stop_name\nS1,Central\n"), ("routes.txt", "route_id,route_name\nR1,Blue\n")],
        zipfile.ZIP_STORED,
        (2020, 1, 1, 0, 0, 0),
    )
    second = fingerprint(
        [("routes.txt", "route_id,route_name\nR9,Green\n"), ("stops.txt", "stop_id,stop_name\nS9,Harbour\n")],
        zipfile.ZIP_DEFLATED,
        (2026, 1, 1, 0, 0, 0),
    )

    assert first == second
