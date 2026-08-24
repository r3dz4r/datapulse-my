# P4C performance reconciliation — 2026-08-24

## Roadmap position

- **P4A:** shipped — evidence coverage is committed, pushed, CI-verified, Pages-deployed, and served.
- **P4B:** deferred accepted risk — direct GitHub Pages has no repository-controlled response-header surface; the Cloudflare proxy canary redirected the custom domain to `r3dz4r.github.io` and was rolled back. Do not retry without a safe origin-compatibility design.
- **Main lane:** P4C performance/payload discipline.
- **Deferred:** P5 discovery/documentation consistency and all unrelated product/edge lanes.

## Live baseline

- `https://data-pulse.my/` returns HTTP 200 from direct GitHub Pages.
- Homepage payload: **1,188,958 bytes**.
- Embedded dashboard data: **943,505 bytes** of the homepage.
- The dashboard uses build-time embedded data; no runtime data-loading redesign is authorized in this slice.
- External resources are Google Fonts plus the shared `assets/datapulse.css`; inline dashboard scripts/styles remain part of the current shell.

## P4C first slice

Establish a deterministic payload baseline and regression guard for the generated homepage. The first implementation must not change the dashboard loading architecture, public copy, dataset taxonomy, or GitHub Pages deployment flow. It should measure the generated HTML and embedded-data block from fixture/local inputs, enforce an explicitly documented initial budget with reviewable headroom, and fail tests on unexpected growth.

Optimization/rearchitecture is a later P4C slice, after the guard exists and a component breakdown identifies the safest reduction.

**Next gate:** write and approve the exact Codex brief for the payload-budget contract; no production artifact generation, commit, or push until approved.
