# DataPulse MY — Release notes

This file is the source of truth for tagged releases. GitHub Releases is auto-generated from the section matching each tag.

## v0.4.0 — 2026-08-06

**Status:** active development. Per-dataset reports under `data/{id}.md` may lag the live `health/latest.json` snapshot — regeneration is a near-term fix. The trust layer (live health + status badges + RSS) is current.

**Milestone coverage:**
- 122 official Malaysian datasets across 7 namespaces (economy, government_open_data, transport, environment, weather, healthcare, other)
- 30 GTFS transit feeds (16 static + 14 realtime) for KTMB, Prasarana, BAS.MY
- AI-ready index: `llms.txt` + 122 health-report markdown files
- Public read-only MCP server (`mcp.data-pulse.my/mcp`, 5 tools, Streamable HTTP)
- Official MCP Registry entry active (`io.github.r3dz4r/datapulse-my`)
- Live dashboard at `data-pulse.my` with namespace filters, status badge grid, per-dataset cards
- Honest 8-status trust taxonomy (`fresh`, `aging`, `stale`, `degraded`, `browser-dependent`, `unreachable`, `unknown`, `unknown-freshness`) — never a blanket green checkmark

**Highlights since v0.3.x:**
- Deploy chain hardened: nginx misconfiguration that blocked the MCP endpoint is fixed; the GitHub Pages `llms.txt` validator now passes cleanly
- Dashboard bug fixed: per-dataset Sample JSON/CSV links previously resolved to doubled URLs (`github.com/.../blob/main/https://raw.githubusercontent.com/...`); they now route correctly
- README reorganised: the daily reference data section is grouped by source (BNM, MET, DOE, KKM, OpenDOSM, data.gov.my) instead of listed under a misleading "Daily Reference Data (Bank Negara Malaysia)" header
- `docs/ai-directory-listings.md` drafts ready for submission to `aiecosystem.my` and `assistants.my` (Malaysian AI directories)

**Known gaps (target: v0.4.1):**
- `data/{id}.md` regeneration not wired into the per-tick deploy chain — last regenerated 2026-07-31
- One dataset (`gtfs_static_prasarana_bus_kuantan`) is `discontinued` per upstream
- BNM financial reports page redirects to a JS-only interface; not yet integrated
- KKM iDengue, DOE APIMS, ePerolehan continue to be `browser-dependent` (Camofox probes)

**Migration notes:**
- Public MCP endpoint unchanged: `https://mcp.data-pulse.my/mcp`
- Tool surface unchanged (5 tools: `search_datasets`, `get_dataset`, `find_stale`, `get_provenance`, `find_by_licence`)
- `llms.txt` URL pattern unchanged

---

## Earlier

Pre-release history lives in git. The first tagged release is `v0.4.0`.
