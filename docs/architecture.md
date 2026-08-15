# Architecture

DataPulse MY is a read-only trust layer. Official publishers remain the source
of record; this repository stores metadata, observations, small samples, and
generated discovery surfaces rather than replacing upstream datasets.

## System boundaries

```text
official sources
  data.gov.my / OpenDOSM / BNM / MET / DOE / KKM / KPDN
       |
       v
scripts/check.sh + extractors + GTFS helper + Camofox
       |
       v
health/latest.json (merge with prior snapshot in --due mode)
       |
       +--> health/history.jsonl --> health/history_daily.json --> health/trends.json
                                      \--> health/drift.json
                                      \--> health/reconciliation.json
       +--> badges/ + feed.xml + README summary + catalog-snapshot.json
       +--> deltas/<cycle>.json
       +--> record-evidence/<vertical-id>/{<run-date>,latest}.json
       +--> datapulse.json + health/latest.json --> catalog-graph.json
       +--> data/json/<id>.json
       +--> data/jsonld/catalog.json + dashboard JSON-LD
       |
       v
GitHub Pages artifact --------------------> data-pulse.my
       |
       +--> manifest, reports, health, samples, agent discovery

mcp/server.py --fetches published manifest + health + trends + drift + reconciliation--> read-only MCP tools
```

`get_evidence` projects pipeline receipts from `health/latest.json`, while
`verify_evidence` performs an independent ephemeral transport check and never
feeds the probe pipeline.

## Sources and probes

`datapulse.json` is the registry and scheduling contract. Direct sources use
HEAD or GET probes; GTFS feeds use `scripts/probe_gtfs.py`; JavaScript-rendered
DOE, iDengue, and ePerolehan pages use Camofox. Content-date extractors provide
freshness evidence when HTTP headers do not.

The 15-minute timer calls `scripts/check.sh --due`. Only due rows are probed,
then their results are merged with preserved rows from the prior snapshot
in manifest order. A successful snapshot drives the `health-cycle`
generation profile.

The frozen-snapshot publisher runs `scripts/gen_health_history.py --compact`
after validating and installing the new `health/latest.json`, and before
staging any artifacts. The writer upserts one observation per manifest dataset
using `(dataset_id, cycle)` as its key. Raw observations remain in
`health/history.jsonl` for 90 days by default; older observations are merged
into per-dataset, per-day aggregates in `health/history_daily.json`. Both
history artifacts are additive; `health/latest.json` remains the compatibility
surface for the dashboard, MCP server, badges, and feed.
`gen_trends.py` then scans the bounded history window and publishes the complete
`health/trends.json` artifact used by trend, anomaly-reliability,
unreliable-publishing, and reliability-summary MCP tools and resources. Reliability
measures publish timeliness, not uptime.
`gen_drift.py` then publishes structural and record-count evidence to
`health/drift.json`.
`gen_reconciliation.py` then applies reviewed seed → exact canonical URL → guarded exact semantic title precedence and publishes `health/reconciliation.json`; differences require human review and are not proof either source is wrong.

## Generation profiles

Two profiles in `scripts/generate.sh` orchestrate the generators in
reviewed order, with explicit path ownership:

- `health-cycle` — 12 steps (`gen_data_reports.sh` →
  `gen_badges.sh` → `gen_readme_summary.sh` → `gen_rss.sh` →
  `gen_catalog_snapshot.py` → `gen_health_history.py --compact` → `gen_trends.py` → `gen_drift.py` →
  `gen_dataset_deltas.py` → `gen_record_evidence.py` →
  `gen_catalog_graph.py`). Owns `data/<id>.md`, `badges/`, README trust
  summary, `feed.xml`, `catalog-snapshot.json`, the deprecated
  `changelog.json` alias, history, `deltas/`, opt-in `record-evidence/`, and
  `catalog-graph.json`, `health/trends.json`, `health/drift.json`, and `health/reconciliation.json`. Invoked by the timer and the
  weekly fallback after a successful probe.
- `release-build` — includes the `health-cycle` generators plus the
  release-only steps (`gen_llms_summary.py` →
  `gen_json_envelope.py --force` → `gen_jsonld_catalog.py` →
  `gen_mcp_reference.py` → `gen_dashboard_filters.py` →
  `gen_trust_snapshot.py`). Owns all
  health-cycle paths plus `data/json/<id>.json`, `data/jsonld/`,
  `docs/mcp-reference.md`, `mcp.json`, `docs/.dashboard_filters.json`, and
  `docs/trust-snapshot-<date>.{md,json}`.
  Invoked by the Pages deploy.

## Vertical pilots

Verticals opt into deeper, row-level processing with `vertical: true`, a
`record_evidence_schema`, and a raw `record_source_url` in `datapulse.json`.
All three fields are optional for backwards compatibility. The generator is a
normal profile step but exits successfully without output when no vertical is
declared.

The sole current pilot is `pharmaceutical_products`, using
`record-evidence/v1`. Its full daily envelope is
`record-evidence/pharmaceutical_products/<run-date>.json`; `latest.json`
retains aggregate counts and a deterministic excerpt for discovery. The CSV
ingestion and base classification code are generic, while the reviewed NPRA
profile supplies the registration-number rule, products freshness window, and
OSA linkage pointers.

The ten statuses and NPRA products cadence are small local constants borrowed
from the pharma engine. DataPulse does not import or clone that module, because
the public pipeline must not depend on a sibling repository or its venv. The
pilot does not yet resolve OSA pointers against the licence datasets, ingest
cancelled registrations as alternatives, or emit record/graph diffs.

## Catalogue relationships

`catalog-graph.json` links catalogue entries using only literal declared
metadata and records the matched physical fields plus the manifest schema URL
on every edge. `same_steward` requires both manifest `source` (publisher
sub-unit) and `steward` (agency) to match, while `same_agency` requires only
`steward` and is emitted when `source` differs or is absent; the other edge
kinds are exact `geography`, `series_code`, and `schema_id` matches plus the
directional `successor_to` relation declared by `supersedes` (the target is the
predecessor). Free-text `geo_coverage` is deliberately not interpreted as
`geography`. The artifact publishes connected/isolated coverage and reports
precision as unmeasured until a reviewed truth set exists; fuzzy matching and
record-level entity resolution are outside this graph.

## MCP source-to-deployment sync

`release-build` first step is `python3 scripts/bump_mcp_source_version.py`,
which stamps the current commit SHA into `mcp/server.py` and `mcp.json`
before any generator introspects them. The deployed MCP service exposes
the SHA in the JSON-RPC `initialize.serverInfo.source_commit_sha` field;
`python3 scripts/verify_mcp_deployment.py` compares it against the
repo HEAD and exits 0 (match), 1 (mismatch), or 2 (unreachable).

## Machine-readable envelopes

After a successful health snapshot, the per-dataset `data/json/<id>.json`
envelopes are generated by `scripts/gen_json_envelope.py` from the
manifest and the freshest health row. As of 2026-08-09 the policy is:

- Every non-GTFS manifest ID has a machine-readable envelope.
- The 30 GTFS datasets are excluded by `scripts/contract-scope.json:json_envelope.excluded_ids` and surface their GTFS samples instead (`samples/gtfs-static/`, `samples/gtfs-realtime/`).

The canonical envelope has 16 ordered keys (`schema`, `id`, `status`,
`last_checked`, `freshness_days`, `next_expected_update`,
`refresh_frequency`, `record_count`, `date_range`, `fields`, `checks`,
`known_quirks`, `breaking_changes`, `reproducibility`, `licence`,
`attribution`). Unavailable scalar values are `null`; unavailable
arrays are `[]`. The contract verifier enforces the scope; missing
files fail CI.

## Publication and MCP

`.github/workflows/deploy-pages.yml` invokes `release-build`, then the
embed step injects manifest + health + dashboard filters into
`docs/index.html`, then assembles the Pages artifact, deploys via
`actions/deploy-pages@v4`, and runs post-deploy invariants.

The MCP service runs independently on the VPS as `datapulse-mcp.service`
(user unit). It reads the same published manifest + health that Pages
serves; it cannot write upstream data or repository state.

### Dashboard filter generator

`scripts/gen_dashboard_filters.py` runs during the Pages deploy
workflow (before the embed step) and writes
`docs/.dashboard_filters.json`. The dashboard renders its category
filter buttons from this artifact via the embedded
`__DATAPULSE_DATA__.dashboardFilters` payload; the buttons are not
hand-maintained in `docs/index.html`.
