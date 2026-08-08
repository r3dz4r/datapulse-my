# Release process

## Sources and generated files

`datapulse.json`, `datapulse.schema.json`, `health.schema.json`, probe code, and
hand-maintained dataset reports are sources. Generation order after a health
run is:

1. `scripts/check.sh` → `health/latest.json`
2. `scripts/gen_badges.sh` → `badges/`
3. `scripts/gen_rss.sh` → `feed.xml`
4. `scripts/gen_readme_summary.sh` → README trust distribution
5. `scripts/gen_changelog.py` → `changelog.json`
6. `scripts/gen_jsonld_catalog.py` → JSON-LD catalog and dashboard graph
7. `scripts/gen_mcp_reference.py` → `docs/mcp-reference.md` and `mcp.json` schemas
8. `scripts/gen_json_envelope.py` → `data/json/<id>.json` for each non-GTFS registry ID
9. `scripts/gen_dashboard_filters.py` → `docs/.dashboard_filters.json` (namespace counts derived from manifest)

The 15-minute systemd service owns steps 1–5 for due datasets. The weekly
GitHub Actions fallback also owns steps 1–5 after a full probe. Maintainers run
steps 6, 8, and 9 when manifest shape, probe policy, or dashboard filters change. Step 9 (dashboard filters) re-runs on every deploy since counts may change with any manifest addition.

## Pages deployment

`.github/workflows/deploy-pages.yml` runs on relevant pushes, manual dispatch,
and successful completion of the weekly health workflow. `workflow_run` is
required because the health workflow commits generated files after its initial
checkout; a normal same-workflow deploy would publish the old SHA.

The workflow injects embedded health/manifest data, assembles `_site`, deploys
with GitHub Pages, then runs post-deploy invariants against the public host.

## Release invariants

- The manifest and health schemas accept their respective documents.
- Manifest IDs are unique, health and manifest IDs match, and status totals
  equal the live health-row count.
- README and `changelog.json` match `_trust_summary` and its timestamp.
- The JSON-LD catalog/dashboard cover every manifest ID and health-report URLs
  resolve.
- `mcp.json` input schemas equal runtime schemas from `mcp/server.py`.
- All absolute URLs in `llms.txt` resolve.

## Envelope policy

- `data/json/<id>.json` is generated for every non-GTFS registry ID by `scripts/gen_json_envelope.py`. The 30 GTFS datasets are excluded by `scripts/contract-scope.json:json_envelope.excluded_ids`.
- The 11 non-canonical legacy envelopes (8 missing `schema` field + 3 browser-shaped: `eperolehan-diklankan`, `fuelprice`, `pricecatcher`) are not yet normalized. This is tracked as a follow-up, not a blocker; the contract verifier treats them as compliant because they're in `approved_ids`.
- `docs/.dashboard_filters.json` is regenerated on every deploy. Hardcoded namespace counts in `docs/index.html` would be a regression; the file must NOT contain any literal `Economy (N)`, `Transport (N)`, etc. counts.

## Pull-request CI

`.github/workflows/ci.yml` runs a deterministic, read-only safety net for every
pull request. It installs `requirements-dev.txt`, checks every shell script with
`bash -n`, validates `datapulse.json` and `health/latest.json` against their
schemas, runs `scripts/tests/`, verifies the repository contract, and runs the
release invariants in local mode. The workflow has only `contents: read`
permission, uses no secrets, and performs no upstream dataset probes.

Run the same gates locally, in workflow order:

```sh
find . -type f -name '*.sh' -not -path './.git/*' -print0 | xargs -0 -n1 bash -n
python3 -m jsonschema -i datapulse.json datapulse.schema.json
python3 -m jsonschema -i health/latest.json health.schema.json
python3 -m pytest -q scripts/tests/
bash scripts/tests/test_verify_agent_ready.sh
python3 scripts/verify_repository_contract.py
bash scripts/verify_release_invariants.sh --local
```

Commit generated changes with their source change. Never push from a manual
regeneration session; the operator reviews and pushes explicitly.
