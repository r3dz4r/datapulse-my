# DataPulse MY — Directory Listing Drafts

**Created:** 2026-08-03
**Updated:** 2026-08-04
**Purpose:** Review drafts for submitting DataPulse MY to Malaysian AI directories. Nothing submitted yet — user review first.

**Context on fit:** DataPulse MY is an open-source, AI-ready trust layer for Malaysian public data. It tracks 122 official datasets (92 general + 30 GTFS transit) with freshness and licences, offers a machine-readable `llms.txt` index, and runs a public read-only MCP server. Best-fit directories are registration-driven (not Open-AI-style marketplaces), and these are the two with clean submission paths.

---

## Target 1 — aiecosystem.my (Malaysian AI Ecosystem Directory)

Submission URL: https://aiecosystem.my/submit-company.php
Form fields: Company Name · Website URL · Description (max 25 words) · Category

| Field | Value |
|---|---|
| Company Name | DataPulse MY |
| Website URL | https://github.com/r3dz4r/datapulse-my |
| Description (limit 25 words) | Open-source AI-ready trust layer for 122 official Malaysian public datasets, with freshness, licences, an agent index, and a live MCP server. |
| Category | AI Products |

Description word count: **21 words** ✅ (within the 25-word cap)

**Category note:** the form offers: AI Academies / AI Communities / AI Products / AI Services / LLM Malaysia. "AI Products" is the closest fit for an open-source data layer. (No explicit "government data" or "developer tools" category here — the field is a single select.)

---

## Target 2 — assistants.my (Malaysia's AI Assistant Directory)

Submission URL: https://assistants.my/submit
Form fields: Tool name · Website URL · Short desc (EN, max 120 chars) · Short desc (BM, max 120) · Category · Pricing model · Bahasa Malaysia support? · Built in Malaysia/SEA? · Logo URL (optional) · Email

| Field | Value |
|---|---|
| Tool name | DataPulse MY |
| Website URL | https://github.com/r3dz4r/datapulse-my |
| Short desc (English, ≤120 chars) | AI-ready trust layer for 122 Malaysian public datasets, with freshness, licences, llms.txt and a live MCP server. |
| Short desc (Bahasa Malaysia, ≤120 chars) | Lapisan kebolehpercayaan data awam Malaysia sedia-AI: 122 set data, kesegaran, lesen, llms.txt dan pelayan MCP aktif. |
| Category | Developer Tools |
| Pricing model | Free |
| Bahasa Malaysia support? | Partial |
| Built in Malaysia/SEA? | ⚠️ See note below |
| Logo URL (optional) | (leave blank, or point to a badge SVG from the repo) |
| Email | mohd.redzafahmy@gmail.com |

**Length checks:**
- English desc: "AI-ready trust layer for 122 Malaysian public datasets, with freshness, licences, llms.txt and a live MCP server." → **113 chars** ✅ (≤120)
- BM desc: "Lapisan kebolehpercayaan data awam Malaysia sedia-AI: 122 set data, kesegaran, lesen, llms.txt dan pelayan MCP aktif." → **117 chars** ✅ (≤120)

**Category note:** the form offers ... Developer Tools / Government / ... — "Developer Tools" remains the best fit now that DataPulse MY provides a machine-readable data layer and MCP server; "Government" also arguably fits (Malaysian official data). Picked Developer Tools.

**"Built in Southeast Asia?" flag (resolved 2026-08-06):** the form field is `sea_built` — a Yes/No for the whole SEA region. DataPulse MY is built by a Malaysian, on Malaysian official data, so the answer is **Yes**. The infra-host ambiguity is moot: the field asks about origin, not hosting.

**Email note (resolved 2026-08-06):** user confirmed `mohd.redzafahmy@gmail.com` may be used for the review/submission.

**aiecosystem.my field re-check (2026-08-06):** the form has only 4 fields (name, url, description, category_id). No email, no "Built in MY" question — both earlier concerns are moot for this form.

---

## Facts baked into both drafts (all verified)

- Repo: https://github.com/r3dz4r/datapulse-my
- 122 official datasets (92 general + 30 GTFS transit: 16 static + 14 realtime)
- Licence mix: 12 OGL Malaysia + 110 CC BY 4.0
- 301 commits
- Live agent index: https://data-pulse.my/llms.txt (HTTP 301 → https://r3dz4r.github.io/datapulse-my/llms.txt → HTTP 200)
- Live MCP server: https://mcp.data-pulse.my/mcp — public, read-only, 122 datasets, and 5 tools (`search_datasets`, `get_dataset`, `find_stale`, `get_provenance`, `find_by_licence`)
- Official MCP Registry: `io.github.r3dz4r/datapulse-my` (status: active)
- Trust layer: 8 health statuses (`fresh`, `aging`, `stale`, `degraded`, `browser-dependent`, `unreachable`, `unknown`, `unknown-freshness`) and a `_trust_summary` block in `health/latest.json`
- Dashboard: https://data-pulse.my → GitHub Pages dashboard with live health distribution
- Namespaces: economy (45), government_open_data (35), transport (30), environment (3), weather (1), healthcare (1), other (7)
- Weekly health cron
- Honest framing: `llms.txt` + MCP are forward-compatible agent infra, NOT a citation/ranking lever (do not overclaim)

## Next steps (awaiting user)

- [x] Review both drafts
- [x] **"Built in Malaysia/SEA?"** — resolved 2026-08-06: sea_built = Yes (origin, not hosting)
- [x] **Email consent** — resolved 2026-08-06: mohd.redzafahmy@gmail.com OK
- [ ] Decide: submit both / submit one / neither

Nothing will be submitted until both are resolved.
