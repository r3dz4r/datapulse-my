# MCP Self-Grade — mcpgrade (2026-08-08)

**Date:** 2026-08-09 00:10 MYT (graded 2026-08-08)
**Tool:** [TengByte/mcpgrade](https://github.com/TengByte/mcpgrade) — Lighthouse-style scorecard for MCP agent usability
**Target:** Live DataPulse MY MCP server — `https://mcp.data-pulse.my/mcp`, v3.4.5
**Method:** Full MCP handshake (initialize → session → tools/list) against the live endpoint, snapshot saved to JSON, graded with mcpgrade.

---

## Result: D — 67/100

```text
  D   67/100

  Descriptions   ░░░░░░░░░░░░░░░░░░░░   0
  Naming         ████████████████████ 100
  Schema design  ██████████████████░░  90
  Token cost     ████████████████████ 100
  Consistency    ████████████████████ 100

  findings: 8 errors · 1 warning · 1 info
```

## Breakdown

| Category | Score | Verdict |
|---|---|---|
| **Descriptions** | **0/100** | ❌ **THE failure. 8 D004 errors.** |
| Naming | 100/100 | ✅ Clean, consistent |
| Schema design | 90/100 | ⚠️ 1 warning (S003), 1 info (S008) |
| Token cost | 100/100 | ✅ Efficient |
| Consistency | 100/100 | ✅ Uniform |

## The 8 errors — all the same rule

**D004 — "Parameter has no description"** on every tool's parameters:

| Tool | Missing descriptions |
|---|---|
| `search_datasets` | `query`, `licence`, `source`, `limit` (4 params) |
| `get_dataset` | `dataset_id` |
| `find_stale` | `max_age_hours` |
| `get_provenance` | `dataset_ids` |
| `find_by_licence` | `licence` |

This is **exactly** Teng Li's Finding #1: *"the ecosystem has an undocumented-parameter epidemic."* He writes:

> "The root cause is visible in the source of nearly all of them: schemas are generated from zod or OpenAPI definitions, and nobody adds `.describe()`. The type system knows `url: string`. The model needs to know which URL, in what format, with what constraints. Your schema generator is quietly stripping the single most important signal your tools have."

DataPulse MY ships parameter names + types but no descriptions. Same disease, same fix.

## The warnings

- **S003** (`find_stale`): declares parameters but no `required` array — model must guess which are optional. Fix: declare `required: []` explicitly (all optional) or list required params.
- **S008** (`get_provenance`): complex parameter `dataset_ids` has no example. Fix: add `examples` or `e.g.` in description.

## Bonus finding (not from mcpgrade)

`search_datasets` description says **"122 Malaysian public datasets"** — a hardcoded total that is now stale (registry is 166). This is the exact drift class Task 5's literal-detector was built to catch. Must be derived, not hardcoded.

## Fix path (one Codex dispatch, ~30-60 min)

The fix is entirely in `mcp/server.py` where tool schemas are declared:

1. Add a description to every parameter via `.describe()` (or the equivalent in the schema builder)
2. Declare `required` explicitly on every tool inputSchema
3. Add example values for complex params (dataset_ids, query)
4. Replace the hardcoded "122" in search_datasets with a derived count
5. Regenerate `docs/mcp-reference.md` + `mcp.json` via `scripts/gen_mcp_reference.py`
6. Re-grade — target: **A grade**

## What this buys us

- **Directly answers the Teng Li quality bar** (exec summary Tier 2.2): 1-in-3 MCP servers fail agent usability; we can be in the top tier with one focused fix.
- **Supports the trust-layer positioning**: "verified, agent-readable data" requires the agent to actually *use* the surface. A D-grade surface contradicts the trust claim.
- **Concrete, measurable, cheap**: ~1h Codex time.

---

**Verified-by:** Hermes Agent (operator-side)
**Verified-at:** 2026-08-09T00:10+08:00
**Snapshot:** /tmp/datapulse-mcp-tools.json (5 tools, live as of grading time)
