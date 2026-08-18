# DataPulse MY — Directory Listing Drafts

**Created:** 2026-08-03
**Updated:** 2026-08-18
**Purpose:** Review drafts for submitting DataPulse MY to Malaysian AI directories. Aiecosystem.my submission in admin-review queue (submitted 2026-08-18 with 389-dataset / 16-tool / AI Products framing); awaiting admin approval before live. Assistants.my not yet submitted — pending aiecosystem verification.

**Context on fit:** DataPulse MY is an open-source, AI-ready trust layer for Malaysian public data. It tracks 389 official datasets across 11+ government portals with a 10-status taxonomy, freshness and licences, offers a machine-readable `llms.txt` index, and runs a public read-only 16-tool MCP server. Best-fit directories are registration-driven (not Open-AI-style marketplaces), and these are the two with clean submission paths.

---

## Target 1 — aiecosystem.my (Malaysian AI Ecosystem Directory)

Submission URL: https://aiecosystem.my/submit-company
Edit path: https://aiecosystem.my/edit-company?company_id=307 (admin-review queue — edit shows "Waiting for admin approval" banner after submit; do not retry via curl — POSTs land in queue, not immediate write)

Form fields: Company Name · Website URL · Description (max 25 words) · Category

| Field | Value |
|---|---|
| Company Name | DataPulse MY |
| Website URL | https://www.data-pulse.my |
| Description (limit 25 words) | Open-source AI-ready trust layer for 389 official Malaysian public datasets, with freshness, licences, and a public read-only MCP server. No API key. |
| Category | AI Products (id=1) |

Description word count: **22 words** ✅ (within the 25-word cap)

**Category note:** the form offers: AI Academies / AI Communities / AI Products / AI Services / LLM Malaysia. "AI Products" is the closest fit for an open-source data layer. (No explicit "government data" or "developer tools" category here — the field is a single select.)

**Submission status (2026-08-18):** submitted manually by operator with values above. Admin-review queue confirmed via screenshot showing "Your edit request has been submitted. Waiting for admin approval." Verifiable by re-fetching `edit-company?company_id=307` after admin applies. **Lesson learned:** see `datapulse-my-docs` skill Anti-pattern 6 — POST returns HTTP 200 with success banner but values do not persist until moderator approves; do not burn 4 curl variants diagnosing this.

---

## Target 2 — assistants.my (Malaysia's AI Assistant Directory)

Submission URL: https://assistants.my/submit
Form fields: Tool name · Website URL · Short desc (EN, max 120 chars) · Short desc (BM, max 120) · Category · Pricing model · Bahasa Malaysia support? · Built in Malaysia/SEA? · Logo URL (optional) · Email

**Note:** when this is submitted, use the same Option-2 description shape locked in for aiecosystem.my (22 words, "389 datasets", "read-only MCP", "No API key"). The form has different fields and slightly different word-count constraints — adjust to fit, but keep the substance.

| Field | Value |
|---|---|
| Tool name | DataPulse MY |
| Website URL | https://www.data-pulse.my |
| Short desc (English, ≤120 chars) | AI-ready trust layer for 389 Malaysian public datasets — licences, freshness, read-only MCP server. |
| Short desc (Bahasa Malaysia, ≤120 chars) | Lapisan kepercayaan AI: 389 set data awam Malaysia — kesegaran, lesen, pelayan MCP. |
| Category | Developer Tools |
| Pricing model | Free |
| Bahasa Malaysia support? | Partial |
| Built in Malaysia/SEA? | Yes (origin, not hosting) |
| Logo URL (optional) | (leave blank, or point to a badge SVG from the repo) |
| Email | mohd.redzafahmy@gmail.com |

**Length checks (verified 2026-08-18):**
- English desc: "AI-ready trust layer for 389 Malaysian public datasets — licences, freshness, read-only MCP server." → **99 chars** ✅ (≤120)
- BM desc: "Lapisan kepercayaan AI: 389 set data awam Malaysia — kesegaran, lesen, pelayan MCP." → **83 chars** ✅ (≤120)

**Category note:** the form offers ... Developer Tools / Government / ... — "Developer Tools" remains the best fit now that DataPulse MY provides a machine-readable data layer and MCP server; "Government" also arguably fits (Malaysian official data). Picked Developer Tools.

**"Built in Southeast Asia?" flag (resolved 2026-08-06):** the form field is `sea_built` — a Yes/No for the whole SEA region. DataPulse MY is built by a Malaysian, on Malaysian official data, so the answer is **Yes**. The infra-host ambiguity is moot: the field asks about origin, not hosting.

**Email note (resolved 2026-08-06):** user confirmed `mohd.redzafahmy@gmail.com` may be used for the review/submission.

**aiecosystem.my field re-check (2026-08-06):** the form has only 4 fields (name, url, description, category_id). No email, no "Built in MY" question — both earlier concerns are moot for this form.

---

## Facts baked into both drafts (all verified)

- Repo: https://github.com/r3dz4r/datapulse-my
- 389 official datasets across 11+ government portals, with a 10-status taxonomy
- Licence mix: 12 OGL Malaysia + 154 CC BY 4.0 (as published by the live agent index)
- Live agent index: https://data-pulse.my/llms.txt (HTTP 301 → https://r3dz4r.github.io/datapulse-my/llms.txt → HTTP 200)
- Live MCP server: https://mcp.data-pulse.my/mcp — public, read-only, 389 datasets, and 16 tools (`search_datasets`, `get_dataset`, `find_stale`, `find_anomalies`, `find_deteriorating`, `find_recovering`, `find_unreliable`, `find_schema_drift`, `check_reconciliation`, `get_provenance`, `get_evidence`, `verify_evidence`, `trust_verdict`, `verify_attestation`, `find_by_licence`, `usage_summary`)
- Official MCP Registry: `io.github.r3dz4r/datapulse-my` (status: active)
- Trust layer: 10-status taxonomy and a `_trust_summary` block in `health/latest.json`
- Dashboard: https://data-pulse.my → GitHub Pages dashboard with live health distribution
- Honest framing: `llms.txt` + MCP are forward-compatible agent infra, NOT a citation/ranking lever (do not overclaim)

Verified by mcpgrade: 100/100 Grade A on 16 tools, 0 findings, last audited 2026-08-17. Top 5% of the agent-usability rubric.

## Next steps

- [x] Review both drafts
- [x] **"Built in Malaysia/SEA?"** — resolved 2026-08-06: sea_built = Yes (origin, not hosting)
- [x] **Email consent** — resolved 2026-08-06: mohd.redzafahmy@gmail.com OK
- [x] **aiecosystem.my submission** — submitted 2026-08-18 with Option-2 description (22 words, 389 datasets, read-only MCP, No API key), category AI Products (id=1), URL https://www.data-pulse.my. Awaiting admin approval.
- [ ] **Verify aiecosystem.my** — re-fetch `edit-company?company_id=307` and confirm description contains "389" + "read-only MCP server" + category shows id=1 after admin applies.
- [ ] **assistants.my submission** — pending aiecosystem verification. Same description shape; Camofox typing API for React-controlled form (per `chapters/ai-directory-listings.md` of `datapulse-my-docs` skill).
- [x] **Description shape locked in:** Option 2 — "Open-source AI-ready trust layer for 389 official Malaysian public datasets, with freshness, licences, and a public read-only MCP server. No API key." (22 words). Do NOT use the 21-word variant with "live 16-tool MCP server" — verified as the form's moderated submission; the live-public version will say "read-only MCP server" because the assistant audience knows what that means without the count.

Nothing further will be submitted to aiecosystem.my. Once it verifies, the same payload is the assistants.my candidate.
