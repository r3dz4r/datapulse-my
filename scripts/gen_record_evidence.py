#!/usr/bin/env python3
"""Generate record-evidence/v1 envelopes for opt-in tabular CSV datasets."""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import os
import re
import time
from collections import Counter
from dataclasses import dataclass
from datetime import UTC, date, datetime
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any

import httpx

try:
    from jsonschema import Draft202012Validator, FormatChecker
except ImportError:  # pragma: no cover - the pure-Python checks remain available
    Draft202012Validator = None  # type: ignore[assignment,misc]
    FormatChecker = None  # type: ignore[assignment,misc]


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_NAME = "record-evidence/v1"
STATUSES = (
    "fresh",
    "aging",
    "stale",
    "discontinued",
    "degraded",
    "browser-dependent",
    "unreachable",
    "unknown",
    "unknown-freshness",
    "reference",
)

# Deliberately ported constants, not an engine.pharma import. The DataPulse
# production checkout must remain independently runnable.
CADENCES: dict[str, dict[str, int | None]] = {
    "pharmaceutical_products": {"freshness_window_days": 1},
}
GENERIC_CADENCE_DAYS: dict[str, int] = {
    "30 seconds": 0,
    "hourly": 0,
    "daily": 1,
    "weekly": 7,
    "monthly": 30,
    "quarterly": 90,
    "annual": 365,
}
IDENTIFIER_CANDIDATES = ("record_id", "id", "reg_no", "license_no")
NPRA_REGISTRATION = re.compile(r"^MAL[0-9]{8}[A-Z]+$", re.IGNORECASE)
NPRA_LINK_FIELDS = (
    ("holder", "holder_osa", "held_by"),
    ("manufacturer", "manufacturer_osa", "manufactured_by"),
    ("importer", "importer_osa", "imported_by"),
)
DEFAULT_EXCERPT_SIZE = 50
MAX_ATTEMPTS = 3
REQUEST_TIMEOUT_SECONDS = 60.0


@dataclass(frozen=True)
class OutputPaths:
    full: Path
    latest: Path


def _iso_datetime(value: datetime) -> str:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("timestamps must be timezone-aware")
    normalized = value.astimezone(UTC).replace(microsecond=0)
    return normalized.isoformat().replace("+00:00", "Z")


def _parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = parsedate_to_datetime(value)
    except (TypeError, ValueError, OverflowError):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError(
                f"invalid source last-modified timestamp: {value!r}"
            ) from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("source last-modified timestamp must include a timezone")
    return parsed.astimezone(UTC)


def _canonical_digest(value: dict[str, Any]) -> str:
    payload = json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def _freshness(
    dataset: dict[str, Any], source_last_modified: datetime | None, run_date: date
) -> dict[str, Any]:
    if (
        dataset.get("discontinued") is True
        or dataset.get("real_status") == "discontinued"
    ):
        status = "discontinued"
    elif dataset.get("data_type") == "reference":
        status = "reference"
    elif source_last_modified is None:
        status = "unknown-freshness"
    else:
        modified_date = source_last_modified.astimezone(UTC).date()
        age_days = (run_date - modified_date).days
        if age_days < 0:
            raise ValueError("source last-modified timestamp is in the future")
        cadence = CADENCES.get(str(dataset.get("id")), {})
        window = cadence.get("freshness_window_days")
        if window is None:
            window = GENERIC_CADENCE_DAYS.get(str(dataset.get("refresh_frequency")))
        if window is None:
            status = "unknown-freshness"
        elif age_days <= window:
            status = "fresh"
        elif age_days <= 3 * window:
            status = "aging"
        else:
            status = "stale"

    age_days_value: int | None = None
    modified_value: str | None = None
    if source_last_modified is not None:
        modified_value = _iso_datetime(source_last_modified)
        age_days_value = (run_date - source_last_modified.astimezone(UTC).date()).days
        if age_days_value < 0:
            raise ValueError("source last-modified timestamp is in the future")
    return {
        "source_last_modified": modified_value,
        "age_days": age_days_value,
        "status": status,
    }


def _parse_csv(content: bytes) -> tuple[list[str], list[list[str]]]:
    try:
        text = content.decode("utf-8-sig")
        reader = csv.reader(io.StringIO(text), strict=True)
        header = next(reader)
        rows = list(reader)
    except (UnicodeDecodeError, csv.Error, StopIteration) as exc:
        raise ValueError(f"source is not a usable UTF-8 CSV: {exc}") from exc
    header = [name.strip() for name in header]
    if not header or any(not name for name in header):
        raise ValueError("CSV header fields must be non-empty")
    if len(header) != len(set(header)):
        raise ValueError("CSV header fields must be unique")
    return header, rows


def _identifier_field(header: list[str]) -> str:
    return next(
        (field for field in IDENTIFIER_CANDIDATES if field in header), header[0]
    )


def _structural_evidence(
    dataset_id: str,
    header: list[str],
    row: list[str],
    identifier_field: str,
) -> dict[str, Any]:
    missing: list[str] = []
    if len(row) != len(header):
        missing.append("$row_width")
    values = dict(zip(header, row))
    identifier = values.get(identifier_field, "").strip()
    if not identifier:
        missing.append(identifier_field)
    elif dataset_id == "pharmaceutical_products" and not NPRA_REGISTRATION.fullmatch(
        identifier
    ):
        missing.append("reg_no:pattern")
    return {
        "schema_ok": not missing,
        "missing_required_fields": missing,
    }


def _linkage(dataset_id: str, values: dict[str, str]) -> dict[str, Any]:
    linked_to: list[dict[str, str]] = []
    unmatched: list[str] = []
    if dataset_id == "pharmaceutical_products":
        for label_field, code_field, kind in NPRA_LINK_FIELDS:
            label = values.get(label_field, "").strip()
            code = values.get(code_field, "").strip()
            if code:
                linked_to.append({"kind": kind, "to": f"osa_code:{code}"})
            elif label:
                unmatched.append(f"{label_field}:{label}")
    return {"linked_to": linked_to, "unmatched": unmatched}


def _record_identifier(
    dataset_id: str,
    identifier_field: str,
    raw_identifier: str,
    row_number: int,
    occurrences: Counter[str],
) -> str:
    identifier = raw_identifier.strip()
    if dataset_id == "pharmaceutical_products" and identifier:
        identifier = identifier.upper()
    base = f"{identifier_field}:{identifier}" if identifier else f"row:{row_number}"
    occurrences[base] += 1
    return base if occurrences[base] == 1 else f"{base}#{occurrences[base]}"


def build_record_evidence(
    dataset: dict[str, Any],
    content: bytes,
    *,
    run_date: date,
    observed_at: datetime,
    source_last_modified: datetime | None,
) -> dict[str, Any]:
    """Build a full envelope from raw CSV bytes and one manifest dataset."""
    dataset_id = dataset.get("id")
    if not isinstance(dataset_id, str) or not dataset_id:
        raise ValueError("vertical dataset must have a non-empty id")
    if dataset.get("record_evidence_schema") != SCHEMA_NAME:
        raise ValueError(
            f"{dataset_id} must declare record_evidence_schema={SCHEMA_NAME!r}"
        )
    source_url = dataset.get("record_source_url") or dataset.get("url")
    if not isinstance(source_url, str) or not source_url:
        raise ValueError(f"{dataset_id} must declare record_source_url or url")

    observed_value = _iso_datetime(observed_at)
    freshness = _freshness(dataset, source_last_modified, run_date)
    header, rows = _parse_csv(content)
    identifier_field = _identifier_field(header)
    occurrences: Counter[str] = Counter()
    records: list[dict[str, Any]] = []
    distribution: Counter[str] = Counter()
    schema_valid_count = 0

    for row_number, row in enumerate(rows, start=1):
        values = dict(zip(header, row))
        structural = _structural_evidence(dataset_id, header, row, identifier_field)
        status = freshness["status"] if structural["schema_ok"] else "degraded"
        schema_valid_count += int(structural["schema_ok"])
        distribution[status] += 1
        explanation = {
            "freshness": {
                "source_last_modified": freshness["source_last_modified"],
                "age_days": freshness["age_days"],
            },
            "structural": structural,
            "linkage": _linkage(dataset_id, values),
            "alternatives": [],
        }
        records.append(
            {
                "record_id": _record_identifier(
                    dataset_id,
                    identifier_field,
                    values.get(identifier_field, ""),
                    row_number,
                    occurrences,
                ),
                "status": status,
                "explanation": explanation,
                "evidence_digest": _canonical_digest(explanation),
            }
        )

    return {
        "schema": SCHEMA_NAME,
        "dataset_id": dataset_id,
        "observed_at": observed_value,
        "run_date": run_date.isoformat(),
        "source_url": source_url,
        "source_sha256": hashlib.sha256(content).hexdigest(),
        "record_count": len(records),
        "schema_valid_count": schema_valid_count,
        "freshness": freshness,
        "status_distribution": {status: distribution[status] for status in STATUSES},
        "records": records,
    }


def _schema_errors(envelope: dict[str, Any]) -> list[str]:
    if Draft202012Validator is None:
        return []
    schema_path = ROOT / "record-evidence.schema.json"
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    return [
        f"{'.'.join(str(part) for part in failure.absolute_path) or '<root>'}: {failure.message}"
        for failure in sorted(
            validator.iter_errors(envelope), key=lambda item: list(item.absolute_path)
        )
    ]


def validate_record_evidence(
    envelope: dict[str, Any], *, full: bool = False
) -> list[str]:
    """Return strict envelope errors without mutating the document."""
    errors = _schema_errors(envelope)
    if errors:
        return errors
    distribution = envelope["status_distribution"]
    if tuple(distribution) != STATUSES:
        errors.append(
            "status_distribution must contain the ten canonical keys in order"
        )
    if sum(distribution.values()) != envelope["record_count"]:
        errors.append("status_distribution counts must sum to record_count")
    if envelope["schema_valid_count"] > envelope["record_count"]:
        errors.append("schema_valid_count must not exceed record_count")
    records = envelope["records"]
    if full and len(records) != envelope["record_count"]:
        errors.append("full envelope records length must equal record_count")
    if len({record["record_id"] for record in records}) != len(records):
        errors.append("record_id values must be unique within an envelope")
    for index, record in enumerate(records):
        expected = _canonical_digest(record["explanation"])
        if record["evidence_digest"] != expected:
            errors.append(f"records.{index}.evidence_digest does not match explanation")
        if record["explanation"]["freshness"] != {
            "source_last_modified": envelope["freshness"]["source_last_modified"],
            "age_days": envelope["freshness"]["age_days"],
        }:
            errors.append(f"records.{index}.freshness differs from envelope freshness")
    if full:
        actual = Counter(record["status"] for record in records)
        if {status: actual[status] for status in STATUSES} != distribution:
            errors.append("status_distribution does not match full records")
    modified = envelope["freshness"]["source_last_modified"]
    age_days = envelope["freshness"]["age_days"]
    if modified is None:
        if age_days is not None:
            errors.append(
                "freshness.age_days must be null without source_last_modified"
            )
    else:
        parsed = _parse_datetime(modified)
        assert parsed is not None
        expected_age = (date.fromisoformat(envelope["run_date"]) - parsed.date()).days
        if age_days != expected_age:
            errors.append(
                "freshness.age_days does not match run_date/source_last_modified"
            )
    return errors


def _representative_excerpt(
    records: list[dict[str, Any]], excerpt_size: int
) -> list[dict[str, Any]]:
    if excerpt_size < 1:
        raise ValueError("excerpt_size must be at least 1")
    if len(records) <= excerpt_size:
        return list(records)
    selected_indices: list[int] = []
    for status in STATUSES:
        match = next(
            (
                index
                for index, record in enumerate(records)
                if record["status"] == status
            ),
            None,
        )
        if match is not None and len(selected_indices) < excerpt_size:
            selected_indices.append(match)
    selected = set(selected_indices)
    selected_indices.extend(
        index
        for index in range(len(records))
        if index not in selected and len(selected_indices) < excerpt_size
    )
    return [records[index] for index in sorted(selected_indices)]


def _write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    serialized = json.dumps(value, ensure_ascii=False, indent=2) + "\n"
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(serialized, encoding="utf-8")
    temporary.replace(path)


def write_record_evidence(
    envelope: dict[str, Any],
    output_root: Path,
    *,
    excerpt_size: int = DEFAULT_EXCERPT_SIZE,
) -> OutputPaths:
    errors = validate_record_evidence(envelope, full=True)
    if errors:
        raise ValueError("invalid record evidence: " + "; ".join(errors))
    directory = output_root / str(envelope["dataset_id"])
    full_path = directory / f"{envelope['run_date']}.json"
    latest_path = directory / "latest.json"
    latest = dict(envelope)
    latest["records"] = _representative_excerpt(envelope["records"], excerpt_size)
    latest_errors = validate_record_evidence(latest, full=False)
    if latest_errors:
        raise ValueError("invalid latest record evidence: " + "; ".join(latest_errors))
    _write_json(full_path, envelope)
    _write_json(latest_path, latest)
    return OutputPaths(full=full_path, latest=latest_path)


def _download(url: str) -> tuple[bytes, datetime | None, datetime]:
    retryable: Exception | None = None
    with httpx.Client(follow_redirects=True, timeout=REQUEST_TIMEOUT_SECONDS) as client:
        for attempt in range(1, MAX_ATTEMPTS + 1):
            try:
                response = client.get(url)
                response.raise_for_status()
                observed_at = datetime.now(UTC)
                return (
                    response.content,
                    _parse_datetime(response.headers.get("Last-Modified")),
                    observed_at,
                )
            except httpx.HTTPStatusError as exc:
                retryable = exc
                if exc.response.status_code != 429 and exc.response.status_code < 500:
                    raise
            except httpx.RequestError as exc:
                retryable = exc
            if attempt < MAX_ATTEMPTS:
                time.sleep(2 ** (attempt - 1))
    assert retryable is not None
    raise retryable


def _load_verticals(manifest_path: Path) -> list[dict[str, Any]]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    rows = manifest.get("datasets") if isinstance(manifest, dict) else None
    if not isinstance(rows, list):
        raise TypeError("manifest.datasets must be an array")
    verticals = [
        row for row in rows if isinstance(row, dict) and row.get("vertical") is True
    ]
    for row in verticals:
        if row.get("record_evidence_schema") != SCHEMA_NAME:
            raise ValueError(
                f"{row.get('id', '<unknown>')}: vertical must declare {SCHEMA_NAME}"
            )
    return verticals


def generate(
    *,
    root: Path,
    manifest_path: Path,
    run_date: date,
    source_file: Path | None = None,
    source_last_modified: datetime | None = None,
    observed_at: datetime | None = None,
    excerpt_size: int = DEFAULT_EXCERPT_SIZE,
) -> list[tuple[dict[str, Any], OutputPaths]]:
    verticals = _load_verticals(manifest_path)
    if source_file is not None and len(verticals) != 1:
        raise ValueError("--source-file requires exactly one vertical dataset")
    generated: list[tuple[dict[str, Any], OutputPaths]] = []
    for dataset in verticals:
        if source_file is None:
            url = dataset.get("record_source_url") or dataset.get("url")
            if not isinstance(url, str) or not url:
                raise ValueError(f"{dataset.get('id')}: no record source URL")
            content, modified, observed = _download(url)
        else:
            content = source_file.read_bytes()
            modified = source_last_modified
            observed = observed_at or datetime.now(UTC)
        envelope = build_record_evidence(
            dataset,
            content,
            run_date=run_date,
            observed_at=observed_at or observed,
            source_last_modified=source_last_modified or modified,
        )
        paths = write_record_evidence(
            envelope, root / "record-evidence", excerpt_size=excerpt_size
        )
        generated.append((envelope, paths))
    return generated


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(os.environ.get("DATAPULSE_REPO_ROOT", ROOT)),
    )
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--run-date", type=date.fromisoformat)
    parser.add_argument("--observed-at")
    parser.add_argument("--source-file", type=Path)
    parser.add_argument("--source-last-modified")
    parser.add_argument("--excerpt-size", type=int, default=DEFAULT_EXCERPT_SIZE)
    args = parser.parse_args(argv)
    root = args.root.resolve()
    manifest = args.manifest or root / "datapulse.json"
    observed_at = _parse_datetime(args.observed_at)
    modified = _parse_datetime(args.source_last_modified)
    generated = generate(
        root=root,
        manifest_path=manifest,
        run_date=args.run_date or datetime.now(UTC).date(),
        source_file=args.source_file,
        source_last_modified=modified,
        observed_at=observed_at,
        excerpt_size=args.excerpt_size,
    )
    if not generated:
        print("No vertical datasets; record evidence generation skipped.")
        return 0
    for envelope, paths in generated:
        print(
            f"Generated {envelope['dataset_id']}: {envelope['record_count']} records; "
            f"full={paths.full}; latest={paths.latest}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
