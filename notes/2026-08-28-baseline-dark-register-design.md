# DataPulse baseline site restructure — dark precision design direction

**Date:** 2026-08-28
**Status:** Design direction (pre-implementation). Approved by Redza on this date: live verified register first, full generator-owned restructure, dark precision visual system.

## Why the current site fails its own goal

Redza's observation is correct and confirmed by live inspection of `https://www.data-pulse.my/` and `/learn`:

1. **`/` and `/learn` overlap heavily.** Both are prose walls about "verified Malaysian public data + connect via MCP." They cover the same decision with different framing.
2. **It is optimized for human reading, not agent/data consumption.** Long methodology sections, tables, and prose paragraphs. The primary object (a dataset's evidence) is buried.
3. **It does not lead with what makes DataPulse distinct** — a continuously verified register with per-dataset evidence — the way the closest analog (c0mm0.com) does.

## Grounding (verified 2026-08-28)

### Closest analog: c0mm0.com (verified live)
"The continuously verified register of European data." The pattern that wins:
- **One-line hero → live checked register.** Hero states exactly what it is; the register (15,420 entries) is immediately browsable below.
- **Per-entry `access` block**: `level` (direct / documented / reference_only) + ranked actionable URLs + `latest_check.probe_url`. This is a *machine-grade evidence receipt* shown as the primary object.
- **Live verification rollup**: "last check 10m ago", per-entry "checked 2h ago" plus a `trust` score (85, 80, 79…).
- **Names AI agents explicitly**: "Built for researchers, journalists, civic developers and AI agents."
- Ship a rich `llms.txt` + DCAT-AP catalog as the machine plane.

### Decube (verified live)
"Trace it / Trust it / Govern it" — three concrete verbs, each with a real-looking data-health/lineage visual. Leads with **data health + lineage + AI accessibility**, not methodology. Clean white, high-contrast, minimal prose.

### Agent-readiness standard (Vercel Agent Readability / AgentGrade / web.dev — verified)
The modern bar for agent-first sites:
- **Discovery**: `llms.txt`, `sitemap.xml`, agent-aware `robots.txt`, canonical links
- **Capability**: MCP server at a wired path, OpenAPI
- **Content negotiation**: return `text/markdown` for `Accept: text/markdown`, JSON for JSON
- **Stable semantic shell**: `html lang`, canonical, og:title/desc, JSON-LD, `d0` `main` landmarks
- Machines consume the **accessibility tree / DOM**, not screenshots — so semantic, stable HTML IS the agent surface. "Everything that makes a site agent-ready also makes it better for humans."

Your own 2026-08-27 design research already concluded: evidence receipt as primary object + `use / warn / stop` decision + machine-readable surfaces first + no manual MCP enumeration + keep methodology distinct. The current pages don't yet implement that call.

## Design decision (Redza-approved)

- **Live verified register first** (c0mm0-style): statuses, evidence, connect — one real dataset decision visible immediately.
- **Full restructure**, generator-owned, test the baseline, then iterate.
- **Dark precision (Linear-style)** visual system: near-black canvas, high-contrast statuses, evidence/register as data-first — reads "engineering / agent-native."

## Baseline information architecture

Separate the human surface from the machine surface instead of two overlapping prose pages:

| Surface | Role | Machines | Primary object |
|---|---|---|---|
| `/` (register) | Live verified register + connect | llms.txt, sitemap, robots, JSON-LD | Per-dataset evidence/status; one real `use/warn/stop` decision |
| `/learn` | Builder path | content-negotiated markdown mirror | Verified → Fetch → Build; notebook; MCP quickstart |
| `/methodology` | De-emphasized, distinct | JSON-LD, canonical | The honest scoring rules (moved out of the hero path) |
| `/npra` | Vertical proof | JSON-LD | Live NPRA vertical |
| `llms.txt`, `mcp.json`, `agent.json`, `datapulse.json`, `health/*` | Hidden machine plane | — | All discovery/capability manifests |

**The primary design object** (hero): one real dataset's evidence receipt — source identity, publisher, licence, observed time, content date, freshness state, structural state, evidence ref, decision posture `use / warn / stop`. Drawn live from `health/latest.json` + the per-dataset report, generator-owned.

## Dark precision design tokens (Linear-inspired baseline)

Derive the shared stylesheet from Linear's system (verified template), flattened to DataPulse:

**Colors**
- Background: `#0a0b0e` (near-black), panel `#121316`, surface `#1a1c20`
- Primary text `#f5f6f7`, secondary `#a8adb8`, tertiary `#7c818c`
- Accent (brand green, DataPulse is green): CTA `#16a34a` → hover `#22c55e`
- Status scale (high-contrast on dark): fresh `#16a34a`, aging `#ca8a04`, stale `#ea580c`, discontinued `#64748b`, degraded `#dc2626`, browser `#8b5cf6`, reference `#0ea5e9`, unknown `#94a3b8`
- Borders `rgba(255,255,255,0.08)`, thin; no black shadows (dark-on-dark) — use luminance stepping
- `font-feature-settings: "cv01", "ss03"` if Inter, or `Inter` + `JetBrains Mono` for data/tools

**Typography**
- `Inter` (or current IBM Plex if you prefer continuity) at weight 510 workhorse, 400 reading, 590 emphasis; negative tracking at display sizes
- `JetBrains Mono` / current mono for identifiers, tool names, code, and status chips

**Data/viz**
- Tabular numerals (`tabular-nums`) for all health counts and timestamps
- Status chips + colored dot, never color-only (text label always present)
- Register rows: source, publisher, licence, status chip, last-checked, access (`direct`/`documented`/`reference`), trust/probe evidence

**Accessibility (agent-readiness = a11y):**
- Semantic landmarks (`header`, `nav`, `main`, `section`), skip-link, `html lang=en`
- Canonical link, og:title/desc, one JSON-LD block per page
- 16px+ body, 44px touch targets, focus rings, `prefers-reduced-motion`
- Content-negotiation: serve `Accept: text/markdown` mirror of `/learn` and register (agent-grade)

## Generator-owned restructure map (no hand-edited surfaces)

Extend the existing canonical chain so every re-render stays self-healing:

- `config/public-surfaces.json` + new `config/landing-page.json` / `config/register.json` — IA, stable copy, claim boundaries
- `scripts/templates/` — new `register.html.tmpl`, refactor `landing.html.tmpl`, shared `assets/site-nav.html`, shared dark CSS tokens
- Fresh generator(s): `gen_register_page.py` (register row data from `health/latest.json` + `datapulse.json` + per-dataset evidence), refactor `gen_landing_page.py`
- `scripts/generate.sh` — release-build includes register generation
- `scripts/contract-scope.json` — register `docs/register.html`/`docs/index.html` as full-output surfaces
- `scripts/verify_*` — served/reproducibility checks include the new register surface
- `docs/index.html`, `/learn`, `/landing`, methodology all remain generator-owned outputs; **no hand-editing**
- Agent surface: content-negotiation route + JSON-LD per page; keep `llms.txt`/`mcp.json`/`agent.json` wired

## What stays / what goes

**Keep (verified facts, must not regress):** 389 datasets; read-only; official sources remain source of record; 10-status taxonomy (adding a status still requires the 6-file contract change); MCP 100/100 mcpgrade + 16 tools; no payment demand; redza honesty doctrine. All these are the *evidence* the register displays.

**Move:** methodology/anti-claims out of the hero path into a distinct, de-emphasized surface (still honest, still cited).

**Avoid (honest posture):** universal trust score (keep per-axis evidence + `use/warn/stop` decision posture, not a single number); "verified truth" language; manual tool enumeration; fabricated health counts.

## Verification gates before calling the baseline done

1. Local generators re-render register + landing + learn byte-identically on two runs (determinism).
2. Repository contract + release-build + served-surface checks pass.
3. Live `https://www.data-pulse.my/` serves the dark register with one real `use/warn/stop` dataset decision visible without scroll.
4. Agent-readiness spot-check: `Accept: text/markdown` mirror works, `llms.txt` links resolve, JSON-LD present, canonical/og tags on every page.
5. Human a11y check: semantic landmarks, skip-link, 16px body, contrast ≥4.5:1, keyboard-nav, reduced-motion.
6. No regression: methodology/NPRA still reachable and intact; MCP/llms/mcp.json unchanged.

## Baseline is the experiment

This is the first iteration of a baseline we will test and iterate over time. Treat the dark register as v0.1 of a template that evolves with real feedback — not a final polish. Success = a visitor (human or agent) immediately sees *live verified data with evidence*, not a prose wall.

---

*Source materials read this session: c0mm0.com (live extract), decube.io (live extract), web.dev/build-agent-friendly-websites, agent-ready.dev complete-guide-to-agent-readability, prior `/home/redza/datapulse-my/notes/2026-08-27-ai-trust-layer-verification-design-research.md`, `/home/redza/datapulse-my/notes/2026-08-27-agent-economy-landing-page-brief.md`, uipro design-system (`Accessible & Ethical` / `Minimal Single Column`, recommended), popular-web-designs `linear.app.md` + `stripe.md` templates.*
