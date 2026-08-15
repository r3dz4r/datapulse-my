from __future__ import annotations

import gzip
import json
import subprocess
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WRITER = ROOT / "scripts/gen_health_history.py"
FIXTURE = ROOT / "scripts/tests/fixtures/health-history-snapshot.json"


def _snapshot(tmp_path: Path, *, count: int = 375, checked_at: str | None = None) -> Path:
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    if checked_at is not None:
        payload["checked_at"] = checked_at
    template = payload["datasets"][0]
    payload["datasets"] = [
        {**template, "dataset_id": f"dataset-{number:03d}", "record_count": number}
        for number in range(count)
    ]
    path = tmp_path / "latest.json"
    path.write_text(json.dumps(payload) + "\n", encoding="utf-8")
    return path


def _run(
    tmp_path: Path,
    snapshot: Path,
    *,
    cycle: str = "2026-08-12T18:00",
    compact: bool = False,
    retention_days: int = 90,
    now: str = "2026-08-12T18:00:05+08:00",
    archives_dir: Path | None = None,
) -> subprocess.CompletedProcess[str]:
    command = [
        "python3",
        str(WRITER),
        "--snapshot",
        str(snapshot),
        "--history",
        str(tmp_path / "history.jsonl"),
        "--daily",
        str(tmp_path / "history_daily.json"),
        "--cycle",
        cycle,
        "--retention-days",
        str(retention_days),
        "--now",
        now,
    ]
    command.extend(["--archives-dir", str(archives_dir or (tmp_path / "archives"))])
    if compact:
        command.append("--compact")
    return subprocess.run(command, capture_output=True, text=True, check=False)


def _history(tmp_path: Path) -> list[dict]:
    return [
        json.loads(line)
        for line in (tmp_path / "history.jsonl").read_text(encoding="utf-8").splitlines()
    ]


def test_history_append(tmp_path: Path) -> None:
    snapshot = _snapshot(tmp_path)

    result = _run(tmp_path, snapshot)

    assert result.returncode == 0, result.stderr
    rows = _history(tmp_path)
    assert len(rows) == 375
    assert rows[0] == {
        "dataset_id": "dataset-000",
        "observed_at": "2026-08-12T10:00:05Z",
        "cycle": "2026-08-12T18:00",
        "status": "fresh",
        "freshness_signal": "content-date-parse",
        "last_modified": "2026-08-08T09:55:45Z",
        "content_date": "2026-08-12",
        "record_count": 0,
        "record_count_estimated": False,
        "http_status": 200,
        "latency_ms": None,
        "probe_outcome": "success",
        "message": "HTTP 200",
    }


def test_history_upsert_idempotent(tmp_path: Path) -> None:
    snapshot = _snapshot(tmp_path)
    first = _run(tmp_path, snapshot)
    assert first.returncode == 0, first.stderr
    payload = json.loads(snapshot.read_text(encoding="utf-8"))
    payload["datasets"][0]["record_count"] = 999
    snapshot.write_text(json.dumps(payload) + "\n", encoding="utf-8")

    second = _run(tmp_path, snapshot)

    assert second.returncode == 0, second.stderr
    rows = _history(tmp_path)
    assert len(rows) == 375
    assert next(row for row in rows if row["dataset_id"] == "dataset-000")[
        "record_count"
    ] == 999


def test_history_carries_delta_comparison_fields(tmp_path: Path) -> None:
    snapshot = _snapshot(tmp_path, count=1)
    payload = json.loads(snapshot.read_text(encoding="utf-8"))
    payload["datasets"][0].update(
        {
            "url": "https://example.test/dataset-000.csv",
            "first_row_hash": "shape-v1:fixture",
            "column_count": 7,
        }
    )
    snapshot.write_text(json.dumps(payload) + "\n", encoding="utf-8")

    result = _run(tmp_path, snapshot)

    assert result.returncode == 0, result.stderr
    row = _history(tmp_path)[0]
    assert row["url"] == "https://example.test/dataset-000.csv"
    assert row["shape_hash"] == "shape-v1:fixture"
    assert row["column_count"] == 7


def test_history_retention(tmp_path: Path) -> None:
    old_snapshot = _snapshot(tmp_path, count=2, checked_at="2026-05-01T00:00:05Z")
    old = _run(
        tmp_path,
        old_snapshot,
        cycle="2026-05-01T08:00",
        now="2026-05-01T08:00:05+08:00",
    )
    assert old.returncode == 0, old.stderr
    current_snapshot = _snapshot(tmp_path, count=2)

    compacted = _run(tmp_path, current_snapshot, compact=True, retention_days=90)

    assert compacted.returncode == 0, compacted.stderr
    assert len(_history(tmp_path)) == 2
    daily = json.loads((tmp_path / "history_daily.json").read_text(encoding="utf-8"))
    assert sum(row["observations"] for row in daily["aggregates"]) == 2
    assert {row["dataset_id"] for row in daily["aggregates"]} == {
        "dataset-000",
        "dataset-001",
    }


def test_history_compaction_shape(tmp_path: Path) -> None:
    snapshot = _snapshot(tmp_path, count=1, checked_at="2026-05-01T00:00:05Z")

    result = _run(tmp_path, snapshot, compact=True, retention_days=1)

    assert result.returncode == 0, result.stderr
    daily = json.loads((tmp_path / "history_daily.json").read_text(encoding="utf-8"))
    assert daily["schema"] == "datapulse/v1/health-history-daily"
    assert daily["retention_days"] == 1
    aggregate = daily["aggregates"][0]
    assert set(aggregate) == {
        "dataset_id",
        "date",
        "first_observed_at",
        "last_observed_at",
        "observations",
        "status_distribution",
        "probe_outcome_distribution",
        "availability_percent",
        "record_count",
        "latency_ms",
    }
    assert aggregate["record_count"] == {
        "min": 0,
        "mean": 0.0,
        "max": 0,
        "samples": 1,
        "sum": 0,
    }
    assert aggregate["latency_ms"] == {"mean": None, "samples": 0, "sum": 0}


def test_history_compaction_is_idempotent(tmp_path: Path) -> None:
    snapshot = _snapshot(tmp_path, count=2, checked_at="2026-05-01T00:00:05Z")
    first = _run(tmp_path, snapshot, compact=True, retention_days=1)
    assert first.returncode == 0, first.stderr

    second = _run(tmp_path, snapshot, compact=True, retention_days=1)

    assert second.returncode == 0, second.stderr
    daily = json.loads((tmp_path / "history_daily.json").read_text(encoding="utf-8"))
    assert daily["compacted_cycles"] == ["2026-08-12T18:00"]
    assert sum(row["observations"] for row in daily["aggregates"]) == 2
    assert _history(tmp_path) == []


def test_archives_expired_rows(tmp_path: Path) -> None:
    history_path = tmp_path / "history.jsonl"
    rows = []
    for day in range(90):
        observed_at = (
            datetime(2026, 5, 19) + timedelta(days=day)
        ).strftime("%Y-%m-%dT00:00:05Z")
        rows.append(
            {
                "dataset_id": "dataset-000",
                "observed_at": observed_at,
                "cycle": observed_at[:16],
                "status": "fresh",
                "probe_outcome": "success",
                "record_count": day,
                "latency_ms": 10,
            }
        )
    history_path.write_text(
        "".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8"
    )
    snapshot = _snapshot(tmp_path, count=1, checked_at="2026-08-16T00:00:05Z")
    archives_dir = tmp_path / "archives"

    first = _run(
        tmp_path,
        snapshot,
        cycle="2026-08-16T00:00",
        compact=True,
        retention_days=30,
        now="2026-08-16T00:00:05+00:00",
        archives_dir=archives_dir,
    )

    assert first.returncode == 0, first.stderr
    hot_rows = _history(tmp_path)
    assert len(hot_rows) == 31
    assert min(row["observed_at"] for row in hot_rows) >= "2026-07-17T00:00:00Z"
    archive_rows = []
    for archive_path in sorted(archives_dir.glob("*.jsonl.gz")):
        with gzip.open(archive_path, "rt", encoding="utf-8") as archive:
            archive_rows.extend(json.loads(line) for line in archive)
    assert len(archive_rows) == 59
    assert {row["cycle"] for row in archive_rows} == {
        row["cycle"] for row in rows if row["observed_at"] < "2026-07-17T00:00:00Z"
    }

    second = _run(
        tmp_path,
        snapshot,
        cycle="2026-08-16T00:00",
        compact=True,
        retention_days=30,
        now="2026-08-16T00:00:05+00:00",
        archives_dir=archives_dir,
    )

    assert second.returncode == 0, second.stderr
    reread_archive_rows = []
    for archive_path in sorted(archives_dir.glob("*.jsonl.gz")):
        with gzip.open(archive_path, "rt", encoding="utf-8") as archive:
            reread_archive_rows.extend(json.loads(line) for line in archive)
    assert reread_archive_rows == archive_rows


def test_history_latest_unchanged(tmp_path: Path) -> None:
    snapshot = _snapshot(tmp_path)
    before = snapshot.read_bytes()

    result = _run(tmp_path, snapshot, compact=True)

    assert result.returncode == 0, result.stderr
    assert snapshot.read_bytes() == before
