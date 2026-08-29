# Headless 360 MCP design vs. DataPulse's 16-tool surface

**Date:** 2026-08-27
**Status:** research / design note — no code change
**Context:** Salesforce + Anthropic announced *Claudeforce* (2026-08-26). Salesforce's
*Headless 360* MCP Server uses a materially different tool-surface strategy than
DataPulse's current 16-tool MCP server. This note distills the pattern and tests it
against the trust layer's goals.

Sources: Salesforce Headless 360 announcement + docs, Salesforce Headless 360 MCP
Server reference, VentureBeat Claudeforce coverage, Anthropic Claudeforce release.

---

## The Headless 360 pattern: small stable surface, big action library

Salesforce's Headless 360 MCP Server deliberately exposes **four tools only**,
backed by a continuously growing library of operations:

| Tool | Role |
|---|---|
| `Discover` | Semantic search across a vector index of every action/skill the server can perform. Returns ranked candidates. |
| `Describe` | Returns the technical contract for an action — APIs, params, dependencies, ordered steps. |
| `Dispatch` | Runs the chosen action. Routes to the right endpoint; enforces access guard before anything runs. |
| `Dispatch (Read-Only)` | Read-only variant — never changes data or config. |

The agent's *tool surface stays small and stable* while the *action surface scales
independently*. They deliberately do **not** expose "thousands of tools" — the four
tools are a fixed contract; the library grows behind them.

Their rationale: an agent shouldn't have to know every endpoint up front. It asks
"what can I do?" (Discover), gets a specification (Describe), then acts (Dispatch).
Permissions are enforced per-transaction by the platform trust layer, not re-built.

---

## How this contrasts with DataPulse's current 16-tool surface

DataPulse lives at `https://mcp.data-pulse.my` with **16 read-only tools** covering
the 10-status trust taxonomy (389 datasets). Trade-off:

### Strength of the 16-tool design
- **Explicit, discoverable capabilities.** Each tool names a distinct capability
  (search datasets, get status, get provenance, list sources, etc.). A developer or
  agent can see the full capability list from the tool registry.
- **Read-only by design** — every tool is read-only, matching the trust-layer
  contract (no mutations, no upstream writes).
- **Good for the current audience** (developer-facing MCP users who know what they
  want and can pick a tool directly).

### Cost of the 16-tool design
- **Tool bloat compounds.** Every new dataset dimension / new query shape wants a new
  tool → surface grows linearly with capability. The tool registry becomes the rate
  limiter: each addition is a new schema, a new annotation, a new test, a new docs
  entry.
- **Discoverability scales with tool *count*, not tool *design*.** A user who wants
  "the current state of Malaysian pharma" must know which of 16 tools answers that.
- **No semantic search.** The four-tool pattern lets the agent *ask what exists*
  (Discover) rather than guessing tool names.

---

## Why this matters for the trust layer

The Salesforce pattern maps onto DataPulse's exact position:

1. **DataPulse is already "governed, trusted data exposed via MCP"** — that's the
   trust-layer thesis validated by the biggest enterprise vendors. The Headless 360
   model is essentially "the enterprise equivalent of the trust layer": real,
   verified, permissioned data an agent can safely call.

2. **The 4-tool pattern is a candidate 2.0 design.** `Discover → Describe → Dispatch`
   over a growing action library would let the trust layer scale to *hundreds* of
   query forms (datasets × status × time-window × source) without a tool for each.
   The surface stays stable; the "action library" (which would still be read-only)
   grows.

3. **"Dispatch (Read-Only)"** is exactly the trust-layer posture: agents can consume,
   never mutate. A read-only variant of this pattern is a natural fit.

### But — don't leap. The gap that matters:

- The 4-tool pattern solves a **surface-scaling** problem DataPulse doesn't yet have
  (it has 16 tools, not thousands).
- DataPulse's current moat work is about **evidence and provenance**, not tool count.
  A rewrite to Discover/Describe/Dispatch is a big surface change that shouldn't ride
  along with evidence/attestation work.
- The 16-tool explicit surface is arguably *better for the current adoption goal*
  (developers reading tool names) than a semantic-search layer that presumes agent
  fluency.

---

## Recommendation (tentative; operator to decide)

Keep the 16-tool surface for now. **Study** the Discover/Describe/Dispatch pattern as
the design if/when DataPulse outgrows a flat tool registry — specifically if the
action library ("query shapes") starts exceeding ~30-40 tools. Do not couple a
surface redesign to the attestation/evidence window work already in flight.

If a redesign is ever pursued, the highest-value single adoptable idea is
`Discover`-style semantic search over the *existing* dataset + status vocabulary —
it adds discoverability without changing the tool contract.

---

## Key sources
- Salesforce: *Introducing Salesforce Headless 360* — "everything is an API, MCP
  tool, or CLI command."
- Salesforce Headless 360 MCP Server reference — `Discover/Describe/Dispatch`,
  `Dispatch (Read-Only)`, per-transaction trust enforcement.
- VentureBeat — Claudeforce; "you'll never need its app again."
