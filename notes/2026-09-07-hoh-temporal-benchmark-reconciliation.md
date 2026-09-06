# 2026-09-07 — HoH temporal stale-evidence benchmark reconciliation

## Roadmap reconciliation

- **Research source:** HoH — How outdated information Harms RAG (arXiv:2503.04800), adopted into DataPulse as a temporal-evidence evaluation discipline. Companion to the merged answerability benchmark (`7be12f9cb`, merge `372c5ade9`).
- **Transferable mechanism:** paired historical/current evidence evaluation where stale evidence must never be presented as current, and "as of date X" queries must select evidence valid at X rather than the latest observation.
- **Main lane:** extend the existing local answerability benchmark with temporal cases. No public MCP surface change.
- **Background:** five-minute DataPulse health observation (live, 413 datasets), daily Engine NPRA output, CI/Pages on merge `372c5ade9`.
- **Deferred/untouched:** buyer/NPRA lane (Engine), claim-level citation validation (next slice), open-data quality dimensions (queued), MCPVerse task suite (queued), deployment/push (separate decision).

## Evidence ground truth (probed 2026-09-07)

- `health/history.jsonl`: 511,123 rows spanning 2026-08-30 → 2026-09-06 (gitignored pipeline output; never loaded at runtime).
- **71 datasets have real status transitions** between first and latest observation. Verified examples:
  - `blood_donations`: aging → fresh
  - `bnm_kijang_emas`: stale → aging
  - `bnm_opr`: stale → reference
  - `currency_in_circulation`: aging → stale
  - `dgm_payments_transactions_fpx`: fresh → stale
- The merged answerability benchmark already covers ahistorical cases (`fresh/aging/unknown-freshness/reference/unsafe/conflicting/underspecified/out-of-catalogue`) in `mcp/answerability_benchmark.py` + fixture + tests.

## Classification

| Track | Status | Evidence |
|---|---|---|
| Answerability benchmark | shipped (merged, pushed) | `7be12f9cb`, merge `372c5ade9` on `origin/main` |
| Temporal stale-evidence benchmark | in progress (this slice) | this note + dispatch brief |
| Claim-level citation validation | queued | after temporal slice |
| Open-data quality dimensions | queued | — |
| MCPVerse agent task suite | queued | — |
| Buyer/NPRA monetization | deferred to Engine | operator boundary 2026-09-06 |

## Fixture design (checked-in, deterministic)

- ~8 cases extracted from real history records (dataset id, observed_at, cycle, status, shape_hash); a few KB total; no runtime read of `history.jsonl`.
- An `as_of_date` field on the candidate request selects the evidence valid at that date when multiple observations exist.
- Precedence builds on the existing evaluator: request shape → no record → conflicting safety classes → unsafe → then temporal resolution:
  1. `as_of_current_fresh`: as-of date ≥ latest observation, fresh → `answer` / `supported_evidence`
  2. `as_of_historical_valid`: as-of date matches an older observation whose status was safe at that time → `answer` / `historical_evidence` with the historical observation exposed (never presented as current)
  3. `as_of_before_first_observation`: as-of date precedes all observations → `abstain` / `no_supported_record` (explicit unknown; never infer absence)
  4. `stale_presented_as_current`: only stale observation, no as-of date → `abstain` / `unsafe_evidence`
  5. `superseded_stale_selection`: candidate picks the older stale observation when a newer safe one exists without as-of justification → `abstain` / `conflicting_evidence` (HoH failure mode)
  6. `temporal_reference_only`: as-of observation is reference-status → `warn` / `reference_only`
  7. `temporal_uncertain`: as-of observation is aging/unknown-freshness → `warn` / `uncertain_freshness`
  8. `future_as_of_date`: as-of date after the latest observation → `warn` / `as_of_beyond_latest` (answerable only with the latest evidence; never fabricate)
- Unknowns preserved; no semantic truth, licence, or real-world-absence inference.

## First gate

New temporal cases pass against the extended evaluator, byte-stable report, full MCP suite green, zero public-surface/tool/taxonomy change.
