# Roadmap reconciliation follow-up — 2026-08-22

## Reconciliation status

- **Main lane:** continue Phase 1 longitudinal evidence, with one prerequisite repair: make the production health pipeline regenerate the trend, drift, and reconciliation artifacts after each probe.
- **Background:** `datapulse-health.timer` continues collecting the six-dataset flagship cohort and the wider catalogue automatically.
- **Deferred:** verdict API wedge until the evidence gate passes; x402 until its locked checklist triggers; broad catalogue expansion; unexecuted sourcing/adoption dispatches.
- **Shipped:** FastMCP 4/MCP 2026-07-28 foundation, government-friendly copy on root/landing/NPRA pages, compacted-history substrate, and production MCP deployment.
- **Paid-product lane:** NPRA engine remains separate and in progress.

## Live evidence

- Manifest and health currently cover 389 datasets.
- `health/history.jsonl` currently contains one comparable observation date: 2026-08-22.
- `health/trends.json` remains conservative at 389 `insufficient_data`, which is correct for the current one-day window, but its generated artifact is dated 2026-08-16.
- `health/drift.json` and `health/reconciliation.json` are also dated 2026-08-16 despite current health cycles on 2026-08-22.
- `/home/redza/dotfiles/scripts/datapulse-pipeline.sh` runs probe, history, badges, RSS, README, catalogue, record evidence, graph, and attestation score stages, but does not invoke `gen_trends.py`, `gen_drift.py`, or `gen_reconciliation.py` in the health-cycle path.

## Decision

Do not wait passively for the evidence window while the evidence surfaces are stale. The next implementation gate is a bounded pipeline repair that runs the three existing generators against the frozen health/history snapshot, validates their generated timestamps and schemas, and publishes them atomically with the existing health artifacts. It must not relax the conservative evidence thresholds.

After that repair, allow at least three daily samples spanning two days to accumulate before evaluating the verdict API gate. The next deliverable is an internal stakeholder explainer using the GTFS declared-vs-observed case study; no public outreach or API wedge starts before the evidence gate and stakeholder language are validated.
