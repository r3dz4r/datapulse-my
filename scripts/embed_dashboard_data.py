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
    from scripts.verify_attestation_binding import ContractError, verify_contract
except ModuleNotFoundError:  # Direct script execution puts scripts/ on sys.path.
    from verify_attestation_binding import ContractError, verify_contract


class EmbedError(RuntimeError):
    """Raised when dashboard data cannot be embedded safely."""


CHANGELOG_BEGIN = "<!-- BEGIN changelog-strip -->"
CHANGELOG_END = "<!-- END changelog-strip -->"
NPRA_CHECKOUT_MARKER = "<!-- NPRA-PADDLE-CHECKOUT -->"
NPRA_CHECKOUT_END = "<!-- END NPRA-PADDLE-CHECKOUT -->"
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
    pattern = re.compile(r'(<span data-npra-cfd=")[^"]*(">).*?(</span>)')
    updated, replacements = pattern.subn(
        lambda match: f'{match.group(1)}{health["checked_at"]}{match.group(2)}{content}{match.group(3)}',
        html,
        count=1,
    )
    if replacements != 1:
        raise EmbedError("NPRA page must contain one freshness marker")
    updated = updated.replace(
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
    return updated


def _npra_checkout_shell(html: str, client_token: str | None = None) -> str:
    """Inject one checkout shell; only Paddle's public client token may be embedded."""
    if client_token is None:
        client_token = os.environ.get("PADDLE_SANDBOX_CLIENT_TOKEN")
        if not client_token:
            existing = re.search(
                r"window\.PADDLE_SANDBOX_CLIENT_TOKEN\s*=\s*(\"(?:[^\"\\]|\\.)*\")\s*;",
                html,
            )
            if existing:
                client_token = json.loads(existing.group(1))
    token_assignment = (
        "window.PADDLE_SANDBOX_CLIENT_TOKEN = "
        + json.dumps(client_token).replace("&", "\\u0026").replace("<", "\\u003c").replace(">", "\\u003e")
        + ";"
        if client_token
        else ""
    )
    shell = f'''<!-- NPRA-PADDLE-CHECKOUT -->
    <section id="npra-pro" aria-labelledby="npra-pro-title"><div class="wrap"><p class="eyebrow">NPRA PRO</p><h2 id="npra-pro-title">100,000 NPRA queries per billing period</h2><p>USD 25/month. Your API key is issued only after Paddle's signed webhook confirms payment.</p><button class="button button-primary" id="npra-pro-checkout" type="button">Start secure checkout</button><button class="button" id="npra-pro-retry" type="button" hidden>Retry activation</button><p id="npra-pro-status" aria-live="polite"></p></div></section>
    <script src="https://cdn.paddle.com/paddle/v2/paddle.js"></script>
    <script>
    {token_assignment}(() => {{
      const priceId = 'pri_01m0fvdratkz274ker6v7y70x3';
      const token = window.PADDLE_SANDBOX_CLIENT_TOKEN;
      const button = document.getElementById('npra-pro-checkout');
      const retryButton = document.getElementById('npra-pro-retry');
      const status = document.getElementById('npra-pro-status');
      let state = 'idle';
      let redemptionNonce = '';
      let issuedKey = '';
      let confirmationDeadline = 0;
      let retryTimer = null;
      let requestInFlight = false;
      const supportGuidance = 'Do not pay again. Retain your receipt. Contact the operator privately.';
      const clearRetry = () => {{
        if (retryTimer !== null) {{ clearTimeout(retryTimer); retryTimer = null; }}
      }};
      const waitingManual = message => {{
        clearRetry();
        state = 'waiting_manual';
        button.disabled = true;
        retryButton.hidden = false;
        retryButton.disabled = false;
        status.dataset.state = 'waiting_manual';
        status.textContent = message || `Confirmation is still pending. Keep this tab open, then use Retry activation. ${{supportGuidance}}`;
      }};
      const needsSupport = message => {{
        clearRetry();
        state = 'needs_support';
        button.disabled = true;
        retryButton.hidden = true;
        retryButton.disabled = true;
        status.dataset.state = 'needs_support';
        status.textContent = `${{message}} ${{supportGuidance}}`;
      }};
      const scheduleRetry = (response, result) => {{
        if (Date.now() >= confirmationDeadline) {{ waitingManual(); return; }}
        const retryAfterHeader = response.headers.get('Retry-After');
        let suppliedDelay = Number(retryAfterHeader);
        if (!Number.isFinite(suppliedDelay)) suppliedDelay = Number(result && result.error && result.error.retry_after_s);
        if (!Number.isFinite(suppliedDelay)) suppliedDelay = 2;
        const delay = Math.min(Math.max(suppliedDelay, 1), 30);
        if (Date.now() + delay * 1000 >= confirmationDeadline) {{ waitingManual(); return; }}
        state = 'confirming';
        retryButton.hidden = true;
        retryTimer = setTimeout(() => {{ retryTimer = null; confirmActivation(); }}, delay * 1000);
      }};
      if (!token || !window.Paddle) {{ button.disabled = true; status.textContent = 'Checkout is temporarily unavailable.'; return; }}
      Paddle.Environment.set('sandbox');
      const eventCallback = event => {{
        if (event.name === 'checkout.completed') {{
          if (state === 'checkout_open' && redemptionNonce) {{
            confirmationDeadline = Date.now() + 15 * 60 * 1000;
            state = 'confirming';
            button.disabled = true;
            status.dataset.state = 'confirming';
            status.textContent = 'Payment received. Waiting for secure confirmation; keep this tab open.';
            confirmActivation();
          }}
        }}
        if (event.name === 'checkout.closed') {{
          if (state === 'checkout_open') {{
            redemptionNonce = '';
            state = 'idle';
            button.disabled = false;
            retryButton.hidden = true;
            status.dataset.state = 'idle';
            status.textContent = 'Checkout was closed before payment.';
          }}
        }}
      }};
      Paddle.Initialize({{ token, eventCallback }});
      const confirmActivation = async () => {{
        if (!redemptionNonce || requestInFlight || state === 'active' || state === 'needs_support') return;
        if (Date.now() >= confirmationDeadline) {{ waitingManual(); return; }}
        clearRetry();
        requestInFlight = true;
        state = 'confirming';
        retryButton.disabled = true;
        try {{
          if (!issuedKey) {{
            const response = await fetch('https://api.data-pulse.my/api/v1/paddle/redeem', {{ method: 'POST', headers: {{'Content-Type': 'application/json'}}, body: JSON.stringify({{redemption_token: redemptionNonce}}) }});
            const result = await response.json().catch(() => ({{}}));
            if (response.status === 409 && result.error && result.error.code === 'redemption_pending') {{ scheduleRetry(response, result); return; }}
            if (response.status >= 500) {{ scheduleRetry(response, result); return; }}
            if (response.status !== 201 || !result.data || !result.data.api_key) {{ needsSupport('Activation could not be completed.'); return; }}
            issuedKey = result.data.api_key;
            window.prompt('Copy your API key for this session.', issuedKey);
          }}
          const verification = await fetch('https://api.data-pulse.my/api/v1/keys/me', {{ headers: {{'X-API-Key': issuedKey}} }});
          const verificationResult = await verification.json().catch(() => ({{}}));
          if (verification.status >= 500) {{ scheduleRetry(verification, verificationResult); return; }}
          if (verification.status === 200 && verificationResult.data && verificationResult.data.tier === 'pro' && verificationResult.data.status === 'active' && Array.isArray(verificationResult.data.scopes) && verificationResult.data.scopes.includes('npra.read')) {{
            clearRetry();
            state = 'active';
            button.disabled = true;
            retryButton.hidden = true;
            status.dataset.state = 'active';
            status.textContent = 'API key is active for NPRA Pro.';
            return;
          }}
          needsSupport('The issued key could not be verified as active.');
        }} catch (_) {{
          scheduleRetry({{headers: new Headers()}}, {{}});
        }} finally {{
          requestInFlight = false;
        }}
      }};
      retryButton.addEventListener('click', () => {{ confirmActivation(); }});
      button.addEventListener('click', () => {{
        if (state !== 'idle') return;
        state = 'checkout_open';
        button.disabled = true;
        try {{
        const bytes = new Uint8Array(32);
        crypto.getRandomValues(bytes);
        redemptionNonce = btoa(String.fromCharCode(...bytes)).replaceAll('+', '-').replaceAll('/', '_').replaceAll('=', '');
          Paddle.Checkout.open({{ items: [{{ priceId, quantity: 1 }}], customData: {{ dp_nonce: redemptionNonce }} }});
        }} catch (_) {{
          redemptionNonce = '';
          state = 'idle';
          button.disabled = false;
          status.dataset.state = 'idle';
          status.textContent = 'Checkout is temporarily unavailable.';
        }}
      }});
    }})();
    </script>
    {NPRA_CHECKOUT_END}'''
    if NPRA_CHECKOUT_MARKER in html:
        # Old generated pages had no closing marker and may contain duplicate scripts.
        # The checkout shell is the final main child, so replace that whole tail atomically.
        pattern = re.compile(rf"{re.escape(NPRA_CHECKOUT_MARKER)}.*?\s*</main>", re.DOTALL)
        updated, replacements = pattern.subn(lambda _match: shell + "\n  </main>", html, count=1)
        if replacements != 1:
            raise EmbedError("NPRA checkout marker is not followed by </main>")
        return updated
    return html.replace("</main>", shell + "\n  </main>", 1)


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
    dataset_count = len(manifest["datasets"])
    replacement = (
        f"{CHANGELOG_BEGIN}\n"
        '    <aside class="changelog-strip" aria-label="Recently shipped">\n'
        "      <strong>Recently shipped</strong>\n"
        f'      <span><time datetime="{shipped_date}">{shipped_date}</time> · '
        f"{dataset_count} datasets tracked</span>\n"
        '      <a href="/catalog-snapshot.json">Machine-readable catalog snapshot</a>\n'
        '      <a href="/health/latest.json">Latest trust snapshot →</a>\n'
        '      <a href="/release-verification.md">Reproducible build proof</a>\n'
        '      <a class="chip" href="/trust-layer-notebook.ipynb" '
        'title="Open the canonical Colab notebook: verify before you use">Trust Layer notebook</a>\n'
        '      <a class="chip" href="#camofox">Browser-dependent</a>\n'
        '      <a class="chip" href="#legal">Legal</a>\n'
        "    </aside>\n"
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


DATASET_COUNT_PATTERNS = (
    r"\b\d+(?= Malaysian public datasets\b)",
    r"\b\d+(?= official datasets\b)",
    r"\b\d+(?= datasets verified\b)",
    r"\b\d+(?= licence-declared datasets\b)",
    r"\b\d+(?=-dataset catalogue\b)",
    r"\b\d+(?= datasets probed\b)",
    r"(?<=Five of )\d+(?= datasets\b)",
)

SCHEDULER_CLAIM = (
    "The scheduler wakes every 5 minutes and probes only datasets due under "
    "their tiered cadence"
)


def _replace_scheduler_claims(html: str) -> str:
    """Replace legacy all-datasets-per-tick claims with the due-tier contract."""
    replacements = {
        r"We monitor official datasets; the scheduler wakes every 5 minutes and probes only datasets due under their tiered cadence\.": (
            "We monitor official datasets. " + SCHEDULER_CLAIM
        ),
        r"We monitor official datasets\. The scheduler wakes every 5 minutes and probes only datasets due under their tiered cadence\.": (
            "We monitor official datasets. " + SCHEDULER_CLAIM
        ),
        r"We probe \d+ official datasets every 5 minutes": (
            "We monitor official datasets. " + SCHEDULER_CLAIM
        ),
        r"A 5-minute timer fetches each dataset": (
            "A 5-minute scheduler wakes and probes datasets due under their tiered cadence"
        ),
        r"\d+ datasets probed every 5 minutes": (
            "Datasets are probed when due under their tiered cadence"
        ),
    }
    for pattern, replacement in replacements.items():
        html = re.sub(pattern, replacement, html)
    return html


def _replace_dataset_counts(html: str, health: object) -> str:
    if not isinstance(health, dict):
        return html
    summary = health.get("_trust_summary")
    if not isinstance(summary, dict) or "datasets_total" not in summary:
        return html
    count = summary["datasets_total"]
    if isinstance(count, bool) or not isinstance(count, int) or count < 0:
        raise EmbedError("health _trust_summary.datasets_total must be a non-negative integer")
    for pattern in DATASET_COUNT_PATTERNS:
        html = re.sub(pattern, str(count), html)
    return html


def _attestation_verification(root: Path) -> dict:
    """Embed only claims verified against the exact health bytes being rendered."""
    try:
        return verify_contract(root)
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


def embed(
    html_path: Path,
    manifest_path: Path,
    health_path: Path,
    filters_path: Path,
    sections_path: Path,
    attestations_path: Path | None = None,
    binding_path: Path | None = None,
) -> None:
    try:
        html = html_path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as error:
        raise EmbedError(f"cannot read {html_path}: {error}") from error

    manifest = _load(manifest_path)
    health = _load(health_path)
    if html_path.name == "index.html":
        html = update_changelog_strip(html, manifest, health)
        html = _replace_attestation_ui(html)
        html = _replace_scheduler_claims(html)
    html = _replace_dataset_counts(html, health)
    if html_path.name == "npra.html":
        html = _npra_freshness(html, health)
        html = _npra_checkout_shell(html)
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

    try:
        _atomic_write_text(html_path, html)
    except (OSError, UnicodeError) as error:
        raise EmbedError(f"cannot write {html_path}: {error}") from error


def parse_args() -> argparse.Namespace:
    root = Path(__file__).resolve().parent.parent
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--html", type=Path, default=root / "docs/index.html")
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
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        embed(args.html, args.manifest, args.health, args.filters, args.sections, args.attestations, args.attestation_binding)
    except EmbedError as error:
        print(f"embed_dashboard_data.py: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
