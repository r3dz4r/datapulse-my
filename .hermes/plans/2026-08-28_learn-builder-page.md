# `/learn` — "Build with Malaysian data" landing page

> Implement with the repo's docs conventions. Content page, not generated-from-data.

**Goal:** Add a dedicated, unmissable `/learn` (docs/learn.html) page that teaches aspiring Malaysian AI builders how to verify and use DataPulse data — the notebook front-and-center, a 3-step verify→fetch→build path, and a drop-in MCP config — and wire it into the site navigation.

**Architecture:** A hand-authored `docs/learn.html` that reuses the shared site partial (`docs/assets/site-nav.html`, injected via `scripts/gen_site_nav.py`) and the shared `docs/assets/datapulse.css` theme. Add a "Learn" link to the nav partial once; regenerate nav across all pages.

**Tech Stack:** Static HTML + existing `datapulse.css` theme; no new tooling. Follow docs/AGENTS.md (no marketing superlatives, citable numbers, no fabricated dataset IDs).

---

## Current context (verified)

- Site root page = GitHub Pages serving `docs/`. `index.html`/`npra.html` are generated; `landing.html` and `health-methodology.html` are generated; many docs (buyer-api-reference, architecture, etc.) are hand-authored.
- Shared nav lives in `docs/assets/site-nav.html` (single source of truth), injected by `scripts/gen_site_nav.py` into every page carrying the `BEGIN/END SITE-NAV` markers.
- The notebook (`docs/trust-layer-notebook.ipynb`, 12 cells) is currently surfaced only as: a README Colab badge + one toolbar `<a class="chip">` at `index.html:5162`. Weak placement = weak uptake.
- Real verifiable numbers available: 389 datasets, 88 fresh / 141 aging / 143 stale / 1 discontinued / 5 browser-dependent / 11 reference (from `health/latest.json` `_trust_summary`), 30 GTFS feeds, `fuelprice` example, MCP endpoint `https://mcp.data-pulse.my/mcp`.
- **Operator has approved adding this new public page** (docs/AGENTS.md lists "adding new public pages without operator approval" as out-of-scope — approval granted).

## Proposed approach

1. Create `docs/learn.html` — hand-authored, includes the SITE-NAV markers + `main-content` skip-link + `datapulse.css`, a hero ("Build with verified Malaysian data"), a 3-step teach-and-do path, the notebook embed/link, a drop-in MCP config block, and citable-number facts. No marketing superlatives, no fabricated dataset IDs.
2. Add a **Learn** link to `docs/assets/site-nav.html` (the shared partial), placed before Methodology.
3. Run `python3 scripts/gen_site_nav.py` to propagate the nav change through all generated pages (`index.html`, `npra.html`, `landing.html`, `health-methodology.html`).
4. Verify no `docs/AGENTS.md` rule is broken; run the deterministic-safety-net tests.
5. Optionally surface the notebook more prominently on the landing hero (separate, low-risk follow-up) — parked unless Redza wants it.

## Files likely to change

- **Create:** `docs/learn.html`
- **Modify:** `docs/assets/site-nav.html` (add Learn link)
- **Modified by regenerator:** `docs/index.html`, `docs/npra.html`, `docs/landing.html`, `docs/health-methodology.html` (nav injected via gen_site_nav.py — do not hand-edit these)

## Verification / acceptance

- `site-nav.html` contains a "Learn" link to `/learn.html`; `gen_site_nav.py` run, and generated pages show the Learn link.
- `learn.html` renders standalone on data-pulse.my/learn.html: hero + teach-and-do steps + notebook link + MCP config + citable numbers, consistent with theme.
- All numbers traceable to `datapulse.json`/`health/latest.json` (run `python3 scripts/check.py` to confirm).
- No `docs/AGENTS.md` violation: no "category-defining/leading/first-mover" superlatives, no fabricated dataset IDs, claim boundaries respected.
- Deterministic-safety-net tests still pass: `python3 -m pytest scripts/tests/ mcp/tests/ -v`.

## Risks / tradeoffs / open questions

- **Content is marketing-adjacent** — docs/AGENTS.md restricts superlatives. Keep tone verifiable ("389 datasets", "verified official sources") not hyperbolic ("unmissable", "#1").
- **New inbound URL to defend** — acceptable; it's a funnel, not a random page.
- **Notebook analytics** — the `/learn` page makes the notebook easy to find, but real uptake measurement needs a view-count signal (a follow-up, not in scope here).
- **Open question:** should `/learn` live as a top-level page or fold into the landing page? Chosen: top-level page — keeps landing focused, gives media-buying a clean target URL.
