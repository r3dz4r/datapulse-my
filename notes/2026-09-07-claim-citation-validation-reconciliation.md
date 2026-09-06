# 2026-09-07 — claim-level citation validation reconciliation

## Roadmap reconciliation (gate per dotfiles AGENTS.md rule 9)

| Track | Status | Evidence |
|---|---|---|
| Answerability benchmark | shipped + merged + pushed | `7be12f9cb`, merge `372c5ade9` on `origin/main` |
| Temporal stale-evidence benchmark | shipped locally, NOT pushed | `58e4240fc` on local `main` (ahead of origin by health-only commits from origin side: origin `e28c921e3`) |
| **Claim-level citation validation** | **queued → in progress (this slice)** | this note + dispatch brief |
| Open-data quality dimensions | queued | after this slice |
| MCPVerse agent task suite | queued | after quality dimensions |
| Buyer/NPRA monetization | deferred to Engine | operator boundary 2026-09-06 |

- **Main lane:** claim-level citation validation (ReClaim/CiteFix adoption).
- **Background:** five-minute DataPulse health observation (live, 413 datasets), daily Engine NPRA output, OpenWiki cron (still credit-blocked).
- **Deferred:** open-data quality dimensions, MCPVerse suite, buyer/NPRA lane, push of `58e4240fc` (awaiting operator "push").
- **Phase justification:** continued — this is the next slice in the operator-approved arXiv adoption sequence (answerability → temporal → claim/evidence alignment).

## Existing reality this slice builds on

- `datapulse://citation/{dataset_id}` resource (in `mcp/server.py:2056-2097`) already emits: `schema datapulse/v1/citation`, `evidence_url`, `observed_at`, `source_url`, `status`, `fingerprint`, `datapulse_verdict` (USE/WARN/REFERENCE-USE/STOP), `limitations`.
- The local benchmark (`mcp/answerability_benchmark.py`) now evaluates evidence candidates including temporal cases, but has **no claim dimension**: it evaluates evidence states, not whether a textual claim is supported by the cited evidence.

## Slice design (no public surface change)

Extend the local benchmark with a claim-support evaluator: given a candidate `{claim, claim_type, citation}` triple, decide `supported | partial | unsupported | unknown` strictly from citation fields — deterministic, no model inference, no network.

Rules (fail-closed, precedence explicit):

1. Citation missing/malformed, or `dataset_id` absent → `unknown` / `malformed_citation`.
2. `claim_type` not in the closed vocabulary (`availability_observed`, `freshness_observed`, `status_observed`, `licence_evidence`, `record_count_observed`, `semantic_truth`) → `unknown` / `unclassified_claim`.
3. `semantic_truth` claims → `unsupported` / `outside_evidence_scope` (matches the citation's own `limitations` text).
4. `licence_evidence` claims → `supported` only if `licence` is a non-empty string; else `unknown` / `licence_unobserved`.
5. Availability/freshness/status/record-count claims → `supported` only if the claim's asserted value matches the citation field exactly AND the temporal benchmark's own verdict for that evidence state is `answer`; `partial` when the field exists but the verdict is `warn`; else `unsupported`.
6. Claim text asserting more than the field (e.g. "authoritative" adjectives) → `unsupported` / `overclaim` (deterministic adjective blocklist; never semantic judgement).

Fixture: ~8 cases added to the same fixture file; report stays byte-stable; full suite green; 18 tools / 8 resources unchanged; no generated surface touched.

## First gate

New claim-support cases pass, byte-stable report, full MCP suite green, zero public-surface change.
