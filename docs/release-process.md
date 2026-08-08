# Release process

## Sources and generated files

`datapulse.json`, `datapulse.schema.json`, probe code, and hand-maintained
dataset reports are sources. Generation order after a health run is:

1. `scripts/check.sh` → `health/latest.json`
2. `scripts/gen_badges.sh` → `badges/`
3. `scripts/gen_rss.sh` → `feed.xml`
4. `scripts/gen_readme_summary.sh` → README trust distribution
5. `scripts/gen_changelog.py` → `changelog.json`
6. `scripts/gen_jsonld_catalog.py` → JSON-LD catalog and dashboard graph
7. `scripts/gen_mcp_reference.py` → `docs/mcp-reference.md` and `mcp.json` schemas

The 15-minute systemd service owns steps 1–5 for due datasets. The weekly
GitHub Actions fallback also owns steps 1–5 after a full probe. Maintainers run
steps 6–7 when manifest, health metadata, or MCP interfaces change.

## Pages deployment

`.github/workflows/deploy-pages.yml` runs on relevant pushes, manual dispatch,
and successful completion of the weekly health workflow. `workflow_run` is
required because the health workflow commits generated files after its initial
checkout; a normal same-workflow deploy would publish the old SHA.

The workflow injects embedded health/manifest data, assembles `_site`, deploys
with GitHub Pages, then runs post-deploy invariants against the public host.

## Release invariants

- The schema accepts all 166 unique manifest rows.
- Health and manifest IDs match and status totals equal 166.
- README and `changelog.json` match `_trust_summary` and its timestamp.
- The JSON-LD catalog/dashboard cover all 166 IDs and health-report URLs resolve.
- `mcp.json` input schemas equal runtime schemas from `mcp/server.py`.
- All absolute URLs in `llms.txt` resolve.

Commit generated changes with their source change. Never push from a manual
regeneration session; the operator reviews and pushes explicitly.
