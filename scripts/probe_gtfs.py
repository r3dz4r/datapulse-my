#!/usr/bin/env python3
"""Probe GTFS static ZIPs and realtime vehicle-position protobuf feeds."""

from __future__ import annotations

import argparse
import csv
import io
import json
import re
import subprocess
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REQUIRED_STATIC_FILES = (
    "agency.txt",
    "stops.txt",
    "routes.txt",
    "trips.txt",
    "stop_times.txt",
    "calendar.txt",
)
MAX_UNCOMPRESSED_BYTES = 250_000_000


def _curl(args: list[str], timeout: int) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(
        ["curl", "--location", "--silent", "--show-error", "--max-time", str(timeout), *args],
        capture_output=True,
        check=False,
    )


def _header_value(headers: str, field: str) -> str | None:
    value = None
    prefix = f"{field}:".casefold()
    for line in headers.splitlines():
        if line.casefold().startswith(prefix):
            value = line.split(":", 1)[1].strip()
    return value


def _http_date(value: str | None) -> str | None:
    if not value:
        return None
    try:
        parsed = datetime.strptime(value, "%a, %d %b %Y %H:%M:%S %Z")
    except ValueError:
        return None
    return parsed.replace(tzinfo=timezone.utc).isoformat().replace("+00:00", "Z")


def _base(dataset_id: str, url: str) -> dict[str, Any]:
    return {
        "dataset_id": dataset_id,
        "url": url,
        "request_url": url,
        "access_method": "direct curl",
    }


def _head(dataset_id: str, url: str, timeout: int) -> tuple[dict[str, Any], int]:
    result = _curl(
        [
            "--head",
            "--dump-header",
            "-",
            "--output",
            "/dev/null",
            "--write-out",
            "\n%{http_code}",
            "--",
            url,
        ],
        timeout,
    )
    output = result.stdout.decode("latin-1", errors="replace")
    header_text, _, status_text = output.rpartition("\n")
    try:
        status = int(status_text)
    except ValueError:
        status = 0
    content_length = _header_value(header_text, "content-length")
    details = _base(dataset_id, url) | {
        "http_status": status,
        "content_length": (
            int(content_length)
            if content_length and content_length.isdigit()
            else None
        ),
        "last_modified": _http_date(_header_value(header_text, "last-modified")),
    }
    return details, status


def _save_first_sample(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_bytes(payload)


def _row_count(archive: zipfile.ZipFile, name: str) -> int:
    with archive.open(name) as raw:
        return max(0, sum(1 for _ in io.TextIOWrapper(raw, encoding="utf-8-sig", newline="")) - 1)


def select_realtime_timestamp(
    header_timestamp: int,
    vehicle_timestamps: list[int],
    *,
    now: datetime | None = None,
) -> int:
    """Use the feed timestamp, falling back to the newest non-future vehicle."""
    if header_timestamp:
        return header_timestamp

    current_timestamp = int((now or datetime.now(timezone.utc)).timestamp())
    return max(
        (
            timestamp
            for timestamp in vehicle_timestamps
            if 0 < timestamp <= current_timestamp
        ),
        default=0,
    )


def check_gtfs_static_dataset(
    dataset_id: str, url: str, sample_path: Path, timeout: int
) -> dict[str, Any]:
    details, status = _head(dataset_id, url, timeout)
    if status < 200 or status >= 300:
        return details | {
            "status": "unreachable",
            "message": f"HTTP {status}" if status else "curl HEAD request failed",
        }

    response = _curl(["--output", "-", "--write-out", "", "--", url], timeout)
    if response.returncode != 0:
        return details | {"status": "unreachable", "message": "curl GET request failed"}
    payload = response.stdout
    _save_first_sample(sample_path, payload)
    details["content_length"] = len(payload)

    try:
        with zipfile.ZipFile(io.BytesIO(payload)) as archive:
            uncompressed_size = sum(item.file_size for item in archive.infolist())
            if uncompressed_size > MAX_UNCOMPRESSED_BYTES:
                raise ValueError(
                    f"uncompressed content exceeds {MAX_UNCOMPRESSED_BYTES} bytes"
                )
            names = set(archive.namelist())
            missing = [name for name in REQUIRED_STATIC_FILES if name not in names]
            if missing:
                raise ValueError(f"missing required files: {', '.join(missing)}")
            counts = {
                name.removesuffix(".txt"): _row_count(archive, name)
                for name in REQUIRED_STATIC_FILES
            }
            with archive.open("calendar.txt") as raw:
                rows = csv.DictReader(
                    io.TextIOWrapper(raw, encoding="utf-8-sig", newline="")
                )
                dates = [
                    (row.get("start_date", ""), row.get("end_date", ""))
                    for row in rows
                    if row.get("start_date") and row.get("end_date")
                ]
    except (ValueError, zipfile.BadZipFile, KeyError, csv.Error, UnicodeError) as exc:
        return details | {"status": "degraded", "message": f"Invalid GTFS ZIP: {exc}"}

    if not dates:
        return details | {
            "status": "degraded",
            "message": "Invalid GTFS ZIP: calendar.txt has no service dates",
            **counts,
            "record_count": max(counts.values(), default=0),
        }

    start_date = max(start for start, _ in dates)
    end_date = max(end for _, end in dates)
    try:
        content_date = datetime.strptime(end_date, "%Y%m%d").date().isoformat()
        start_iso = datetime.strptime(start_date, "%Y%m%d").date().isoformat()
    except ValueError as exc:
        return details | {
            "status": "degraded",
            "message": f"Invalid GTFS calendar date: {exc}",
            **counts,
        }

    return details | {
        "status": "fresh",
        "message": "HTTP 200; valid GTFS static ZIP",
        **counts,
        "record_count": max(counts["stops"], counts["trips"], counts["stop_times"]),
        "date_range": {"start": start_iso, "end": content_date},
        "content_freshness_date": content_date,
    }


def check_gtfs_realtime_dataset(
    dataset_id: str, url: str, sample_path: Path, timeout: int
) -> dict[str, Any]:
    details = _base(dataset_id, url)
    response = _curl(
        ["--output", "-", "--write-out", "%{http_code}", "--", url], timeout
    )
    if response.returncode != 0:
        return details | {
            "http_status": 0,
            "status": "unreachable",
            "message": "curl GET request failed",
        }

    try:
        status = int(response.stdout[-3:].decode("ascii"))
    except (UnicodeDecodeError, ValueError):
        status = 0
    payload = response.stdout[:-3]
    details |= {"http_status": status, "content_length": len(payload)}
    if status < 200 or status >= 300:
        return details | {"status": "unreachable", "message": f"HTTP {status}"}

    _save_first_sample(sample_path, payload)
    try:
        from google.transit import gtfs_realtime_pb2

        feed = gtfs_realtime_pb2.FeedMessage()
        feed.ParseFromString(payload)
        if not feed.IsInitialized():
            raise ValueError("protobuf is missing its required feed header")
    except Exception as exc:
        return details | {"status": "degraded", "message": f"Invalid GTFS realtime protobuf: {exc}"}

    vehicle_timestamps = [
        entity.vehicle.timestamp
        for entity in feed.entity
        if entity.HasField("vehicle") and entity.vehicle.timestamp
    ]
    vehicle_count = sum(entity.HasField("vehicle") for entity in feed.entity)
    header_timestamp = feed.header.timestamp if feed.header.HasField("timestamp") else 0
    newest_vehicle_timestamp = max(vehicle_timestamps, default=0)
    newest_timestamp = select_realtime_timestamp(header_timestamp, vehicle_timestamps)
    content_date = (
        datetime.fromtimestamp(newest_timestamp, tz=timezone.utc).date().isoformat()
        if newest_timestamp
        else None
    )
    return details | {
        "status": "fresh",
        "message": f"HTTP 200; valid GTFS realtime protobuf ({vehicle_count} vehicles)",
        "vehicle_count": vehicle_count,
        "record_count": vehicle_count,
        "header_timestamp": header_timestamp or None,
        "newest_vehicle_timestamp": newest_vehicle_timestamp or None,
        "content_freshness_date": content_date,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("dataset_id")
    parser.add_argument("url")
    parser.add_argument("--sample", required=True, type=Path)
    parser.add_argument("--timeout", type=int, default=45)
    args = parser.parse_args()
    if not re.fullmatch(r"gtfs_(?:static|realtime)_[a-z0-9_]+", args.dataset_id):
        parser.error("dataset_id contains unsupported characters")
    if args.dataset_id.startswith("gtfs_static_"):
        result = check_gtfs_static_dataset(args.dataset_id, args.url, args.sample, args.timeout)
    elif args.dataset_id.startswith("gtfs_realtime_"):
        result = check_gtfs_realtime_dataset(args.dataset_id, args.url, args.sample, args.timeout)
    else:
        parser.error("dataset_id must start with gtfs_static_ or gtfs_realtime_")
    json.dump(result, sys.stdout, separators=(",", ":"))
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
