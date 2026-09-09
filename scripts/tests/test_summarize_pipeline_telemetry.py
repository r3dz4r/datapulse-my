from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/summarize_pipeline_telemetry.py"


def _event(
    ts: str,
    stage: str,
    duration_ms: int,
    status: str = "success",
    cycle: str = "cycle-a",
    extra: object | None = None,
) -> dict[str, object]:
    return {
        "ts": ts,
        "stage": stage,
        "duration_ms": duration_ms,
        "status": status,
        "cycle": cycle,
        "extra": {} if extra is None else extra,
    }


def _write_events(path: Path, events: list[dict[str, object]]) -> None:
    path.write_text("\n".join(json.dumps(event) for event in events) + "\n", encoding="utf-8")


def _run(input_path: Path, output_path: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--input",
            str(input_path),
            "--output",
            str(output_path),
            "--mode",
            "health-cycle",
            "--source-commit",
            "abcdef1",
            "--health-commit",
            "1234567",
            *args,
        ],
        capture_output=True,
        text=True,
        check=False,
    )


def test_aggregates_a_sanitized_receipt_for_selected_cycle(tmp_path: Path) -> None:
    telemetry = tmp_path / "stages.jsonl"
    receipt = tmp_path / "receipt.json"
    _write_events(
        telemetry,
        [
            _event("2026-09-09T00:00:00Z", "probe", 120, extra={"token": "secret"}),
            _event(
                "2026-09-09T00:00:02Z",
                "publish",
                45,
                extra={"lag_ms": 2000, "publication_lag_ms": 2000, "ignored": {"secret": "x"}},
            ),
            _event("2026-09-09T00:00:03Z", "mcp-sync", 30, extra={"result": "no-change", "source": "deploy"}),
        ],
    )

    result = _run(telemetry, receipt, "--cycle", "cycle-a")

    assert result.returncode == 0, result.stderr
    assert json.loads(receipt.read_text(encoding="utf-8")) == {
        "cycle": "cycle-a",
        "failed_stages": [],
        "first_timestamp": "2026-09-09T00:00:00Z",
        "health_commit": "1234567",
        "last_timestamp": "2026-09-09T00:00:03Z",
        "mode": "health-cycle",
        "schema": "datapulse/v1/pipeline-run-receipt",
        "source_commit": "abcdef1",
        "stages": {
            "mcp-sync": {"duration_ms": 30, "metadata": {"result": "no-change", "source": "deploy"}, "status": "success"},
            "probe": {"duration_ms": 120, "metadata": {}, "status": "success"},
            "publish": {"duration_ms": 45, "metadata": {"lag_ms": 2000, "publication_lag_ms": 2000}, "status": "success"},
        },
        "total_elapsed_ms": 3000,
        "version": 1,
    }
    assert "secret" not in receipt.read_text(encoding="utf-8")


def test_selects_latest_cycle_deterministically_when_cycle_is_omitted(tmp_path: Path) -> None:
    telemetry = tmp_path / "stages.jsonl"
    receipt = tmp_path / "receipt.json"
    _write_events(
        telemetry,
        [
            _event("2026-09-09T00:00:00Z", "probe", 1, cycle="older"),
            _event("2026-09-09T01:00:00Z", "probe", 2, cycle="newer"),
        ],
    )

    result = _run(telemetry, receipt)

    assert result.returncode == 0, result.stderr
    assert json.loads(receipt.read_text(encoding="utf-8"))["cycle"] == "newer"


def test_reports_failed_stages_and_non_fatal_metadata(tmp_path: Path) -> None:
    telemetry = tmp_path / "stages.jsonl"
    receipt = tmp_path / "receipt.json"
    _write_events(
        telemetry,
        [
            _event("2026-09-09T00:00:00Z", "probe", 12, status="fail", extra={"exit_code": 7, "non_fatal": False}),
            _event("2026-09-09T00:00:01Z", "evidence", 5, status="skipped"),
        ],
    )

    result = _run(telemetry, receipt, "--cycle", "cycle-a")

    assert result.returncode == 0, result.stderr
    payload = json.loads(receipt.read_text(encoding="utf-8"))
    assert payload["failed_stages"] == ["probe"]
    assert payload["stages"]["probe"]["metadata"] == {"exit_code": 7, "non_fatal": False}


def test_rejects_malformed_rows_and_preserves_existing_output(tmp_path: Path) -> None:
    telemetry = tmp_path / "stages.jsonl"
    receipt = tmp_path / "receipt.json"
    telemetry.write_text('{"ts":"not-a-timestamp"}\n', encoding="utf-8")
    receipt.write_text("known-good\n", encoding="utf-8")

    result = _run(telemetry, receipt)

    assert result.returncode != 0
    assert receipt.read_text(encoding="utf-8") == "known-good\n"
    assert not list(tmp_path.glob(".receipt.json.*.tmp"))


def test_rejects_unknown_values_unsafe_metadata_and_contradictory_duplicates(tmp_path: Path) -> None:
    cases = [
        [_event("2026-09-09T00:00:00Z", "unknown", 1)],
        [{**_event("2026-09-09T00:00:00Z", "probe", 1), "stage": ["probe"]}],
        [_event("2026-09-09T00:00:00Z", "probe", 1, status="unknown")],
        [_event("2026-09-09T00:00:00Z", "probe", 1, extra=["not-an-object"])],
        [
            _event("2026-09-09T00:00:00Z", "probe", 1),
            _event("2026-09-09T00:00:01Z", "probe", 2),
        ],
    ]
    for index, events in enumerate(cases):
        telemetry = tmp_path / f"stages-{index}.jsonl"
        receipt = tmp_path / f"receipt-{index}.json"
        _write_events(telemetry, events)

        result = _run(telemetry, receipt, "--cycle", "cycle-a")

        assert result.returncode != 0
        assert not receipt.exists()


def test_output_is_byte_deterministic_and_identical_duplicates_are_accepted(tmp_path: Path) -> None:
    telemetry = tmp_path / "stages.jsonl"
    first = tmp_path / "first.json"
    second = tmp_path / "second.json"
    event = _event("2026-09-09T00:00:00+00:00", "probe", 12, extra={"source": "runner", "ignored": "value"})
    _write_events(telemetry, [event, event])

    assert _run(telemetry, first, "--cycle", "cycle-a").returncode == 0
    assert _run(telemetry, second, "--cycle", "cycle-a").returncode == 0
    assert first.read_bytes() == second.read_bytes()


def test_rejects_invalid_pipeline_metadata_identifiers(tmp_path: Path) -> None:
    telemetry = tmp_path / "stages.jsonl"
    receipt = tmp_path / "receipt.json"
    _write_events(telemetry, [_event("2026-09-09T00:00:00Z", "probe", 1)])

    for option, value in (
        ("--mode", "production"),
        ("--source-commit", "ABC1234"),
        ("--source-commit", "abcdef"),
        ("--health-commit", "abcdefg "),
        ("--health-commit", "/tmp/commit"),
    ):
        result = _run(telemetry, receipt, option, value)

        assert result.returncode != 0
        assert not receipt.exists()
