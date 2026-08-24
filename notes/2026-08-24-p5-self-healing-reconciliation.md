# P5 self-healing website reconciliation — 2026-08-24

## Strategic correction

P5 is not a batch of manual metadata/documentation fixes. Redza's requirement is that the whole website and its machine-readable public surfaces are auto-generated and self-healing from canonical runtime/source inputs.

**What would have caught the earlier mis-scope:** the roadmap gate should have classified every stale count, date, hostname, or ownership statement as a generator-ownership problem before proposing a hand edit.

## Current source-of-truth map

- Dataset identity/count/status: `datapulse.json`, `health/latest.json`, and the stable ten-status contract.
- MCP tools/descriptions/schemas/provenance: `mcp/server.py` and the live initialize/tools-list contract.
- MCP/discovery surfaces already partly generator-owned: `scripts/gen_mcp_reference.py`, `mcp.json`, `docs/mcp-reference.md`, marked MCP blocks in `llms.txt`, `README.md`, `agent.json`, and `docs/mcp-deploy.md`.
- Dashboard and generated HTML blocks: `scripts/embed_dashboard_data.py`, `scripts/gen_site_nav.py`, and the existing generated-page templates/markers.
- Service ownership/cadence: canonical units and scripts under `/home/redza/dotfiles` plus the repository's operations contract.
- Buyer API facts: API route/config/OpenAPI source, not hand-entered prose.

## Verified drift examples

- `mcp.json` still says “8-status health taxonomy” despite the ten-status contract.
- Public `agent.json` still has `last_updated: 2026-08-04`.
- `sitemap.xml` still uses `r3dz4r.github.io` URLs.
- Buyer API docs contain a malformed example hostname and stale `total: 375`.
- Operations docs describe root ownership while the current operating contract differs.

## P5 scope

Extend the existing generator architecture so all runtime-derived website/discovery/API/operations facts are generator-owned, marker-bounded or structured JSON, atomically written, idempotent, and dynamically verified. Preserve hand-authored explanatory prose only outside generator-owned blocks.

Required properties:

1. One canonical input per fact class; never replace one hardcoded value with another.
2. Existing generators are extended before a new generator is introduced.
3. Every generated Markdown/HTML fact section has exactly one marker pair; missing/duplicate markers fail loudly.
4. JSON outputs are load-modify-write with atomic replacement and stable key order.
5. Release-build and relevant health-cycle profiles regenerate the owned surfaces.
6. CI/release invariants compare generated surfaces against canonical inputs dynamically.
7. Two identical generator runs are byte-identical.
8. Public served/source parity is checked after deployment.

Non-goals: no new product claims, no taxonomy changes, no Cloudflare/P4B work, no runtime-fetch dashboard redesign, no API behavior change, and no hand-editing generated outputs.

**Next gate:** a complete P5 inventory and exact Terra/Sol implementation brief that names every owned surface, canonical input, marker, generator, profile, fixture, invariant, and non-goal before code dispatch.
