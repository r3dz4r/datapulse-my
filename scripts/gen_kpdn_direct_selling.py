#!/usr/bin/env python3
"""Observe the GET-only KPDN AJL register and reproducibly register its snapshot."""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import re
import subprocess
import tempfile
from collections import Counter
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from string import Template
from typing import Any

import requests
from jsonschema import Draft202012Validator, FormatChecker, ValidationError

try:
    from scripts.gen_dataset_pages import render_page
    from scripts.gen_json_envelope import SCHEMA, standard_checks
    from scripts.gen_jsonld_catalog import dataset_object
    from scripts.gen_public_discovery import render_sitemap
    from scripts.public_surface_generation import load_public_surfaces
except ModuleNotFoundError:
    from gen_dataset_pages import render_page
    from gen_json_envelope import SCHEMA, standard_checks
    from gen_jsonld_catalog import dataset_object
    from gen_public_discovery import render_sitemap
    from public_surface_generation import load_public_surfaces


ROOT = Path(__file__).resolve().parents[1]
DATASET_ID = "kpdn_direct_selling_licences"
BASE = "https://www.kpdn.gov.my/perkhidmatan-kpdn/jom-berniaga/pembangunan-industri-jualan-langsung/"
SOURCES = {
    "active_expired": BASE + "status-syarikat-jualan-langsung",
    "cancelled": BASE + "senarai-lesen-yang-dibatalkan",
}
TABLE_IDS = {"myTable-aktif", "myTable-tamat", "myTable-batal"}
STATUS = {"AKTIF": "active", "TAMAT TEMPOH": "expired", "BATAL LESEN": "cancelled"}
FIELDS = {
    "company_name": ("NAMA SYARIKAT",),
    "registration_no": ("NO. PENDAFTARAN PERNIAGAAN",),
    "ajl_no": ("NO. LESEN",),
    "licence_start": ("TARIKH MULA", "TARIKH MULA LESEN"),
    "licence_expiry": ("TARIKH TAMAT", "TARIKH TAMAT LESEN"),
    "sector": ("SEKTOR",),
    "address_management": ("ALAMAT PREMIS PERNIAGAAN (PENGURUSAN)",),
    "address_operations": ("ALAMAT PREMIS PERNIAGAAN (OPERASI)",),
}
LOGGER = logging.getLogger(__name__)


class SourceError(ValueError):
    """A source cannot safely be interpreted as the expected register."""


class RegisterParser(HTMLParser):
    """Read text cells and their published tab labels, including hidden tabs."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.tables: list[dict[str, Any]] = []
        self.labels: dict[str, str] = {}
        self.panels: list[str | None] = []
        self.table: dict[str, Any] | None = None
        self.row: list[str] | None = None
        self.cell: list[str] | None = None
        self.anchor: str | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        if tag == "div":
            self.panels.append(attributes.get("aria-labelledby") if attributes.get("role") == "tabpanel" else (self.panels[-1] if self.panels else None))
        if tag == "a" and attributes.get("role") == "tab":
            self.anchor = attributes.get("id")
            if self.anchor:
                self.labels[self.anchor] = ""
        if tag == "table":
            if self.table is not None:
                raise SourceError("nested register tables are unsupported")
            self.table = {"id": attributes.get("id"), "panel": self.panels[-1] if self.panels else None, "rows": []}
            self.tables.append(self.table)
        if self.table is not None:
            if tag == "tr":
                self.handle_endtag("tr")
                self.row = []
            if tag in {"td", "th"}:
                self.handle_endtag("td")
                self.cell = []
            if tag == "br" and self.cell is not None:
                self.cell.append("\n")

    def handle_data(self, data: str) -> None:
        if self.cell is not None:
            self.cell.append(data)
        if self.anchor:
            self.labels[self.anchor] += data

    def handle_endtag(self, tag: str) -> None:
        if tag == "div" and self.panels:
            self.panels.pop()
        if tag == "a":
            self.anchor = None
        if tag in {"td", "th", "tr", "table"} and self.cell is not None:
            if self.row is not None:
                self.row.append("".join(self.cell))
            self.cell = None
        if tag in {"tr", "table"} and self.row is not None:
            if self.table is not None:
                self.table["rows"].append(self.row)
            self.row = None
        if tag == "table":
            self.table = None


def normalise_date(value: str | None) -> str | None:
    """Accept both measured source formats; absent values are not dates."""
    if value is None or value.strip() in {"", "-"}:
        return None
    for pattern in ("%d.%m.%Y", "%d/%m/%Y"):
        try:
            return datetime.strptime(value.strip(), pattern).date().isoformat()
        except ValueError:
            continue
    raise ValueError(f"invalid source date: {value!r}")


def parse_page(source: str, body: bytes, fetched_at: str) -> dict[str, Any]:
    """Preserve every data row, including malformed rows and duplicate licences."""
    parser = RegisterParser()
    parser.feed(body.decode("utf-8"))
    tables = [t for t in parser.tables if t["id"] in TABLE_IDS] if source == "active_expired" else parser.tables
    if not tables or (source == "active_expired" and {t["id"] for t in tables} != TABLE_IDS):
        raise SourceError(f"{source}: missing register tables; stop without switching access lanes")
    records: list[dict[str, Any]] = []
    sections = []
    for table in tables:
        rows = table["rows"]
        if not rows or "NAMA SYARIKAT" not in rows[0] or "NO. LESEN" not in rows[0]:
            raise SourceError(f"{source}: unrecognised register headers")
        headers = [h.strip() for h in rows[0]]
        label = parser.labels.get(table["panel"], "").strip()
        if not label:
            raise SourceError(f"{source}: missing published section label")
        section: dict[str, Any] = {"source": source, "source_section": label, "table_id": table["id"], "table_rows": len(rows), "data_rows": len(rows) - 1, "skipped_rows": 1, "skipped_reasons": {"header": 1}, "malformed_rows": 0}
        for number, cells in enumerate(rows[1:], start=2):
            raw = dict(zip(headers, cells))
            values = {key: next((raw[h].strip() for h in choices if h in raw), None) for key, choices in FIELDS.items()}
            issues = [] if len(cells) == len(headers) else ["column_count_mismatch"]
            for key in values:
                if values[key] in {"", "-"}:
                    values[key] = None
            for key in ("licence_start", "licence_expiry"):
                try:
                    values[key] = normalise_date(values[key])
                except ValueError:
                    values[key] = None
                    issues.append(f"invalid_{key}")
            if values["ajl_no"]:
                values["ajl_no"] = re.sub(r"\s+", "", values["ajl_no"])
                # Older cancellation tables publish the number without "AJL".
                # Keep that representation rather than inventing a prefix.
                if not re.fullmatch(r"(?:AJL)?\d+", values["ajl_no"]):
                    issues.append("invalid_ajl_no")
            else:
                issues.append("missing_ajl_no")
            if not values["company_name"]:
                issues.append("missing_company_name")
            status_raw = raw.get("STATUS")
            status = STATUS.get(status_raw.strip()) if status_raw is not None else ("cancelled" if source == "cancelled" else None)
            if status is None:
                issues.append("unknown_status")
            records.append({**values, "status": status, "status_raw": status_raw, "status_context_raw": "Senarai Lesen Yang Dibatalkan" if source == "cancelled" else label, "source_section": label, "source_url": SOURCES[source], "fetched_at": fetched_at, "source_row": number, "raw": raw, "raw_cells": cells, "issues": issues})
            section["malformed_rows"] += bool(issues)
        sections.append(section)
    return {"source": source, "source_url": SOURCES[source], "fetched_at": fetched_at, "http_status": 200, "bytes": len(body), "sha256": hashlib.sha256(body).hexdigest(), "sections": sections, "records": records}


def combine(pages: list[dict[str, Any]]) -> dict[str, Any]:
    """Build a pinned observation; count overlaps without resolving identity."""
    if [page["source"] for page in pages] != list(SOURCES):
        raise SourceError("both source pages are required in the declared order")
    records = [r for page in pages for r in page["records"]]
    counts = Counter(r["status"] for r in records)
    ajls = Counter(r["ajl_no"] for r in records if r["ajl_no"])
    return {
        "schema": "datapulse/kpdn-ajl-observation/v1",
        "dataset_id": DATASET_ID,
        "pages": [{k: v for k, v in page.items() if k not in {"records", "sections"}} for page in pages],
        "sections": [s for page in pages for s in page["sections"]],
        "counts": {s: counts[s] for s in ("active", "expired", "cancelled")},
        "unknown_status_rows": counts[None],
        "duplicate_ajl_numbers": {k: v for k, v in sorted(ajls.items()) if v > 1},
        "records": records,
    }


def validate_observation(observation: dict[str, Any]) -> None:
    """Reject incomplete or inconsistent pinned evidence before any write."""
    try:
        if observation["schema"] != "datapulse/kpdn-ajl-observation/v1" or observation["dataset_id"] != DATASET_ID:
            raise ValueError("unexpected identity")
        pages = [dict(page) for page in observation["pages"]]
        if [page["source"] for page in pages] != list(SOURCES):
            raise ValueError("both approved source pages are required")
        for page in pages:
            if page["source_url"] != SOURCES[page["source"]] or page["http_status"] != 200:
                raise ValueError("source URL or HTTP status mismatch")
            if page["bytes"] <= 0 or not re.fullmatch(r"[a-f0-9]{64}", page["sha256"]):
                raise ValueError("invalid source size or digest")
            if datetime.fromisoformat(page["fetched_at"].replace("Z", "+00:00")).utcoffset() is None:
                raise ValueError("observation time must have a timezone")
            page["records"] = [r for r in observation["records"] if r["source_url"] == page["source_url"]]
            page["sections"] = [s for s in observation["sections"] if s["source"] == page["source"]]
        rebuilt = combine(pages)
        for key in ("records", "sections", "counts", "unknown_status_rows", "duplicate_ajl_numbers"):
            if rebuilt[key] != observation[key]:
                raise ValueError(f"inconsistent {key}")
        for page in pages:
            for row in page["records"]:
                if row["fetched_at"] != page["fetched_at"] or not all(key in row for key in FIELDS):
                    raise ValueError("row provenance or required field mismatch")
            for section in page["sections"]:
                rows = [r for r in page["records"] if r["source_section"] == section["source_section"]]
                if len(rows) != section["data_rows"] or section["table_rows"] != len(rows) + section["skipped_rows"]:
                    raise ValueError("inconsistent section counts")
    except (KeyError, TypeError, ValueError) as error:
        raise SourceError(f"invalid pinned observation: {error}") from error


def fetch_page(source: str) -> dict[str, Any]:
    """Use only the two operator-approved HTTPS GET URLs; never retry a block."""
    url = SOURCES[source]
    with requests.get(url, timeout=60, allow_redirects=False, stream=True) as response:
        # KPDN's measured redirect only adds /ms/. Do not follow arbitrary links.
        if response.status_code in {301, 302, 303, 307, 308}:
            location = response.headers.get("Location", "")
            expected = url.replace("www.kpdn.gov.my/", "www.kpdn.gov.my/ms/", 1)
            if location not in {expected, expected.removeprefix("https://www.kpdn.gov.my")}:
                raise SourceError(f"{source}: unexpected redirect; stopped")
            url = expected
        else:
            return read_response(source, response, url)
    with requests.get(url, timeout=60, allow_redirects=False, stream=True) as response:
        return read_response(source, response, url)


def read_response(source: str, response: requests.Response, url: str) -> dict[str, Any]:
    """Bound the response before parsing; an error leaves prior artifacts intact."""
    if response.status_code != 200 or "text/html" not in response.headers.get("Content-Type", ""):
        raise SourceError(f"{source}: HTTP {response.status_code} or unexpected content type; stopped")
    body = bytearray()
    for chunk in response.iter_content(65536):
        body.extend(chunk)
        if len(body) > 5_000_000:
            raise SourceError(f"{source}: response exceeds 5 MB; stopped")
    result = parse_page(source, bytes(body), datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"))
    result["resolved_url"] = url
    return result


def write_atomic(path: Path, content: str) -> None:
    """Preserve existing files when bytes match, including their modification time."""
    if path.exists() and path.read_text(encoding="utf-8") == content:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(content, encoding="utf-8")
    temporary.chmod(0o644)
    temporary.replace(path)


def json_text(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2) + "\n"


def render_report(config: dict[str, Any], observation: dict[str, Any]) -> str:
    """Render only the pinned observation; later probes retain their own times."""
    dataset = config["dataset"]
    records = observation["records"]
    section_rows = [
        f"| {s['source']} | {s['source_section']} | {s['data_rows']} | "
        f"{s['skipped_rows']} (header) | {s['malformed_rows']} |"
        for s in observation["sections"]
    ]
    source_rows = [
        f"- [{p['source']}]({p['source_url']}): GET HTTP {p['http_status']}, "
        f"{p['bytes']} bytes; fetched {p['fetched_at']}; SHA-256 `{p['sha256']}`."
        for p in observation["pages"]
    ]
    issues = Counter(issue for row in records for issue in row["issues"])
    nulls = {key: sum(row[key] is None for row in records) for key in FIELDS}
    numeric_only = sum(bool(re.fullmatch(r"\d+", row["ajl_no"] or "")) for row in records)
    template = Template((ROOT / "scripts/templates/kpdn-direct-selling.md.tmpl").read_text())
    return template.substitute(
        last_checked=observation["pages"][0]["fetched_at"],
        name=dataset["name"],
        licence=dataset["licence"],
        attribution=dataset["attribution"],
        section_rows="\n".join(section_rows),
        source_rows="\n".join(source_rows),
        status_counts=", ".join(f"{key}={value}" for key, value in observation["counts"].items()),
        unknown_count=observation["unknown_status_rows"],
        duplicate_count=len(observation["duplicate_ajl_numbers"]),
        numeric_only_count=numeric_only,
        issue_counts=json.dumps(dict(sorted(issues.items()))),
        null_counts=json.dumps(nulls),
        refresh_rationale=config["refresh_rationale"],
        licence_evidence=config["licence_evidence"],
    )


def register(root: Path, config: dict[str, Any], observation: dict[str, Any]) -> list[Path]:
    """Upsert this dataset through the existing manifest/policy/report contract."""
    validate_observation(observation)
    dataset = dict(config["dataset"])
    if dataset["id"] != DATASET_ID or dataset["url"] != SOURCES["active_expired"]:
        raise SourceError("unexpected registration identity or URL")
    primary = observation["pages"][0]
    dataset["verified_at"] = primary["fetched_at"][:10]
    manifest = json.loads((root / "datapulse.json").read_text())
    rows = manifest["datasets"]
    indexes = [i for i, row in enumerate(rows) if row["id"] == DATASET_ID]
    if len(indexes) > 1:
        raise SourceError("duplicate existing manifest registration")
    if indexes:
        rows[indexes[0]] = dataset
    else:
        rows.append(dataset)
    Draft202012Validator(json.loads((root / "datapulse.schema.json").read_text()), format_checker=FormatChecker()).validate(manifest)
    policy = json.loads((root / "scripts/probe-policy.json").read_text())
    if policy["datasets"].get(DATASET_ID) != {"adapter": "direct", "url": dataset["url"], "freshness": {"extraction-mode": "structural-hash", "fallback": "unknown-freshness"}}:
        raise SourceError("KPDN direct probe must first be declared in scripts/probe-policy.json")
    Draft202012Validator(json.loads((root / "scripts/probe-policy.schema.json").read_text()), format_checker=FormatChecker()).validate(policy)
    health_document = json.loads((root / "health/latest.json").read_text())
    health = {
        "dataset_id": DATASET_ID,
        "last_checked": primary["fetched_at"],
        "url": dataset["url"],
        "request_url": primary.get("resolved_url", dataset["url"]),
        "status": "unknown-freshness",
        "namespace": dataset["namespace"],
        "http_status": 200,
        "access_method": "direct GET",
        "content_length": primary["bytes"],
        # The register publishes no Last-Modified header; the key is emitted as
        # null because the per-dataset receipt generator reads it unconditionally.
        "last_modified": None,
        "content_freshness_date": None,
        "first_record_timestamp": None,
        "record_count": sum(s["data_rows"] for s in observation["sections"] if s["source"] == "active_expired"),
        "record_count_estimated": False,
        # No prior cycle exists for this dataset, so tolerance and freshness
        # signal are unknown rather than assumed true.
        "record_count_within_tolerance": None,
        "freshness_signal": None,
        "freshness_signal_source": None,
        "message": "HTTP 200; primary register rows observed; publication date unknown. Historical cancellation rows are recorded separately in the observation report.",
    }
    # A replay must not roll back a later pipeline probe for this dataset.
    existing = next((r for r in health_document["datasets"] if r["dataset_id"] == DATASET_ID), None)
    if existing and existing.get("last_checked") and datetime.fromisoformat(existing["last_checked"].replace("Z", "+00:00")) > datetime.fromisoformat(health["last_checked"].replace("Z", "+00:00")):
        health = existing
    health_document["datasets"] = [health if r["dataset_id"] == DATASET_ID else r for r in health_document["datasets"]]
    if existing is None:
        health_document["datasets"].append(health)
    health_document["_trust_summary"]["datasets_total"] = len(health_document["datasets"])
    status_counts = Counter(row["status"].replace("-", "_") for row in health_document["datasets"])
    health_document["_trust_summary"]["by_status"] = {key: status_counts[key] for key in health_document["_trust_summary"]["by_status"]}
    Draft202012Validator(json.loads((root / "health.schema.json").read_text()), format_checker=FormatChecker()).validate(health_document)
    scope = json.loads((root / "scripts/contract-scope.json").read_text())
    if DATASET_ID not in scope["json_envelope"]["approved_ids"]:
        raise SourceError("KPDN envelope must first be declared in scripts/contract-scope.json")
    report = render_report(config, observation)
    envelope = {
        "schema": SCHEMA,
        "id": DATASET_ID,
        "status": health["status"],
        "last_checked": health["last_checked"],
        "freshness_days": None,
        "next_expected_update": None,
        "refresh_frequency": dataset["refresh_frequency"],
        "record_count": health.get("record_count"),
        "date_range": None,
        "fields": [],
        "checks": standard_checks(dataset, health),
        "known_quirks": ["HTML columns vary by section; parsed row fields and raw source cells are in data/observations/kpdn_direct_selling_licences.json"],
        "breaking_changes": [],
        "licence": dataset["licence"],
        "attribution": dataset["attribution"],
        "reproducibility": {
            "url": health["url"],
            "access_method": health["access_method"],
        },
    }
    public = load_public_surfaces(root)
    base_url = public["origins"]["website"]
    outputs = {
        "datapulse.json": json_text(manifest),
        "health/latest.json": json_text(health_document),
        f"data/{DATASET_ID}.md": report,
        f"data/observations/{DATASET_ID}.json": json_text(observation),
        f"data/json/{DATASET_ID}.json": json_text(envelope),
        f"data/jsonld/{DATASET_ID}.json": json_text(dataset_object(dataset, health, base_url=base_url)),
    }
    outputs[f"docs/datasets/{DATASET_ID}.html"] = render_page(dataset, health, base_url, public["dataset_pages"]["path_template"])
    outputs["sitemap.xml"] = render_sitemap(public, sorted(row["id"] for row in rows))
    # Reuse the existing badge generator in an isolated directory so its global
    # status legend is not rewritten as part of a single-dataset registration.
    with tempfile.TemporaryDirectory(dir=root, prefix=".kpdn-badge-") as temporary:
        stage = Path(temporary)
        (stage / "scripts").symlink_to(ROOT / "scripts", target_is_directory=True)
        (stage / "health.json").write_text(json_text({"datasets": [health], "_trust_summary": {"by_status": {}}}))
        subprocess.run(["bash", str(ROOT / "scripts/gen_badges.sh"), str(stage / "health.json")], cwd=stage, check=True, capture_output=True, text=True)
        outputs[f"badges/{DATASET_ID}.svg"] = (stage / f"badges/{DATASET_ID}.svg").read_text()
    for relative, content in outputs.items():
        write_atomic(root / relative, content)
    return [root / relative for relative in outputs]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--in", dest="input", type=Path, help="Pinned observation JSON; default is the committed observation")
    parser.add_argument("--fetch", action="store_true", help="Observe both approved pages with GET; stop on access failure")
    parser.add_argument("--quick-test", action="store_true", help="Replay pinned input without network requests")
    args = parser.parse_args()
    if args.fetch and (args.quick_test or args.input):
        parser.error("--fetch cannot be combined with --quick-test or --in")
    try:
        config = json.loads((args.root / "config/kpdn-direct-selling.json").read_text())
        observation = combine([fetch_page(source) for source in SOURCES]) if args.fetch else json.loads((args.input or args.root / f"data/observations/{DATASET_ID}.json").read_text())
        paths = register(args.root, config, observation)
    except (OSError, ValueError, ValidationError, requests.RequestException, subprocess.CalledProcessError) as error:
        LOGGER.error("KPDN registration stopped: %s", error)
        if isinstance(error, subprocess.CalledProcessError):
            LOGGER.error("%s%s", error.stdout, error.stderr)
        return 1
    LOGGER.info("Registered %s: %s; %d artifact paths", DATASET_ID, observation["counts"], len(paths))
    return 0


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    raise SystemExit(main())
