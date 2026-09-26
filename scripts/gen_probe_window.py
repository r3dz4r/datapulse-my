#!/usr/bin/env python3
"""Generate deterministic per-dataset probe counts for signed attestations."""

from __future__ import annotations

import argparse
import json
import logging
import os
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

LOGGER = logging.getLogger(__name__)
ROOT = Path(__file__).resolve().parents[1]
DEFAULT_HISTORY = ROOT / "health/history.jsonl"
DEFAULT_HEALTH = ROOT / "health/latest.json"
DEFAULT_MANIFEST = ROOT / "datapulse.json"
DEFAULT_OUTPUT = ROOT / "health/probe-window.json"
SCHEMA = "datapulse/v1/probe-window-counts"
WINDOW_DAYS = (14, 1)


class ProbeWindowError(ValueError):
    """Raised when an input cannot produce a valid probe-window artifact."""


def parse_timestamp(value: Any, *, field: str) -> datetime:
    """Parse a timezone-aware ISO-8601 timestamp."""
    if not isinstance(value, str):
        raise ProbeWindowError(f"{field} must be an ISO-8601 string")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ProbeWindowError(f"{field} is not a valid ISO-8601 timestamp") from exc
    if parsed.tzinfo is None:
        raise ProbeWindowError(f"{field} must include a timezone offset")
    return parsed


def read_json(path: Path, *, description: str) -> dict[str, Any]:
    """Read one JSON object and raise a typed error for malformed input."""
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ProbeWindowError(f"cannot read {description} {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise ProbeWindowError(f"{description} must be a JSON object: {path}")
    return payload


def manifest_dataset_ids(path: Path) -> list[str]:
    """Return manifest dataset IDs in deterministic sorted order."""
    payload = read_json(path, description="manifest")
    datasets = payload.get("datasets")
    if not isinstance(datasets, list):
        raise ProbeWindowError("manifest must contain a datasets array")
    dataset_ids: list[str] = []
    for index, dataset in enumerate(datasets):
        if not isinstance(dataset, dict) or not isinstance(dataset.get("id"), str):
            raise ProbeWindowError(f"manifest dataset {index} has no string id")
        dataset_ids.append(dataset["id"])
    if len(set(dataset_ids)) != len(dataset_ids):
        raise ProbeWindowError("manifest contains duplicate dataset IDs")
    return sorted(dataset_ids)


def count_probe_windows(
    history_path: Path, health_path: Path, manifest_path: Path
) -> dict[str, Any]:
    """Build the pinned probe-window payload from the three source inputs."""
    health = read_json(health_path, description="health snapshot")
    reference_at = health.get("checked_at")
    reference_time = parse_timestamp(reference_at, field="checked_at")
    dataset_ids = manifest_dataset_ids(manifest_path)
    counts: dict[str, dict[str, int]] = {
        dataset_id: {"probe_count_14d": 0, "probe_count_24h": 0}
        for dataset_id in dataset_ids
    }
    thresholds = {
        "probe_count_14d": reference_time - timedelta(days=14),
        "probe_count_24h": reference_time - timedelta(days=1),
    }
    try:
        history_file = history_path.open(encoding="utf-8")
    except OSError as exc:
        raise ProbeWindowError(f"cannot read history {history_path}: {exc}") from exc
    with history_file:
        for line_number, line in enumerate(history_file, start=1):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ProbeWindowError(
                    f"invalid history JSON at line {line_number}: {exc}"
                ) from exc
            if not isinstance(row, dict):
                raise ProbeWindowError(f"history line {line_number} is not an object")
            dataset_id = row.get("dataset_id")
            if not isinstance(dataset_id, str):
                raise ProbeWindowError(
                    f"history line {line_number} has no string dataset_id"
                )
            if dataset_id not in counts:
                continue
            observed_at = parse_timestamp(
                row.get("observed_at"), field=f"history line {line_number} observed_at"
            )
            for field, threshold in thresholds.items():
                if observed_at >= threshold:
                    counts[dataset_id][field] += 1
    return {
        "schema": SCHEMA,
        "reference_at": reference_at,
        "window_days": list(WINDOW_DAYS),
        "counts": counts,
    }


def serialise(payload: dict[str, Any]) -> bytes:
    """Serialise an artifact with stable key and byte ordering."""
    return (json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n").encode(
        "utf-8"
    )


def write_atomic(path: Path, content: bytes) -> None:
    """Write bytes beside the target and atomically replace the target."""
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    try:
        with os.fdopen(descriptor, "wb") as temporary_file:
            temporary_file.write(content)
            temporary_file.flush()
            os.fsync(temporary_file.fileno())
        os.replace(temporary_name, path)
    except OSError as exc:
        try:
            os.unlink(temporary_name)
        except OSError:
            pass
        raise ProbeWindowError(f"cannot atomically write {path}: {exc}") from exc


def generate(
    history_path: Path,
    health_path: Path,
    manifest_path: Path,
    output_path: Path,
) -> bool:
    """Generate the artifact, returning false when history is unavailable."""
    if not history_path.exists():
        LOGGER.warning(
            "history input %s is missing; committed artifact %s is left untouched",
            history_path,
            output_path,
        )
        return False
    payload = count_probe_windows(history_path, health_path, manifest_path)
    write_atomic(output_path, serialise(payload))
    LOGGER.info("wrote probe-window artifact %s", output_path)
    return True


def build_parser() -> argparse.ArgumentParser:
    """Build the command-line parser."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--history", type=Path, default=DEFAULT_HISTORY)
    parser.add_argument("--health", type=Path, default=DEFAULT_HEALTH)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUTPUT)
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run the generator CLI."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    arguments = build_parser().parse_args(argv)
    generate(arguments.history, arguments.health, arguments.manifest, arguments.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
