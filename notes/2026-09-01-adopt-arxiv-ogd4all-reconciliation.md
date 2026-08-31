# 2026-09-01 — Adopt arXiv #20 OGD4All

## Roadmap reconciliation

- **Source:** arXiv:2602.00012, OGD4All: Accessible Interaction with Geospatial Open Government Data Based on Large Language Models.
- **Transferable mechanism adopted:** transparent, auditable public-data QA discipline: answerability/grounding checks, explicit unsupported-question abstention, reproducible benchmark fixtures, and no hallucinated fallback.
- **Main lane:** extend the existing Malaysia Data Engine local evidence path with the #20 mechanism without building a generic public chatbot.
- **Background:** five-minute DataPulse health observation and daily Engine NPRA output continue.
- **Deferred/untouched:** public DataPulse route correction, Cloudflare publication, MCP hardening, x402, private trust-plane work, and unrelated Engine work.

## Execution result

- **Status:** implemented locally in `/home/redza/work/malaysia-data-engine` via Codex dispatch `20260901-022907-3267266`.
- Added a pure, fail-closed answerability gate with structured verdicts for answerable, unsupported, stale/unknown, ambiguous/conflicting, and out-of-scope evidence.
- Added a seven-case synthetic Malaysian benchmark covering positive support, missing evidence, stale evidence, unknown health, scope mismatch, conflicting claims, and bounded no-supported-record results.
- Independent verification: answerability tests `7 passed`; benchmark expected verdicts all matched; deterministic report byte equality passed; full Engine suite `161 passed, 1 skipped`; scoped Ruff/format and diff checks passed.
- **Not shipped:** no commit, push, deployment, service restart, Cloudflare publication, or public DataPulse surface change.

## Boundary

This is a local adoption of OGD4All’s evaluation/abstention discipline, not a claim that DataPulse now provides a citizen-facing AI service or that the Zurich benchmark transfers unchanged to Malaysian data. Public exposure still requires a deliberate Malaysian benchmark, real evidence-contract integration, human review policy, and a separate publication decision.
