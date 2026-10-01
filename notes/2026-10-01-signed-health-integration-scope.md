# 2026-10-01 — Signed-health operational integration scope

## Source and decision

Operator selected “Codex gpt-6.1-sol” after the recommendation for staged signer/storage integration and preview runtime rehearsal, including trusted-registry refresh and revocation delivery. This authorises local staged implementation, not public publication, remote preview deployment, production promotion or secret/config/service changes. The local Cloudflare runtime rehearsal is a pre-publication step; an actual hosted preview remains a separately approved gate, not replaced by this local exercise.

## Direct observations before dispatch

- Fetch of public origin/main: eaf56e5fc910ac380b270ff0f655adc9bd0d658e.
- Reviewed local signed-response foundation: c3d47ef33569bbe6aae919f2098d913e6518b0c6; existing branch tracked tree clean, only expected .venv untracked. Re-run focused acceptance: 191 passed in 28.84s.
- New worktree: /home/redza/.worktrees/wt-dp-signed-health-integration, branch session/dp-signed-health-integration, based on that exact local foundation. Existing signed-response and preview branches preserved.
- Production datapulse-health.service executes /srv/datapulse-my, not either implementation tree. No production changes or implementation acceptance there.
- Existing production publisher owns independently mutable unsigned health keys and selects a production namespace by default. New verified transport must not inherit those defaults or cadence.
- Existing signed protocol requires verified immutable object read-back before pointer advancement; blind Cloudflare KV GET/PUT is not atomic creation. External exclusive writer authority is not proven by a local lock.
- Existing attestation signer uses explicit key JSON with attestation-chain-signing purpose. The observation receipt socket is a different authority/purpose, not silently reusable.
- Existing verified route reads trusted registry through fixed same-deployment ASSETS, not untrusted KV. Old deployments cannot learn a later revocation merely from no-store; this is an explicit integration threat boundary.
- Node v22.23.1 and existing Python virtualenv available. Wrangler was absent; parent installed free local dev tooling Wrangler 4.145.0 into ignored health/staging-tooling/ only, no tracked dependency/config changes. CLI help confirms Pages local bindings and local KV persistence flags. Real local runtime has not yet been exercised.
- Repository wrangler.toml has real production/preview namespace IDs; it must not be used in local rehearsal. Generated isolated config must use local bindings only, no credentials/dotenv/OAuth discovery or public network.

## Roadmap reconciliation

| Track | Evidence | Classification | Next action |
|---|---|---|---|
| Exact signed health response protocol | Local foundation c3d47ef33569; 191 focused tests and earlier independent review | Queued for deployment; local slice complete, not shipped | Build operational adapters and local runtime proof |
| Operational signer/storage/trust delivery | Foundation integration gaps, explicit operator lane selection | Queued before worker launch | Opt-in integration plus REST/coordination and workerd evidence |
| Separate preview/scanner remediation | session/dp-pr-head-sha at a28e989d137282e3d13fe87c3360e6e212ba8f2c | Blocked; unresolved, not superseded | Separate scanner/config/publication approvals |
| Production observers and Engine timers | Existing running service path; no changes authorised | Background | Continue unchanged |
| Dashboard/MCP signed derivation | Explicit protocol exclusions | Queued | After operational signing/trust foundation |
| One dataset/use-specific assurance | Operator-approved sequence | Queued | After cryptographic/consumer foundation; no universal truth claim |
| Engine Stage 2 and other strategic lanes | Existing recorded decisions | Paused from this dispatch | Separate repo/scoping/decision gates |

Main lane: continued operator-directed signed-health operational integration.
Background: existing observers/signers/Engine timers, unchanged.
Deferred: separate preview/scanner work, Engine Stage 2, dashboard/MCP adoption and scoped assurance, all outside this worker.
Narrative lag: state-now still renders the earlier remediation priority; appended manual signed-response records define the newer operator direction. Do not rewrite historical or auto sections to hide this disagreement.

## Deliverable and acceptance

Primary source: scripts/signed_health_integration.py, with exact allowlist and requirements in the staged brief. Explicit signer capability; no discovery or private-key fixture persistence. Explicit KV REST destination and bounded safe transport; enforced destination-bound cooperating-writer serialization and mandatory external sole-writer promotion gate. Trusted-registry artifact delivery/refresh, revocation rejection and honest obsolete-deployment limits. Actual isolated local Pages/workerd HTTP routing and independent consumer verification; no mock-only substitute.

Acceptance: focused protocol/publisher/binding/contract/integration fixtures, executable quick-test, executable local runtime rehearsal, discriminating behavioral mutation control, committed-state re-verification and independent review. Full scripts/MCP sweeps and hosted preview/provider proof remain separate gates. No generators or public surfaces are adopted by this build. source_truth_verified remains false.

Next promotion gates: independent review; full relevant regression/runtime proof; literal public push and merge/deploy approval; preview-only credential and environment configuration approval; remote immutable storage/single-writer proof; trusted-registry refresh/revocation delivery and old-deployment/offline-consumer containment; monitoring/retention/write-budget/rollback readiness. No approval is consumed for those operations by this coding-lane choice.
