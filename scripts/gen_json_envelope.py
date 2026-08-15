#!/usr/bin/env python3
"""Generate canonical JSON health envelopes for non-GTFS manifest datasets."""

from __future__ import annotations

import argparse
import csv
import io
import json
import multiprocessing
import os
import re
import urllib.request
from pathlib import Path
from typing import Any


SCHEMA = "datapulse/v0.1/dataset-health"
MAX_SOURCE_BYTES = 262_144
SAMPLE_ROWS = 100
CHECK_NAMES = ("file_reachable", "row_count", "freshness", "schema_stable")


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path}: expected a JSON object")
    return value


def fetch_source(url: str) -> tuple[bytes, str | None]:
    request = urllib.request.Request(
        url,
        headers={"Range": f"bytes=0-{MAX_SOURCE_BYTES - 1}", "User-Agent": "DataPulse-envelope-generator/0.1"},
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        return response.read(MAX_SOURCE_BYTES), response.headers.get_content_type()


def scalar_type(value: Any) -> str | None:
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int):
        return "integer"
    if isinstance(value, float):
        return "number"
    text = str(value).strip()
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}(?:[T ][^\s]+)?", text):
        return "date"
    if text.lower() in {"true", "false"}:
        return "boolean"
    if re.fullmatch(r"[+-]?\d+", text):
        return "integer"
    if re.fullmatch(r"[+-]?(?:\d+\.\d*|\d*\.\d+)(?:[Ee][+-]?\d+)?", text):
        return "number"
    return "string"


def merge_types(values: list[Any]) -> str:
    observed = {kind for value in values if (kind := scalar_type(value)) is not None}
    if not observed:
        return "string"
    if observed <= {"integer", "number"}:
        return "number" if "number" in observed else "integer"
    return observed.pop() if len(observed) == 1 else "string"


def infer_csv_fields(payload: bytes) -> list[dict[str, str]]:
    text = payload.decode("utf-8-sig", errors="replace")
    rows = csv.reader(io.StringIO(text))
    try:
        headers = next(rows)
    except StopIteration:
        return []
    if not headers or any(not header.strip() for header in headers):
        return []
    samples = [[] for _ in headers]
    for row_number, row in enumerate(rows):
        if row_number >= SAMPLE_ROWS:
            break
        for index, value in enumerate(row[: len(headers)]):
            samples[index].append(value)
    return [
        {"name": header.strip(), "type": merge_types(samples[index])}
        for index, header in enumerate(headers)
    ]


def infer_json_fields(payload: bytes) -> list[dict[str, str]]:
    value = json.loads(payload.decode("utf-8-sig"))
    if isinstance(value, dict):
        candidates = [value]
    elif isinstance(value, list):
        candidates = [item for item in value[:SAMPLE_ROWS] if isinstance(item, dict)]
    else:
        return []
    if not candidates:
        return []
    names = list(candidates[0])
    return [
        {"name": name, "type": merge_types([item.get(name) for item in candidates])}
        for name in names
    ]


def infer_fields(url: str) -> list[dict[str, str]]:
    payload, content_type = fetch_source(url)
    clean_url = url.split("?", 1)[0].lower()
    if clean_url.endswith(".json") or content_type == "application/json":
        return infer_json_fields(payload)
    if clean_url.endswith(".csv") or content_type in {"text/csv", "application/csv"}:
        return infer_csv_fields(payload)
    return []


def markdown_section(report_path: Path, heading: str) -> list[str]:
    try:
        lines = report_path.read_text(encoding="utf-8").splitlines()
    except FileNotFoundError:
        return []
    target = re.compile(rf"^##+\s+{re.escape(heading)}\s*$", re.IGNORECASE)
    heading_line = next((index for index, line in enumerate(lines) if target.match(line)), None)
    if heading_line is None:
        return []
    values: list[str] = []
    for line in lines[heading_line + 1 :]:
        if re.match(r"^#{1,6}\s+", line):
            break
        match = re.match(r"^\s*[-*]\s+(.+?)\s*$", line)
        if match and match.group(1).rstrip(".").lower() not in {"none", "n/a"}:
            values.append(match.group(1))
    return values


def record_count(health: dict[str, Any]) -> int | None:
    for key in ("record_count", "estimated_record_count", "record_count_estimated"):
        value = health.get(key)
        if isinstance(value, int) and not isinstance(value, bool):
            return value
    return None


def standard_checks(manifest: dict[str, Any], health: dict[str, Any]) -> list[dict[str, str]]:
    probe_note = manifest.get("probe_note") or "The underlying probe has not produced this measurement."
    http_status = health.get("http_status")
    status = health.get("status")
    count = record_count(health)
    shape_changed = health.get("content_shape_changed")
    column_count = health.get("column_count")

    if isinstance(http_status, int) and 200 <= http_status < 400:
        reachable = ("pass", f"Probe received HTTP {http_status} via {health.get('access_method') or 'the configured access method'}")
    elif status == "unreachable":
        reachable = ("fail", health.get("message") or str(probe_note))
    else:
        reachable = ("warn", health.get("message") or str(probe_note))

    if count is not None:
        row_count = ("pass", f"Probe measured {count} record(s)")
    else:
        row_count = ("warn", str(probe_note))

    if status == "fresh":
        freshness = ("pass", "Health snapshot classifies the dataset as fresh")
    elif status == "stale":
        freshness = ("fail", "Health snapshot classifies the dataset as stale")
    else:
        freshness = ("warn", f"Health snapshot classifies the dataset as {status or 'unknown'}")

    if shape_changed is True:
        schema = ("fail", "Probe detected a content-shape change")
    elif shape_changed is False and isinstance(column_count, int):
        schema = ("pass", f"Probe observed {column_count} column(s) with no content-shape change")
    else:
        schema = ("warn", str(probe_note))

    results = (reachable, row_count, freshness, schema)
    return [
        {"name": name, "status": result[0], "method": result[1]}
        for name, result in zip(CHECK_NAMES, results)
    ]


def access_method(health: dict[str, Any]) -> str:
    method = str(health.get("access_method") or "")
    if "camofox" in method.lower() or health.get("access_dependency") == "browser":
        wait = health.get("wait_seconds")
        return f"Camofox; {wait}s before snapshot" if wait is not None else "Camofox; wait before snapshot"
    return "curl"


def build_envelope(root: Path, manifest: dict[str, Any], health: dict[str, Any]) -> dict[str, Any]:
    source_url = manifest.get("source_url") or manifest.get("url")
    fields: list[dict[str, str]] = []
    fields_unavailable = False
    if isinstance(source_url, str):
        try:
            fields = infer_fields(source_url)
        except (OSError, UnicodeError, ValueError, json.JSONDecodeError):
            fields_unavailable = True
    else:
        fields_unavailable = True

    report = root / str(manifest.get("health_report") or f"data/{manifest['id']}.md")
    quirks = markdown_section(report, "Known quirks")
    if fields_unavailable or not fields:
        quirks.append("Fields are inferred at the next probe run.")

    date_range = health.get("date_range")
    if not isinstance(date_range, dict):
        date_range = None
    elif set(date_range) >= {"start", "end"}:
        date_range = {"start": date_range.get("start"), "end": date_range.get("end")}
    else:
        date_range = None

    source_name = manifest.get("source")
    namespace = manifest.get("namespace")
    attribution = f"{source_name} ({namespace})" if source_name and namespace else None
    return {
        "schema": SCHEMA,
        "id": manifest["id"],
        "status": health.get("status"),
        "last_checked": health.get("last_checked"),
        "freshness_days": health.get("freshness_days", health.get("staleness_days")),
        "next_expected_update": health.get("next_expected_update"),
        "refresh_frequency": manifest.get("refresh_frequency"),
        "record_count": record_count(health),
        "date_range": date_range,
        "fields": fields,
        "checks": standard_checks(manifest, health),
        "known_quirks": quirks,
        "breaking_changes": markdown_section(report, "Breaking changes"),
        "reproducibility": {
            "url": source_url,
            "access_method": access_method(health),
        },
        "licence": manifest.get("licence"),
        "attribution": attribution,
    }


def generate_envelope(root: str, row: dict[str, Any], health: dict[str, Any]) -> tuple[str, str]:
    envelope = build_envelope(Path(root), row, health)
    serialized = json.dumps(envelope, indent=2, ensure_ascii=False) + "\n"
    return row["id"], serialized


def generate(root: Path, *, dry_run: bool, force: bool) -> int:
    manifest = load_json(root / "datapulse.json")
    snapshot = load_json(root / "health/latest.json")
    manifest_rows = manifest.get("datasets")
    health_rows = snapshot.get("datasets")
    if not isinstance(manifest_rows, list) or not isinstance(health_rows, list):
        raise ValueError("datapulse.json and health/latest.json must contain datasets arrays")
    health_by_id = {
        row["dataset_id"]: row
        for row in health_rows
        if isinstance(row, dict) and isinstance(row.get("dataset_id"), str)
    }
    output_dir = root / "data/json"
    targets: list[dict[str, Any]] = []
    for row in manifest_rows:
        if not isinstance(row, dict) or not isinstance(row.get("id"), str):
            raise ValueError("datapulse.json contains a dataset without a string id")
        dataset_id = row["id"]
        if "gtfs" in dataset_id.lower():
            continue
        path = output_dir / f"{dataset_id}.json"
        if path.exists() and not force:
            continue
        if dataset_id not in health_by_id:
            raise ValueError(f"health/latest.json has no row for {dataset_id}")
        targets.append(row)

    if dry_run:
        for row in targets:
            print(f"Would generate data/json/{row['id']}.json")
        print(f"Dry run: {len(targets)} envelope(s) would be generated.")
        return len(targets)

    output_dir.mkdir(parents=True, exist_ok=True)
    worker_args = [
        (str(root), row, health_by_id[row["id"]])
        for row in targets
    ]
    workers = min(os.cpu_count() or 1, 8)
    with multiprocessing.Pool(processes=workers) as pool:
        generated = pool.starmap(generate_envelope, worker_args)
    for dataset_id, serialized in generated:
        path = output_dir / f"{dataset_id}.json"
        if path.exists() and not force:
            raise FileExistsError(f"refusing to overwrite {path}; pass --force to replace it")
        path.write_text(serialized, encoding="utf-8")
    print(f"Generated {len(targets)} envelope(s).")
    return len(targets)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    generate(args.root.resolve(), dry_run=args.dry_run, force=args.force)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
