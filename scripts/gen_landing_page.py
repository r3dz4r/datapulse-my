#!/usr/bin/env python3
"""Generate the canonical DataPulse source-verification landing page."""

from __future__ import annotations

import argparse
import html
import json
import re
import sys
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

SCRIPT_ROOT = Path(__file__).resolve().parents[1]
if str(SCRIPT_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPT_ROOT))

from scripts.public_surface_generation import GenerationError, atomic_write_text, load_json, load_public_surfaces

ROOT = Path(__file__).resolve().parents[1]
MARKER = "<!-- generated: scripts/gen_landing_page.py;"
FORBIDDEN_CLAIMS = ("universal trust score", "regulatory certification", "agent reputation", "webmcp")
MCP_TOOL_NAME = re.compile(r"\b(?:search_datasets|get_dataset|list_datasets|check_[a-z_]+)\b", re.IGNORECASE)
TOKEN = re.compile(r"{{([a-z_]+)}}")

# Decision chip derived from the observed health status. The 10-status taxonomy is
# stable; this map never renames a status, it only folds each status into the
# "use / warn / stop / reference-use" decision the landing page advertises.
VERDICT_BY_STATUS: dict[str, str] = {
    "fresh": "use",
    "aging": "warn",
    "stale": "stop",
    "degraded": "stop",
    "browser_dependent": "stop",
    "unreachable": "stop",
    "reference": "reference-use",
    "discontinued": "stop",
    "unknown": "stop",
    "unknown_freshness": "stop",
}

# Colour swatch class for each verdict (all classes are defined by the canonical
# stylesheet's .legend-swatch.{fresh,aging,stale,reference} rules).
SWATCH_BY_VERDICT: dict[str, str] = {
    "use": "fresh",
    "warn": "aging",
    "stop": "stale",
    "reference-use": "reference",
}

# Status ordering for the bounded landing register: most-actionable first, the
# long-tail reference/unknown statuses last. This never renames a status; it only
# orders the bounded preview so the landing page leads with what matters.
REGISTER_STATUS_ORDER: tuple[str, ...] = (
    "fresh",
    "aging",
    "stale",
    "degraded",
    "browser_dependent",
    "unreachable",
    "discontinued",
    "unknown",
    "unknown_freshness",
    "reference",
)

REGISTER_BOUND = 12


def _text(value: object, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise GenerationError(f"{label} must be a non-empty string")
    return value


def _local_href(value: object, surfaces: dict[str, Any], label: str, dataset_id: str | None = None) -> str:
    href = _text(value, label)
    if href == "/data/example.md":
        href = _evidence_report_href(dataset_id or "")
    if href.startswith("mcp:"):
        if href != "mcp:/mcp":
            raise GenerationError(f"{label} has an unsupported MCP endpoint")
        return surfaces["origins"]["mcp"] + "/mcp"
    parsed = urlsplit(href)
    if parsed.scheme or parsed.netloc or not href.startswith("/") or parsed.query or parsed.fragment:
        raise GenerationError(f"{label} must be a canonical local path or mcp:/mcp")
    allowed = set(surfaces["pages"]) | set(surfaces["artifacts"])
    if dataset_id is not None:
        allowed.add(_evidence_report_href(dataset_id))
    if href not in allowed:
        raise GenerationError(f"{label} is not a declared canonical public surface: {href}")
    return href


def _evidence_report_href(dataset_id: str) -> str:
    href = f"/data/{dataset_id}.md"
    parsed = urlsplit(href)
    if parsed.scheme or parsed.netloc or ".." in dataset_id or not href.startswith("/"):
        raise GenerationError(f"example.dataset_id is not a valid report path component: {dataset_id!r}")
    return href


def _list(document: dict[str, Any], key: str, *, minimum: int = 1) -> list[Any]:
    value = document.get(key)
    if not isinstance(value, list) or len(value) < minimum:
        raise GenerationError(f"config/landing-page.json:{key} must be an array with at least {minimum} item(s)")
    return value


def _render_list(items: list[str], tag: str) -> str:
    return "\n".join(f"        <{tag}>{html.escape(item)}</{tag}>" for item in items)


def load_landing_config(root: Path, surfaces: dict[str, Any]) -> dict[str, Any]:
    path = root / "config/landing-page.json"
    document = load_json(path)
    required = {"schema", "title", "description", "hero", "example", "rails", "machine_surfaces", "boundaries", "vertical", "final_ctas"}
    if set(document) != required or document.get("schema") != "datapulse/v1/landing-page":
        raise GenerationError(f"{path}: unsupported or incomplete landing configuration")
    serialised = json.dumps(document, ensure_ascii=False).lower()
    if any(claim in serialised for claim in FORBIDDEN_CLAIMS) or MCP_TOOL_NAME.search(serialised):
        raise GenerationError(f"{path}: contains an unsupported claim or manual MCP tool enumeration")
    hero = document["hero"]
    example = document["example"]
    vertical = document["vertical"]
    if not all(isinstance(value, dict) for value in (hero, example, vertical)):
        raise GenerationError(f"{path}: hero, example, and vertical must be objects")
    receipt_preview = example.get("receipt_preview")
    if not isinstance(receipt_preview, dict) or set(receipt_preview) != {"mode", "label", "copy"}:
        raise GenerationError(f"{path}: example.receipt_preview must contain only mode, label, and copy")
    if receipt_preview.get("mode") != "live_evidence":
        raise GenerationError(f"{path}: example.receipt_preview.mode must be live_evidence")
    receipt_label = _text(receipt_preview["label"], "example.receipt_preview.label")
    receipt_copy = _text(receipt_preview["copy"], "example.receipt_preview.copy")
    workflow = [_text(value, "example.workflow item") for value in _list(example, "workflow", minimum=5)]
    fields = [_text(value, "example.receipt_fields item") for value in _list(example, "receipt_fields", minimum=10)]
    dataset_id = _text(example.get("dataset_id"), "example.dataset_id")
    rails: list[dict[str, Any]] = []
    for item in _list(document, "rails", minimum=5):
        if not isinstance(item, dict) or set(item) - {"name", "copy", "future"} or not {"name", "copy"} <= set(item):
            raise GenerationError(f"{path}: rails must contain name, copy, and optional future only")
        rails.append(item)
    if [item["name"] for item in rails] != ["Readable", "Discoverable", "Callable", "Verifiable", "Payable"] or rails[-1].get("future") is not True:
        raise GenerationError(f"{path}: rails must be ordered and label Payable as future")
    surfaces_config = []
    for item in _list(document, "machine_surfaces"):
        if not isinstance(item, dict) or set(item) != {"label", "href"}:
            raise GenerationError(f"{path}: machine surfaces must contain only label and href")
        surfaces_config.append(( _text(item["label"], "machine surface label"), _local_href(item["href"], surfaces, "machine surface href")))
    ctas = []
    for item in _list(document, "final_ctas", minimum=2):
        if not isinstance(item, dict) or set(item) != {"label", "href"}:
            raise GenerationError(f"{path}: final_ctas must contain only label and href")
        ctas.append((_text(item["label"], "final CTA label"), _local_href(item["href"], surfaces, "final CTA href", dataset_id)))
    for required_boundary in ("read-only", "source of record", "substantive truth", "Unknown"):
        if not any(required_boundary.lower() in _text(item, "boundary").lower() for item in _list(document, "boundaries", minimum=4)):
            raise GenerationError(f"{path}: missing required claim boundary: {required_boundary}")
    primary = hero.get("primary_cta")
    secondary = hero.get("secondary_cta")
    if not isinstance(primary, dict) or not isinstance(secondary, dict):
        raise GenerationError(f"{path}: hero CTAs must be objects")
    return {
        "title": _text(document["title"], "title"),
        "description": _text(document["description"], "description"),
        "hero_heading": _text(hero.get("heading"), "hero.heading"),
        "hero_copy": _text(hero.get("copy"), "hero.copy"),
        "hero_primary_label": _text(primary.get("label"), "hero primary label"),
        "hero_primary_href": _local_href(primary.get("href"), surfaces, "hero primary href", dataset_id),
        "hero_secondary_label": _text(secondary.get("label"), "hero secondary label"),
        "hero_secondary_href": _local_href(secondary.get("href"), surfaces, "hero secondary href"),
        "dataset_id": dataset_id,
        "evidence_href": _evidence_report_href(dataset_id),
        "workflow": workflow,
        "receipt_fields": fields,
        "receipt_preview_label": receipt_label,
        "receipt_preview_copy": receipt_copy,
        "rails": rails,
        "machine_surfaces": surfaces_config,
        "boundaries": [_text(item, "boundary") for item in _list(document, "boundaries", minimum=4)],
        "vertical_label": _text(vertical.get("label"), "vertical.label"),
        "vertical_href": _local_href(vertical.get("href"), surfaces, "vertical href"),
        "vertical_copy": _text(vertical.get("copy"), "vertical.copy"),
        "final_ctas": ctas,
        "mcp_endpoint": surfaces["origins"]["mcp"] + "/mcp",
        "health_href": "/health/latest.json",
    }


def _obs(value: object) -> str:
    """Return a signal as text, or an explicit 'not observed' marker for gaps."""
    if value is None or (isinstance(value, str) and not value.strip()):
        return "not observed"
    return str(value)


def _find_health_row(health: dict[str, Any], dataset_id: str) -> dict[str, Any]:
    datasets = health.get("datasets")
    if not isinstance(datasets, list):
        raise GenerationError("health/latest.json: datasets must be an array")
    for row in datasets:
        if isinstance(row, dict) and row.get("dataset_id") == dataset_id:
            return row
    raise GenerationError(f"health/latest.json has no dataset_id {dataset_id!r}; refusing to render a placeholder receipt")


def _find_manifest_entry(manifest: dict[str, Any], dataset_id: str) -> dict[str, Any]:
    datasets = manifest.get("datasets")
    if not isinstance(datasets, list):
        raise GenerationError("datapulse.json: datasets must be an array")
    for entry in datasets:
        if isinstance(entry, dict) and entry.get("id") == dataset_id:
            return entry
    raise GenerationError(f"datapulse.json has no dataset id {dataset_id!r}; refusing to render a placeholder receipt")


def build_evidence_receipt(
    dataset_id: str,
    field_labels: list[str],
    health: dict[str, Any],
    manifest: dict[str, Any],
) -> dict[str, str]:
    """Render the live evidence receipt fields and decision chip from real observations."""
    health_row = _find_health_row(health, dataset_id)
    manifest_entry = _find_manifest_entry(manifest, dataset_id)

    status = health_row.get("status")
    if not isinstance(status, str) or status not in VERDICT_BY_STATUS:
        raise GenerationError(f"health/latest.json:{dataset_id}: unsupported status {status!r}")
    verdict = VERDICT_BY_STATUS[status]
    swatch = SWATCH_BY_VERDICT[verdict]

    namespace = health_row.get("namespace") or manifest_entry.get("namespace")
    source = manifest_entry.get("source")
    licence = manifest_entry.get("licence")
    last_checked = health_row.get("last_checked")
    content_date = health_row.get("content_freshness_date") or manifest_entry.get("content_freshness_date")
    record_count = health_row.get("record_count")
    within_tolerance = health_row.get("record_count_within_tolerance")

    if record_count is None:
        record_signal = "not observed"
    elif within_tolerance is True:
        record_signal = f"{record_count} records; within tolerance"
    elif within_tolerance is False:
        record_signal = f"{record_count} records; outside tolerance"
    else:
        record_signal = f"{record_count} records; tolerance unknown"

    report_path = f"/data/{dataset_id}.md"
    evidence_ref = (
        f'<a href="{html.escape(report_path, quote=True)}">{html.escape(report_path)}</a>'
        f' · <a href="/health/latest.json">/health/latest.json</a>'
    )

    field_values: dict[str, str] = {
        "Source identity": html.escape(f"{dataset_id} · {_obs(namespace)}"),
        "Publisher": html.escape(_obs(source)),
        "Licence and reuse context": html.escape(_obs(licence)),
        "Observed time": html.escape(_obs(last_checked)),
        "Content date": html.escape(_obs(content_date)),
        "Freshness state": html.escape(status.capitalize()),
        "Schema or record signal": html.escape(record_signal),
        "Evidence reference": evidence_ref,
        "Claim scope": "Read-only observation; official publisher remains source of record; observed health is not objective truth.",
        "Limitations": "No universal truth verdict; gaps stay visible; freshness signal is content-date-parse.",
    }
    unknown = set(field_labels) - set(field_values)
    if unknown:
        raise GenerationError(f"config/landing-page.json: unsupported receipt field label(s): {', '.join(sorted(unknown))}")

    fields_html = "\n".join(
        f"        <div><dt>{html.escape(label)}</dt><dd>{field_values[label]}</dd></div>"
        for label in field_labels
    )
    verdict_html = (
        f'<span class="legend-item"><span class="legend-swatch {html.escape(swatch)}"></span>'
        f' Evidence verdict: {html.escape(verdict)}</span>'
    )
    return {"fields_html": fields_html, "verdict_html": verdict_html}


def _dash(value: object) -> str:
    """Render a value for display, using an em dash for null/empty gaps."""
    if value is None or (isinstance(value, str) and not value.strip()):
        return "—"
    return str(value)


def _status_slug(status: object) -> str:
    """Canonicalise a status token to its underscore taxonomy form.

    The taxonomy spells multi-word statuses as ``browser_dependent``, while the
    live health rows use the hyphenated spelling ``browser-dependent``. Folding
    hyphens into underscores keeps counting and ordering stable across both.
    """
    if isinstance(status, str) and status.strip():
        return status.replace("-", "_")
    return "unknown"


def _status_label(status: object) -> str:
    """Return a status token for display, hyphenating multi-word statuses."""
    if isinstance(status, str) and status.strip():
        return status.replace("_", "-")
    return "—"


def build_live_register(health: dict[str, Any], manifest: dict[str, Any]) -> dict[str, str]:
    """Render a bounded live register and its status distribution from real observations."""
    datasets = health.get("datasets")
    if not isinstance(datasets, list):
        raise GenerationError("health/latest.json: datasets must be an array")
    manifest_datasets = manifest.get("datasets")
    if not isinstance(manifest_datasets, list):
        raise GenerationError("datapulse.json: datasets must be an array")
    by_id = {entry["id"]: entry for entry in manifest_datasets if isinstance(entry, dict) and entry.get("id")}

    counts: dict[str, int] = {}
    for row in datasets:
        if isinstance(row, dict) and isinstance(row.get("status"), str):
            slug = _status_slug(row.get("status"))
            counts[slug] = counts.get(slug, 0) + 1
    total = sum(counts.values())

    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in datasets:
        if isinstance(row, dict):
            grouped.setdefault(_status_slug(row.get("status")), []).append(row)
    for bucket in grouped.values():
        bucket.sort(key=lambda row: str(row.get("dataset_id", "")))

    ordered_statuses = [status for status in REGISTER_STATUS_ORDER if status in grouped]
    ordered_statuses += [status for status in sorted(grouped) if status not in REGISTER_STATUS_ORDER]

    bounded: list[dict[str, Any]] = []
    index: dict[str, int] = {status: 0 for status in ordered_statuses}
    while len(bounded) < REGISTER_BOUND:
        progressed = False
        for status in ordered_statuses:
            if index[status] < len(grouped[status]):
                bounded.append(grouped[status][index[status]])
                index[status] += 1
                progressed = True
                if len(bounded) >= REGISTER_BOUND:
                    break
        if not progressed:
            break

    row_lines: list[str] = []
    for row in bounded:
        dataset_id = row.get("dataset_id")
        entry = by_id.get(dataset_id) if isinstance(dataset_id, str) else {}
        name = html.escape(_dash(entry.get("name")))
        id_text = html.escape(_dash(dataset_id))
        source = html.escape(_dash(entry.get("source")))
        swatch = _status_slug(row.get("status")).replace("_", "-")
        label = _status_label(row.get("status"))
        chip = (
            f'<span class="legend-item"><span class="legend-swatch {html.escape(swatch)}"></span>'
            f"{html.escape(label)}</span>"
        )
        last_checked = html.escape(_dash(row.get("last_checked")))
        record_count = row.get("record_count")
        records = "—" if record_count is None else html.escape(str(record_count))
        row_lines.append(
            f"<tr>"
            f"<td>{name}<br>{id_text}</td>"
            f"<td>{source}</td>"
            f"<td>{chip}</td>"
            f"<td>{last_checked}</td>"
            f"<td>{records}</td>"
            f"</tr>"
        )

    table = (
        '<div class="table-wrap"><table>'
        "<thead><tr><th>Dataset</th><th>Source</th><th>Status</th><th>Last checked</th><th>Records</th></tr></thead>"
        f"<tbody>{''.join(row_lines)}</tbody>"
        "</table></div>"
    )

    more_html = ""
    if total > len(bounded):
        more = total - len(bounded)
        more_html = f'<p class="data-strip">…and {more} more datasets — the full register is available at the register home.</p>'

    ordered = [status for status in REGISTER_STATUS_ORDER if counts.get(status, 0) > 0]
    ordered += sorted(set(counts) - set(REGISTER_STATUS_ORDER))
    parts = [f"{html.escape(status.replace('_', '-'))} {counts[status]}" for status in ordered]
    summary = f'<p class="data-strip">{" · ".join(parts)} — {total} datasets total</p>'

    return {"rows_html": table + more_html, "summary_html": summary}


def render(root: Path = ROOT) -> str:
    surfaces = load_public_surfaces(root)
    config = load_landing_config(root, surfaces)
    template = (root / "scripts/templates/landing.html.tmpl").read_text(encoding="utf-8")
    values: dict[str, str] = {key: html.escape(value, quote=True) for key, value in config.items() if isinstance(value, str)}
    values["canonical_href"] = "/"
    missing = set(TOKEN.findall(template)) - set(values)
    if missing or TOKEN.sub(lambda match: values[match.group(1)], template).find("{{") >= 0:
        raise GenerationError(f"landing template has unresolved token(s): {', '.join(sorted(missing))}")
    rendered = TOKEN.sub(lambda match: values[match.group(1)], template)
    if not rendered.startswith("<!doctype html>\n" + MARKER) or MCP_TOOL_NAME.search(rendered):
        raise GenerationError("rendered landing page violates generated ownership or MCP enumeration contract")
    return rendered


def compatibility_outputs(root: Path) -> dict[Path, str]:
    """Render each static Pages compatibility document exactly once.

    Cloudflare Pages normalises ``index.html`` to ``/``.  Redirect rules that
    point aliases at either spelling can therefore loop at the edge.  A static
    document lets the browser resolve the declared canonical target instead.
    """
    surfaces = load_public_surfaces(root)
    outputs: dict[Path, str] = {}
    for alias in surfaces["compatibility_aliases"]:
        path, target = alias["path"], alias["target"]
        if target != "/":
            raise GenerationError("compatibility aliases must target the root register")
        if path.endswith(".html"):
            output = root / "docs" / path.lstrip("/")
        else:
            output = root / "docs" / f"{path.lstrip('/')}.html"
        previous = outputs.get(output)
        page = render(root)
        if previous is not None and previous != page:
            raise GenerationError(f"compatibility aliases disagree for {output}")
        outputs[output] = page
    required = {root / "docs/landing.html", root / "docs/dashboard.html", root / "docs/register.html"}
    if set(outputs) != required:
        raise GenerationError("compatibility aliases must generate landing.html, dashboard.html, and register.html")
    return outputs


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Fail if docs/landing.html would change.")
    args = parser.parse_args()
    root = Path(__import__("os").environ.get("DATAPULSE_REPO_ROOT", ROOT)).resolve()
    try:
        outputs = compatibility_outputs(root)
        changed = any(not output.is_file() or output.read_text(encoding="utf-8") != content for output, content in outputs.items())
        if args.check:
            return 1 if changed else 0
        for output, content in outputs.items():
            if not output.is_file() or output.read_text(encoding="utf-8") != content:
                atomic_write_text(output, content)
    except (GenerationError, OSError, UnicodeError) as error:
        print(f"Unable to generate landing page: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
