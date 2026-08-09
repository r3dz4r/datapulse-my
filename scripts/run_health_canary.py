#!/usr/bin/env python3
"""Run a full health probe in a temporary directory and compare it to production."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import tempfile
import time
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable


ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = ROOT / "datapulse.json"
LIVE_HEALTH_PATH = ROOT / "health/latest.json"
EXPECTED_DATASETS = 166
COMPARED_FIELDS = (
    "status",
    "last_checked",
    "freshness_days",
    "content_freshness_date",
    "record_count",
    "column_count",
)
NORMAL_FRESHNESS_STATUSES = {"fresh", "aging", "stale"}


class SetupError(RuntimeError):
    """Raised when the canary cannot be run or validated."""


@dataclass(frozen=True)
class Finding:
    classification: str
    category: str
    dataset_id: str
    field: str
    before: object
    after: object
    reason: str


def _load_object(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SetupError(f"cannot read valid JSON from {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise SetupError(f"{path} must contain a JSON object")
    return value


def _rows(value: dict, source: str) -> list[dict]:
    rows = value.get("datasets")
    if not isinstance(rows, list) or not all(isinstance(row, dict) for row in rows):
        raise SetupError(f"{source} must contain a datasets array of objects")
    return rows


def _index(rows: Iterable[dict], id_field: str, source: str) -> dict[str, dict]:
    indexed: dict[str, dict] = {}
    for row in rows:
        dataset_id = row.get(id_field)
        if not isinstance(dataset_id, str) or not dataset_id:
            raise SetupError(f"{source} has an invalid {id_field}: {dataset_id!r}")
        if dataset_id in indexed:
            raise SetupError(f"{source} has duplicate dataset ID {dataset_id!r}")
        indexed[dataset_id] = row
    return indexed


def _trust_summary(snapshot: dict, source: str) -> dict:
    summary = snapshot.get("_trust_summary")
    if not isinstance(summary, dict):
        raise SetupError(f"{source} has no valid _trust_summary")
    if not isinstance(summary.get("by_status"), dict):
        raise SetupError(f"{source} has no valid _trust_summary.by_status")
    return summary


def _decode(value: object) -> str:
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return str(value or "")


def _run_probe(probe_timeout: int) -> tuple[dict, str, float]:
    started = time.monotonic()
    try:
        completed = subprocess.run(
            ["bash", "scripts/check.sh"],
            capture_output=True,
            timeout=probe_timeout,
        )
    except subprocess.TimeoutExpired as exc:
        raise SetupError(f"full probe timed out after {probe_timeout} seconds") from exc
    except OSError as exc:
        raise SetupError(f"could not start full probe: {exc}") from exc
    duration = time.monotonic() - started
    if completed.returncode != 0:
        stderr = _decode(completed.stderr).strip()
        detail = f": {stderr}" if stderr else ""
        raise SetupError(f"scripts/check.sh exited {completed.returncode}{detail}")

    stdout = completed.stdout if isinstance(completed.stdout, bytes) else _decode(completed.stdout).encode()
    with tempfile.TemporaryDirectory(prefix="datapulse-health-canary-") as workdir:
        canary_path = Path(workdir) / "canary_health.json"
        canary_path.write_bytes(stdout)
        try:
            canary = json.loads(canary_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise SetupError(f"full probe did not produce valid JSON: {exc}") from exc
        if not isinstance(canary, dict):
            raise SetupError("full probe JSON must be an object")
        summary = _trust_summary(canary, "canary output")
        if summary.get("datasets_total") != EXPECTED_DATASETS:
            raise SetupError(
                "canary _trust_summary.datasets_total is "
                f"{summary.get('datasets_total')!r}, expected {EXPECTED_DATASETS}"
            )
        canary_sha = hashlib.sha256(stdout).hexdigest()
    return canary, canary_sha, duration


def _parse_datetime(value: object) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _output_path(value: Path) -> Path:
    output = value.resolve() if value.is_absolute() else (ROOT / value).resolve()
    try:
        relative = output.relative_to(ROOT)
    except ValueError:
        return output
    if not relative.parts or relative.parts[0] != "docs":
        raise SetupError("report output inside the repository must be under docs/")
    return output


def _classification(
    field: str,
    before: object,
    after: object,
    live_row: dict,
    canary_row: dict,
) -> tuple[str, str]:
    if field == "status":
        transition = (before, after)
        if transition in {("fresh", "aging"), ("aging", "fresh")}:
            return "Approved", "freshness-window transition consistent with policy"
        if before in {"stale", "degraded", "unreachable", "unknown-freshness"} and after in NORMAL_FRESHNESS_STATUSES:
            return "Approved", "successful probe supplied improved freshness evidence"
        if transition == ("aging", "stale"):
            return "Approved", "freshness aged beyond the policy stale boundary"
        if transition == ("fresh", "stale"):
            old_checked = _parse_datetime(live_row.get("last_checked"))
            new_checked = _parse_datetime(canary_row.get("last_checked"))
            old_age = live_row.get("freshness_days", live_row.get("staleness_days"))
            new_age = canary_row.get("freshness_days", canary_row.get("staleness_days"))
            if (
                old_checked is not None
                and new_checked is not None
                and new_checked > old_checked
                and isinstance(old_age, (int, float))
                and isinstance(new_age, (int, float))
                and new_age > old_age
            ):
                return "Approved", "freshness aged across the policy stale boundary"
            return "Blocker", "fresh to stale without evidence that freshness time passed"
        if before == "unknown" and after != "unknown":
            return "Approved", "first completed probe replaced unknown status"
        return "Pending", "status transition is not pre-classified by the canary policy"

    if field == "last_checked":
        old_time = _parse_datetime(before)
        new_time = _parse_datetime(after)
        if before is None and new_time is not None:
            return "Approved", "first successful observation recorded"
        if old_time is not None and new_time is not None and new_time >= old_time:
            return "Approved", "full probe advanced the observation timestamp"
        if old_time is not None and after is None:
            return "Blocker", "full probe removed an existing observation timestamp"
        if old_time is not None and new_time is not None and new_time < old_time:
            return "Blocker", "full probe moved the observation timestamp backwards"
        return "Pending", "observation timestamp change needs review"

    if field in {"freshness_days", "content_freshness_date"}:
        if before is None and after is not None:
            return "Approved", "full probe supplied new freshness evidence"
        if field == "freshness_days" and isinstance(before, (int, float)) and isinstance(after, (int, float)):
            return "Approved", "freshness age changed with the probe observation time"
        old_time = _parse_datetime(before)
        new_time = _parse_datetime(after)
        if old_time is not None and new_time is not None and new_time >= old_time:
            return "Approved", "publisher freshness date advanced"
        if old_time is not None and new_time is not None and new_time < old_time:
            return "Blocker", "publisher freshness date moved backwards"
        return "Pending", "freshness evidence change needs review"

    if field == "record_count":
        if isinstance(before, (int, float)) and not isinstance(before, bool) and isinstance(after, (int, float)) and not isinstance(after, bool):
            denominator = abs(before)
            change = float("inf") if denominator == 0 else abs(after - before) / denominator
            if change > 0.10:
                return "Blocker", "record count changed by more than 10%"
            return "Approved", "record count changed within the 10% tolerance"
        if before is None and isinstance(after, (int, float)) and not isinstance(after, bool):
            return "Approved", "full probe extracted a record count"
        return "Pending", "record-count comparability needs review"

    if field == "column_count":
        return "Blocker", "schema-shape column count changed"

    return "Pending", "difference category is not pre-classified"


def _finding(
    classification: str,
    category: str,
    dataset_id: str,
    field: str,
    before: object,
    after: object,
    reason: str,
) -> Finding:
    return Finding(classification, category, dataset_id, field, before, after, reason)


def _compare(manifest: dict, live: dict, canary: dict) -> list[Finding]:
    manifest_rows = _rows(manifest, "manifest")
    live_rows = _rows(live, "live health")
    canary_rows = _rows(canary, "canary output")
    manifest_by_id = _index(manifest_rows, "id", "manifest")
    live_by_id = _index(live_rows, "dataset_id", "live health")
    canary_by_id = _index(canary_rows, "dataset_id", "canary output")
    findings: list[Finding] = []

    if len(manifest_by_id) != EXPECTED_DATASETS:
        findings.append(_finding("Blocker", "Shape", "(manifest)", "datasets_total", EXPECTED_DATASETS, len(manifest_by_id), "manifest count is not the expected canonical count"))
    canary_total = _trust_summary(canary, "canary output").get("datasets_total")
    if canary_total != len(manifest_by_id):
        findings.append(_finding("Blocker", "Shape", "(canary)", "datasets_total", len(manifest_by_id), canary_total, "canary summary count does not equal manifest count"))

    manifest_ids = set(manifest_by_id)
    live_ids = set(live_by_id)
    canary_ids = set(canary_by_id)
    for dataset_id in sorted(manifest_ids - canary_ids):
        findings.append(_finding("Blocker", "ID set", dataset_id, "dataset_id", "present in manifest", "missing from canary", "manifest dataset is missing from canary"))
    for dataset_id in sorted(canary_ids - manifest_ids):
        findings.append(_finding("Blocker", "ID set", dataset_id, "dataset_id", "absent from manifest", "present in canary", "canary contains an ID absent from the manifest"))
    for dataset_id in sorted(live_ids - canary_ids):
        if dataset_id not in manifest_ids:
            findings.append(_finding("Blocker", "ID set", dataset_id, "dataset_id", "present in live", "missing from canary", "live dataset is missing from canary"))
    for dataset_id in sorted(canary_ids - live_ids):
        findings.append(_finding("Blocker", "ID set", dataset_id, "dataset_id", "missing from live", "present in canary", "canary and live ID sets differ"))

    for dataset_id in sorted(live_ids & canary_ids):
        live_row = live_by_id[dataset_id]
        canary_row = canary_by_id[dataset_id]
        for field in COMPARED_FIELDS:
            before = live_row.get(field)
            after = canary_row.get(field)
            if before == after:
                continue
            classification, reason = _classification(field, before, after, live_row, canary_row)
            category = {
                "status": "Status flip",
                "record_count": "Record count",
                "column_count": "Schema",
            }.get(field, "Field")
            findings.append(_finding(classification, category, dataset_id, field, before, after, reason))

    summary = _trust_summary(canary, "canary output")
    reported = summary["by_status"]
    actual = Counter(str(row.get("status", "unknown")).replace("-", "_") for row in canary_rows)
    all_statuses = set(reported) | set(actual)
    for status in sorted(all_statuses):
        if reported.get(status, 0) != actual.get(status, 0):
            findings.append(_finding("Blocker", "Distribution", "(canary)", f"by_status.{status}", actual.get(status, 0), reported.get(status, 0), "canary by_status does not agree with its dataset rows"))
    return findings


def _git_value(*args: str) -> str:
    try:
        return subprocess.check_output(
            ["git", *args], cwd=ROOT, text=True, stderr=subprocess.PIPE
        ).strip()
    except (OSError, subprocess.CalledProcessError) as exc:
        raise SetupError(f"git metadata lookup failed: {' '.join(args)}") from exc


def _display(value: object) -> str:
    rendered = json.dumps(value, ensure_ascii=False, sort_keys=True)
    escaped = rendered.replace("|", "\\|")
    return f"`{escaped}`"


def _table(findings: list[Finding]) -> list[str]:
    if not findings:
        return ["_None._", ""]
    lines = [
        "| Classification | Dataset ID | Field | Before | After | Reason |",
        "|---|---|---|---|---|---|",
    ]
    for item in findings:
        reason = item.reason.replace("|", "\\|")
        lines.append(
            f"| {item.classification} | `{item.dataset_id}` | `{item.field}` | "
            f"{_display(item.before)} | {_display(item.after)} | {reason} |"
        )
    lines.append("")
    return lines


def _render_report(
    manifest: dict,
    live: dict,
    canary: dict,
    findings: list[Finding],
    canary_sha: str,
    duration: float,
) -> str:
    source_sha = _git_value("rev-parse", "HEAD")
    live_commit = _git_value("log", "-1", "--format=%H", "--", "health/latest.json")
    live_timestamp = _git_value("log", "-1", "--format=%cI", "--", "health/latest.json")
    generated = datetime.now().astimezone().isoformat(timespec="seconds")
    manifest_count = len(_rows(manifest, "manifest"))
    counts = Counter(item.classification for item in findings)
    live_status = _trust_summary(live, "live health")["by_status"]
    canary_status = _trust_summary(canary, "canary output")["by_status"]
    status_names = sorted(set(live_status) | set(canary_status))

    lines = [
        "# Full-probe health policy compatibility canary",
        "",
        f"- Date: `{generated}`",
        f"- Source SHA: `{source_sha}`",
        f"- Live `health/latest.json` commit SHA: `{live_commit}`",
        f"- Live `health/latest.json` last commit timestamp: `{live_timestamp}`",
        f"- Canary SHA-256: `{canary_sha}`",
        f"- Full-probe duration: `{duration:.2f} seconds`",
        "",
        "## Summary",
        "",
        f"- Total datasets: **{manifest_count}**",
        f"- Approved changes: **{counts['Approved']}**",
        f"- Blockers: **{counts['Blocker']}**",
        f"- Pending review: **{counts['Pending']}**",
        "",
        "## Per-status distribution",
        "",
        "| Status | Live | Canary | Delta |",
        "|---|---:|---:|---:|",
    ]
    for status in status_names:
        before = live_status.get(status, 0)
        after = canary_status.get(status, 0)
        lines.append(f"| `{status}` | {before} | {after} | {after - before:+d} |")
    lines.extend([""])

    for heading, category in (
        ("Status flips", "Status flip"),
        ("Record-count changes", "Record count"),
        ("Schema changes", "Schema"),
    ):
        lines.extend([f"## {heading}", ""])
        lines.extend(_table([item for item in findings if item.category == category]))

    for heading in ("Approved", "Blockers", "Pending"):
        lines.extend([f"## {heading}", ""])
        lines.extend(_table([item for item in findings if item.classification == heading.rstrip("s")]))

    lines.extend(
        [
            "## Reproduction",
            "",
            "Run from the repository root. The full probe remains temporary; only this report is written.",
            "",
            "```bash",
            "python3 scripts/run_health_canary.py",
            "```",
            "",
        ]
    )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("docs/health-policy-compatibility.md"),
    )
    parser.add_argument("--probe-timeout", type=int, default=1200)
    args = parser.parse_args(argv)
    if args.probe_timeout <= 0:
        print("Health canary setup failed: --probe-timeout must be positive", file=sys.stderr)
        return 2

    try:
        manifest = _load_object(MANIFEST_PATH)
        live = _load_object(LIVE_HEALTH_PATH)
        canary, canary_sha, duration = _run_probe(args.probe_timeout)
        findings = _compare(manifest, live, canary)
        report = _render_report(manifest, live, canary, findings, canary_sha, duration)
        output = _output_path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(report, encoding="utf-8")
    except (SetupError, OSError) as exc:
        print(f"Health canary setup failed: {exc}", file=sys.stderr)
        return 2

    blockers = sum(item.classification == "Blocker" for item in findings)
    print(
        f"Health canary: {len(_rows(canary, 'canary output'))} datasets, "
        f"{sum(item.classification == 'Approved' for item in findings)} approved, "
        f"{blockers} blockers, "
        f"{sum(item.classification == 'Pending' for item in findings)} pending"
    )
    return 1 if blockers else 0


if __name__ == "__main__":
    raise SystemExit(main())
