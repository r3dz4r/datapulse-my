#!/usr/bin/env python3
"""Generate a deterministic Open Knowledge Format v0.2 bundle."""

from __future__ import annotations

import argparse
import json
import logging
import os
import re
import shutil
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker


LOGGER = logging.getLogger(__name__)
ROOT = Path(__file__).resolve().parents[1]
PIPELINE_ACTOR = "process:datapulse-pipeline"
HEALTH_ACTOR = "process:datapulse-health-timer"
DEFAULT_CADENCE_DAYS = 90
WEEKDAY_DAILIES = frozenset(
    {
        "daily (weekdays)",
        "daily (weekdays, 0900 myt)",
        "daily (weekdays, 1130 myt)",
        "daily (weekdays, 1200 myt)",
        "daily (weekdays, 1700 myt)",
    }
)
CADENCE_DAYS = {
    "hourly": 1,
    "daily": 1,
    "weekly": 7,
    "monthly": 31,
    "quarterly": 92,
    "annual": 365,
    "biennial to triennial (survey years)": 1095,
    "as-required": DEFAULT_CADENCE_DAYS,
}
NO_STALE_STATUSES = frozenset({"unknown-freshness", "reference", "discontinued"})


class OkfBundleError(Exception):
    """Raised when an OKF bundle cannot be rendered safely."""


def _load_json(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise OkfBundleError(f"cannot read {label} at {path}: {error}") from error
    if not isinstance(value, dict):
        raise OkfBundleError(f"{label} at {path} must be a JSON object")
    return value


def _validate(document: dict[str, Any], schema_path: Path, label: str) -> None:
    schema = _load_json(schema_path, f"{label} schema")
    errors = sorted(
        Draft202012Validator(schema, format_checker=FormatChecker()).iter_errors(document),
        key=lambda error: list(error.path),
    )
    if errors:
        raise OkfBundleError(f"{label} does not validate: {errors[0].message}")


def _iso(value: str, label: str) -> str:
    """Normalize a date or UTC ISO timestamp to a Z-suffixed timestamp."""
    if not isinstance(value, str) or not value:
        raise OkfBundleError(f"{label} must be a non-empty ISO date or timestamp")
    try:
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
            parsed = datetime.fromisoformat(value).replace(tzinfo=timezone.utc)
        else:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                raise ValueError("UTC offset is required")
            parsed = parsed.astimezone(timezone.utc)
    except ValueError as error:
        raise OkfBundleError(f"{label} is not an ISO timestamp: {value!r}") from error
    return parsed.strftime("%Y-%m-%dT%H:%M:%SZ")


def cadence_stale_after(
    refresh_frequency: object, content_freshness_date: object, last_checked: object
) -> tuple[str | None, str | None]:
    """Return stale_after and its deterministic cadence basis."""
    if not isinstance(content_freshness_date, str) or not content_freshness_date:
        return None, None
    freshness = datetime.fromisoformat(_iso(content_freshness_date, "content_freshness_date").replace("Z", "+00:00"))
    cadence = refresh_frequency.casefold() if isinstance(refresh_frequency, str) else ""
    if cadence == "30 seconds":
        if not isinstance(last_checked, str) or not last_checked:
            raise OkfBundleError("realtime dataset needs health last_checked")
        checked = datetime.fromisoformat(_iso(last_checked, "last_checked").replace("Z", "+00:00"))
        return (checked + timedelta(minutes=10)).strftime("%Y-%m-%dT%H:%M:%SZ"), "realtime"
    if cadence in WEEKDAY_DAILIES:
        result = freshness + timedelta(days=1)
        if result.weekday() == 5:
            result += timedelta(days=2)
        elif result.weekday() == 6:
            result += timedelta(days=1)
        return result.strftime("%Y-%m-%dT%H:%M:%SZ"), "weekday_cadence"
    if cadence in CADENCE_DAYS:
        basis = "default_90d" if cadence == "as-required" else "cadence"
        days = CADENCE_DAYS[cadence]
    else:
        basis = "default_90d"
        days = DEFAULT_CADENCE_DAYS
    return (freshness + timedelta(days=days * 1.5)).strftime("%Y-%m-%dT%H:%M:%SZ"), basis


def _scalar(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ": "))


def _slug(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-")
    return slug or "unclassified"


def _frontmatter(values: list[tuple[str, object]]) -> str:
    lines = ["---"]
    for key, value in values:
        if isinstance(value, list) and key in {"sources", "verified", "parameters"}:
            lines.append(f"{key}:")
            for item in value:
                lines.append(f"  - {_scalar(item)}")
        else:
            lines.append(f"{key}: {_scalar(value)}")
    lines.append("---")
    return "\n".join(lines)


def _health_schema_text(row: dict[str, Any]) -> str:
    fields: list[str] = []
    for name in ("schema_fingerprint", "column_count", "first_row_hash", "record_count"):
        value = row.get(name)
        if value is not None:
            fields.append(f"- `{name}`: `{value}`")
    return "\n".join(fields) if fields else "No structural fingerprint was recorded by the latest probe."


def _dataset_document(entry: dict[str, Any], row: dict[str, Any], family: str) -> str:
    identifier = entry["id"]
    status = row["status"]
    verified_at = _iso(str(entry.get("verified_at") or row["last_checked"]), f"manifest verified_at for {identifier}")
    checked_at = _iso(row["last_checked"], f"health last_checked for {identifier}")
    source: dict[str, object] = {"id": entry["custodian"], "resource": entry["url"], "title": entry["steward"]}
    if isinstance(row.get("header_timestamp"), str) and row["header_timestamp"]:
        source["last_modified"] = _iso(row["header_timestamp"], f"header timestamp for {identifier}")
    values: list[tuple[str, object]] = [
        ("type", "Dataset"),
        ("title", entry["name"]),
        ("description", f"DataPulse projection of {entry['name']} from {entry['steward']}."),
        ("resource", entry["url"]),
        ("tags", [entry["source"], "vertical" if entry.get("vertical") else "non-vertical", entry["refresh_frequency"]]),
        ("sources", [source]),
        ("generated", {"by": PIPELINE_ACTOR, "at": verified_at}),
        ("verified", [{"by": HEALTH_ACTOR, "at": checked_at}]),
        ("status", "deprecated" if status == "discontinued" else "stable"),
        ("datapulse:licence", entry["licence"]),
        ("datapulse:attribution", entry["attribution"]),
        ("datapulse:real_status", status),
        ("datapulse:health_report", "/" + str(entry["health_report"]).lstrip("/")),
        ("datapulse:methodology_version", entry.get("methodology_version")),
        ("datapulse:expected_record_count", entry.get("expected_record_count")),
    ]
    stale_after, basis = cadence_stale_after(entry.get("refresh_frequency"), row.get("content_freshness_date"), row.get("last_checked"))
    if status not in NO_STALE_STATUSES and stale_after is not None and basis is not None:
        values.extend([("stale_after", stale_after), ("datapulse:stale_after_basis", basis)])
    frontmatter = _frontmatter(values)
    quirks = entry.get("probe_note") or row.get("status_reason")
    quirks_text = str(quirks) if quirks else "No probe quirks were recorded."
    return (
        f"{frontmatter}\n\n# Summary\n\n{entry['name']} is published by {entry['steward']} and tracked by DataPulse. "
        f"The latest published probe classifies it as `{status}`.\n\n# Schema\n\n{_health_schema_text(row)}\n\n"
        f"# Quirks\n\n{quirks_text}\n\n# Health\n\nSee the [published health report](/{str(entry['health_report']).lstrip('/')}). "
        f"The probe is described by [the {family} attested computation](/computations/{_slug(family)}.md).\n"
    )


def _computation_document(family: str, checked_at: str) -> str:
    frontmatter = _frontmatter(
        [
            ("type", "Attested Computation"),
            ("title", f"DataPulse probe family: {family}"),
            ("description", f"Deterministic DataPulse health probe receipt projection for the {family} family."),
            ("status", "stable"),
            ("runtime", "datapulse-pipeline"),
            ("parameters", [{"name": "dataset_id", "type": "string", "required": True}]),
            ("executor", {"resource": "scripts/gen_per_dataset_receipt.py", "receipt": ["dataset_id", "last_checked", "http_status", "content_freshness_date", "record_count"]}),
            ("attester", {"resource": "scripts/verify_per_dataset_receipt.py"}),
            ("generated", {"by": PIPELINE_ACTOR, "at": checked_at}),
            ("verified", [{"by": HEALTH_ACTOR, "at": checked_at}]),
        ]
    )
    return f"{frontmatter}\n\n# Computation\n\nRun the recorded DataPulse probe pipeline for the supplied `dataset_id` and inspect the declared receipt fields.\n"


def _log(changelog: dict[str, Any], dataset_count: int) -> str:
    generated_at = _iso(str(changelog.get("generated_at")), "changelog generated_at")
    date = generated_at[:10]
    return f"# Directory Update Log\n\n## {date}\n\n* **Update**: Projected {dataset_count} dataset entries from the published changelog snapshot.\n"


def render_bundle(manifest: dict[str, Any], health: dict[str, Any], changelog: dict[str, Any], *, quick_test: bool = False) -> dict[Path, str]:
    """Render the complete deterministic bundle as relative paths and content."""
    entries = manifest["datasets"]
    rows = health["datasets"]
    by_id = {entry["id"]: entry for entry in entries}
    health_by_id = {row["dataset_id"]: row for row in rows}
    if set(by_id) != set(health_by_id):
        raise OkfBundleError("manifest and health dataset identifiers must match")
    selected_ids = sorted(by_id)[:8] if quick_test else sorted(by_id)
    selected = [(by_id[identifier], health_by_id[identifier]) for identifier in selected_ids]
    families = sorted({str(entry.get("freshness_policy", {}).get("family") or "unclassified") for entry, _ in selected})
    checked_at = _iso(health["checked_at"], "health checked_at")
    outputs: dict[Path, str] = {
        Path("index.md"): "---\nokf_version: \"0.2\"\n---\n\n# DataPulse MY Open Knowledge Format bundle\n\n## Concepts\n\n* [Datasets](datasets/) - Dataset projections with published provenance and health signals.\n* [Attested computations](computations/) - Probe-family receipt contracts.\n* [Agencies](agencies/) - Agency-specific dataset indexes.\n",
        Path("log.md"): _log(changelog, len(selected)),
        Path("datasets/index.md"): "# Datasets\n\n" + "".join(f"* [{entry['name']}]({entry['id']}.md) - {entry['source']}.\n" for entry, _ in selected),
        Path("computations/index.md"): "# Attested computations\n\n" + "".join(f"* [{family}]({_slug(family)}.md) - DataPulse probe-family receipt contract.\n" for family in families),
    }
    agencies: dict[str, list[dict[str, Any]]] = {}
    for entry, row in selected:
        family = str(entry.get("freshness_policy", {}).get("family") or "unclassified")
        outputs[Path("datasets") / f"{entry['id']}.md"] = _dataset_document(entry, row, family)
        agencies.setdefault(str(entry["custodian"]), []).append(entry)
    for family in families:
        outputs[Path("computations") / f"{_slug(family)}.md"] = _computation_document(family, checked_at)
    for agency, agency_entries in sorted(agencies.items()):
        outputs[Path("agencies") / _slug(agency) / "index.md"] = "# " + agency + " datasets\n\n" + "".join(
            f"* [{entry['name']}](../../datasets/{entry['id']}.md) - {entry['source']}.\n" for entry in sorted(agency_entries, key=lambda item: item["id"])
        )
    outputs[Path("agencies/index.md")] = "# Agencies\n\n" + "".join(
        f"* [{agency}](./{_slug(agency)}/) - Published dataset index.\n" for agency in sorted(agencies)
    )
    return outputs


def _publish(output: Path, files: dict[Path, str]) -> None:
    """Publish the entire generated tree through a staged directory swap."""
    output = output.resolve()
    if output.exists() and (output.is_symlink() or not output.is_dir()):
        raise OkfBundleError(f"output must be a directory, not a symlink: {output}")
    output.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix=f".{output.name}.tmp-", dir=output.parent))
    backup = output.parent / f".{output.name}.previous"
    try:
        for relative, content in files.items():
            target = stage / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            temporary = target.with_suffix(target.suffix + ".tmp")
            temporary.write_text(content, encoding="utf-8", newline="\n")
            os.replace(temporary, target)
        if backup.exists():
            shutil.rmtree(backup)
        if output.exists():
            os.replace(output, backup)
        os.replace(stage, output)
        if backup.exists():
            shutil.rmtree(backup)
    except OSError as error:
        if not output.exists() and backup.exists():
            os.replace(backup, output)
        raise OkfBundleError(f"cannot publish OKF bundle at {output}: {error}") from error
    finally:
        if stage.exists():
            shutil.rmtree(stage)


def generate(
    manifest_path: Path,
    health_path: Path,
    changelog_path: Path,
    output: Path | None,
    *,
    quick_test: bool = False,
    manifest_schema_path: Path = ROOT / "datapulse.schema.json",
    health_schema_path: Path = ROOT / "health.schema.json",
) -> dict[Path, str]:
    """Validate inputs, render the bundle, and publish it when requested."""
    manifest = _load_json(manifest_path, "manifest")
    health = _load_json(health_path, "health snapshot")
    changelog = _load_json(changelog_path, "changelog")
    _validate(manifest, manifest_schema_path, "manifest")
    _validate(health, health_schema_path, "health snapshot")
    files = render_bundle(manifest, health, changelog, quick_test=quick_test)
    if output is not None:
        _publish(output, files)
    return files


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--in", dest="manifest", type=Path, default=ROOT / "datapulse.json")
    parser.add_argument("--health", type=Path, default=ROOT / "health/latest.json")
    parser.add_argument("--changelog", type=Path, default=ROOT / "changelog.json")
    parser.add_argument("--out", type=Path)
    parser.add_argument("--quick-test", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    output = args.out if args.out is not None else (None if args.quick_test else ROOT / "docs/okf")
    try:
        files = generate(args.manifest, args.health, args.changelog, output, quick_test=args.quick_test)
    except OkfBundleError as error:
        LOGGER.error("gen_okf_bundle.py: %s", error)
        return 1
    LOGGER.info("rendered %d OKF files%s", len(files), f" at {output}" if output else "")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
