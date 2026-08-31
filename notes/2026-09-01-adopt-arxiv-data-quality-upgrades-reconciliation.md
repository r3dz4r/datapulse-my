# 2026-09-01 — Adopt arXiv data-quality upgrades

## Roadmap reconciliation

- **Source:** the 20-paper arXiv review completed 2026-09-01; operator direction: “Proceed to adopt #1, 5, 16 and 16 now.”
- **Interpretation:** the earlier repeated `#16` was a duplicate. The current operator direction adds #15 SmartDiff, so the four unique tracks are #1 Zero-Scan Data Quality, #5 Croissant Baker, #15 SmartDiff, and #16 Auto-Validate-by-History.
- **Main lane:** implement the four unique, bounded upgrades across the Malaysia Data Engine’s evidence and packaging path.
- **Background:** five-minute DataPulse health observation and daily Engine NPRA output continue.
- **Deferred/untouched:** MCP hardening papers (#6–#11), bitemporal graph store (#12), agent telemetry (#13), evidence arbitration (#14), procurement/ranking (#18–#19), OGD4All benchmark (#20), x402, private trust-plane work, and unrelated Engine work.

## Current classifications

| Track | Evidence | Status | Classification | Next action |
|---|---|---|---|---|
| DataPulse OSS trust plane | `STATE.md`, live health/MCP probes | shipped/live | shipped | extend without breaking read-only/fail-closed contract |
| DataPulse public-surface route correction | `notes/2026-09-01-datapulse-route-discovery-parity-reconciliation.md` | redirect-loop verification failed | blocked | do not touch in this wave |
| Engine NPRA daily pipeline | recent Engine commits and generated outputs | active | background/in progress | preserve generated dirty output |
| #1 Zero-Scan | arXiv:2605.30308 | Engine manifest now emits metadata-first provenance signals | implemented locally | validate consumer integration before publication |
| #5 Croissant Baker | arXiv:2605.15079 | deterministic local generator and current-snapshot validation pass | implemented locally | decide packaging/public-surface consumer |
| #15 SmartDiff | arXiv:2509.00293 | pure explainable schema/content comparator added | implemented locally | integrate into a deliberate consumer workflow |
| #16 Auto-Validate-by-History | arXiv:2306.02421 | advisory median/MAD history bounds added | implemented locally | collect more history; keep advisory until policy review |

## Execution result

- Implemented locally in `/home/redza/work/malaysia-data-engine` via Codex dispatch `20260901-015807-3179375`.
- Independent verification: full Engine suite `154 passed, 1 skipped`; focused scoped suite `147 passed, 1 skipped, 7 deselected`; scoped Ruff and format checks passed; current NPRA manifest produced a valid 5-distribution/5-record-set Croissant sidecar with byte-identical repeated generation.
- Repository-wide Ruff remains red on 26 pre-existing violations and 41 pre-existing formatting files outside this wave; no remediation was attempted.
- **Not shipped:** no commit, push, deployment, service restart, Cloudflare publication, Hugging Face upload, or DataPulse public-surface change. The generated `data/pharma/health.json` timestamp-only dirty file remained untouched.

## Execution boundary

Codex implemented code in one bounded Engine slice. No push, production restart, Cloudflare publication, upstream mutation, credential handling, or modification of pre-existing dirty files was performed. The next gate is a separate consumer-integration decision for DataPulse/public packaging; inferred constraints remain advisory until policy review.
