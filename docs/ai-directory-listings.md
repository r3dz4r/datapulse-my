# DataPulse — Directory Listing Drafts and Audit

**Created:** 2026-08-03
**Historical submission date:** 2026-08-18
**Last live audit:** 2026-09-01
**Document status:** Historical submission record plus current directory audit. Do not treat old payloads or third-party metadata as current DataPulse capability truth.

**Current result:** The aiecosystem.my listing is live and visible. The assistants.my submission has not been made. The official MCP Registry has one active latest record and four deprecated historical records. Glama’s listing exists but is stale/unhealthy.

**Context on fit:** DataPulse is an open-source, AI-ready evidence layer for Malaysian public data. It publishes freshness, licence, provenance, and source-condition evidence through machine-readable surfaces and a public read-only MCP server. Current capability counts belong to the live `mcp.json` advertisement, not this submission record.

**Audit references:** [aiecosystem.my](https://aiecosystem.my/) · [aiecosystem edit record](https://aiecosystem.my/edit-company?company_id=307) · [assistants.my](https://assistants.my/) · [official MCP Registry query](https://registry.modelcontextprotocol.io/v0.1/servers?search=io.github.r3dz4r%2Fdatapulse-my) · [Glama connector](https://glama.ai/mcp/connectors/io.github.r3dz4r/datapulse-my)

---

## Target 1 — aiecosystem.my (Malaysian AI Ecosystem Directory)

Submission URL: https://aiecosystem.my/submit-company
Edit path: https://aiecosystem.my/edit-company?company_id=307 (the current edit form displays a review warning for future changes; the public homepage is the evidence that the existing listing is live)

Form fields: Company Name · Website URL · Description (max 25 words) · Category

| Field | Value |
|---|---|
| Company Name | DataPulse MY |
| Website URL | https://www.data-pulse.my |
| Description (limit 25 words) | Open-source AI-ready trust layer for 389 official Malaysian public datasets, with freshness, licences, and a public read-only MCP server. No API key. |
| Category | AI Products (id=1) |

Description word count: **22 words** ✅ (within the 25-word cap)

**Category note:** the form offers: AI Academies / AI Communities / AI Products / AI Services / LLM Malaysia. "AI Products" is the closest fit for an open-source data layer. (No explicit "government data" or "developer tools" category here — the field is a single select.)

**Submission record (2026-08-18):** submitted manually by the operator with the values above. **Current live verification (2026-09-01):** the aiecosystem.my homepage visibly lists DataPulse MY with the submitted description and website. The edit-page review warning applies to future edits; it is not evidence that the existing listing is still pending. **Lesson learned:** a successful form response or review banner is weaker evidence than a re-fetched public listing.

---

## Target 2 — assistants.my (Malaysia's AI Assistant Directory)

Submission URL: https://assistants.my/submit
Form fields: Tool name · Website URL · Short desc (EN, max 120 chars) · Short desc (BM, max 120) · Category · Pricing model · Bahasa Malaysia support? · Built in Malaysia/SEA? · Logo URL (optional) · Email

**Current audit (2026-09-01):** no DataPulse listing was found on the assistants.my directory homepage. The form remains available, but no submission has been made. Use count-free copy unless the live machine contract is rechecked immediately before submission.

| Field | Value |
|---|---|
| Tool name | DataPulse MY |
| Website URL | https://www.data-pulse.my |
| Short desc (English, ≤120 chars) | AI-ready verification layer for Malaysian public datasets — licences, freshness, read-only MCP server. |
| Short desc (Bahasa Malaysia, ≤120 chars) | Lapisan pengesahan AI untuk data awam Malaysia — lesen, kesegaran, pelayan MCP baca sahaja. |
| Category | Developer Tools |
| Pricing model | Free |
| Bahasa Malaysia support? | Partial |
| Built in Malaysia/SEA? | Yes (origin, not hosting) |
| Logo URL (optional) | (leave blank, or point to a badge SVG from the repo) |
| Email | Retained privately by the operator; do not commit to the public repository. |

**Length checks:** Recalculate immediately before any submission; the count-free candidates above are intentionally not treated as permanently locked copy.

**Category note:** the form offers ... Developer Tools / Government / ... — "Developer Tools" remains the best fit now that DataPulse MY provides a machine-readable data layer and MCP server; "Government" also arguably fits (Malaysian official data). Picked Developer Tools.

**"Built in Southeast Asia?" flag (resolved 2026-08-06):** the form field is `sea_built` — a Yes/No for the whole SEA region. DataPulse MY is built by a Malaysian, on Malaysian official data, so the answer is **Yes**. The infra-host ambiguity is moot: the field asks about origin, not hosting.

**aiecosystem.my field re-check (2026-08-06):** the form has only 4 fields (name, url, description, category_id). No email, no "Built in MY" question — both earlier concerns are moot for this form.

---

## Current and historical facts

- Repo: https://github.com/r3dz4r/datapulse-my
- Current catalogue coverage must be read from `datapulse.json` and `health/latest.json` immediately before reuse.
- Current MCP capability must be read from `mcp.json`; do not copy a tool count into directory copy.
- Live agent index: https://www.data-pulse.my/llms.txt
- Live MCP server: https://mcp.data-pulse.my/mcp — public, read-only, machine-readable dataset discovery and evidence.
- Official MCP Registry: `io.github.r3dz4r/datapulse-my` — active latest record verified 2026-09-01 as version `3.4.6`; four older records are deprecated.
- Glama: listing exists but was last tested 2026-08-20 and currently reports stale/unhealthy metadata; not a current source of DataPulse capability truth.
- Trust boundary: DataPulse reports observable source evidence and does not certify upstream semantic truth.

The original 2026-08-18 aiecosystem payload is retained above as a historical submission record. It is not a reusable current capability manifest.

## Disposition

- [x] Review both historical submission drafts.
- [x] Verify aiecosystem.my listing on the public homepage — live as of 2026-09-01.
- [x] Confirm the aiecosystem edit page is a review-gated edit surface, not proof that the existing listing is pending.
- [x] Confirm assistants.my has no DataPulse listing — no submission performed.
- [x] Confirm the official MCP Registry has one active latest record and four deprecated historical records.
- [x] Mark Glama metadata as stale/unhealthy external metadata.
- [x] Remove personal submission contact detail from this public document.
- [x] Remove reusable 16-tool and count-heavy current claims.
- [ ] Reconcile served `agent.json` with served `mcp.json` before any future count-based submission copy.
- [ ] Decide separately whether to submit DataPulse to assistants.my after the machine-surface parity gate passes.

No external directory should be edited or resubmitted from this document without a fresh source audit, explicit operator approval, and a new dated submission record.
