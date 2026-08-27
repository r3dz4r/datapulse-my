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


def _text(value: object, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise GenerationError(f"{label} must be a non-empty string")
    return value


def _local_href(value: object, surfaces: dict[str, Any], label: str) -> str:
    href = _text(value, label)
    if href.startswith("mcp:"):
        if href != "mcp:/mcp":
            raise GenerationError(f"{label} has an unsupported MCP endpoint")
        return surfaces["origins"]["mcp"] + "/mcp"
    parsed = urlsplit(href)
    if parsed.scheme or parsed.netloc or not href.startswith("/") or parsed.query or parsed.fragment:
        raise GenerationError(f"{label} must be a canonical local path or mcp:/mcp")
    allowed = set(surfaces["pages"]) | set(surfaces["artifacts"]) | {"/data/fuelprice.md"}
    if href not in allowed:
        raise GenerationError(f"{label} is not a declared canonical public surface: {href}")
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
    if receipt_preview.get("mode") != "schema_preview":
        raise GenerationError(f"{path}: receipt values require a declared canonical artifact; only schema_preview is supported")
    receipt_label = _text(receipt_preview["label"], "example.receipt_preview.label")
    receipt_copy = _text(receipt_preview["copy"], "example.receipt_preview.copy")
    if "preview" not in receipt_label.lower() or "not verified evidence" not in receipt_label.lower():
        raise GenerationError(f"{path}: receipt schema preview label must state that it is not verified evidence")
    workflow = [_text(value, "example.workflow item") for value in _list(example, "workflow", minimum=5)]
    fields = [_text(value, "example.receipt_fields item") for value in _list(example, "receipt_fields", minimum=10)]
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
        ctas.append((_text(item["label"], "final CTA label"), _local_href(item["href"], surfaces, "final CTA href")))
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
        "hero_primary_href": _local_href(primary.get("href"), surfaces, "hero primary href"),
        "hero_secondary_label": _text(secondary.get("label"), "hero secondary label"),
        "hero_secondary_href": _local_href(secondary.get("href"), surfaces, "hero secondary href"),
        "example_href": _local_href(f"/data/{_text(example.get('dataset_id'), 'example.dataset_id')}.md", surfaces, "example dataset"),
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


def render(root: Path = ROOT) -> str:
    surfaces = load_public_surfaces(root)
    config = load_landing_config(root, surfaces)
    template = (root / "scripts/templates/landing.html.tmpl").read_text(encoding="utf-8")
    nav = (root / "docs/assets/site-nav.html").read_text(encoding="utf-8").rstrip()
    if "<nav class=\"site-nav\"" not in nav:
        raise GenerationError("docs/assets/site-nav.html is not the canonical site navigation")
    values: dict[str, str] = {key: html.escape(value, quote=True) for key, value in config.items() if isinstance(value, str)}
    values.update({"site_nav": nav, "workflow": _render_list(config["workflow"], "li"), "receipt_fields": "\n".join(f"        <div><dt>{html.escape(field)}</dt><dd>Preview schema field; see the published evidence surface for the dataset-specific value.</dd></div>" for field in config["receipt_fields"]), "rails": "\n".join(f"        <article><h3>{html.escape(_text(item['name'], 'rail name'))}{' <span>(Future)</span>' if item.get('future') else ''}</h3><p>{html.escape(_text(item['copy'], 'rail copy'))}</p></article>" for item in config["rails"]), "machine_surfaces": "\n".join(f"        <li><a href=\"{html.escape(href, quote=True)}\">{html.escape(label)}</a></li>" for label, href in config["machine_surfaces"]), "boundaries": _render_list(config["boundaries"], "li"), "final_ctas": "\n".join(f"          <a class=\"button {'button-primary' if index == 0 else 'button-secondary'}\" href=\"{html.escape(href, quote=True)}\">{html.escape(label)}</a>" for index, (label, href) in enumerate(config["final_ctas"]))})
    missing = set(TOKEN.findall(template)) - set(values)
    if missing or TOKEN.sub(lambda match: values[match.group(1)], template).find("{{") >= 0:
        raise GenerationError(f"landing template has unresolved token(s): {', '.join(sorted(missing))}")
    rendered = TOKEN.sub(lambda match: values[match.group(1)], template)
    if not rendered.startswith("<!doctype html>\n" + MARKER) or MCP_TOOL_NAME.search(rendered):
        raise GenerationError("rendered landing page violates generated ownership or MCP enumeration contract")
    return rendered


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Fail if docs/landing.html would change.")
    args = parser.parse_args()
    root = Path(__import__("os").environ.get("DATAPULSE_REPO_ROOT", ROOT)).resolve()
    try:
        content = render(root)
        output = root / "docs/landing.html"
        changed = not output.is_file() or output.read_text(encoding="utf-8") != content
        if args.check:
            return 1 if changed else 0
        if changed:
            atomic_write_text(output, content)
    except (GenerationError, OSError, UnicodeError) as error:
        print(f"Unable to generate landing page: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
