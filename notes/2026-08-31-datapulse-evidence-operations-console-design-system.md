# DataPulse v0.1 design system — Evidence Operations Console

**Date:** 2026-08-31
**Status:** Proposed product/design system for review
**Product name:** DataPulse
**Primary surface:** Live verified dataset register
**Primary user:** AI and agent builders deciding whether a public dataset is usable

---

## 1. Design-system decision

DataPulse should look and behave like an **Evidence Operations Console**: a live instrument for deciding whether a source is usable, what was observed, and what should happen next.

This is not a generic AI landing page, a marketing dashboard, or a cyberpunk terminal. Its visual authority comes from:

- current observable data;
- compact evidence presentation;
- explicit uncertainty;
- source-first actions;
- stable machine-readable contracts;
- restrained, high-contrast operational design.

### Product promise

> **Verify Malaysian data before your AI agent uses it.**

The interface must make that promise demonstrable in the first viewport, rather than explaining it through a long prose introduction.

---

## 2. Inspiration synthesis

The system is deliberately composed from several relevant patterns rather than copied from one brand.

| Source/pattern | What DataPulse takes | What DataPulse rejects |
|---|---|---|
| UI/UX Pro Max: Real-Time / Operations Landing | Live state first, operational indicators, trust signals, concise action path | Generic SaaS conversion sections and trial-first CTAs |
| UI/UX Pro Max: Data-Dense Dashboard | High information density, compact rows, scannable controls, status visibility | KPI-card overload and chart-first hierarchy |
| UI/UX Pro Max: Drill-Down Analytics | Summary → evidence detail, context preservation, progressive disclosure | Deep nested navigation that hides the first decision |
| UI/UX Pro Max: API Developer Portal / Trust & Authority | Quickstart grammar, contract clarity, technical authority, source/reference actions | Documentation walls before the user sees the product |
| c0mm0-style verified register | Live register as the primary object, per-entry access/evidence receipt, checked timestamps | Treating the register as a secondary catalogue below marketing copy |
| Decube-style evidence/lineage hierarchy | Traceable evidence and concrete verbs before methodology | Abstract trust language without a visible proof object |
| Linear-style dark precision | Near-black surfaces, restrained borders, dense but calm engineering feel | Excessive glow, decorative gradients, ornamental motion |

### Resulting style name

**Evidence Operations Console**

Supporting descriptors:

- dark precision;
- live verified register;
- source-first;
- evidence-forward;
- agent-readable;
- progressive disclosure.

---

## 3. Design principles

### 3.1 Show the decision object first

The first meaningful object is one real dataset row with its status, observed time, source, and action. The product explanation is subordinate to the evidence object.

### 3.2 Evidence is local to the action

A user should not have to leave the dataset row and search a separate methodology page to understand why a source is marked usable, reviewable, or unsuitable.

### 3.3 Preserve uncertainty

Unknown, stale, inaccessible, conflicting, and incomplete signals are product states, not visual defects to hide. The interface must show the limitation and the next sensible action.

### 3.4 Density without noise

Use compact structures, but establish hierarchy through spacing, grouping, typography, and luminance. Do not compress every field into a wall of tiny text.

### 3.5 One primary action per context

For a dataset row, the primary action is the **official source**. Evidence/detail and MCP/API access are secondary. The page-level primary action is finding or opening a relevant dataset, not a generic signup.

### 3.6 Human and machine surfaces share a semantic core

The same source, status, timestamp, limitation, and action model should be understandable through visible HTML, accessibility structure, Markdown, JSON-LD, and canonical machine artifacts.

### 3.7 Product name and geography are separate

The product is always called **DataPulse**. Geography belongs in descriptive copy such as “Malaysian public data,” never as a suffix in the product name.

### 3.8 No unsupported authority claims

DataPulse reports observed evidence conditions. It does not replace the official publisher, establish substantive truth, guarantee accuracy, or certify an agent.

---

## 4. Visual language

### 4.1 Canvas and surfaces

Use a dark, low-emission system with luminance steps rather than heavy shadows:

| Token | Proposed value | Purpose |
|---|---|---|
| `--dp-canvas` | `#090d12` | Page background |
| `--dp-surface` | `#111820` | Primary panels |
| `--dp-surface-raised` | `#17212b` | Evidence expansion and raised controls |
| `--dp-surface-inset` | `#0b1117` | Inputs and recessed values |
| `--dp-border` | `#2b3946` | Dividers and controls |
| `--dp-text` | `#edf4f8` | Primary text |
| `--dp-text-muted` | `#a7b7c3` | Secondary text |
| `--dp-text-subtle` | `#78909f` | Placeholder and tertiary text |

Avoid pure-white backgrounds, large decorative gradients, and dark-on-dark borders that disappear.

### 4.2 Brand and semantic colors

Brand accents should remain recognizably DataPulse while status colors communicate operational posture:

| Semantic role | Proposed value | Meaning |
|---|---|---|
| `--dp-accent` | `#56c6e9` | Primary interactive accent and source action |
| `--dp-accent-strong` | `#9ee7fb` | Links, focus, high-emphasis accent |
| `--dp-use` | `#54d69a` | Evidence posture: use |
| `--dp-warn` | `#f1bd62` | Evidence posture: review/warn |
| `--dp-stop` | `#ff8a8a` | Evidence posture: stop |
| `--dp-reference` | `#94b7ff` | Evidence posture: reference-use |

Every status must include a visible text label. Color is reinforcement, never the sole carrier of meaning.

### 4.3 Typography

Use a **system-first** stack. Do not reintroduce a remote font dependency merely to imitate a dashboard style.

- Body: `Inter`, `ui-sans-serif`, `system-ui`, sans-serif where available.
- Identifiers and machine values: `ui-monospace`, `SFMono-Regular`, `Menlo`, `Consolas`, monospace.
- Body baseline: 16px with line-height around 1.5.
- Display heading: responsive 26–40px, tight line-height, restrained negative tracking.
- Section heading: 15–18px, medium/bold weight.
- Labels and status metadata: 12–13px, uppercase or compact sentence case with deliberate tracking.
- Dataset IDs, timestamps, tool names, and counts: tabular or monospace figures where useful.

UI/UX Pro Max suggested Fira Code/Fira Sans for technical dashboards. DataPulse does **not** adopt that remote-font dependency in the alpha because core readability must remain independent of external assets.

### 4.4 Shape and elevation

- Radius: low or modest, generally 0–8px for register surfaces.
- Borders: 1px semantic border, not heavy card outlines.
- Elevation: luminance stepping between canvas, panel, raised surface, and inset.
- Status: use a border/accent edge plus text chip; do not use a full-card red/green wash.
- Focus: 2–3px high-contrast outline with visible offset.

The register should feel like an instrument, not a collection of floating promotional cards.

---

## 5. Layout grammar

### 5.1 Page structure

The canonical register page uses this order:

1. compact product header;
2. concise live-register heading;
3. live observation context;
4. search and filter controls;
5. decision-posture legend;
6. full dataset register;
7. expandable evidence within each row;
8. supporting links to methodology and machine surfaces.

The first viewport must reveal at least one real dataset row. Do not place a large hero, multi-column marketing pitch, or methodology table between the heading and the register.

### 5.2 Desktop register

At desktop widths:

- constrain the main content to a readable maximum width;
- use a three-zone row where practical:
  - identity and decision;
  - compact metadata;
  - action/evidence controls;
- keep dataset name and identifier visually dominant;
- keep source action visually primary;
- use small, stable gaps rather than excessive card padding;
- align timestamps and counts consistently.

### 5.3 Mobile register

At mobile widths:

- stack identity, metadata, and actions vertically;
- keep the page width inside the viewport with valid `calc()` sizing;
- allow long dataset names, publishers, URLs, and identifiers to wrap;
- make actions full-width or clearly separated touch targets;
- keep search input and filter controls at least 44px high;
- keep the first dataset row understandable without horizontal scrolling;
- preserve the evidence summary as an obvious expandable control.

Target review widths:

- 390px phone;
- 768px tablet;
- 1024px desktop transition;
- 1440px wide desktop.

### 5.4 Spacing rhythm

Use a restrained 4/8px rhythm:

- 4px: inline label gaps;
- 8px: control and metadata gaps;
- 12px: compact row padding;
- 16px: panel padding;
- 24px: major section separation;
- 32px: page-level separation;

Whitespace should separate decisions, not create a long empty hero.

---

## 6. Component specifications

### 6.1 Product header

**Purpose:** persistent identity and minimal orientation.

- Product name: `DataPulse`.
- One current-observation link.
- No oversized logo treatment.
- Same placement across public surfaces.
- Visible active/current state where applicable.

### 6.2 Live observation strip

**Purpose:** prove that the page is connected to a current published observation.

Show:

- current check/observation timestamp;
- dataset total derived from canonical input;
- explicit unavailable state when the observation cannot be loaded.

Do not hardcode a count or imply that every dataset is probed on every scheduler tick.

### 6.3 Search and filter bar

**Purpose:** get from 389 records to a relevant dataset quickly.

Required controls:

- labelled dataset search;
- status filter;
- publisher/category filter;
- access-method filter;
- recency filter.

Rules:

- labels remain visible;
- checked/active state is visibly distinct;
- controls are keyboard reachable;
- mobile layout wraps without overflow;
- empty results explain how to recover;
- interaction state should be deep-linkable in the production implementation where compatible with the current static architecture.

### 6.4 Decision legend

Show the four presentation postures:

- use;
- warn;
- stop;
- reference-use.

The legend explains presentation posture while the row retains the exact underlying taxonomy status.

### 6.5 Register row

**Primary object:** one evidence-qualified dataset decision.

Required visible fields:

- dataset name;
- dataset ID;
- exact underlying status;
- derived decision posture;
- publisher/category;
- access method;
- recency/last observed signal;
- official-source action;
- evidence/detail action;
- MCP/API action where applicable.

Row rules:

- compact by default;
- source action first in visual hierarchy;
- status text never omitted;
- long values wrap;
- no universal score introduced;
- no manually maintained capability count;
- no false green aggregate that hides problematic records.

### 6.6 Evidence disclosure

Use a native progressive-disclosure control such as `<details>` where appropriate.

Expanded evidence may include:

- observed time;
- content date;
- record signal;
- evidence reference;
- freshness reason;
- limitations;
- source/licence context;
- relevant drift/anomaly/reconciliation information.

The evidence block should answer “why this posture?” without becoming a duplicate methodology page.

### 6.7 Actions

Action hierarchy:

1. `Open official source` — primary;
2. `Evidence and detail` — secondary;
3. `MCP/API access` — secondary.

All actions must have visible labels, adequate touch targets, focus styles, and clear hover/pressed states. Do not rely on icon-only affordances.

### 6.8 Empty, unavailable, and error states

Every dynamic surface needs an explicit state for:

- no matching datasets;
- health snapshot unavailable;
- missing evidence signal;
- malformed or incomplete record;
- unavailable machine surface.

Use language such as “not observed” where the evidence is absent. Never replace missing data with a neutral-looking fake value.

---

## 7. Interaction model

### 7.1 First-minute task

A successful first session is:

1. arrive at the register;
2. search a topic or dataset;
3. filter if needed;
4. read the posture and last observed signal;
5. open the official source;
6. optionally inspect evidence or connect through MCP/API.

The interface should support this without requiring a user to read a positioning essay first.

### 7.2 Progressive disclosure

Default view: decision essentials.
Expanded view: evidence and limitations.
Reference surface: methodology and machine contracts.

Do not move essential source identity or status information behind a click.

### 7.3 Motion

Motion is optional and subordinate to evidence clarity:

- use 150–300ms transitions for focus/expand states if added;
- do not animate rows in a way that disrupts scanning;
- do not animate width/height to create layout shift;
- respect `prefers-reduced-motion`;
- no decorative scanlines, glitch effects, pulsing alerts, or glowing status text in the alpha.

### 7.4 State preservation

Production implementation should preserve search/filter state and scroll context when opening/closing evidence or returning from a detail path, within the limits of the static deployment architecture.

---

## 8. Content and naming rules

### Product naming

- Always: **DataPulse**.
- Geographic descriptor: “Malaysian public data” or equivalent.
- Never append the geographic descriptor to the product name.
- Technical repository slugs and URLs remain technical identifiers, not visible brand copy.

### Claims

Use:

- “observed”;
- “published health snapshot”;
- “official source”;
- “evidence reference”;
- “not observed”;
- “source of record.”

Avoid:

- “source of truth”;
- “guaranteed accuracy”;
- “verified truth”;
- “safe agent”;
- “certified” without an actual certification;
- “always current”;
- unsupported market/category superlatives;
- active payment or x402 claims.

### Tense and time

Use absolute timestamps or explicit relative wording backed by the current artifact. Do not imply that a record is currently true merely because it was observed previously.

---

## 9. Accessibility and quality gates

These are non-negotiable for the public register:

- primary and secondary text contrast meets WCAG AA targets;
- status meaning is available in text, not color alone;
- all controls have visible labels and accessible names;
- keyboard order follows visual order;
- focus rings remain visible;
- touch targets are at least 44px where practical;
- body text remains readable at 16px or above;
- no horizontal scrolling at 390px;
- headings follow a logical hierarchy;
- evidence disclosure exposes expanded/collapsed state to assistive technology;
- reduced-motion preference is respected;
- long identifiers and source names wrap rather than truncate without recovery.

### Performance gates

- no external font or analytics dependency for the core register;
- no large decorative media above the fold;
- register rendering remains deterministic;
- below-fold evidence should not introduce avoidable blocking work;
- future interactive filtering must avoid per-keystroke expensive full-page rebuilds.

---

## 10. Surface-specific application

| Surface | Design role | Application of this system |
|---|---|---|
| `/` | Product register | Full Evidence Operations Console; live rows first |
| `/landing.html` | Compatibility alias | Resolve to `/`; no second prose wall |
| `/learn.html` | Builder path | Same shell; concise Verify → Fetch → Build workflow |
| `/health-methodology.html` | Reference | Same shell; evidence rules and limitations, lower in the primary journey |
| NPRA internal surface | Future proof | Same tokens and components, not linked or publicly discovered in the alpha |
| `llms.txt`, `agent.json`, `mcp.json`, JSON-LD, sitemap, robots | Machine plane | Canonical names, routes, claims, and capabilities derived from source contracts |

---

## 11. What the current preview proves—and does not prove

The current local preview proves:

- the register can render all 389 records from real inputs;
- posture-first ordering is possible;
- the visual direction can use dark precision;
- rows can expose source, evidence, and machine actions;
- the product name can be rendered as DataPulse only;
- the output can remain self-contained and deterministic.

It does not yet prove:

- production homepage integration;
- fully functional search/filter behavior;
- genuine mobile browser reflow, because the current Camofox viewport operation did not change the page CSS viewport;
- final token contrast across every component;
- route/discovery migration for all public surfaces;
- production acceptance of the new information architecture.

The preview is therefore a validated design direction and data-rendering foundation, not the shipped homepage.

---

## 12. Implementation sequence

1. Complete a genuine mobile-browser review or equivalent responsive render.
2. Freeze the design tokens and component contract.
3. Integrate the register into the canonical homepage generator in a bounded slice.
4. Replace `/landing.html` with the compatibility alias and update canonical links.
5. Apply the shared shell to Learn and methodology.
6. Align machine-readable surfaces and contract tests.
7. Keep the internal NPRA surface out of public discovery.
8. Run served-state, accessibility, mobile, determinism, and regression verification.

Each slice requires visual review before the next. Do not bundle all public surfaces into one Codex dispatch.

---

## 13. Final design verdict

The right design language for DataPulse is **not** “dark dashboard” in the generic sense.

It is:

> **A calm, evidence-first operations console for deciding whether public data is usable by an agent.**

That means the register is the product surface, evidence is the proof object, source access is the primary action, and visual restraint is part of the trust model.
