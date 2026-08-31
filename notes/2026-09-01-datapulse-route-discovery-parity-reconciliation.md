# DataPulse route/discovery parity reconciliation — 2026-09-01

## Roadmap reconciliation

| Track | Evidence | Live status | Classification | Next action |
|---|---|---|---|---|
| Register homepage implementation | Local commit `a491c1c9`; exact CI/Release/Pages runs passed | Register served at `/dashboard` | shipped | Promote register to `/` |
| Root-first product route | `config/public-surfaces.json`, redesign brief, design system | `/` still serves the previous landing surface | queued | Update source/config/workflow contract |
| `/landing.html` compatibility alias | Redesign brief + design system | redirects to `/landing#`, not `/` | queued | Generate alias/redirect to `/` |
| Learn/methodology shell | Design system and redesign brief | Existing pages remain served | queued | Separate future slice |
| Machine-plane parity | Existing canonical artifacts | Existing machine surfaces remain served | queued | Separate future slice; preserve contracts |
| NPRA | Explicit unpublished boundary | Existing surface remains available but not promoted | deferred | No public discovery change in this slice |
| Health observation/evidence | Scheduled health commits and live snapshots | Continues automatically | background | Do not mix with route work |
| Payments/x402/new infrastructure | Deferral notes and operator rules | Not started | paused | Remain untouched |

## Decision

**Main lane:** canonical route/discovery parity. The register implementation is shipped and the next product correction is operator-directed continuation of the approved register-first architecture.

**First gate:** make `https://www.data-pulse.my/` return the 389-row register and make `/landing.html` resolve to `/` without creating a duplicate landing experience.

**Current constraint:** the deploy workflow still asserts the previous arrangement: landing at `/` and register/dashboard at `/dashboard`. The next implementation must update that workflow's verification contract and the source-owned route/discovery generators together; changing only the deployed HTML would fail closed or be overwritten.

**Untouched lanes:** Learn, methodology, machine-surface migration, NPRA publication, payments/x402, new infrastructure, and unrelated Malaysia Data Engine work.
