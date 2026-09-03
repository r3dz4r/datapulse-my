#!/usr/bin/env python3
"""Embed generated dashboard inputs into docs/index.html."""

from __future__ import annotations

import argparse
import json
import os
import re
import stat
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

try:
    from scripts import gen_register_page
    from scripts import gen_jsonld_catalog
except ImportError:  # Direct script execution puts scripts/ on sys.path.
    import gen_register_page
    import gen_jsonld_catalog

try:
    from scripts.verify_attestation_binding import ContractError, verify_contract
    from scripts.public_surface_generation import (
        GenerationError,
        load_public_surfaces,
        publish_text_outputs,
        replace_owned_block,
    )
except ModuleNotFoundError:  # Direct script execution puts scripts/ on sys.path.
    from verify_attestation_binding import ContractError, verify_contract
    from public_surface_generation import (
        GenerationError,
        load_public_surfaces,
        publish_text_outputs,
        replace_owned_block,
    )


class EmbedError(RuntimeError):
    """Raised when dashboard data cannot be embedded safely."""


CHANGELOG_BEGIN = "<!-- BEGIN changelog-strip -->"
CHANGELOG_END = "<!-- END changelog-strip -->"
DASHBOARD_SUMMARY_MARKER = "dashboard-summary"
DASHBOARD_TRUST_FACTS_MARKER = "dashboard-trust-facts"
DASHBOARD_BROWSER_FACTS_MARKER = "dashboard-browser-facts"
NPRA_FRESHNESS_MARKER = "npra-freshness"
NPRA_CONNECT_MARKER = "npra-connect"
NPRA_SURFACES_MARKER = "npra-surfaces"
NPRA_DATASET_IDS = {
    "pharmaceutical_products",
    "pharmaceutical_importers",
    "pharmaceutical_manufacturers",
    "pharmaceutical_wholesalers",
    "pharmaceutical_products_cancelled",
    "cosmetic_notifications",
    "cosmetic_notifications_cancelled",
    "cosmetics_manufacturers",
}
HOMEPAGE_TEMPLATE = Path("scripts/templates/register-home.html.tmpl")


def _format_myt(value: str) -> str:
    """Format an ISO timestamp for the NPRA page's visible Malaysian time."""
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise EmbedError("NPRA timestamp must include a UTC offset")
    local = parsed.astimezone(timezone.utc).astimezone(
        timezone(timedelta(hours=8))
    )
    return f"{local.strftime('%-d %b %Y, %-I:%M')} {local.strftime('%p').lower()} MYT"


def _npra_freshness(html: str, health: object) -> str:
    """Render probe freshness separately from upstream source modification time."""
    if not isinstance(health, dict) or not isinstance(health.get("checked_at"), str):
        raise EmbedError("health checked_at must be an ISO-8601 string")
    records = health.get("datasets")
    if not isinstance(records, list):
        raise EmbedError("health datasets must be an array")
    npra_records = [
        row for row in records
        if isinstance(row, dict) and row.get("dataset_id") in NPRA_DATASET_IDS
    ]
    fresh = sum(row.get("status") == "fresh" for row in npra_records)
    stale = sum(row.get("status") == "stale" for row in npra_records)
    source_updates = sorted(
        row["last_modified"] for row in npra_records
        if isinstance(row.get("last_modified"), str)
    )
    content = (
        f"{len(npra_records)} datasets · {fresh} fresh · {stale} stale · "
        f"last checked {_format_myt(health['checked_at'])}"
    )
    if source_updates:
        content += f" · Latest source update: {_format_myt(source_updates[-1])}"
    return replace_owned_block(
        html,
        NPRA_FRESHNESS_MARKER,
        f'<span data-npra-cfd="{health["checked_at"]}">{content}</span>',
    )


def _npra_runtime_script(html: str) -> str:
    """Keep the browser's live-health enhancement aligned with the static fallback."""
    return html.replace(
        "          return records;",
        "          return payload;",
        1,
    ).replace(
        "      const render = records => {\n"
        "        const counts = records.reduce",
        "      const render = payload => {\n"
        "        const records = payload.datasets.filter(row => plainObject(row) && ids.includes(row.dataset_id));\n"
        "        const counts = records.reduce",
        1,
    ).replace(
        "        const checkedDate = latest ? new Date(latest) : null;",
        "        const checkedDate = new Date(payload.checked_at);",
        1,
    ).replace(
        "        document.querySelector('[data-npra-cfd]').textContent = `${records.length} datasets · ${counts.fresh || 0} fresh · ${counts.stale || 0} stale · last checked ${checked} MYT`;",
        "        const sourceUpdate = latest ? ` · Latest source update: ${new Intl.DateTimeFormat('en-MY', { dateStyle: 'medium', timeStyle: 'short', timeZone: 'Asia/Kuala_Lumpur' }).format(new Date(latest))} MYT` : '';\n"
        "        document.querySelector('[data-npra-cfd]').textContent = `${records.length} datasets · ${counts.fresh || 0} fresh · ${counts.stale || 0} stale · last checked ${checked} MYT${sourceUpdate}`;",
        1,
    ).replace(
        "      health().then(records => { if (records) render(records); });",
        "      health().then(payload => { if (payload) render(payload); });",
        1,
    )
    return html


def _load(path: Path) -> object:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise EmbedError(f"cannot read {path}: {error}") from error


def _load_optional(path: Path | None) -> object:
    return _load(path) if path is not None and path.exists() else {}


def _dump(document: object) -> str:
    return json.dumps(document, ensure_ascii=False, separators=(",", ":")).replace(
        "</", "<\\/"
    )


def _atomic_write_text(path: Path, content: str) -> None:
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", dir=path.parent
    )
    try:
        os.fchmod(descriptor, stat.S_IMODE(path.stat().st_mode))
        with os.fdopen(
            descriptor, "w", encoding="utf-8", newline="\n"
        ) as temporary_file:
            temporary_file.write(content)
            temporary_file.flush()
            os.fsync(temporary_file.fileno())
        os.replace(temporary_name, path)
    except BaseException:
        try:
            os.unlink(temporary_name)
        except FileNotFoundError:
            pass
        raise


def update_changelog_strip(html: str, manifest: object, health: object) -> str:
    if not isinstance(manifest, dict) or not isinstance(manifest.get("datasets"), list):
        raise EmbedError("manifest must contain a datasets array")
    if not isinstance(health, dict) or not isinstance(health.get("checked_at"), str):
        raise EmbedError("health checked_at must be an ISO-8601 string")

    checked_at = health["checked_at"]
    try:
        observed_at = datetime.fromisoformat(checked_at.replace("Z", "+00:00"))
    except ValueError as error:
        raise EmbedError("health checked_at must be an ISO-8601 string") from error
    if observed_at.tzinfo is None:
        raise EmbedError("health checked_at must include a UTC offset")

    shipped_date = observed_at.astimezone(timezone.utc).date().isoformat()
    # The dataset total is stated once by _dashboard_facts (dashboard-trust-facts).
    # This strip only publishes the snapshot date so the aside never restates the total.
    replacement = (
        f"{CHANGELOG_BEGIN}\n"
        f'      <p>Live health snapshot: <a href="/health/latest.json"><time datetime="{shipped_date}">{shipped_date}</time></a>.</p>\n'
        f"    {CHANGELOG_END}"
    )
    pattern = re.compile(
        rf"{re.escape(CHANGELOG_BEGIN)}.*?{re.escape(CHANGELOG_END)}", re.DOTALL
    )
    updated, replacements = pattern.subn(replacement, html)
    if replacements != 1:
        raise EmbedError(
            "dashboard must contain exactly one complete changelog-strip marker block"
        )
    return updated


def _dashboard_facts(html: str, manifest: object, health: object, website: str) -> str:
    """Render only explicit dashboard facts; editorial prose remains untouched."""
    if not isinstance(manifest, dict) or not isinstance(manifest.get("datasets"), list):
        raise EmbedError("manifest must contain a datasets array")
    if not isinstance(health, dict) or not isinstance(health.get("checked_at"), str):
        raise EmbedError("health checked_at must be an ISO-8601 string")
    summary = health.get("_trust_summary")
    if not isinstance(summary, dict) or summary.get("datasets_total") != len(manifest["datasets"]):
        raise EmbedError("health _trust_summary.datasets_total must match the manifest")
    total = len(manifest["datasets"])
    records = health.get("datasets")
    if not isinstance(records, list):
        raise EmbedError("health datasets must be an array")
    by_status = summary.get("by_status")
    browser_dependent = by_status.get("browser_dependent", 0) if isinstance(by_status, dict) else None
    if (
        not isinstance(by_status, dict)
        or isinstance(browser_dependent, bool)
        or not isinstance(browser_dependent, int)
        or browser_dependent < 0
        or browser_dependent > total
    ):
        raise EmbedError(
            "health _trust_summary.by_status.browser_dependent must be a count between zero and the manifest total"
        )
    html = replace_owned_block(
        html,
        DASHBOARD_SUMMARY_MARKER,
        f'<meta name="description" content="Live register of {total} observed Malaysian public datasets from DataPulse.">',
    )
    html = replace_owned_block(
        html,
        DASHBOARD_TRUST_FACTS_MARKER,
        f'<p><a href="{website}/health/latest.json">{total} datasets observed</a>; use the official publisher for the source of record.</p>',
    )
    percentage = browser_dependent / total * 100 if total else 0
    return replace_owned_block(
        html,
        DASHBOARD_BROWSER_FACTS_MARKER,
        f"<p>{browser_dependent} of {total} datasets ({percentage:.1f}%) require a real browser for observation.</p>",
    )


def _jsonld_block(manifest: dict[str, object], origins: dict[str, str]) -> str:
    """Render homepage JSON-LD from the canonical generator, never prior HTML."""
    try:
        graph = gen_jsonld_catalog.homepage_graph(manifest, origins)
        encoded = gen_jsonld_catalog.script_safe_json(graph)
    except (KeyError, TypeError, ValueError) as error:
        raise EmbedError(f"cannot render canonical homepage JSON-LD: {error}") from error
    return f'  <script type="application/ld+json">\n{encoded}\n  </script>'


def _render_homepage(root: Path, previous_html: str) -> str:
    """Render the production shell through the reviewed register renderer's shared logic."""
    config = gen_register_page._validate_config(root)
    surfaces = gen_register_page.load_public_surfaces(root)
    manifest = gen_register_page._load_manifest(root)
    health = gen_register_page._load_health(root)
    template = (root / HOMEPAGE_TEMPLATE).read_text(encoding="utf-8")
    stylesheet = (root / "scripts/templates/register.css").read_text(encoding="utf-8")
    filter_attributes = {
        "status": "status", "publisher": "publisher", "category": "category", "access_method": "accessMethod", "recency": "recency",
    }
    filters = "\n        ".join(
        f'<label class="register-chip" data-register-chip><span class="register-chip-label">{gen_register_page.html.escape(item.replace("_", " ").title())}</span><select id="register-filter-{item}" data-register-filter="{filter_attributes[item]}" aria-label="Filter by {gen_register_page.html.escape(item.replace("_", " "))}"><option value="">All {gen_register_page.html.escape(item.replace("_", " "))}</option></select><span class="register-chip-caret" aria-hidden="true"></span></label>'
        for item in config["filters"]
    )
    legend = "".join(
        f'<li data-posture="{gen_register_page.html.escape(label, quote=True)}">'
        f"Decision: {gen_register_page.html.escape(label)}</li>"
        for label in config["decision_labels"]
    )
    ordered = sorted(
        manifest,
        key=lambda entry: gen_register_page._presentation_sort_key(entry, health.get(entry["id"])),
    )
    values = {
        "title": gen_register_page.html.escape(config["title"], quote=True),
        "description": gen_register_page.html.escape(config["description"], quote=True),
        "purpose": gen_register_page.html.escape(config["purpose"]),
        "health_href": config["routes"]["health"],
        "site_nav": (root / "docs/assets/site-nav.html").read_text(encoding="utf-8").rstrip(),
        "stylesheet": stylesheet,
        "filter_controls": filters,
        "status_legend": legend,
        "status_taxonomy": "".join(
            f'<li data-posture-status="{gen_register_page.html.escape(gen_register_page.STATUS_TO_POSTURE[status], quote=True)}">'
            f'<span class="register-status-dot" aria-hidden="true"></span>'
            f"Status: {gen_register_page.html.escape(status.replace('_', '-'))}</li>"
            for status in gen_register_page.STATUS_TO_POSTURE
        ),
        "record_count": str(len(manifest)),
        "rows": "\n".join(
            gen_register_page._row_html(entry, health.get(entry["id"]), config, surfaces["origins"]["mcp"] + "/mcp")
            for entry in ordered
        ),
        "jsonld": _jsonld_block({"datasets": manifest}, surfaces["origins"]),
    }
    missing = set(gen_register_page.TOKEN.findall(template)) - set(values)
    if missing:
        raise EmbedError(f"homepage template has unresolved token(s): {', '.join(sorted(missing))}")
    rendered = gen_register_page.TOKEN.sub(lambda match: values[match.group(1)], template)
    if "{{" in rendered or any(claim in rendered.lower() for claim in gen_register_page.FORBIDDEN_CLAIMS):
        raise EmbedError("rendered homepage violates the register claim-boundary contract")
    return rendered


def _npra_links(html: str, origins: dict[str, str]) -> str:
    """Render NPRA public links from the sole canonical origin contract."""
    html = replace_owned_block(
        html,
        NPRA_CONNECT_MARKER,
        """<div class="mcp-layout">
          <div class="code-wrap"><pre><code>{
  "mcpServers": {
    "datapulse-my": {
      "transport": "streamable-http",
      "url": "%s/mcp"
    }
  }
}</code></pre></div>
          <div><p class="section-lead">The read-only MCP surface gives AI systems cited NPRA catalogue context for search, freshness, drift, reconciliation, provenance, and evidence review. It complements the official source rather than replacing it.</p><a class="inline-arrow" href="https://modelcontextprotocol.io/docs/tools/inspector">Try it in MCP Inspector <span aria-hidden="true">→</span></a><p class="endpoint">Endpoint: <a href="%s/mcp">%s/mcp</a></p></div>
        </div>""" % (origins["mcp"], origins["mcp"], origins["mcp"]),
    )
    return replace_owned_block(
        html,
        NPRA_SURFACES_MARKER,
        """<div class="surface-table-wrap"><table><caption class="visually-hidden">NPRA catalogue programmatic surfaces</caption><thead><tr><th scope="col">Surface</th><th scope="col">URL</th></tr></thead><tbody>
            <tr><td>Manifest</td><td><a class="surface-url" href="%s/datapulse.json">%s/datapulse.json</a></td></tr>
            <tr><td>MCP server</td><td><a class="surface-url" href="%s/mcp">%s/mcp</a></td></tr>
            <tr><td>Status badges</td><td><a class="surface-url" href="%s/badges/status-fresh.svg">/badges/&lt;id&gt;.svg</a></td></tr>
            <tr><td>Live health</td><td><a class="surface-url" href="%s/health/latest.json">%s/health/latest.json</a></td></tr>
            <tr><td>JSON-LD catalogue</td><td><a class="surface-url" href="%s/data/jsonld/catalog.json">/data/jsonld/catalog.json</a></td></tr>
          </tbody></table></div>""" % (origins["website"], origins["website"], origins["mcp"], origins["mcp"], origins["website"], origins["website"], origins["website"], origins["website"]),
    )


def _reproducibility_verification_time() -> datetime | None:
    """Return the verifier clock only inside its isolated build subprocesses."""
    if os.environ.get("DATAPULSE_ISOLATED_REPRODUCIBILITY_BUILD") != "1":
        return None
    value = os.environ.get("DATAPULSE_REPRODUCIBILITY_VERIFY_AT")
    if not value:
        raise EmbedError("isolated reproducibility build is missing its verification time")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise EmbedError("isolated reproducibility verification time must be ISO-8601") from error
    if parsed.tzinfo is None:
        raise EmbedError("isolated reproducibility verification time must include a UTC offset")
    return parsed.astimezone(timezone.utc)


def _attestation_verification(root: Path) -> dict:
    """Embed only claims verified against the exact health bytes being rendered."""
    verification_time = _reproducibility_verification_time()
    try:
        if verification_time is None:
            return verify_contract(root)
        return verify_contract(root, now=verification_time)
    except ContractError:
        return {
            "schema": "datapulse/v1/attestation-verification-result",
            "claims": {
                "artifact_signed": False,
                "rekor_witnessed": False,
                "source_truth_verified": False,
            },
            "freshness": {"status": "unavailable"},
            "reason": "no current verified contract for this health snapshot",
        }


def _replace_attestation_ui(html: str) -> str:
    old = '''        const signedRef = window.__DATAPULSE_DATA__?.attestations?.attestations?.[dataset.id];
        const signed = dataset.attestation_ref === signedRef;
        addFact(facts, "Signed", signed ? `yes — ${dataset.attestation_ref || signedRef}` : "no");'''
    new = '''        const signedRef = window.__DATAPULSE_DATA__?.attestations?.attestations?.[dataset.id];
        const verification = window.__DATAPULSE_DATA__?.attestationVerification || {};
        const claims = verification.claims || {};
        const artifactSigned = claims.artifact_signed === true;
        addFact(facts, "Artifact signature", artifactSigned ? "verified for this health snapshot" : "not verified for this health snapshot");
        addFact(facts, "Rekor witness", claims.rekor_witnessed === true ? "verified inclusion proof" : "not published or not verified");
        addFact(facts, "Source truth", "not verified by attestation");'''
    if old in html:
        html = html.replace(old, new, 1)
    html = html.replace(
        '        if (signed) links.append(makeLink("Signed attestation", `${REPO}${signedRef}`));',
        '        if (artifactSigned && signedRef) links.append(makeLink("Verified attestation proof", `${REPO}${signedRef}`));',
        1,
    )
    return html


def _render_page(
    html_path: Path,
    manifest_path: Path,
    health_path: Path,
    filters_path: Path,
    sections_path: Path,
    attestations_path: Path | None = None,
    binding_path: Path | None = None,
    public_surfaces_path: Path | None = None,
) -> str:
    try:
        html = html_path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as error:
        raise EmbedError(f"cannot read {html_path}: {error}") from error

    manifest = _load(manifest_path)
    health = _load(health_path)
    root = (public_surfaces_path or manifest_path.parent).resolve()
    try:
        surfaces = load_public_surfaces(root)
    except GenerationError as error:
        raise EmbedError(str(error)) from error
    if html_path.name == "index.html":
        template_path = root / HOMEPAGE_TEMPLATE
        if template_path.is_file():
            html = _render_homepage(root, html)
        html = update_changelog_strip(html, manifest, health)
        html = _dashboard_facts(html, manifest, health, surfaces["origins"]["website"])
    if html_path.name == "npra.html":
        html = _npra_freshness(html, health)
        html = _npra_runtime_script(html)
        html = _npra_links(html, surfaces["origins"])
    data = (
        '<script id="embedded-data">\n'
        "    window.__DATAPULSE_DATA__ = {"
        f"health: {_dump(health)}, "
        f"manifest: {_dump(manifest)}, "
        f"dashboardFilters: {_dump(_load(filters_path))}, "
        f"dashboardSections: {_dump(_load(sections_path))}, "
        f"attestations: {_dump(_load_optional(attestations_path))}, "
        f"attestationBinding: {_dump(_load_optional(binding_path))}, "
        f"attestationVerification: {_dump(_attestation_verification(manifest_path.parent))}"
        "};\n"
        "  </script>"
    )
    marker = '<script id="embedded-data">'
    start = html.find(marker)
    if start >= 0:
        try:
            end = html.index("</script>", start) + len("</script>")
        except ValueError as error:
            raise EmbedError(f"{html_path}: embedded-data script is not closed") from error
        html = html[:start] + data + html[end:]
    elif "</body>" in html:
        html = html.replace("</body>", f"  {data}\n</body>", 1)
    else:
        raise EmbedError(f"{html_path}: cannot find embedded-data block or </body>")

    return html


def embed(
    html_path: Path,
    manifest_path: Path,
    health_path: Path,
    filters_path: Path,
    sections_path: Path,
    attestations_path: Path | None = None,
    binding_path: Path | None = None,
    public_surfaces_path: Path | None = None,
) -> None:
    """Render and atomically publish one explicitly requested page."""
    rendered = _render_page(
        html_path, manifest_path, health_path, filters_path, sections_path,
        attestations_path, binding_path, public_surfaces_path,
    )
    try:
        publish_text_outputs({html_path: rendered})
    except GenerationError as error:
        raise EmbedError(str(error)) from error


def embed_all(
    html_paths: tuple[Path, ...], manifest_path: Path, health_path: Path,
    filters_path: Path, sections_path: Path, attestations_path: Path | None,
    binding_path: Path | None, public_surfaces_path: Path,
) -> None:
    """Validate and render all dashboard targets before publishing any one of them."""
    try:
        rendered = {
            path: _render_page(
                path, manifest_path, health_path, filters_path, sections_path,
                attestations_path, binding_path, public_surfaces_path,
            )
            for path in html_paths
        }
    except GenerationError as error:
        raise EmbedError(str(error)) from error
    try:
        publish_text_outputs(rendered)
    except GenerationError as error:
        raise EmbedError(str(error)) from error


def parse_args() -> argparse.Namespace:
    root = Path(__file__).resolve().parent.parent
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--html", type=Path, default=root / "docs/index.html")
    parser.add_argument("--npra", type=Path, default=root / "docs/npra.html")
    parser.add_argument("--manifest", type=Path, default=root / "datapulse.json")
    parser.add_argument("--health", type=Path, default=root / "health/latest.json")
    parser.add_argument(
        "--filters", type=Path, default=root / "docs/.dashboard_filters.json"
    )
    parser.add_argument(
        "--sections", type=Path, default=root / "docs/.dashboard_sections.json"
    )
    parser.add_argument(
        "--attestations", type=Path, default=root / "attestations/latest/index.json"
    )
    parser.add_argument(
        "--attestation-binding", type=Path, default=root / "attestations/latest/binding.json"
    )
    parser.add_argument(
        "--public-surfaces", type=Path, default=root / "config"
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        embed_all(
            (args.html, args.npra), args.manifest, args.health, args.filters,
            args.sections, args.attestations, args.attestation_binding,
            args.public_surfaces.parent,
        )
    except EmbedError as error:
        print(f"embed_dashboard_data.py: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
