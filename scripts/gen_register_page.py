#!/usr/bin/env python3
"""Render the deterministic, preview-only DataPulse dataset register."""

from __future__ import annotations

import argparse
import html
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

SCRIPT_ROOT = Path(__file__).resolve().parents[1]
if str(SCRIPT_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPT_ROOT))

from scripts.public_surface_generation import GenerationError, atomic_write_text, load_json, load_public_surfaces

ROOT = Path(__file__).resolve().parents[1]
TOKEN = re.compile(r"{{([a-z_]+)}}")
DATASET_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
STATUS_TO_POSTURE: dict[str, str] = {
    "fresh": "use", "aging": "warn", "stale": "stop", "discontinued": "stop",
    "degraded": "stop", "browser_dependent": "stop", "unreachable": "stop",
    "unknown": "stop", "unknown_freshness": "stop", "reference": "reference-use",
}
# Warn rows intentionally lead reference-use rows because they need review before a reference-only source.
POSTURE_ORDER = {"use": 0, "warn": 1, "reference-use": 2, "stop": 3}
FORBIDDEN_CLAIMS = ("objective truth", "guaranteed accuracy", "regulatory certification", "safe mcp server", "universal trust score")


def _display(value: object) -> str:
    return "not observed" if value is None or (isinstance(value, str) and not value.strip()) else str(value)


def _status_key(value: object) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return None
    return value.replace("-", "_")


def _recency_timestamp(health_row: dict[str, Any] | None) -> float | None:
    """Return the preferred observed recency signal, or None when it is unavailable."""
    value = (health_row or {}).get("content_freshness_date") or (health_row or {}).get("last_checked")
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.timestamp()


def _presentation_sort_key(entry: dict[str, Any], health_row: dict[str, Any] | None) -> tuple[int, bool, float, str]:
    """Sort decision posture first, then newest available signal, then dataset id."""
    status = _status_key(health_row.get("status")) if health_row else None
    posture = STATUS_TO_POSTURE.get(status, "stop")
    recency = _recency_timestamp(health_row)
    return (POSTURE_ORDER[posture], recency is None, -(recency or 0), entry["id"])


def _safe_url(value: object, label: str) -> str | None:
    if value is None or value == "":
        return None
    if not isinstance(value, str):
        raise GenerationError(f"{label} must be a URL string")
    parsed = urlsplit(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc or parsed.username or parsed.password:
        raise GenerationError(f"{label} must be an absolute HTTP(S) URL")
    return value


def _validate_dataset_id(value: object, label: str) -> str:
    """Validate an identifier before using it in a same-origin path."""
    if not isinstance(value, str) or not value or not DATASET_ID.fullmatch(value) or ".." in value:
        raise GenerationError(f"{label} must be a single safe dataset-id path segment")
    return value


def _validate_config(root: Path) -> dict[str, Any]:
    schema = load_json(root / "config/register-page.schema.json")
    config = load_json(root / "config/register-page.json")
    try:
        from jsonschema import Draft202012Validator
    except ImportError as error:
        raise GenerationError("jsonschema is required to validate register configuration") from error
    errors = sorted(Draft202012Validator(schema).iter_errors(config), key=lambda item: list(item.path))
    if errors:
        raise GenerationError(f"config/register-page.json: {errors[0].message}")
    expected = {"status", "publisher_category", "access_method", "recency"}
    if set(config["filters"]) != expected or set(config["compact_fields"]) != {"status", "publisher", "category", "access_method", "recency"} or set(config["evidence_fields"]) != {"observed_time", "content_date", "record_signal", "evidence_reference", "limitations"}:
        raise GenerationError("config/register-page.json must declare the complete supported register controls and fields")
    if config["actions"]["primary"]["kind"] != "official_source" or [item["kind"] for item in config["actions"]["secondary"]] != ["evidence", "machine_access"]:
        raise GenerationError("config/register-page.json must place official_source before evidence and machine_access actions")
    if set(config["decision_labels"]) != set(STATUS_TO_POSTURE.values()):
        raise GenerationError("config/register-page.json has unsupported decision labels")
    return config


def _load_manifest(root: Path) -> list[dict[str, Any]]:
    datasets = load_json(root / "datapulse.json").get("datasets")
    if not isinstance(datasets, list):
        raise GenerationError("datapulse.json: datasets must be an array")
    rows: list[dict[str, Any]] = []
    ids: set[str] = set()
    for entry in datasets:
        if not isinstance(entry, dict):
            raise GenerationError("datapulse.json: every dataset must have a non-empty id")
        dataset_id = _validate_dataset_id(entry.get("id"), "datapulse.json:id")
        if dataset_id in ids:
            raise GenerationError(f"datapulse.json: duplicate dataset id {dataset_id!r}")
        ids.add(dataset_id)
        _safe_url(entry.get("url"), f"datapulse.json:{dataset_id}:url")
        rows.append(entry)
    return rows


def _load_health(root: Path) -> dict[str, dict[str, Any]]:
    datasets = load_json(root / "health/latest.json").get("datasets")
    if not isinstance(datasets, list):
        raise GenerationError("health/latest.json: datasets must be an array")
    by_id: dict[str, dict[str, Any]] = {}
    for row in datasets:
        if not isinstance(row, dict):
            raise GenerationError("health/latest.json: every health record must have a non-empty dataset_id")
        dataset_id = _validate_dataset_id(row.get("dataset_id"), "health/latest.json:dataset_id")
        if dataset_id in by_id:
            raise GenerationError(f"health/latest.json: duplicate dataset_id {dataset_id!r}")
        status = _status_key(row.get("status"))
        if status not in STATUS_TO_POSTURE:
            raise GenerationError(f"health/latest.json:{dataset_id}: unsupported status {row.get('status')!r}")
        by_id[dataset_id] = row
    return by_id


def _row_html(entry: dict[str, Any], health_row: dict[str, Any] | None, config: dict[str, Any], mcp_endpoint: str) -> str:
    dataset_id = entry["id"]
    status = _status_key(health_row.get("status")) if health_row else None
    status_label = status.replace("_", "-") if status else "not observed"
    posture = STATUS_TO_POSTURE.get(status, "stop")
    publisher = _display(entry.get("source") or entry.get("steward"))
    category = _display(entry.get("namespace"))
    access_method = _display(health_row.get("access_method") if health_row else None)
    recency = _display((health_row or {}).get("content_freshness_date") or (health_row or {}).get("last_checked"))
    observed_time = _display((health_row or {}).get("last_checked"))
    record_count = (health_row or {}).get("record_count")
    record_signal = "not observed" if record_count is None else f"{record_count} records"
    evidence_href = f"{config['routes']['evidence_prefix']}{dataset_id}.md"
    official_url = _safe_url(entry.get("url"), f"datapulse.json:{dataset_id}:url")
    official_action = f'<a data-action="official-source" href="{html.escape(official_url, quote=True)}">{html.escape(config["actions"]["primary"]["label"])}</a>' if official_url else '<span data-action="official-source">Official source: not observed</span>'
    secondary = config["actions"]["secondary"]
    return f'''      <article class="register-row" data-dataset-id="{html.escape(dataset_id, quote=True)}" data-status="{html.escape(status or "not-observed", quote=True)}" data-posture="{html.escape(posture, quote=True)}" data-publisher="{html.escape(publisher, quote=True)}" data-category="{html.escape(category, quote=True)}" data-access-method="{html.escape(access_method, quote=True)}" data-recency="{html.escape(recency, quote=True)}">
        <header class="register-row-header"><h3>{html.escape(_display(entry.get("name")))}</h3><p class="register-id"><code>{html.escape(dataset_id)}</code></p><p class="register-decision"><span class="register-status">Status: {html.escape(status_label)}</span><span class="register-posture">Decision: {html.escape(posture)}</span></p></header>
        <dl class="compact-facts"><div><dt>Publisher</dt><dd>{html.escape(publisher)}</dd></div><div><dt>Category</dt><dd>{html.escape(category)}</dd></div><div><dt>Access method</dt><dd>{html.escape(access_method)}</dd></div><div><dt>Recency</dt><dd>{html.escape(recency)}</dd></div></dl>
        <footer class="register-row-footer"><p class="register-actions">{official_action} <a data-action="evidence" href="{html.escape(evidence_href, quote=True)}">{html.escape(secondary[0]["label"])}</a> <a data-action="machine-access" href="{html.escape(mcp_endpoint, quote=True)}">{html.escape(secondary[1]["label"])}</a></p>
        <details class="register-evidence"><summary>Observed evidence</summary><dl class="evidence-facts"><div><dt>Observed time</dt><dd>{html.escape(observed_time)}</dd></div><div><dt>Content date</dt><dd>{html.escape(_display((health_row or {}).get("content_freshness_date")))}</dd></div><div><dt>Record signal</dt><dd>{html.escape(record_signal)}</dd></div><div><dt>Evidence reference</dt><dd><a href="{html.escape(evidence_href, quote=True)}">{html.escape(evidence_href)}</a></dd></div><div><dt>Limitations</dt><dd>Observation is read-only; the official publisher remains the source of record.</dd></div></dl></details></footer>
      </article>'''


def render(root: Path) -> str:
    config = _validate_config(root)
    surfaces = load_public_surfaces(root)
    manifest = _load_manifest(root)
    health = _load_health(root)
    template = (root / "scripts/templates/register.html.tmpl").read_text(encoding="utf-8")
    stylesheet = (root / "scripts/templates/register.css").read_text(encoding="utf-8")
    filters = " ".join(f'<label><input type="checkbox" data-filter-dimension="{html.escape(item, quote=True)}"> {html.escape(item.replace("_", " "))}</label>' for item in config["filters"])
    legend = "".join(f"<li>Decision: {html.escape(label)}</li>" for label in config["decision_labels"])
    ordered_manifest = sorted(manifest, key=lambda entry: _presentation_sort_key(entry, health.get(entry["id"])))
    values = {"title": html.escape(config["title"], quote=True), "description": html.escape(config["description"], quote=True), "purpose": html.escape(config["purpose"]), "health_href": config["routes"]["health"], "stylesheet": stylesheet, "filter_controls": filters, "status_legend": legend, "record_count": str(len(manifest)), "rows": "\n".join(_row_html(entry, health.get(entry["id"]), config, surfaces["origins"]["mcp"] + "/mcp") for entry in ordered_manifest)}
    missing = set(TOKEN.findall(template)) - set(values)
    if missing:
        raise GenerationError(f"register template has unresolved token(s): {', '.join(sorted(missing))}")
    rendered = TOKEN.sub(lambda match: values[match.group(1)], template)
    if "{{" in rendered or any(claim in rendered.lower() for claim in FORBIDDEN_CLAIMS):
        raise GenerationError("rendered register violates template or claim-boundary contract")
    return rendered


def _preview_output_is_safe(root: Path, output: Path) -> bool:
    """Keep this foundation renderer from becoming an accidental production writer."""
    protected = (root / "docs", root / "data", root / "health")
    return not any(output == path or path in output.parents for path in protected)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT, help="Repository root (default: this repository).")
    parser.add_argument("--out", type=Path, help="Caller-controlled preview output path.")
    parser.add_argument("--check", action="store_true", help="Validate and fail if --out would change.")
    args = parser.parse_args()
    if args.check and args.out is None:
        parser.error("--check requires --out")
    try:
        content = render(args.root.resolve())
        if args.out is not None:
            output = args.out.resolve()
            if not _preview_output_is_safe(args.root.resolve(), output):
                raise GenerationError(f"preview output must not target a production surface: {output}")
            changed = not output.is_file() or output.read_text(encoding="utf-8") != content
            if args.check:
                return 1 if changed else 0
            if changed:
                atomic_write_text(output, content)
    except (GenerationError, OSError, UnicodeError) as error:
        print(f"Unable to generate register page: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
