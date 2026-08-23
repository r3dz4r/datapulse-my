# Roadmap reconciliation — 2026-08-22

## Why this note exists

The 2026-08-19 deep-dive research produced a highest-adoption technology roadmap, but the roadmap was converted into queued dispatches rather than executed. On 2026-08-22, a separate DataPulse trust-proof phase was started without explicitly reconciling that sourcing roadmap. The tactical phase was valid, but the transition was not made explicit.

## Reconciliation

| Track | Evidence | Live status | Classification | Next action |
|---|---|---|---|---|
| Highest-star foundational technology adoption | `~/.hermes/analyses/datapulse-sourcing-2026-08-19.md`, `todos.md` `src-1` through `src-7` | Research and briefs exist; no verified adoption commits for Sigstore/Rekor, OSCAL, Evidently, Playwright MCP, or middleware | queued | Select the first adoption dispatch explicitly; do not call the research plan shipped |
| FastMCP/MCP foundation | `todos.md` `dq-2`, `mcp/requirements.txt`, current FastMCP 3.4.7 environment | Partial version alignment exists; MCP 2026-07-28 work remains unfinished | in progress / queued | Reconcile the remaining dq-2 scope before dispatch |
| Phase 1 trust proof | `notes/phase-1-baseline-2026-08-22.md`, pushed compacted-history substrate, active health timer | Cohort baseline exists; collection runs automatically; longitudinal evidence has only one daily sample so far | background | Let automatic collection accumulate the evidence window |
| Verdict API wedge | `todos.md` `phase1-verdict-wedge` | Explicitly gated on longitudinal evidence | paused | Do not start until cadence, lag, structural gaps, and unproven claims are measured |
| x402 paid MCP | `notes/x402-revisit-checklist.md`, `todos.md` `dq-7` | Deferral checklist remains authoritative | paused | Revisit only when its stated triggers are met or the checklist is explicitly amended |
| NPRA engine product | `malaysia-data-engine` dispatch queue and live HF listing | Product lane exists independently of the trust-proof phase | in progress | Keep as the paid-product track; do not conflate it with foundational-tech adoption |

## Lane decision

- **Main lane:** no new foundational-tech dispatch is started by this note; the next active lane must be selected from the reconciled sourcing queue.
- **Background:** DataPulse health collection and Phase 1 evidence accumulation continue automatically.
- **Deferred:** verdict API until evidence gate; x402 until checklist triggers; broad catalogue expansion until the trust proof is sufficient.

## Mandatory gate installed

- `roadmap-reconciliation-gate` skill created and persisted.
- `dotfiles/AGENTS.md` hard rule 9 now requires reconciliation before starting a phase, changing priority, or acting on a strategic `proceed`.
- The gate requires research, STATE, todos, dispatch briefs, git history, and live artifacts to be classified before execution.

## Failure prevented going forward

A research memo or queued dispatch brief must never be described as shipped. Every new phase must state what happens to the previous roadmap, what remains background, and what is deferred.
