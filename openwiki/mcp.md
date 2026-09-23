---
type: "Reference"
title: "Read-only MCP Integrations"
description: "Reference for DataPulse's unauthenticated read-only MCP contract, published-artifact flow, deployment verification, and the current repository integration boundary."
tags: ["MCP", "integrations", "deployment"]
verified:
  - by: openwiki/0.4.3
    at: 2026-08-29T10:52:57.734Z
sources:
  - id: openwiki-source-00defdc44caf88700f10e4ce
    resource: repo://deploy/cloudflared/config.yml.example
  - id: openwiki-source-47d1bd4a82ddd11fc2a418dd
    resource: repo://deploy/nginx/datapulse-mcp.conf
  - id: openwiki-source-910861586532d062f16e5be7
    resource: repo://docs/mcp-deploy.md
  - id: openwiki-source-83fe3cd6171f4749991ccee9
    resource: repo://mcp.json
  - id: openwiki-source-a142396a7263c3e58ad95b67
    resource: repo://mcp/server.py
  - id: openwiki-source-73db7b1811c4b31152a67a0b
    resource: repo://mcp/tests/test_server.py
  - id: openwiki-source-c497d4cb0975a9d5d866792f
    resource: repo://scripts/verify_mcp_deployment.py
generated: { by: "openwiki/0.4.3", at: "2026-08-29T10:52:57.734Z" }
---

# Read-only MCP Integrations

DataPulse serves one integration surface from this repository:

- **Public MCP:** `POST https://mcp.data-pulse.my/mcp`, unauthenticated, for reading the published Malaysian catalogue and its derived evidence artifacts.

The canonical website origin is **https://www.data-pulse.my**. The current catalogue contains **418 datasets** and the MCP advertisement describes **19 read-only tools**. `mcp.json` is the generated wire-level advertisement, while `mcp/server.py` is the implementation contract; current source and tests take precedence over older documentation.

## Public MCP contract

The endpoint uses MCP streamable HTTP with `POST`. A client must establish a session before discovery: `initialize`, then `notifications/initialized`, then `tools/list` (and similarly resource discovery). Calling `tools/list` before initialization is intentionally rejected by FastMCP. The initialize response exposes the server version and source markers (`source_commit_sha`, `source_commit_date`) so a deployment can be compared with repository HEAD.

```mermaid
sequenceDiagram
    participant C as MCP Client
    participant E as MCP Edge
    participant S as FastMCP Server
    participant P as Published Pages
    C->>E: POST initialize
    E->>S: Forward MCP request
    S-->>C: serverInfo and session id
    C->>E: POST notifications/initialized
    C->>E: POST tools/list or resources/list
    E->>S: Forward session request
    S-->>C: Contract discovery with public cache hints
    C->>E: POST tools/call or resources/read
    E->>S: Forward read request
    S->>P: Fetch published JSON artifacts
    P-->>S: Manifest health and derived artifacts
    S-->>C: Read-only result
```

*Figure 1. MCP session initialization, discovery, and published-artifact read flow.*

All tools advertise `readOnlyHint: true`, `destructiveHint: false`, `idempotentHint: true`, and `openWorldHint: true`. FastMCP applies a public five-minute cache hint (`ttl_ms: 300000`, scope `public`) to discovery and cacheable resource results. Tool calls are logged with bounded, credential-redacted arguments and a result summary; usage records are written as daily JSONL under `DATAPULSE_USAGE_DIR` (default `/var/lib/datapulse/usage`). This ledger is for usage reporting, not a data mutation path.

### The 19 read-only tools

The authoritative list and schemas are in `mcp.json`:

| Tool | Purpose and notable inputs |
| --- | --- |
| `search_datasets` | Natural-language title search, optional case-insensitive `source` and canonical/alias `licence`, `limit` 1–50. Exact title, substring, and term scoring are title-weighted; the current manifest has no description field for search. |
| `get_dataset` | Merge one exact manifest entry with its latest health record, freshness signal, access dependency, `last_verified`, and schema version. Missing health is represented as `unknown`, not inferred healthy. |
| `find_stale` | Find aging, stale, or degraded datasets, missing health rows, or an over-age health snapshot. |
| `find_anomalies` | Return pipeline-published update anomalies, optionally filtered by detection mode, reliability grade, and a limit up to 200. |
| `find_deteriorating` | Return published worsening freshness trends, optionally requiring a minimum anomaly rate. |
| `find_recovering` | Return published improving freshness trends. |
| `find_unreliable` | Return low publish-reliability grades; reliability means timeliness of successful freshness observations, not uptime. |
| `find_schema_drift` | Return published structural or record-count drift, optionally requiring structural transitions. |
| `check_reconciliation` | Resolve a dataset ID or exact name to its published cross-source group; discrepancies require human review and do not prove which source is wrong. |
| `get_provenance` | Return citation metadata and compact pipeline evidence for 1–418 dataset IDs. |
| `get_evidence` | Return the complete published evidence receipt without MCP-side recomputation. |
| `verify_evidence` | Perform a constrained ephemeral transport check for one direct-access dataset. |
| `trust_verdict` | Join published attestation facts, unsigned methodology-versioned score, and existing health/trend/drift/reconciliation evidence; it does not verify signatures or re-probe. |
| `verify_attestation` | Verify an Ed25519 attestation (L1), optionally replay daily chain heads to a Git-tag anchor (L2); L3 is the separate `verify_evidence` check. |
| `find_by_licence` | Enumerate dataset summaries for a canonical licence or supported alias. |
| `usage_summary` | Aggregate anonymous persisted MCP tool usage by inclusive ISO date range, tool, dataset, and trust-score bucket. |

### Resources

The server exposes eight fixed JSON resources and one template, as advertised by `mcp.json`:

- `datapulse://index` — lightweight ID, status, title, source, licence, and namespace index for all 418 datasets.
- `datapulse://anomalies` — current anomaly results.
- `datapulse://trends` — freshness trend and publish-reliability artifact.
- `datapulse://reliability` — counts by reliability grade.
- `datapulse://drift` — schema and record-count drift artifact.
- `datapulse://reconciliation` — cross-source reconciliation artifact.
- `datapulse://attestations` — latest attestation index and chain head.
- `datapulse://licences` — licence-to-dataset counts.
- `datapulse://{dataset_id}` — on-demand full published manifest entry.

MCP reads `datapulse.json`, `health/latest.json`, and the published trend, drift, reconciliation, and attestation artifacts. It does not become the health owner and does not write those artifacts.

## Live verification is intentionally limited

`verify_evidence` is not a second health pipeline. It only compares transport receipts against the latest published evidence: request/final URL, HTTP status, `Last-Modified`, and content length where available. It streams a GET without downloading the body, has a 30-second timeout, follows at most five redirects, and caches the result for 600 seconds under an in-process lock. Results explicitly mark content date, record count, and first-row/shape fingerprint as unverified and are ephemeral; **they never update health**.

Safety gates refuse browser-dependent/Camofox datasets, non-HTTPS URLs, credentials, non-default HTTPS ports, and hosts outside the reviewed allowlist (`api.bnm.gov.my`, `api.data.gov.my`, `eqms.doe.gov.my`, `hansard.parlimen.gov.my`, `idengue.mysa.gov.my`, `storage.data.gov.my`, `storage.dosm.gov.my`, `www.eperolehan.gov.my`). Unsafe redirects are rejected as well. A failed request yields an `unreachable` result; a transport mismatch yields `mismatch`; a browser-dependent or otherwise blocked source remains `not_verifiable`.

## Deployment and source synchronization

The production path is:

```text
Cloudflare edge → cloudflared tunnel → nginx at 127.0.0.1:8443 → MCP at 127.0.0.1:8788
```

`deploy/cloudflared/config.yml.example` routes the public hostname to the local nginx TLS listener and contains a deployment-time tunnel UUID placeholder. `deploy/nginx/datapulse-mcp.conf` accepts only the `/mcp` location, allows the documented dashboard/GitHub origins (or empty Origin), limits requests to 1 request/second with burst 20 and returns 429 on excess, caps bodies at 256 KiB, disables proxy buffering/cache, and permits long-lived sessions with a 3600-second read timeout. Cloudflare's connecting IP is used at the local proxy boundary. The MCP server itself runs as the enabled user service `datapulse-mcp.service`; `docs/mcp-deploy.md` documents its installed paths and operations.

Run locally with Python 3.11+ and the documented dependencies:

```sh
uv run --with fastmcp,httpx python mcp/server.py
```

The local defaults are `DATA_BASE=https://www.data-pulse.my`, `MCP_HOST=127.0.0.1`, and `MCP_PORT=8788`; `REQUEST_TIMEOUT_SECONDS` is 30. The release process updates the source marker using `scripts/bump_mcp_source_version.py`. To verify a deployment, `scripts/verify_mcp_deployment.py` performs the protocol-valid initialize/initialized/tools-list sequence, reads `serverInfo.source_commit_sha`, and compares it with `git rev-parse HEAD`. It reports `UNREACHABLE` when the endpoint cannot be inspected and `MISMATCH` when source and deployment differ; a successful discovery is not proof that every published artifact is current.

Focused MCP tests use FastMCP's in-memory client plus checked-in/live artifacts. They assert the current protocol, all 19 tools, eight resources and one template, cache hints, read-only annotations, tool parameter contracts, evidence limitations, attestation tamper rejection, drift/reconciliation behavior, and live-artifact matching. Network access is required for the live portions:

```sh
uv run --with fastmcp,httpx pytest mcp/tests/ -v
```

## Integration boundary

This repository serves one integration surface: the public, unauthenticated, read-only MCP endpoint described above. It contains no authenticated API application. Commercial NPRA control belongs to Malaysia Data Engine and is not operated by DataPulse. `config/public-surfaces.json` still declares an `https://api.data-pulse.my` origin alongside the website and MCP origins; this page does not assert that any surface is currently available.

The MCP surface must not be widened by adding secrets, credentials, browser-dependent probing, or MCP-side health writes.

## Neighboring documentation and invariants

Use `/openwiki/datasets.md` for catalogue semantics and `/openwiki/operations.md` for health-generation operations. This page covers the integration boundary: the MCP surface is public, read-only, and artifact-backed.

Canonical facts: **https://www.data-pulse.my**, **418 datasets**, and **19 read-only tools**.

## Canonical facts

- Product: DataPulse
- Canonical website: https://www.data-pulse.my
- Datasets: 418 datasets
- MCP server: 19 read-only tools
