from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from scripts import aggregate_pipeline_observation as observation


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/aggregate_pipeline_observation.py"
START = "2026-09-09T00:00:00Z"
END = "2026-09-10T00:00:00Z"


def _run(output: Path, *inputs: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--start", START, "--end", END, "--output", str(output), *inputs],
        capture_output=True,
        text=True,
        check=False,
    )


def _event(ts: str, stage: str = "probe", status: str = "success", cycle: str = "cycle-a") -> dict[str, object]:
    return {"ts": ts, "stage": stage, "duration_ms": 5, "status": status, "cycle": cycle, "extra": {"token": "hidden"}}


def _receipt(checked_at: str = "2026-09-09T01:00:00Z", source: str = "a" * 40, health: str = "b" * 40) -> dict[str, object]:
    return {
        "schema": "datapulse/v1/shadow-health-publication-envelope", "version": 1,
        "source_commit": source, "health_commit": health, "checked_at": checked_at,
        "dataset_count": 2, "health_sha256": "c" * 64, "semantic_sha256": "d" * 64,
    }


def test_aggregates_valid_multi_source_evidence_without_payloads(tmp_path: Path) -> None:
    telemetry, producer, shadow, workflows, output = (tmp_path / name for name in ("telemetry", "producer", "shadow", "workflows", "report"))
    telemetry.write_text("\n".join(json.dumps(item) for item in [
        _event("2026-09-09T01:00:00Z"), _event("2026-09-09T01:02:00Z", "publish", "fail"),
    ]) + "\n", encoding="utf-8")
    producer.write_text(
        "\n".join(
            [
                "datapulse-health: probe started at 2026-09-09T00:01:00Z",
                "2026-09-09T00:02:00+00:00 datapulse-health: publish pushed",
                "2026-09-09T00:03:00Z datapulse-health: failed (exit 7)",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    shadow.write_text(json.dumps(_receipt()) + "\n", encoding="utf-8")
    workflows.write_text(json.dumps([
        {"workflowName": "Deploy", "status": "completed", "conclusion": "success", "headSha": "a" * 40, "createdAt": "2026-09-09T03:00:00Z"}
    ]), encoding="utf-8")

    result = _run(output, "--telemetry", str(telemetry), "--producer-log", str(producer), "--shadow-receipts", str(shadow), "--workflow-runs", str(workflows))

    assert result.returncode == 0, result.stderr
    report = json.loads(output.read_text(encoding="utf-8"))
    assert report["schema"] == "datapulse/v1/pipeline-observation-report"
    assert report["cycle_counts"] == {"cycles": 1, "stage_events": 2, "stages": {"probe": {"success": 1}, "publish": {"fail": 1}}}
    assert report["shadow"] == {"equivalent": 1, "mismatch": 0, "unknown": 0}
    assert report["producer"]["failure_count"] == 1
    assert report["producer"]["signals"] == {"failed": 1, "probe_started": 1, "publish_pushed": 1}
    assert report["workflows"] == [{"conclusions": {"success": 1}, "workflow": "Deploy"}]
    assert all(item["status"] == "verifiable" for item in report["coverage"].values())
    text = output.read_text(encoding="utf-8")
    assert "hidden" not in text and "failed (exit 7)" not in text and str(telemetry) not in text


def test_filters_window_and_marks_out_of_window_evidence_unknown(tmp_path: Path) -> None:
    telemetry, output = tmp_path / "telemetry", tmp_path / "report"
    telemetry.write_text("\n".join(json.dumps(item) for item in [
        _event("2026-09-08T23:59:59Z"), _event("2026-09-09T01:00:00Z"), _event("2026-09-10T00:00:00Z"),
    ]) + "\n", encoding="utf-8")

    result = _run(output, "--telemetry", str(telemetry))

    assert result.returncode == 0
    report = json.loads(output.read_text(encoding="utf-8"))
    assert report["cycle_counts"]["stage_events"] == 1
    assert "out_of_window" in report["coverage"]["telemetry"]["reasons"]
    assert report["evidence_bounds"]["telemetry"] == {"first": "2026-09-09T01:00:00Z", "last": "2026-09-09T01:00:00Z"}


def test_missing_and_malformed_sources_fail_closed_without_replacing_output(tmp_path: Path) -> None:
    output = tmp_path / "report"
    result = _run(output, "--telemetry", str(tmp_path / "missing"))
    assert result.returncode == 0
    report = json.loads(output.read_text(encoding="utf-8"))
    assert report["coverage"]["telemetry"] == {"reasons": ["missing_input"], "status": "unknown"}
    assert report["coverage"]["producer_log"]["status"] == "unknown"

    malformed = tmp_path / "malformed"
    malformed.write_text("not-json\n", encoding="utf-8")
    output.write_bytes(b"preserve-me\n")
    result = _run(output, "--telemetry", str(malformed))
    assert result.returncode == 0
    assert json.loads(output.read_text())["coverage"]["telemetry"]["status"] == "unknown"


def test_malformed_telemetry_and_shadow_mismatch_are_unknown(tmp_path: Path) -> None:
    telemetry, shadow, output = tmp_path / "telemetry", tmp_path / "shadow", tmp_path / "report"
    telemetry.write_text(json.dumps(_event("2026-09-09T01:00:00Z")) + "\n{" + "\n", encoding="utf-8")
    left, right, invalid_digest = _receipt(), _receipt(health="e" * 40), _receipt()
    invalid_digest["health_sha256"] = "not-a-digest"
    shadow.write_text("\n".join(json.dumps(row) for row in (left, right, invalid_digest)) + "\n", encoding="utf-8")

    result = _run(output, "--telemetry", str(telemetry), "--shadow-receipts", str(shadow))

    assert result.returncode == 0
    report = json.loads(output.read_text())
    assert report["coverage"]["telemetry"]["status"] == "unknown"
    assert report["shadow"] == {"equivalent": 0, "mismatch": 2, "unknown": 1}
    assert "invalid_identity" in report["coverage"]["shadow_receipts"]["reasons"]
    assert "invalid_digest" in report["coverage"]["shadow_receipts"]["reasons"]


def test_workflow_conclusions_determinism_redaction_and_atomic_preservation(tmp_path: Path) -> None:
    workflows, first, second = tmp_path / "workflows", tmp_path / "first", tmp_path / "second"
    workflows.write_text(json.dumps([
        {"workflowName": "Deploy", "status": "completed", "conclusion": "failure", "headSha": "a" * 40},
        {"workflowName": "Deploy", "status": "completed", "conclusion": "success", "headSha": "b" * 40},
        {"workflowName": "Deploy", "status": "completed", "conclusion": "success", "headSha": "d" * 40, "url": "https://x/?token=secret"},
        {"workflowName": "Health-only", "status": "completed", "conclusion": "success", "headSha": "c" * 40},
    ]), encoding="utf-8")

    assert _run(first, "--workflow-runs", str(workflows)).returncode == 0
    assert _run(second, "--workflow-runs", str(workflows)).returncode == 0
    assert first.read_bytes() == second.read_bytes()
    report = json.loads(first.read_text())
    assert report["workflows"] == [{"conclusions": {"failure": 1, "success": 1}, "workflow": "Deploy"}, {"conclusions": {"success": 1}, "workflow": "Health-only"}]
    assert report["health_only_classification_counts"] == {"health_only": 1, "unknown": 2}
    assert "https" not in first.read_text() and "secret" not in first.read_text()


def test_producer_filters_timestamped_events_and_marks_untimestamped_as_unknown(tmp_path: Path) -> None:
    producer, output = tmp_path / "producer", tmp_path / "report"
    producer.write_text(
        "\n".join(
            [
                "datapulse-health: shadow health equivalent; equivalent=true",
                "2026-09-08T23:59:59Z datapulse-health: probe finished at 2026-09-08T23:59:59Z",
                "datapulse-health: shadow comparison failed",
                "2026-09-09T00:00:00Z datapulse-health: pipeline receipt written",
                "2026-09-09T06:00:00Z datapulse-health: probe finished",
                "2026-09-09T07:00:00Z datapulse-health: shadow comparison failed",
                "2026-09-09T12:00:00+00:00 datapulse-health: shadow health equivalent; equivalent=true",
                "2026-09-10T00:00:00Z datapulse-health: failed (exit 9)",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    result = _run(output, "--producer-log", str(producer))

    assert result.returncode == 0, result.stderr
    report = json.loads(output.read_text(encoding="utf-8"))
    assert report["producer"] == {
        "failure_count": 0,
        "signals": {
            "pipeline_receipt_written": 1,
            "probe_finished": 1,
            "shadow_comparison_failed": 1,
            "shadow_equivalent": 1,
        },
    }
    assert report["coverage"]["producer_log"]["reasons"] == ["no_matching_evidence", "out_of_window"]


def test_producer_requires_strict_lines_and_redacts_failure_details(tmp_path: Path) -> None:
    producer, output = tmp_path / "producer", tmp_path / "report"
    producer.write_text(
        "\n".join(
            [
                "2026-09-09T01:00:00Z datapulse-health: failed (exit 12)",
                "2026-09-09T01:01:00Z datapulse-health: failed (exit 0)",
                "prefix datapulse-health: failed (exit 99)",
                "2026-09-09T01:02:00Z datapulse-health: publish pushed /tmp/private-payload",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    result = _run(output, "--producer-log", str(producer))

    assert result.returncode == 0, result.stderr
    rendered = output.read_text(encoding="utf-8")
    report = json.loads(rendered)
    assert report["producer"] == {"failure_count": 1, "signals": {"failed": 1}}
    assert "exit 12" not in rendered and "/tmp/private-payload" not in rendered

    preserved = tmp_path / "preserved"
    preserved.write_bytes(b"preserve-me\n")
    with patch.object(observation.os, "replace", side_effect=OSError("forced")):
        with pytest.raises(observation.ObservationError, match="write_failed"):
            observation.write_report(preserved, {"safe": True})
    assert preserved.read_bytes() == b"preserve-me\n"


def test_invalid_window_preserves_existing_output(tmp_path: Path) -> None:
    output = tmp_path / "report"
    output.write_bytes(b"preserve-me\n")

    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--start", END, "--end", START, "--output", str(output)],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode != 0
    assert output.read_bytes() == b"preserve-me\n"
