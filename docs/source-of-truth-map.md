# Source-of-truth map

This document maps important DataPulse facts to their canonical inputs, generated surfaces, and verification paths. It exists to prevent documentation from becoming a second, stale implementation.

## Canonical fact map

| Fact or contract | Canonical source | Public/generated consumers | Verification |
|---|---|---|---|
| Dataset identity and catalogue membership | `datapulse.json` and `datapulse.schema.json` | README, dataset pages, JSON/JSON-LD catalogue, dashboard, MCP responses | Repository contract and schema validation |
| Current health observation | `health/latest.json` and health schema | Dashboard, badges, RSS, trust snapshots, MCP health responses | Health schema, pipeline checks, served-state read-back |
| Health status meaning | `health-methodology.md` plus `status-semantics.md` | Methodology HTML, dashboard legend, agent guidance | Methodology tests and status vocabulary checks |
| MCP endpoint and capability advertisement | Runtime/source MCP contract and `mcp.json` | `agent.json`, `llms.txt`, MCP reference, API reference, quickstart | MCP source-sync and deployment verification |
| MCP tool schemas and annotations | MCP runtime source | Generated MCP reference and machine advertisements | MCP tests and source/deployment parity checks |
| Evidence object shape | `evidence-receipt-spec.md`, current evidence schema/code | Evidence responses, per-dataset envelopes, attestation references | Schema and evidence verification tests |
| Release identity | Git source revision and release metadata | Release verification, machine advertisements, changelog | Reproducible build and served source-identity checks |
| Source licence and attribution | Dataset metadata plus cited publisher terms | Dataset pages, JSON envelopes, MCP results, governance guide | Dataset contract and licence review |
| Public route inventory | Public-surface configuration | Sitemap, robots/discovery, documentation links, deployed pages | Public-discovery and route verification |
| Operational ownership | `operations.md` and deployment configuration | Maintainer runbooks | Service/timer and deployment checks |
| Historical observations | Immutable health history, snapshots, digests, and attestations | Reproducibility and audit material | Reconstruction and digest verification |

## Fact classes

### Live facts

Examples include current health, counts, checked timestamps, current route state, and deployed source identity. These must be generated, fetched, or labelled with an observation time. A hand-authored number is not current merely because it appears in a recent commit.

### Contract facts

Examples include status semantics, evidence fields, MCP annotations, authentication posture, and read-only boundaries. These require an intentional change, version consideration, and consumer review.

### Historical facts

Examples include an audit result, a trust snapshot, or an incident observation. These are evidence of what was known at a point in time and must not be silently rewritten to match present state.

### Derived facts

Examples include status distributions, trend summaries, and readiness decisions. Derived facts must identify their inputs and policy. Missing input remains missing; it must not be replaced with a neutral or mid-scale default.

## Documentation rules

1. If two documents repeat a volatile fact, one must be generated from the other or the repetition must be explicitly historical.
2. If a document describes code behaviour, identify the source module or generator that owns the behaviour.
3. If a route is documented, verify the route, content type, response shape, and effective URL before publication.
4. If an example names a dataset, verify the identifier against `datapulse.json` before publication.
5. If a signature or digest is documented, explain its evidence boundary; integrity is not substantive truth.
6. If a document cannot name its source or verification method, it is explanatory opinion, not evidence-bearing documentation, and must be labelled accordingly.

## Review triggers

Review this map when:

- a schema changes;
- a status is added, removed, or renamed;
- an MCP tool or route changes;
- a generator starts or stops owning a surface;
- an evidence or attestation format changes;
- a new public page is added;
- a public claim is retracted or materially narrowed.
