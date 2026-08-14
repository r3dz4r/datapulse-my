#!/usr/bin/env python3
"""Generate one immutable dataset-level delta ledger for a probe cycle."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CYCLE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}$")
DELTA_NAMES = (
    "added",
    "removed",
    "status_changed",
    "anomaly_changed",
    "url_changed",
    "schema_changed",
    "record_count_changed",
)


def _read_json(path: Path, *, datasets: bool = True) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read valid JSON {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    if datasets and not isinstance(value.get("datasets"), list):
        raise ValueError(f"{path} must contain a datasets array")
    return value


def _read_history(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    try:
        with path.open(encoding="utf-8") as source:
            for line_number, line in enumerate(source, start=1):
                if not line.strip():
                    continue
                row = json.loads(line)
                if not isinstance(row, dict):
                    raise ValueError("line is not an object")
                if not isinstance(row.get("dataset_id"), str) or not isinstance(
                    row.get("cycle"), str
                ):
                    raise ValueError("line has no dataset_id/cycle")
                rows.append(row)
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
        line_number = locals().get("line_number", 0)
        raise ValueError(
            f"invalid history {path} at line {line_number}: {exc}"
        ) from exc
    return rows


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _cycle_digest(rows: list[dict[str, Any]], cycle: str) -> str:
    content = "".join(
        json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n"
        for row in sorted(
            (row for row in rows if row["cycle"] == cycle),
            key=lambda row: row["dataset_id"],
        )
    ).encode()
    return hashlib.sha256(content).hexdigest()


def _index(rows: list[dict[str, Any]], key: str) -> dict[str, dict[str, Any]]:
    indexed: dict[str, dict[str, Any]] = {}
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get(key), str):
            raise ValueError(f"every datasets entry must have a string {key}")
        if row[key] in indexed:
            raise ValueError(f"duplicate dataset identifier: {row[key]}")
        indexed[row[key]] = row
    return indexed


def _latest_successful_prior(
    rows: list[dict[str, Any]], cycle: str
) -> dict[str, dict[str, Any]]:
    baselines: dict[str, dict[str, Any]] = {}
    for row in rows:
        if row["cycle"] >= cycle or row.get("probe_outcome") != "success":
            continue
        dataset_id = row["dataset_id"]
        prior = baselines.get(dataset_id)
        if prior is None or (row["cycle"], row.get("observed_at", "")) > (
            prior["cycle"],
            prior.get("observed_at", ""),
        ):
            baselines[dataset_id] = row
    return baselines


def _display_name(dataset_id: str, *rows: dict[str, Any] | None) -> str:
    for row in rows:
        if row and isinstance(row.get("name"), str) and row["name"]:
            return row["name"]
    return dataset_id.replace("_", " ").replace("-", " ").title()


def _number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _prior_manifest_digest(output_dir: Path, previous_cycle: str | None) -> str | None:
    if previous_cycle is None:
        return None
    path = output_dir / f"{previous_cycle}.json"
    if not path.is_file():
        return None
    try:
        payload = _read_json(path, datasets=False)
        value = payload.get("source_artifacts", {}).get("manifest_sha256")
    except ValueError:
        return None
    return value if isinstance(value, str) else None


def build_delta(
    *,
    cycle: str,
    manifest: dict[str, Any],
    health: dict[str, Any],
    history: list[dict[str, Any]],
    source_artifacts: dict[str, str | None],
) -> dict[str, Any]:
    if not CYCLE_PATTERN.fullmatch(cycle):
        raise ValueError("cycle must use YYYY-MM-DDTHH:MM")
    manifest_by_id = _index(manifest["datasets"], "id")
    health_by_id = _index(health["datasets"], "dataset_id")
    current_rows = [row for row in history if row["cycle"] == cycle]
    prior_cycles = sorted({row["cycle"] for row in history if row["cycle"] < cycle})
    previous_cycle = prior_cycles[-1] if prior_cycles else None
    deltas: dict[str, list[dict[str, Any]]] = {name: [] for name in DELTA_NAMES}

    if not current_rows:
        skipped_reason = f"no_history_line_for_cycle_{cycle}"
        previous_cycle = None
    elif previous_cycle is None:
        skipped_reason = "no_history_baseline_yet"
    else:
        skipped_reason = None
        previous_ids = {
            row["dataset_id"] for row in history if row["cycle"] == previous_cycle
        }
        current_ids = set(manifest_by_id)
        baselines = _latest_successful_prior(history, cycle)

        for dataset_id in sorted(current_ids - previous_ids):
            entry = manifest_by_id[dataset_id]
            current = health_by_id.get(dataset_id, {})
            deltas["added"].append(
                {
                    "dataset_id": dataset_id,
                    "name": _display_name(dataset_id, entry),
                    "status": current.get("status", "unknown"),
                    "url": entry.get("url"),
                }
            )

        for dataset_id in sorted(previous_ids - current_ids):
            baseline = baselines.get(dataset_id)
            if baseline is None:
                continue
            deltas["removed"].append(
                {
                    "dataset_id": dataset_id,
                    "name": _display_name(dataset_id, baseline),
                    "last_known_status": baseline.get("status", "unknown"),
                    "from_cycle": baseline["cycle"],
                }
            )

        for dataset_id in sorted(current_ids & set(baselines)):
            entry = manifest_by_id[dataset_id]
            current = health_by_id.get(dataset_id)
            if current is None:
                continue
            baseline = baselines[dataset_id]
            name = _display_name(dataset_id, entry, baseline)
            if baseline.get("status") != current.get("status"):
                signal = (
                    "content-shape-changed"
                    if current.get("content_shape_changed") is True
                    else current.get("freshness_signal_source")
                    or current.get("freshness_signal")
                    or "health-probe"
                )
                deltas["status_changed"].append(
                    {
                        "dataset_id": dataset_id,
                        "name": name,
                        "from_status": baseline.get("status"),
                        "to_status": current.get("status"),
                        "from_cycle": baseline["cycle"],
                        "signal_source": signal,
                    }
                )
            if (
                "anomaly_detected" in baseline
                and baseline.get("anomaly_detected") != current.get("anomaly_detected")
            ):
                deltas["anomaly_changed"].append(
                    {
                        "dataset_id": dataset_id,
                        "name": name,
                        "from_anomaly_detected": baseline.get("anomaly_detected"),
                        "to_anomaly_detected": current.get("anomaly_detected"),
                        "from_cycle": baseline["cycle"],
                        "metric": "freshness_delta_days",
                    }
                )
            old_url, new_url = baseline.get("url"), entry.get("url")
            if (
                isinstance(old_url, str)
                and isinstance(new_url, str)
                and old_url != new_url
            ):
                deltas["url_changed"].append(
                    {
                        "dataset_id": dataset_id,
                        "name": name,
                        "from_url": old_url,
                        "to_url": new_url,
                        "from_cycle": baseline["cycle"],
                    }
                )
            old_shape = baseline.get("shape_hash") or baseline.get("first_row_hash")
            new_shape = current.get("first_row_hash")
            if (
                isinstance(old_shape, str)
                and isinstance(new_shape, str)
                and old_shape != new_shape
            ):
                deltas["schema_changed"].append(
                    {
                        "dataset_id": dataset_id,
                        "name": name,
                        "from_shape_hash": old_shape,
                        "to_shape_hash": new_shape,
                        "from_cycle": baseline["cycle"],
                    }
                )
            old_count = baseline.get("record_count")
            new_count = current.get("record_count")
            if (
                _number(old_count)
                and _number(new_count)
                and baseline.get("record_count_estimated") is not True
                and current.get("record_count_estimated") is not True
                and old_count != new_count
            ):
                deltas["record_count_changed"].append(
                    {
                        "dataset_id": dataset_id,
                        "name": name,
                        "from_count": old_count,
                        "to_count": new_count,
                        "delta": new_count - old_count,
                        "from_cycle": baseline["cycle"],
                    }
                )

    return {
        "cycle": cycle,
        "observed_at": health["checked_at"],
        "previous_cycle": previous_cycle,
        "previous_cycle_skipped_reason": skipped_reason,
        "summary": {name: len(deltas[name]) for name in DELTA_NAMES},
        "deltas": deltas,
        "source_artifacts": source_artifacts,
    }


def _immutable_write(path: Path, content: bytes) -> bool:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
    except FileExistsError:
        if path.read_bytes() == content:
            return False
        raise ValueError(f"immutable delta already exists with different content: {path}")
    try:
        with os.fdopen(descriptor, "wb") as destination:
            destination.write(content)
            destination.flush()
            os.fsync(destination.fileno())
    except BaseException:
        try:
            path.unlink()
        except FileNotFoundError:
            pass
        raise
    return True


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--cycle",
        help="probe cycle as YYYY-MM-DDTHH:MM (defaults to health checked_at)",
    )
    parser.add_argument("--manifest", type=Path, default=ROOT / "datapulse.json")
    parser.add_argument("--health", type=Path, default=ROOT / "health/latest.json")
    parser.add_argument("--history", type=Path, default=ROOT / "health/history.jsonl")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "deltas")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    try:
        manifest = _read_json(args.manifest)
        health = _read_json(args.health)
        history = _read_history(args.history)
        cycle = args.cycle or health["checked_at"][:16]
        prior_cycles = sorted(
            {row["cycle"] for row in history if row["cycle"] < cycle}
        )
        previous_cycle = prior_cycles[-1] if prior_cycles else None
        source_artifacts = {
            "manifest_sha256": _sha256(args.manifest),
            "previous_manifest_sha256": _prior_manifest_digest(
                args.output_dir, previous_cycle
            ),
            "health_latest_sha256": _sha256(args.health),
            "history_jsonl_cycle_sha256": _cycle_digest(history, cycle),
        }
        document = build_delta(
            cycle=cycle,
            manifest=manifest,
            health=health,
            history=history,
            source_artifacts=source_artifacts,
        )
        path = args.output_dir / f"{cycle}.json"
        content = (json.dumps(document, ensure_ascii=False, indent=2) + "\n").encode()
        created = _immutable_write(path, content)
    except (OSError, UnicodeError, KeyError, ValueError) as exc:
        raise SystemExit(f"dataset delta generation failed: {exc}") from exc
    action = "Generated" if created else "Verified existing"
    print(f"{action} immutable delta {path}")


if __name__ == "__main__":
    main()
