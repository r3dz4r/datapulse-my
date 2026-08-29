# OSS Phase 1 reconciliation — 2026-08-29

## Roadmap mapping

Requested label: `Phase 1 of OSS plan`
Canonical project: DataPulse OSS adoption/build plan
Source: `notes/2026-08-28-build-plan-adopt-commodity-signing-provenance.md`, Phase 1
Research source: `notes/2026-08-28-oss-trust-provenance-niche-scan.md`

## Reconciliation table

| Track | Evidence | Intended outcome | Live status | Classification | Next action |
|---|---|---|---|---|---|
| OSS trust/provenance research | 2026-08-28 niche scan | select commodity standards and retain custom evidence/MCP moat | research note exists and is the current strategy source | shipped | implement the selected Phase 1 slice |
| Phase 0 contract | build plan lines 23–32 | preserve read-only posture, legacy Ed25519 chain, non-blocking signer, exact receipt contract | constraints are present in the plan; no separate Phase 1 implementation has started | shipped as design constraint | carry into Phase 1 brief and tests |
| Phase 1 health snapshot bundle | build plan lines 34–57 | publish independently verifiable Sigstore bundle + DSSE/in-toto statement for `health/latest.json` | no `gen_sigstore_bundle.py`, no signed bundle output, and no Phase 1 CI implementation found in DataPulse | queued | prepare implementation brief and dispatch Codex |
| Phase 2 receipt contracts | build plan lines 61–81 | ODCS-shaped receipts and datacontract validation | no Phase 2 implementation started | queued | leave untouched until Phase 1 proves the bundle path |
| Phase 3 per-dataset signatures | build plan lines 85–103 | independently verifiable receipt per dataset | no Phase 3 implementation started | queued | depends on Phase 1 and 2 |
| Phase 4 MCP hardening | build plan lines 107–123 | expose signed-receipt verification through MCP | current MCP remains the existing 16-tool surface | queued | depends on Phase 3 |
| Phase 5 sovereignty positioning | build plan lines 127–138 | docs/messaging, no code | not started in this lane | queued | may follow Phase 1, but not part of this implementation |
| Private OpenBao/Rekor lane | STATE.md / P6 decision | private signing/witness infrastructure | intentionally stood down; no reactivation approved | paused | preserve the gate and do not touch |
| Five-minute health pipeline | live repo + health artifacts | continue observation and health-only publication | active background lane; latest health commits continue arriving | background | leave operational path unchanged except explicit Phase 1 integration |
| Malaysia Data Engine NPRA product | engine git history and product docs | commercial vertical proof | daily outputs active; current buyer SLA remains unproven | background | do not let OSS Phase 1 replace the product lane |

## Lane decision

- **Main lane:** DataPulse OSS Phase 1 — health snapshot Sigstore bundle contract and implementation.
- **Background:** five-minute DataPulse health observation/publication; daily Malaysia Data Engine NPRA output.
- **Deferred:** Phase 2–5, dq-3/dq-6/dq-7/dq-8, private OpenBao/Rekor pilot, external-source pilot, and UI/operator-only lanes.
- **Research plan status:** shipped; implementation is queued.
- **Phase justification:** operator-directed continuation of the existing OSS build plan after the website remediation closed.

## Corrections and implementation boundary

1. The build plan's “GitHub Pages” references are stale. The canonical website publisher is `.github/workflows/deploy-cloudflare-pages.yml` and the public origin is `https://www.data-pulse.my`.
2. The current repository has no `cosign` executable installed locally and no Phase 1 bundle generator or signed output. The implementation must therefore make the CI dependency and signer-unavailable behavior explicit rather than assuming local signing capability.
3. Phase 1 must not change the health schema, per-dataset signing, MCP tool behavior, private OpenBao/Rekor services, upstream sources, or payment/product surfaces.
4. The exact first implementation gate is a tested, deterministic unsigned statement/bundle assembly contract plus an additive CI signing path whose unavailable signer leaves canonical health publication healthy and honest. The public Sigstore signing mechanism must be verified against current official cosign/Sigstore behavior before deployment.

## First concrete gate

Produce and approve a Phase 1 Codex brief naming the exact generator, workflow surface, release invariant, tests, signer-unavailable behavior, and Cloudflare publication path. Do not dispatch until that brief is approved.
