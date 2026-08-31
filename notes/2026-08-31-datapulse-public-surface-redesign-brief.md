# DataPulse public-surface redesign — product/design brief

**Date:** 2026-08-31
**Status:** Draft for product/design approval; no implementation authorized by this document
**Scope owner:** Redza
**Product:** `r3dz4r/datapulse-my` / DataPulse
**Design direction:** Dark precision, live verified register first

---

## 1. Decision this brief proposes

Rebuild the public DataPulse experience around the **live verified dataset register** rather than around explanatory prose.

The homepage should let an AI/agent builder answer, quickly and honestly:

> **Can I use this Malaysian public dataset now, what evidence supports that decision, and where do I connect to the official source?**

The site should become a coherent public system across all human-facing and machine-readable surfaces. It should not become a new data product, a generic AI brochure, or a new trust infrastructure project.

The alpha is a **presentation and information-architecture redesign**. It preserves the existing DataPulse data, evidence, routes, status semantics, and machine capabilities.

---

## 2. Operator decisions already made

These are hard inputs to the design, not open questions:

- The primary product surface is the **live register**.
- The primary audience is **AI/agent builders deciding whether they can use a dataset**.
- The primary outcome is a fast, evidence-backed **use-now decision**.
- The homepage exposes a live, searchable register of **all current datasets**, not a curated showcase.
- Register controls prioritize search plus filters for:
  - status;
  - publisher/category;
  - access method;
  - recency.
- Default ordering is:
  1. use-now datasets;
  2. review/warn datasets;
  3. stop datasets;
  with recency used within each group.
- Each row is compact by default and shows:
  - status/verdict;
  - any already-existing score or signal appropriate to display;
  - last checked;
  - source/access information;
  - one clear use/connect action;
  with evidence details available on expansion or detail view.
- The primary action opens the **official source first**. MCP/API connection is a secondary action.
- Stale, unreachable, unknown, discontinued, degraded, and browser-dependent states remain visible with explicit warnings. They are not hidden to make the product look healthier.
- The visual system is **dark precision**: near-black canvas, dense register, high-contrast status signals, engineering feel.
- Existing DataPulse brand accents and identity are preserved; the redesign changes hierarchy, density, and information architecture rather than replacing the brand.
- Tone is technical and terse: evidence, status, access, and action before marketing narrative.
- All public human-facing surfaces and machine-readable surfaces are in scope.
- NPRA may be redesigned internally for consistency, but remains unlinked and excluded from public discovery for this alpha.
- `/` becomes the register. `/landing.html` becomes a lightweight redirect/alias to `/`.
- The current manifest, 10-status taxonomy, MCP behavior, routes, and trust semantics are preserved.
- The design must work against real current DataPulse data, not only static mock data.
- Generated outputs are never hand-edited. Every generated surface has a canonical source, generator, and contract test.
- Acceptance must include: a builder can find a relevant dataset and decide whether to use it in under one minute; accessibility and mobile usability must pass.
- The existing `notes/2026-08-28-datapulse-v2-prototype/` is inspiration only. Its layout is not assumed to be correct.

---

## 3. Current product grounding

Verified against the repository on 2026-08-31:

- `datapulse.json` contains **389 datasets**.
- `health/latest.json` is current to `2026-08-31T08:51:10Z`.
- Current health rollup:
  - fresh: 84;
  - aging: 141;
  - stale: 147;
  - browser-dependent: 5;
  - discontinued: 1;
  - reference: 11;
  - degraded: 0;
  - unknown: 0;
  - unknown-freshness: 0;
  - unreachable: 0.
- The configured public page inventory currently includes:
  - `/`;
  - `/landing.html`;
  - `/npra.html`;
  - `/health-methodology.html`;
  - `/learn.html`.
- The public artifact inventory includes the manifest, health, evidence/discovery artifacts, RSS, badges, JSON-LD catalogue, `agent.json`, and `mcp.json`.
- The current `mcp.json` declares **18 tools** at drafting time. Earlier research referenced 16 tools. This discrepancy is not to be papered over in copy: the redesign must consume canonical machine surfaces and tests, never maintain a manually enumerated tool count.
- Current production HEAD at grounding time: `7b17812d6 chore(health): update due dataset health [skip deploy]`.

### Product truth boundary

DataPulse reports what it observed, fetched, parsed, compared, and timestamped. It does not establish objective truth merely because a dataset is present or receives a high signal.

The design must preserve these distinctions:

| Term | Meaning in the product |
|---|---|
| Source of record | The official upstream publisher |
| Observed evidence | What DataPulse measured or retrieved, and when |
| Supported claim | What the evidence permits a builder or agent to say |
| Unknown | What the current evidence did not establish |

The site must not claim “source of truth,” “guaranteed accuracy,” “verified truth,” or “safe MCP server.”

---

## 4. Positioning and product promise

### Primary public sentence

> **Verify Malaysian data before your AI agent uses it.**

### Supporting sentence

> DataPulse shows what an official source exposes, when it was observed, how its access and freshness signals behave, what reuse context is available, and where an agent can connect.

### Short product explanation

> A live evidence register for Malaysian public datasets, delivered through human-readable pages and machine-readable discovery, health, evidence, and MCP surfaces.

### Copy rules

Lead with:

- the dataset;
- its current observable condition;
- the official source;
- the evidence timestamp;
- the permitted decision posture;
- the next action.

Avoid:

- generic “AI is changing everything” language;
- claims that agents automatically trust or adopt `llms.txt`;
- active payment/x402 claims;
- broad Southeast Asian or global coverage claims;
- regulatory certification claims;
- a universal trust score that collapses independent evidence dimensions;
- manually copied feature or tool counts.

If an existing numeric score is displayed in a row, it must be labelled according to its existing contract and subordinate to the evidence/status explanation. The redesign must not introduce or promote a new universal “trust score.”

---

## 5. Public information architecture

### 5.1 `/` — Live verified register, public primary surface

**Job:** Help a builder find a relevant dataset and decide whether to use it.

**First viewport:**

1. restrained product sentence;
2. live rollup showing current dataset count and check recency;
3. compact explanation of the use/warn/stop reading model;
4. search and primary filters;
5. first real register rows visible without navigating through a prose wall.

**Register behavior:**

- Render all current records from the canonical manifest and health/evidence sources.
- Default to use-now → review/warn → stop grouping.
- Sort within each group by recency.
- Make group and filter state visible and shareable where the current architecture permits.
- Preserve all existing 10 taxonomy statuses. The use/warn/stop presentation is a derived decision posture, not an 11th status.
- Never imply that “fresh” means universally correct or that “stale” means unusable for every conceivable purpose.

**Compact row:**

- dataset name and short description;
- publisher/category;
- explicit status label and decision posture;
- existing score/signal only when contractually supported;
- last observed/check time;
- source/access indicator;
- primary “Open official source” action;
- secondary evidence/detail or MCP/API action.

**Expanded/detail evidence:**

- official source identity and URL;
- publisher and licence/reuse context;
- observed-at timestamp;
- content date or source update signal where available;
- freshness classification and its reason;
- schema/record evidence where available;
- anomaly, trend, drift, or reconciliation indicators where available;
- evidence reference and limitations;
- MCP/API connection information where applicable;
- explicit unknowns rather than empty reassurance.

The detail view is an evidence receipt, not a second marketing page.

### 5.2 `/landing.html` — Compatibility alias

- Redirect or alias to `/`.
- Do not maintain a second positioning page.
- Preserve the route only to avoid breaking existing links and discovery references.
- Canonical, sitemap, JSON-LD, and machine-readable references should resolve to `/`.

### 5.3 `/learn.html` — Builder path

**Job:** Explain how to go from a verified dataset decision to a working agent/data workflow.

Information order:

1. Verify — inspect status and evidence.
2. Fetch — open the official source and understand access/licence context.
3. Build — use the machine-readable manifest, health/evidence artifacts, or MCP surface.
4. Re-check — understand that evidence is time-bound and should be re-evaluated.

The page should contain one short working path and copyable examples, but must not duplicate the register or methodology. It should link to canonical machine surfaces rather than list tools manually.

### 5.4 `/health-methodology.html` — De-emphasized methodology surface

**Job:** Explain how the register’s evidence and status classifications are produced.

- Keep it public and discoverable from the appropriate footer/detail/help path.
- Move it out of the primary decision path.
- Use concise definitions, examples, limitations, and links to schemas/artifacts.
- Do not lead the homepage with methodology tables.
- Preserve the 10-status taxonomy and existing methodology semantics.

### 5.5 Supporting public documentation

Supporting public pages and artifacts such as the agent quickstart, MCP reference, buyer API reference, architecture/operations documentation, feed, badges, and JSON-LD catalogue should receive the shared shell, canonical metadata, link corrections, and terminology alignment required by the redesign.

They do not all need the same visual density or a full content rewrite in the first implementation slice. Their role is to support the register without competing with it.

### 5.6 `/npra.html` — Internal redesign, not public alpha surface

- Redesign internally against the same future design system if useful.
- Do not include it in the public primary navigation.
- Exclude it from public discovery/navigation claims for this alpha.
- Do not use it as proof of a publicly launched paid vertical.
- No new payment, buyer-key, or publication work is authorized by this brief.

### 5.7 Machine plane — first-class contract surface

The redesign includes alignment, not cosmetic rewriting, of:

- `llms.txt`;
- `agent.json`;
- `mcp.json`;
- `datapulse.json` and its schema;
- `health/latest.json`, trends, drift, reconciliation, and evidence artifacts;
- `robots.txt`;
- `sitemap.xml`;
- RSS/feed surfaces;
- JSON-LD catalogue and per-page JSON-LD;
- canonical links and Open Graph metadata;
- content negotiation, including Markdown where supported;
- stable links from machine surfaces to the new canonical register and detail paths.

Machine surfaces must be generated or validated from canonical configuration. The site must never claim a fixed tool count in hand-authored HTML when `mcp.json` or the server contract can change.

---

## 6. Design principles

### 6.1 Evidence before explanation

The first useful object is a real dataset decision, not a paragraph describing DataPulse.

### 6.2 Progressive disclosure

Show the minimum information needed for the first decision. Let the user expand into evidence, limitations, and implementation details.

### 6.3 Status is not decoration

Status colors and labels communicate action posture. Every status must have a text label, accessible name, and explanatory meaning. Color alone is insufficient.

### 6.4 Dense but not hostile

The register can feel like an engineering instrument without becoming an unreadable spreadsheet. Use strong hierarchy, tabular numbers for counts/timestamps, restrained borders, and clear row grouping.

### 6.5 Preserve uncertainty

Unknown, stale, unreachable, and incomplete evidence are legitimate states. The UI should make uncertainty legible rather than hiding it behind a green aggregate.

### 6.6 Human and machine surfaces share a semantic core

Semantic HTML, stable landmarks, predictable headings, canonical links, JSON-LD, and content negotiation are not post-hoc SEO work. They are part of the product interface for agents.

### 6.7 Use the existing brand; change the operating posture

Retain DataPulse recognition and accents. Move the feel from “documentation site” toward “live verification instrument.”

---

## 7. Dark-precision design system direction

The implementation design system should formalize three layers:

1. **Primitive tokens** — canvas, panels, surfaces, text, borders, spacing, type scale, status hues.
2. **Semantic tokens** — use, warn, stop, observed, unknown, action, focus, disabled.
3. **Component tokens** — register row, status chip, filter, evidence block, source action, detail drawer, metadata strip, navigation.

Required characteristics:

- near-black canvas and luminance-stepped panels;
- existing DataPulse brand accent retained;
- high-contrast semantic status colors;
- text labels always paired with status colors;
- monospace treatment for identifiers, tool names, timestamps, and machine values where useful;
- tabular numerals for counts and time values;
- visible keyboard focus;
- no dependency on external fonts for core readability;
- no color-only status communication;
- comfortable touch targets and responsive register behavior.

The exact token values are an implementation/design-system decision after this brief, not a reason to assume the prototype’s CSS is canonical.

---

## 8. Generator and contract ownership

This redesign must be implemented as a source-to-surface chain, not as hand-edited HTML.

The future implementation brief should identify, for each changed surface:

| Surface | Canonical input | Generator/template | Contract test |
|---|---|---|---|
| Register | manifest + health/evidence artifacts + register config | register generator/template | row/schema/determinism tests |
| Shared shell | public-surface config + design tokens | shared navigation/layout generator | route/link/metadata tests |
| Learn | Learn page config/content source | page generator/template | content/route/contract tests |
| Methodology | methodology source and taxonomy contract | methodology renderer | taxonomy/content parity tests |
| Landing alias | route contract | redirect/route configuration | canonical/redirect tests |
| Machine plane | canonical manifests and public-surface config | existing generators/validators | URL, schema, count, and parity tests |
| NPRA internal preview | internal design source | separate preview path | must not enter public discovery |

Hard requirements:

- deterministic generation: two runs with identical inputs produce byte-identical output;
- no manual tool enumeration;
- no hand-editing generated `docs/` outputs;
- no mutation of upstream publishers;
- no change to existing MCP tool signatures or behavior;
- source/config schemas are reviewed before generators are changed;
- generated page changes are tested against real current data and edge-case fixtures.

---

## 9. Alpha acceptance criteria

The redesign is acceptable for implementation review only when all of the following are true:

### Product behavior

- A builder can search the live register, apply the primary filters, open a relevant row, and reach the official source in under one minute.
- The first viewport contains a real current dataset decision, not only positioning copy.
- The default ordering clearly leads with use-now evidence while preserving access to all other states.
- The primary action is the official source; MCP/API access is available but secondary.
- Evidence details are discoverable without turning every row into a prose wall.
- No dataset is hidden solely because its status is inconvenient.

### Truthfulness and contract safety

- Dataset count, health rollups, timestamps, statuses, URLs, and capability references come from current canonical inputs.
- No universal trust claim or unsupported accuracy claim is introduced.
- The 10-status taxonomy remains unchanged.
- The use/warn/stop presentation does not become a new taxonomy status.
- Machine surfaces do not contain a manually maintained tool count or stale route list.
- NPRA is redesigned only as an internal/unlinked surface and is not presented as publicly launched.

### Agent readiness

- Every public page has correct canonical metadata and semantic landmarks.
- `llms.txt`, `agent.json`, `mcp.json`, sitemap/robots, JSON-LD, and content-negotiated outputs resolve to current routes and capabilities.
- A machine consumer can discover the register, the detail/evidence path, and the MCP surface without parsing visual-only UI.
- The register’s key facts are represented in stable DOM/Markdown/JSON forms where the current architecture supports them.

### Accessibility and mobile

- Keyboard navigation and focus states work across search, filters, rows, expansion, and actions.
- Status meaning is available in text and is not communicated by color alone.
- Layout remains usable on a narrow mobile viewport.
- Touch targets are usable and dense tables do not become horizontally unusable without an intentional responsive treatment.
- Reduced-motion preferences are respected where animation exists.

### Regression safety

- Existing public routes remain available unless explicitly classified as an alias/redirect.
- Existing manifest, health, evidence, feed, badge, API, and MCP behavior remains intact.
- Methodology and NPRA are not silently removed.
- The repository contract, deterministic build, and relevant tests remain green.
- The live deployment is checked after implementation; a local render is not sufficient evidence.

---

## 10. Recommended implementation sequence after design approval

This is sequencing guidance, not implementation authorization.

### Slice 0 — Contract inventory and baseline

- Freeze the public route/artifact inventory.
- Resolve the current `16` versus `18` MCP capability-count discrepancy from canonical sources.
- Identify existing generators, templates, schemas, and contract tests.
- Capture current production screenshots/HTML snapshots and real-data edge cases.
- Confirm the exact status-to-use/warn/stop presentation mapping without changing the taxonomy.

### Slice 1 — Shared dark-precision shell

- Establish tokens, navigation, metadata, landmarks, focus behavior, and mobile foundations.
- Keep generated output ownership explicit.
- Apply only to a bounded surface before expanding.

### Slice 2 — Register baseline

- Generate the homepage register from real manifest/health/evidence inputs.
- Implement search, primary filters, default grouping/order, compact rows, and expanded evidence.
- Verify the under-one-minute use decision against real records, including stale and unknown-like edge states.

### Slice 3 — Builder and methodology surfaces

- Redesign `/learn.html` as the concise Verify → Fetch → Build path.
- Redesign methodology as a distinct reference surface.
- Align supporting public documentation and links.

### Slice 4 — Machine-plane parity

- Regenerate/validate `llms.txt`, `agent.json`, `mcp.json`, sitemap/robots, JSON-LD, and content-negotiated outputs.
- Verify every machine link and capability reference against the canonical route/config contract.

### Slice 5 — Internal NPRA consistency pass

- Apply the shared system to the internal NPRA preview.
- Keep it unlinked and excluded from public discovery.
- Do not add payment, publication, or buyer-access behavior.

### Slice 6 — Served-state verification

- Run the full repository and release invariants.
- Verify the deployed homepage, aliases, supporting pages, machine surfaces, accessibility, and mobile behavior.
- Review the result as v0.1 baseline; iterate based on observed use, not polish preference.

The generator deployment should be split into small implementation briefs with review between slices. An approved design brief or static prototype is not equivalent to approval of a production rewrite.

---

## 11. Explicit non-goals

This alpha does **not** authorize:

- new datasets or new upstream ingestion;
- a new status in the taxonomy;
- a new universal trust score;
- changes to MCP tool signatures or server behavior;
- x402, payments, Paddle, or monetization work;
- public NPRA publication;
- reanimation of OpenBao/Rekor or any signing/witness infrastructure;
- new Cloudflare or hosting infrastructure;
- redesigning DataPulse into a general-purpose data marketplace;
- claims of regulatory certification or objective truth;
- hand-editing generated pages or generated data artifacts;
- replacing the official source as the source of record;
- treating the existing prototype as production-ready code.

---

## 12. Approval gate for the next document

This brief is ready for Redza’s product/design review. The next document, only after approval, should be a **bounded implementation plan** that turns the slices above into small Codex briefs with exact file scope, tests, and review checkpoints.

No code, dispatch, commit, push, publication, route change, or infrastructure action is implied by this document.
