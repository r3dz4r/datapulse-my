# Release process

## Sources and generated files

`datapulse.json`, `datapulse.schema.json`, `health.schema.json`, probe code, and
extractor configuration are sources. `scripts/check.sh` writes
`health/latest.json`; the two generation profiles own everything derived from
that snapshot and the manifest:

- `health-cycle` owns `data/<id>.md`, `badges/`, the README trust-summary block,
  `feed.xml`, `catalog-snapshot.json`, its temporary `changelog.json` alias,
  `health/history*`, `health/trends.json`, `health/drift.json`, `health/reconciliation.json`, and `deltas/`. The 15-minute timer and weekly health
  workflow invoke it after a successful probe.
- `release-build` owns the `health-cycle` paths plus
  `data/json/<id>.json`, `data/jsonld/`, `docs/mcp-reference.md`, `mcp.json`,
  `docs/.dashboard_filters.json`, and the weekly
  `docs/trust-snapshot-<date>.{md,json}` roundup, plus the rendered
  `docs/health-methodology.html`. `scripts/gen_health_methodology_html.py`
  owns the last file and renders it from `docs/health-methodology.md` with
  `scripts/templates/health-methodology.html.tmpl`. The Pages deploy workflow
  invokes it before embedding and assembling the public artifact.

Treat generated paths as profile outputs: change their source or generator,
then run the owning profile instead of patching an output directly.

## Generation profiles

Two named profiles in `scripts/generate.sh` orchestrate the generators in reviewed order:

- `health-cycle` — invoked by the 15-minute timer / weekly GH Actions fallback after a `check.sh --due` produces a fresh `health/latest.json`. Owns `data/<id>.md`, `badges/`, `README.md` (trust-summary block only), `feed.xml`, `catalog-snapshot.json` plus the deprecated `changelog.json` alias, `health/history*`, `health/trends.json`, `health/drift.json`, `health/reconciliation.json`, signed `attestations/`, methodology-v1 scores, `datapulse.json` attestation refs, and `deltas/`.
- `release-build` — invoked by the Pages deploy workflow. Adds JSON envelopes (`data/json/`), JSON-LD (`data/jsonld/`), MCP discovery (`docs/mcp-reference.md`, `mcp.json`), dashboard filters (`docs/.dashboard_filters.json`), and the date-stamped trust snapshot (`docs/trust-snapshot-<date>.{md,json}`).

`release-build` numbers the source stamp as Step 0, followed by twenty-one artifact
generators through Step 21. Step 21 runs
`python3 scripts/gen_health_methodology_html.py` and owns
`docs/health-methodology.html`. Both profiles support `--list` for dry-run enumeration
of steps + owned paths. Both refuse to push or deploy — those actions remain
with their operational owner.

## Pages deployment

`.github/workflows/deploy-pages.yml` runs on relevant pushes, manual dispatch,
and successful completion of the weekly health workflow. `workflow_run` is
required because the health workflow commits generated files after its initial
checkout; a normal same-workflow deploy would publish the old SHA.

Timer-driven health commits carry a `[skip deploy]` trailer so their pushes do
not rebuild Pages. The trailer gates only `push` events; manual `workflow_dispatch`
and successful `workflow_run` events continue through the deployment workflow.

The workflow injects embedded health/manifest data, assembles `_site`, deploys
with GitHub Pages, then runs post-deploy invariants against the public host.

## Release invariants

The post-deploy block in `.github/workflows/deploy-pages.yml` is the canonical
7-gate check. Keep its executable checks byte-identical unless a workflow
change is reviewed separately:

1. The checked-out repository SHA equals the SHA captured for deployment.
2. The deployed dashboard mentions the live health-row count and embeds one
   dataset card per health row.
3. The deployed `llms.txt` reports the live count, mentions MCP, and lists all
   advertised MCP tools.
4. The deployed JSON-LD catalog is valid and contains one entry per health row.
5. The deployed `mcp.json` is valid and advertises the reviewed 15-tool order
   (including `trust_verdict` and `verify_attestation`) and 8-concrete-resource-plus-1-template order
   (including `datapulse://attestations`).
6. The deployed `health/latest.json`, `health/trends.json`, `health/drift.json`, and `health/reconciliation.json` are valid and contain the expected live health rows.
7. `scripts/verify_agent_ready.sh` and
   `scripts/verify_release_invariants.sh` accept the public surfaces.
8. Rendered `health-methodology.html` exists, is non-empty, and contains the
   level-one title from `docs/health-methodology.md`; this prevents a source-only
   documentation edit from reintroducing the public 404.

Public artifact fetches inside `scripts/verify_release_invariants.sh` retry HTTP
errors, including transient 404 responses, for a three-minute Pages-propagation
delay budget before rejecting the deployed release.

A failure blocks the workflow after deployment and identifies the rejected
surface. Resolve the source or generation issue, rerun the same
`release-build` → embed → deploy sequence, and do not waive the failing gate.

## MCP source synchronization

Each `release-build` invocation starts with `python3 scripts/bump_mcp_source_version.py`,
which stamps the current commit SHA into:

- `mcp/server.py` — exposed in JSON-RPC `initialize.serverInfo.source_commit_sha`
- `mcp.json` — discovery doc field `server.source_commit_sha`

`python3 scripts/verify_mcp_deployment.py` reads the deployed MCP service's
`source_commit_sha` and compares against the repo HEAD. Exit codes:

- `0` — deployed matches HEAD
- `1` — mismatch (deployed service lags)
- `2` — endpoint unreachable (not a sync failure, transient network)

Run this after any MCP code change. If it reports `MISMATCH`, the
deployed service needs a redeploy (copy `mcp/server.py` +
`requirements.txt` to `/home/redza/.local/share/datapulse-mcp/` +
`systemctl --user restart datapulse-mcp.service`). The verify script
is read-only — it doesn't write to the deployed service.

## Envelope policy

- `data/json/<id>.json` is generated for every non-GTFS registry ID by `scripts/gen_json_envelope.py`. The 30 GTFS datasets are excluded by `scripts/contract-scope.json:json_envelope.excluded_ids`.
- The non-canonical legacy envelopes (8 missing `schema` field + 3 browser-shaped: `eperolehan-diklankan`, `fuelprice`, `pricecatcher`) are not yet normalized. This is tracked as a follow-up, not a blocker; the contract verifier treats them as compliant because they're in `approved_ids`.

The reviewed MCP order is `search_datasets`, `get_dataset`, `find_stale`,
`find_anomalies`, `find_deteriorating`, `find_recovering`, `find_unreliable`,
`find_schema_drift`, `check_reconciliation`, `get_provenance`, `get_evidence`,
`verify_evidence`, `find_by_licence`. The live verifier unit suite is required
before release.
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
