"""Regression coverage for a coalesced stage record superseded by the work record.

Measured 2026-10-05: ``publish.push`` lands twice in one cycle. The first attempt
is coalesced by the minimum publish interval and recorded as ``skipped``
(``elapsed_seconds`` 265 against ``interval_seconds`` 1200); the second performs
the push and records ``success`` (``duration_ms`` 890). The summariser treated
that legal sequence as a contradiction and wrote no receipt at all.

The paired guard proves the relaxation is narrow: two differing non-skipped
records for one stage remain a genuine contradiction and are still refused.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/summarize_pipeline_telemetry.py"
CYCLE = "2026-10-05T00:00:00Z"


def _event(
    ts: str,
    stage: str,
    duration_ms: int,
    status: str = "success",
    extra: object | None = None,
) -> dict[str, object]:
    return {
        "ts": ts,
        "stage": stage,
        "duration_ms": duration_ms,
        "status": status,
        "cycle": CYCLE,
        "extra": {} if extra is None else extra,
    }


def _write_events(path: Path, events: list[dict[str, object]]) -> None:
    path.write_text("\n".join(json.dumps(event) for event in events) + "\n", encoding="utf-8")


def _run(input_path: Path, output_path: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--input",
            str(input_path),
            "--output",
            str(output_path),
            "--cycle",
            CYCLE,
            "--mode",
            "health-cycle",
            "--source-commit",
            "abcdef1",
            "--health-commit",
            "1234567",
        ],
        capture_output=True,
        text=True,
        check=False,
    )


def _coalesced_then_work() -> list[dict[str, object]]:
    """The exact measured two-attempt publish.push sequence for one cycle."""
    return [
        _event(
            "2026-10-05T00:00:00Z",
            "publish.push",
            0,
            status="skipped",
            extra={"elapsed_seconds": 265, "interval_seconds": 1200},
        ),
        _event("2026-10-05T00:00:01Z", "publish.push", 890, status="success"),
    ]


def test_coalesced_attempt_is_superseded_by_the_work_record(tmp_path: Path) -> None:
    telemetry = tmp_path / "stages.jsonl"
    receipt = tmp_path / "receipt.json"
    _write_events(telemetry, _coalesced_then_work())

    result = _run(telemetry, receipt)

    assert result.returncode == 0, result.stderr
    payload = json.loads(receipt.read_text(encoding="utf-8"))
    entry = payload["stages"]["publish.push"]
    # The recorded outcome is the attempt that actually performed the push.
    assert entry["status"] == "success"
    assert entry["duration_ms"] == 890
    # The coalesced attempt is preserved, not dropped, ahead of the work record.
    coalesced = entry["coalesced"]
    assert [attempt["status"] for attempt in coalesced] == ["skipped"]
    assert coalesced[0]["duration_ms"] == 0
    assert coalesced[0]["timestamp"] == "2026-10-05T00:00:00Z"
    assert payload["failed_stages"] == []


def test_coalesced_precedence_does_not_depend_on_file_order(tmp_path: Path) -> None:
    telemetry = tmp_path / "stages.jsonl"
    receipt = tmp_path / "receipt.json"
    # Same timestamps, opposite file order: chronology decides precedence, not
    # the order in which the producer happened to append the rows.
    _write_events(telemetry, list(reversed(_coalesced_then_work())))

    result = _run(telemetry, receipt)

    assert result.returncode == 0, result.stderr
    entry = json.loads(receipt.read_text(encoding="utf-8"))["stages"]["publish.push"]
    assert entry["status"] == "success"
    assert entry["duration_ms"] == 890
    assert [attempt["status"] for attempt in entry["coalesced"]] == ["skipped"]


def test_differing_non_skipped_records_are_still_contradictory(tmp_path: Path) -> None:
    cases = [
        # A success against a failure.
        [
            _event("2026-10-05T00:00:00Z", "publish.push", 890, status="success"),
            _event("2026-10-05T00:00:01Z", "publish.push", 12, status="fail"),
        ],
        # Two successes with different durations.
        [
            _event("2026-10-05T00:00:00Z", "publish.push", 890, status="success"),
            _event("2026-10-05T00:00:01Z", "publish.push", 901, status="success"),
        ],
    ]
    for index, events in enumerate(cases):
        telemetry = tmp_path / f"stages-{index}.jsonl"
        receipt = tmp_path / f"receipt-{index}.json"
        _write_events(telemetry, events)

        result = _run(telemetry, receipt)

        assert result.returncode != 0
        assert "contradictory duplicate record for stage publish.push" in result.stderr
        assert not receipt.exists()
