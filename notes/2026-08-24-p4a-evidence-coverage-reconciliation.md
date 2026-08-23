# P4A evidence-coverage reconciliation — 2026-08-24

## Roadmap reconciliation

- **Source audit:** `/tmp/datapulse-full-trust-platform-audit.md`, P4 finding and Brief 8.
- **Main lane:** Trust-platform remediation, Phase 4A — evidence/longitudinal coverage.
- **Background:** five-minute health collection; Phase 1 longitudinal accumulation; existing Ed25519/Rekor dual-publish work and private trust boundary.
- **Deferred:** P4B browser security headers (edge/Cloudflare approval required); P4C payload/performance work (UX/design decision required); P5–P8 discovery/API/docs consistency; payment, registry, and third-party source lanes.

## Reconciled status

| Track | Evidence | Classification |
|---|---|---|
| P0/P1/P2/P3 trust remediation | Verified commits, CI, and served proof from STATE.md | shipped |
| Phase 1 history substrate | `d51d72ff`, `c838460d`; focused tests and current consumers | shipped |
| Phase 1 longitudinal accumulation | `health/trends.json` remains `389/389 insufficient_data`; daily aggregate is empty | background/in progress |
| P4A evidence coverage | Audit P4 finding: all trends insufficient; two record-evidence receipts | operator-directed now |
| P4B headers | Audit E07; edge control is outside this repo | deferred |
| P4C performance | Audit E06; page-size and browser verification decision pending | deferred |

## P4A scope

Add deterministic, honest coverage reporting around existing history/trend/drift/record-evidence outputs. Preserve the existing minimum-sample and history-span thresholds. Do not manufacture evidence, change the ten-status taxonomy, alter trend classifications, add a public marketing claim, touch Cloudflare/edge configuration, or regenerate production artifacts during implementation.

The execution brief must name the exact source/test files after a read-only audit and require a fixture-based coverage contract, deterministic output, full relevant tests, and no push.

**Next gate:** approved Terra Codex brief with a verifiable coverage artifact/contract and explicit non-goals for P4B/P4C.
