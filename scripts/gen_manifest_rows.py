#!/usr/bin/env python3
"""Generate selected manifest rows from data.gov.my catalogue page metadata.

Usage: python3 scripts/gen_manifest_rows.py [--source config/manifest-onboarding.json]
Offline replay: add --metadata FILE (a JSON object mapping dataset IDs to pageProps).

The onboarding document has schema ``datapulse/v1/manifest-onboarding`` and a
``datasets`` array. Every entry explicitly supplies id, licence, custodian,
steward, attribution, geo_coverage, namespace, vertical, expected_record_count
(integer or null), and freshness_policy (the manifest schema's full object).
New entries also require real_status, verified_at, attestation_ref, and
methodology_version: this generator cannot invent lifecycle checks or signed
evidence. Existing values of those four fields belong to other writers and
are retained. The ID is the upstream catalogue slug; aliases are unsupported.

Only full CSV links are accepted: both the default direct probe and the record
evidence consumer can read them, whereas previews and edition collections do
not describe the full dataset. Missing frequency is allowed only for explicitly
reviewed reference tables, scheduled as as-required. Unknown cadences fail closed.

Rows outside the input set retain their exact bytes. Existing positions and
top-level bytes are retained; new IDs append in lexical order because the real
manifest has historical, non-lexical ordering. No clock or health/artifact
generation is performed. The committed empty source is a byte-preserving no-op.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import re
import tempfile
from datetime import date
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import requests

ROOT = Path(__file__).resolve().parents[1]
LOGGER = logging.getLogger(__name__)
SOURCE_SCHEMA = "datapulse/v1/manifest-onboarding"
ID_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]*\Z")
JUDGEMENT_FIELDS = {
    "licence", "custodian", "steward", "attribution", "geo_coverage",
    "namespace", "vertical", "expected_record_count", "freshness_policy",
}
OWNED_FIELDS = {"real_status", "verified_at", "attestation_ref", "methodology_version"}
FREQUENCIES = {
    "YEARLY": "annual", "ANNUAL": "annual", "MONTHLY": "monthly",
    "QUARTERLY": "quarterly", "DAILY": "daily", "WEEKLY": "weekly",
}


class GenerationError(ValueError):
    """An input cannot produce a complete, probeable manifest row."""


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise GenerationError(f"duplicate JSON key {key!r}")
        result[key] = value
    return result


DECODER = json.JSONDecoder(object_pairs_hook=_unique_object)


def _load(path: Path) -> Any:
    return DECODER.decode(path.read_text(encoding="utf-8"))


def _validate(value: Any, spec: dict[str, Any], schema: dict[str, Any], label: str) -> None:
    """Check row constraints used by the committed schema, without a new dependency."""
    if "$ref" in spec:
        target = schema
        for part in spec["$ref"].removeprefix("#/").split("/"):
            target = target[part]
        _validate(value, target, schema, label)
        return
    types = spec.get("type", [])
    types = [types] if isinstance(types, str) else types
    checks = {
        "string": isinstance(value, str), "boolean": type(value) is bool,
        "integer": type(value) is int, "null": value is None,
        "object": isinstance(value, dict), "array": isinstance(value, list),
    }
    if types and not any(checks.get(kind, False) for kind in types):
        raise GenerationError(f"{label}: expected {' or '.join(types)}")
    if "enum" in spec and value not in spec["enum"]:
        raise GenerationError(f"{label}: unsupported value {value!r}")
    if "const" in spec and value != spec["const"]:
        raise GenerationError(f"{label}: expected {spec['const']!r}")
    if isinstance(value, str):
        if len(value.strip()) < spec.get("minLength", 0):
            raise GenerationError(f"{label}: empty string")
        if "pattern" in spec and not re.search(spec["pattern"], value):
            raise GenerationError(f"{label}: invalid pattern")
        if spec.get("format") == "date":
            if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
                raise GenerationError(f"{label}: expected ISO date")
            date.fromisoformat(value)
        if spec.get("format") == "uri":
            parsed = urlsplit(value)
            if (parsed.scheme != "https" or not parsed.hostname or parsed.username
                    or parsed.password or any(char.isspace() for char in value)):
                raise GenerationError(f"{label}: expected an absolute HTTPS URL without credentials")
    if type(value) is int and value < spec.get("minimum", value):
        raise GenerationError(f"{label}: below minimum")
    if isinstance(value, dict):
        missing = set(spec.get("required", [])) - value.keys()
        if missing:
            raise GenerationError(f"{label}: missing fields {', '.join(sorted(missing))}")
        properties = spec.get("properties", {})
        if spec.get("additionalProperties") is False and value.keys() - properties.keys():
            raise GenerationError(f"{label}: unknown fields {', '.join(sorted(value.keys() - properties.keys()))}")
        for key in sorted(value.keys() & properties.keys()):
            _validate(value[key], properties[key], schema, f"{label}.{key}")


class _NextDataParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=False)
        self.active = False
        self.blocks: list[list[str]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "script" and dict(attrs).get("id") == "__NEXT_DATA__":
            self.active = True
            self.blocks.append([])

    def handle_data(self, data: str) -> None:
        if self.active:
            self.blocks[-1].append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == "script":
            self.active = False


def parse_metadata(page: str, dataset_id: str) -> dict[str, Any]:
    """Extract the exact catalogue pageProps, rejecting ambiguous/mismatched pages."""
    parser = _NextDataParser()
    parser.feed(page)
    if len(parser.blocks) != 1:
        raise GenerationError(f"{dataset_id}: expected one __NEXT_DATA__ metadata block")
    payload = DECODER.decode("".join(parser.blocks[0]))
    try:
        metadata = payload["props"]["pageProps"]
    except (KeyError, TypeError) as error:
        raise GenerationError(f"{dataset_id}: missing pageProps") from error
    if not isinstance(metadata, dict) or metadata.get("id") != dataset_id:
        raise GenerationError(f"{dataset_id}: metadata ID mismatch")
    return metadata


def fetch_metadata(dataset_id: str) -> dict[str, Any]:
    """Read one upstream page once; failed requests never produce partial output."""
    response = requests.get(
        f"https://data.gov.my/data-catalogue/{dataset_id}", timeout=30,
        headers={"User-Agent": "DataPulseMY/1.0 (+https://www.data-pulse.my/about)"},
    )
    response.raise_for_status()
    return parse_metadata(response.text, dataset_id)


def emit_row(entry: dict[str, Any], metadata: dict[str, Any],
             schema: dict[str, Any], existing: dict[str, Any] | None = None) -> dict[str, Any]:
    """Build a full schema-valid row, preserving fields owned by other writers."""
    dataset_id = entry["id"]
    if not isinstance(metadata, dict) or metadata.get("id") != dataset_id:
        raise GenerationError(f"{dataset_id}: metadata ID mismatch")
    title = metadata.get("title")
    sources = metadata.get("data_source")
    fields = metadata.get("fields")
    if not isinstance(title, str) or not title.strip():
        raise GenerationError(f"{dataset_id}: missing metadata title")
    if (not isinstance(sources, list) or not sources
            or any(not isinstance(source, str) or not source.strip() for source in sources)):
        raise GenerationError(f"{dataset_id}: missing metadata data_source")
    if (not isinstance(fields, list) or not fields
            or any(not isinstance(field, dict) or not isinstance(field.get("name"), str)
                   or not field["name"].strip() for field in fields)):
        raise GenerationError(f"{dataset_id}: missing metadata fields")
    policy = entry["freshness_policy"]
    if (not policy["reference_table"]
            and policy["content_date_field"] not in {field["name"] for field in fields}):
        raise GenerationError(f"{dataset_id}: freshness content_date_field absent from metadata fields")
    frequency = metadata.get("frequency")
    if frequency is None or frequency == "":
        if not policy["reference_table"]:
            raise GenerationError(f"{dataset_id}: absent frequency requires an explicit reference_table policy")
        cadence = "as-required"
    elif frequency not in FREQUENCIES:
        raise GenerationError(f"{dataset_id}: unsupported publisher frequency {frequency!r}")
    else:
        cadence = FREQUENCIES[frequency]
    csv_url = metadata.get("link_csv")
    _validate(csv_url, {"type": "string", "format": "uri"}, schema, f"{dataset_id}.link_csv")
    if not urlsplit(csv_url).path.endswith(".csv") or urlsplit(csv_url).fragment:
        raise GenerationError(f"{dataset_id}: link_csv must identify a full CSV dataset")
    row = dict(existing or {})
    row.update({key: entry[key] for key in sorted(JUDGEMENT_FIELDS)})
    for key in sorted(OWNED_FIELDS):
        if existing is None or key not in existing:
            if key not in entry:
                raise GenerationError(f"{dataset_id}: missing explicit {key}")
            row[key] = entry[key]
    row.update({
        "id": dataset_id, "name": title, "source": f"{', '.join(sources)} via data.gov.my",
        "url": csv_url, "record_source_url": csv_url,
        "record_evidence_schema": "record-evidence/v1", "refresh_frequency": cadence,
        "health_report": f"data/{dataset_id}.md",
    })
    _validate(row, schema["$defs"]["dataset"], schema, dataset_id)
    return row


def _row_spans(text: str) -> tuple[int, list[tuple[int, int]]]:
    """Locate rows structurally so untouched JSON is never reserialized."""
    def skip(position: int) -> int:
        while position < len(text) and text[position].isspace():
            position += 1
        return position

    position = skip(text.index("{") + 1)
    while text[position] != "}":
        key, position = DECODER.raw_decode(text, position)
        start = skip(skip(position) + 1)  # colon
        _, end = DECODER.raw_decode(text, start)
        if key == "datasets":
            spans: list[tuple[int, int]] = []
            position = skip(start + 1)
            while text[position] != "]":
                _, row_end = DECODER.raw_decode(text, position)
                spans.append((position, row_end))
                position = skip(row_end)
                if text[position] == ",":
                    position = skip(position + 1)
            return start, spans
        position = skip(end)
        if text[position] == ",":
            position = skip(position + 1)
    raise GenerationError("manifest: missing datasets array")


def _render(text: str, rows: list[dict[str, Any]], selected: dict[str, dict[str, Any]]) -> str:
    array_start, spans = _row_spans(text)
    edits: list[tuple[int, int, str]] = []

    def formatted(row: dict[str, Any], indent: str) -> str:
        return json.dumps(row, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False).replace("\n", "\n" + indent)

    for row, (start, end) in zip(rows, spans):
        new = selected.get(row["id"])
        if new is not None and new != row:
            prefix = text[text.rfind("\n", 0, start) + 1:start]
            indent = prefix if prefix.isspace() else "    "
            edits.append((start, end, formatted(new, indent)))
    additions = [selected[key] for key in sorted(selected.keys() - {row["id"] for row in rows})]
    if additions:
        body = ",\n".join("    " + formatted(row, "    ") for row in additions)
        if spans:
            edits.append((spans[-1][1], spans[-1][1], ",\n" + body))
        else:
            edits.append((array_start + 1, array_start + 1, "\n" + body + "\n  "))
    for start, end, replacement in sorted(edits, reverse=True):
        text = text[:start] + replacement + text[end:]
    return text


def generate(root: Path = ROOT, source: Path | None = None,
             metadata_path: Path | None = None) -> int:
    """Validate all selected rows, then atomically replace only datapulse.json."""
    path = root / "datapulse.json"
    original = path.read_bytes()
    text = original.decode("utf-8")
    manifest = DECODER.decode(text)
    if not isinstance(manifest, dict) or not isinstance(manifest.get("datasets"), list):
        raise GenerationError("manifest: expected datasets array")
    rows = manifest["datasets"]
    existing: dict[str, dict[str, Any]] = {}
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get("id"), str):
            raise GenerationError("manifest: every row requires an id")
        if row["id"] in existing:
            raise GenerationError(f"manifest: duplicate dataset id {row['id']}")
        existing[row["id"]] = row
    onboarding = _load(source or root / "config/manifest-onboarding.json")
    if (not isinstance(onboarding, dict) or onboarding.get("schema") != SOURCE_SCHEMA
            or not isinstance(onboarding.get("datasets"), list)):
        raise GenerationError(f"onboarding: expected {SOURCE_SCHEMA} and datasets array")
    schema = _load(root / "datapulse.schema.json")
    custodians = _load(root / "custodians.json")["custodians"]
    probe = _load(root / "scripts/probe-policy.json")
    entries: dict[str, dict[str, Any]] = {}
    for entry in onboarding["datasets"]:
        if not isinstance(entry, dict) or not isinstance(entry.get("id"), str) or not ID_PATTERN.fullmatch(entry["id"]):
            raise GenerationError("onboarding: id must be a safe catalogue slug")
        dataset_id = entry["id"]
        if dataset_id in entries:
            raise GenerationError(f"onboarding: duplicate dataset id {dataset_id}")
        missing = JUDGEMENT_FIELDS - entry.keys()
        if missing:
            raise GenerationError(f"{dataset_id}: missing judgement fields {', '.join(sorted(missing))}")
        unknown = entry.keys() - JUDGEMENT_FIELDS - OWNED_FIELDS - {"id"}
        if unknown:
            raise GenerationError(f"{dataset_id}: unknown onboarding fields {', '.join(sorted(unknown))}")
        for key in sorted(entry.keys() - {"id"}):
            _validate(entry[key], schema["$defs"]["dataset"]["properties"][key], schema, f"{dataset_id}.{key}")
        if entry["custodian"] not in custodians:
            raise GenerationError(f"{dataset_id}: unresolved custodian {entry['custodian']!r}")
        effective = dict(probe["defaults"])
        specific = probe["datasets"].get(dataset_id, {})
        if specific.get("template"):
            effective.update(probe.get("templates", {}).get(specific["template"], {}))
        effective.update(specific)
        if effective.get("adapter") != "direct":
            raise GenerationError(f"{dataset_id}: full CSV rows require the direct probe adapter")
        entries[dataset_id] = entry
    cached = _load(metadata_path) if metadata_path else None
    if metadata_path and not isinstance(cached, dict):
        raise GenerationError("metadata cache: expected object keyed by dataset ID")
    selected: dict[str, dict[str, Any]] = {}
    for dataset_id in sorted(entries):
        if cached is not None:
            if dataset_id not in cached:
                raise GenerationError(f"{dataset_id}: missing cached metadata")
            metadata = cached[dataset_id]
        else:
            metadata = fetch_metadata(dataset_id)
        selected[dataset_id] = emit_row(entries[dataset_id], metadata, schema, existing.get(dataset_id))
    updated = _render(text, rows, selected).encode("utf-8")
    if updated != original:
        temporary: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(dir=path.parent, prefix=".manifest-", delete=False) as handle:
                temporary = Path(handle.name)
                handle.write(updated)
                handle.flush()
                os.fsync(handle.fileno())
            temporary.chmod(path.stat().st_mode & 0o777)
            os.replace(temporary, path)
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
    return len(selected)


def main() -> int:
    """Run the generator with explicit offline replay and root overrides."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--source", type=Path)
    parser.add_argument("--metadata", type=Path)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="gen_manifest_rows.py: %(message)s")
    try:
        count = generate(args.root, args.source, args.metadata)
    except (GenerationError, OSError, ValueError, KeyError, TypeError, requests.RequestException) as error:
        LOGGER.error("%s", error)
        return 1
    LOGGER.info("generated %d selected rows", count)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
