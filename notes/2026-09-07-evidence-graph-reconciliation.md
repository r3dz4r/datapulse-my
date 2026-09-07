# 2026-09-07 — Evidence Graph contract reconciliation

## Roadmap reconciliation

| Track | Status | Evidence |
|---|---|---|
| DataPulse catalogue/health/attestation plane | shipped + live | 418-dataset served parity; 18 MCP tools; signed health evidence |
| Current citation resource | shipped | `datapulse://citation/{dataset_id}` in `mcp/server.py`, served reference and tests |
| Answerability/temporal/claim validation | shipped as local evaluation contracts | `mcp/answerability_benchmark.py` and 127-test MCP suite |
| Record-level evidence pilot | shipped for one vertical | `record-evidence/v1`, pharmaceutical-products pilot |
| **Unified Evidence Graph contract** | **queued → in progress (this slice)** | this note + dispatch brief |
| Public historical evidence graph | queued | after local contract validation |
| Open-data quality dimensions | queued | after Evidence Graph contract |
| MCPVerse task suite | queued | after quality dimensions |
| Singapore expansion | live reference pack, separate breadth lane | current manifest includes 418 datasets; do not widen this slice |
| Buyer/NPRA monetization | deferred to Malaysia Data Engine | locked product boundary |

## Main lane

Build the local Evidence Graph contract that connects existing dataset, observation, receipt, claim, attestation and reconciliation primitives. This is the natural continuation of the citation/temporal/claim adoption sequence.

## Background

- Five-minute DataPulse health observation continues.
- Daily Malaysia Data Engine NPRA output continues.
- Existing public MCP and generated surfaces remain unchanged.

## Deferred / untouched

- No new MCP resource or tool.
- No public schema or generated surface change.
- No runtime history ingestion.
- No individual telemetry.
- No buyer, payment or commercial API work.
- No new Singapore breadth or promotion.

## Contract decision

Use `evidence-graph/v1` as a local-only contract with five node types:

- `dataset`: canonical dataset identity;
- `observation`: one time-bound source observation;
- `receipt`: digest/attestation pointer for the observation;
- `claim`: a bounded statement about the observation;
- `reconciliation`: an agreement/conflict relationship.

Edges are typed and directional: `observes`, `derived_from`, `attested_by`, `supports`, `supersedes`, `conflicts_with`.

Every claim marked `supported` must point to an observation and evidence digest. Every observation must point to one dataset, one observed timestamp, one source URL, status and fingerprint. Unknowns and unsupported claims remain explicit; no semantic truth is inferred.

## First gate

A deterministic builder/verifier produces a byte-stable graph from small fixtures, rejects dangling nodes/edges, rejects unsupported claims marked as supported, validates digest/identifier formats, and passes the full existing test suite without public-surface changes.
