---
type: operational concept
title: DataPulse MY Wiki Quickstart
description: Route coding agents through DataPulse MY’s read-only trust-layer boundary to the dataset contract, MCP integration, or operations and contribution guidance. Use this page to identify the authoritative artifact, safe change owner, and focused verification path before editing.
tags: [quickstart, routing, read-only, datasets, MCP, operations]
verified:
  - by: openwiki/0.4.3
    at: 2026-08-29T10:52:57.734Z
sources:
  - id: openwiki-source-164e2da859b5277df81c7d94
    resource: repo://.github/workflows/ci.yml
  - id: openwiki-source-378b07edcc123a4ad7e94363
    resource: repo://.github/workflows/deploy-cloudflare-pages.yml
  - id: openwiki-source-6d4b4e707b8d60b6ccfa3425
    resource: repo://.github/workflows/openwiki-update.yml
  - id: openwiki-source-b801e3030787d5f9ac603f52
    resource: repo://config/public-surfaces.json
  - id: openwiki-source-53cc7c2d889d1fead610dba7
    resource: repo://datapulse.json
  - id: openwiki-source-1a180b1bc921529852474c20
    resource: repo://health/latest.json
  - id: openwiki-source-770cce86fff48e46671ba377
    resource: repo://llms.txt
  - id: openwiki-source-83fe3cd6171f4749991ccee9
    resource: repo://mcp.json
  - id: openwiki-source-a142396a7263c3e58ad95b67
    resource: repo://mcp/server.py
  - id: openwiki-source-23775c3de52f3ab95a13cb8b
    resource: repo://README.md
  - id: openwiki-source-f9fafda300b014057921ac73
    resource: repo://scripts/check.sh
  - id: openwiki-source-d470dc444e0001374b65b519
    resource: repo://scripts/generate.sh
  - id: openwiki-source-9ba932a354745d3f1bf461f2
    resource: repo://scripts/verify_agent_ready.sh
generated: { by: "openwiki/0.4.3", at: "2026-08-29T10:52:57.734Z" }
---

# DataPulse MY Wiki Quickstart

DataPulse MY is a read-only metadata and evidence layer around upstream public
datasets. It records what an upstream source publishes, its declared licence and
provenance, observed access and freshness signals, schema/record evidence, and
known quirks; it is **not the official publisher**. Upstream sources remain
authoritative for substantive data, content, licensing, and attribution.

The canonical website origin is **https://www.data-pulse.my**. The current
manifest contains **389 datasets**, and the public MCP catalogue exposes **16
read-only tools**. Treat those as live facts from the sources of record, not as
values to copy from an older page.

## Start here: route the task

| If the task is about… | Start with | Safe investigation / change boundary |
|---|---|---|
| Finding a dataset, changing identity, licence, steward, namespace, URL, cadence, expected count, or schema contract | [Dataset manifest, health evidence, and schema](datasets.md) | Inspect `datapulse.json` and `datapulse.schema.json`; follow the dataset ID into its health row, `data/<id>.md`, envelope or sample. Change the canonical input, then use its generator and URL/contract checks rather than hand-editing derived output. |
| Agent discovery, tool/resource behaviour, MCP sessions, provenance, live evidence checks, or the buyer boundary | [Read-only MCP and buyer API integrations](mcp.md) | Use `mcp.json` for the advertised wire contract and `mcp/server.py` plus its tests for implementation behaviour. Keep public MCP reads separate from the authenticated `/api/v1/` buyer API; `verify_evidence` is ephemeral and does not update health. |
| Health probes, generated artifacts, scheduled jobs, deployment, attestations, rollback, contribution, or release testing | [Health operations, release workflows, and safe change boundaries](operations.md) | Identify the owner (`health-cycle` versus `release-build`), inspect commands with `bash scripts/generate.sh <profile> --list`, and run focused gates. Do not treat a generated artifact as an independent source of truth. |
| OpenWiki wording or canonical fact refresh | This page and [OpenWiki instructions](INSTRUCTIONS.md) | Derive claims from the repository sources of record. Only the allowed OpenWiki outputs may change; OpenWiki documents the system and does not regenerate health or dataset envelopes. |

## The trust-layer model

The principal joins are stable dataset identity and published observations:

- `datapulse.json` is the canonical registry. Its `datasets` array supplies IDs,
  official URLs, stewards, custodians, licences, attribution, cadence,
  geography, namespace, expected record counts, and health-report paths.
- `health/latest.json` is the complete published health snapshot. A due health
  run probes selected rows and merges unchanged rows with new observations, so
  consumers should not mistake it for a log containing only recently probed
  datasets. Its statuses distinguish freshness, reachability, browser
  dependency, degradation, discontinued upstream lifecycle, and missing evidence.
- Reports, JSON envelopes, badges, feeds, catalogues, attestations, and discovery
  indexes are projections owned by generators. Regenerate them from their source
  inputs; do not “fix” one projection in isolation.
- `llms.txt`, `config/public-surfaces.json`, and `mcp.json` describe public entry
  points and declared capabilities. They do not grant DataPulse authority over
  upstream content.

A health label is evidence classification, not a semantic endorsement. In
particular, `unknown-freshness` means no defensible freshness signal was found,
`browser-dependent` records an access limitation, and `reference` is for
versioned lookup data where date freshness does not apply. The latest snapshot
currently reports 94 `fresh`, 134 `aging`, 144 `stale`, 1 `discontinued`, 5
`browser_dependent`, and 11 `reference` datasets; consult the snapshot for the
current checked timestamp and details.

## Agent entrypoints

For a first machine-readable pass, fetch the canonical `llms.txt` from
`https://www.data-pulse.my/llms.txt`; it links the manifest, health snapshot,
MCP advertisement, and dataset reports. For native agent access, connect to
`https://mcp.data-pulse.my/mcp` using Streamable HTTP and no authentication:

```json
{
  "mcpServers": {
    "datapulse-my": {
      "transport": "streamable-http",
      "url": "https://mcp.data-pulse.my/mcp"
    }
  }
}
```

MCP is a read-only consumer of published repository artifacts. Initialize the
session before requesting tool or resource discovery. Use `search_datasets`
then `get_dataset` for discovery and a dataset’s current metadata/health; use
`get_provenance` or `get_evidence` when citation and pipeline evidence matter.
Use `find_stale`, `find_anomalies`, `find_deteriorating`, `find_recovering`,
`find_unreliable`, or `find_schema_drift` for published risk signals. Use
`verify_attestation` for attestation verification and `verify_evidence` only for
its constrained transport check: its result is temporary and never updates
`health/latest.json`.

## Safe change and failure rules

1. **Locate ownership first.** Manifest and source metadata changes belong to the
   dataset contract; probe observations belong to the health cycle; public
   discovery, MCP metadata, envelopes, and dashboard packaging belong to the
   release build. `scripts/generate.sh` orchestrates these profiles but never
   commits, pushes, or deploys.
2. **Preserve complete snapshots.** A health probe may record an individual source
   failure and continue, but malformed snapshots, generator errors, missing
   artifacts, stale health commits, URL drift, or contract violations must fail
   closed. Concurrent health cycles skip on the lock rather than racing.
3. **Respect access and legal boundaries.** Browser-dependent sources require the
   configured Camofox sidecar; missing Camofox is reported honestly rather than
   silently bypassed. Probes do not bypass authentication, CAPTCHAs, or terms of
   service, and contributions must not add credentials, cookies, personal data,
   or copied source records.
4. **Separate publication from observation.** The canonical website workflow
   validates `health/latest.json`; health-only changes use the health path, while
   source/configuration/workflow changes use the release profile. A website or
   endpoint definition is not proof that external infrastructure is currently
   available.

## Focused verification

Before changing a contract or generated surface, inspect ownership without
running generators:

```bash
bash scripts/generate.sh health-cycle --list
bash scripts/generate.sh release-build --list
```

For repository changes, the CI-focused checks are:

```bash
python3 -m pytest -q scripts/tests/ mcp/tests/
bash scripts/tests/test_verify_agent_ready.sh
python3 scripts/verify_repository_contract.py
python3 scripts/verify_openwiki.py
python3 scripts/check_url_drift.py
bash scripts/verify_release_invariants.sh --local
python3 scripts/fact_lint.py
```

For a local published-surface check, run
`bash scripts/verify_agent_ready.sh --local`; without `--local` it fetches the
canonical public surfaces with retries and rejects non-canonical discovery
hosts. Interpret failures as evidence to investigate the owning source or
workflow, not as a reason to patch a derived JSON file manually.

## Sources of record

- [`config/public-surfaces.json`](../config/public-surfaces.json) — canonical origins and declared public artifacts.
- [`datapulse.json`](../datapulse.json) — dataset registry and metadata contract input.
- [`health/latest.json`](../health/latest.json) — current aggregate health evidence.
- [`mcp.json`](../mcp.json) — advertised MCP endpoint, taxonomy, tools, and schemas.
- [`README.md`](../README.md) — public purpose, trust posture, and consumer guidance.
- [`llms.txt`](../llms.txt) — agent discovery index.
- [`openwiki/INSTRUCTIONS.md`](INSTRUCTIONS.md) — documentation generation contract.

## Canonical facts

- Canonical website: https://www.data-pulse.my
- Datasets: 389 datasets
- MCP server: 16 read-only tools
