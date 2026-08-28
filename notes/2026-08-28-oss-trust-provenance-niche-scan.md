# OSS trust/provenance/observability niche scan for DataPulse — 2026-08-28

**Author:** Hermes (operator-requested deep research)
**Method:** 3 parallel subagent probes (data-observability, signing/attestation,
agent-health-MCP) + independent GitHub API cross-check. All star/fork/license/pushed
verified via GitHub API as of 2026-08-28.
**Context:** DataPulse = continuous per-dataset health + provenance + evidence receipts,
MCP-native, agent-facing trust for Malaysian government open data. Private OpenBao+Rekor
signer lane deliberately stood down (P6, 2026-08-24); signing deferred/non-blocking.

---

## The strategic read (all three probes + cross-check agree)

**No single open-source repo does what DataPulse aims to be.** Every commodity tool covers
only 1–2 of DataPulse's dimensions. The wedge — "agent consumes licensed-government-data
health/provenance before trusting a source" — is **unclaimed in OSS** (the closest commercial
entrant, MCPVerify, is proprietary: 8 patents pending, L1–L5 badges). This is an opportunity,
not a research gap.

Therefore: **do NOT adopt one framework as the core. Compose DataPulse on a small set of
commodity building blocks, keep the evidence-receipt engine + MCP surface custom (the moat).**

## Category A — Signing / attestation / transparency (commodity, verified 2026-08-28)

| Component | Stars | License | Fit verdict |
|---|---|---|---|
| Sigstore bundle format `*.sigstore.json` | — | Apache-2.0 | ✅ Adopt (offline-verifiable, self-contained) |
| cosign (`sign-blob` keyless) | 6,262 | Apache-2.0 | ✅ Adopt (OIDC identity, no key custody) |
| DSSE + in-toto attestation + SLSA predicates | 369 | — | ✅ Adopt (machine trust format inside bundles) |
| Public Rekor (`*.sigstore.dev`) | 1,201 | Apache-2.0 | ✅ Adopt (auditable inclusion w/o self-hosting) |
| RFC 3161 timestamp | — | — | ✅ Optional (log-independent existence proof) |
| OpenBao | 7,188 | MPL-2.0 | ⚠️ Defer (full KMS server; matches P6 stand-down) |
| Self-hosted Rekor + Fulcio | — | — | ⚠️ Defer (heavy; use public instance) |
| HashiCorp Vault | 36,181 | BUSL-1.1 | ❌ Not fit (IBM license, heaviest ops) |
| Notary v2 / C2PA / WASM-TEE | — | — | ❌ Not fit (different artifact domains) |

## Category B — Data observability / data contract (building blocks)

OpenMetadata 15,008★ Apache-2.0 (closest single heap: catalog+lineage+DQ profiler+MCP; heavy, no evidence receipts);
OpenLineage 2,629★ (provenance standard, converging on agent/MCP case RFC #4484; spec/emit only);
datacontract/cli 1,050★ MIT + bitol ODCS 1,098★ (contract-validation engine + schema standard);
Great Expectations 11,743★ (**GX Cloud shut down June 2026**, revived OSS "GX Core" under Fivetran, no freshness monitor);
Soda 2,419★ (moving behind Cloud), Elementary 2,400★ (dbt-only), Marquez 2,268★ (release 2024, slow),
DataHub 12,602★ (heavy, governance), Amundsen 4,783★ (dormant, no quality). <20★ newcomers (Aegis, OpenDQV, DataQ, provero) = research-grade, don't adopt.

## Category C — Agent-facing data-health MCP (EMPTY wedge)

Best OSS building blocks: datacontract-cli (#1 enforcement engine), jorge-martinez-gil/dataq (#1
health/provenance scoring brain, DCAT+PROV-O, DQV-compatible — matches 10-status/provenance
model), aegis-dq/OpenDQV (#1 MCP-server reference: write-time contract validation with native MCP).
MCPVerify = commercial (not OSS). No repo does "agent-facing data-health MCP for gov open data."

## Recommended adoption stack (lowest operational burden, zero servers)

1. **cosign `sign-blob` keyless → Sigstore bundles** per artifact (CI job per refresh).
2. **DSSE + in-toto statements / SLSA provenance predicates** inside the bundle.
3. **Public Rekor** for auditable inclusion (no self-hosting).
4. **datacontract/cli + bitol ODCS** as the per-dataset contract-validation engine + standards-shaped evidence serialization.
5. Optional **OpenMetadata** as open health/provenance backbone (only if a heavier single source is wanted; the OpenLineage-events + datacontract path is lighter).
6. **Legacy Ed25519 chain retained and published alongside** — do not migrate key material into a KMS.

**Net burden: zero servers.** A small CI job calls cosign per refresh; consumers verify
`cosign verify-blob --bundle …`. Private OpenBao/Rekor stays deferred, no re-instatement.

## Keep custom (the moat, do NOT outsource)

- Evidence-receipt engine (source, dataset ID, licence, timestamp, content date, status,
  schema state, claim scope, limitations, evidence URL) — signed, replayable, Ed25519.
- MCP-native health surface (`get_dataset_health`, `get_freshness`, `get_schema_drift`,
  `get_evidence_receipt`, `verify_dataset`).
- 10-status taxonomy + licence/provenance metadata for Malaysian government open data.
- Malaysia/Asia data-sovereignty positioning no Western entrant can replicate.

## References

- Subagent transcripts: `~/.hermes/cache/delegation/deleg_f5cbafa1/`
- Trust infra selection: `strategic-consulting/references/trust-infrastructure-selection.md`
- Prior niche audit (2026-08-17, 4 funded entrants): `strategic-consulting/references/locked-claim-shelf-life-2026-08-17.md`
