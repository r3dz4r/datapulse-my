# 2026-09-01 — Trust-stack adoption dispatch package

## Operator direction

Prepare adoption of arXiv #2 + #3 + #4 + #6 + #8 together:

- #2 SetGo — metadata readiness across FAIR/licensing/provenance/governance/reproducibility/catalog readiness.
- #3 ContextNest — governed, versioned, integrity-checked context with point-in-time reconstruction.
- #4 F(AI)²R — machine-readable provenance for AI-in-loop claims and artefacts, with human verification rungs.
- #6 Attested Tool-Server Admission — signed clearance, deny-by-default tool allowlist, fail-closed enforcement, audit trail.
- #8 TrustShiftProbe — staged-trust threat model and runtime behavioural monitoring for MCP responses.

## Current reconciliation

- DataPulse OSS trust plane: shipped/live; current public contract is read-only and no-auth, with signed health/evidence artefacts and a generated MCP advertisement.
- Engine #1/#5/#15/#16/#20 wave: implemented locally and independently verified; not committed, pushed, deployed, or exposed through DataPulse.
- This five-paper cluster is a new security/contract phase. It is **not** a direct instruction to change the live public MCP surface.
- Background: five-minute DataPulse health observation and daily Engine NPRA output continue.
- Deferred/untouched: Cloudflare publication, x402, private trust-plane recovery, public route correction, and unrelated Engine work.

## Dispatch package

1. `/tmp/datapulse-trust-stack-spec-brief.md` — Sol design/specification dispatch; no code, no keys, no publication.
2. `/tmp/datapulse-trust-stack-implementation-brief.md` — Terra DataPulse implementation dispatch; only after the spec is accepted.
3. `/tmp/engine-trust-stack-implementation-brief.md` — Terra Engine implementation dispatch; only after the shared spec and DataPulse contracts are accepted.

The three dispatches are intentionally sequential. Do not launch all three in parallel: the Engine brief depends on the shared contract produced by the spec brief.

## Hard safety boundary

No brief authorizes cryptographic key generation or rotation, private-key access, production deployment, service restart, public publication, upstream mutation, external communication, or spending. Any key operation requires a separate explicit approval for that operation.
