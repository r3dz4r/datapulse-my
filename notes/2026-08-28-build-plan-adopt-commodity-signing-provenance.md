# DataPulse build plan — adopt commodity signing/provenance, keep evidence-mcp moat

**Date:** 2026-08-28
**Supersedes / builds on:** `2026-08-28-oss-trust-provenance-niche-scan.md` (research),
`2026-08-24-p6-attestation-architecture-decision.md` (P6 stand-down),
`strategic-consulting/references/trust-infrastructure-selection.md` (trust-infra selection).
**Model:** phased Codex dispatches; each phase is a discrete, verifiable slice.
**Constraint:** legacy Ed25519 chain retained; private OpenBao/Rekor stays deferred (P6).

---

## Design principle

DataPulse is the trust/evidence **output** layer. Adopt commodity standards for provenance
currency + verification format; keep custom (and moat-protected): the evidence-receipt engine,
the MCP-native health surface, and the 10-status/provenance model for MY gov data.

**Operational burden of the adopted stack: zero servers.** Artifacts ship as static JSON on
GitHub Pages; a CI job signs per refresh; consumers verify with `cosign verify-blob --bundle`.

---

## Phase 0 — Contract (before any build)

1. Keep DataPulse read-only, no upstream mutations (AGENTS.md hard rule #5).
2. No re-instatement of OpenBao/Rekor publisher timers or real-lab-gate until a separate
   P6.2 approval. All new signing is **public-Sigstore / cosign keyless**, never private Raft.
3. Every phase lands behind the deterministic-safety-net (`ci.yml`) + release invariants.
4. Evidence receipts keep the exact current field contract (source, dataset ID, licence,
   observed timestamp, content date, status, schema state, claim scope, limitations, evidence URL).

---

## Phase 1 — Cosign/Sigstore bundle signing of the health snapshot (highest leverage)

**Goal:** publish an independently verifiable Sigstore bundle + DSSE/in-toto statement for
`health/latest.json` per refresh, proving it was produced this cycle with a stable identity.

**Adopt:** cosign `sign-blob` keyless (OIDC `--identity-token`), Sigstore bundle format,
DSSE/in-toto/SLSA predicates, public Rekor inclusion (SET embedded in bundle for offline verify).

**Files (Codex dispatch #1, datapulse-my, sol):**
- New `scripts/gen_sigstore_bundle.py` — builds the in-toto Statement (subject = health/latest.json
  digest; predicate = dataset count, checked-at, source SHA, methodology versions, legacy binding ref)
  and renders it + the cosign bundle path in the pipeline output set.
- New CI job (or extension of `ci.yml` / an `attest`-style job) that, on each health refresh,
  calls `cosign sign-blob --bundle` with OIDC identity → emits `signatures/health.latest.sigstore.json`
  + the in-toto statement → commits/publishes to Pages.
- `verify_agent_ready.sh` / release invariants add: bundle is parseable + offline-verifiable
  (cosign verify-blob --bundle against the OIDC identity) — but **must not red the deploy when
  signer unavailable** (align with the P6 non-blocking deploy fix already in flight).

**Acceptance:** a human or agent can `cosign verify-blob --bundle health.latest.sigstore.json
--certificate-identity <oidc> --certificate-oidc-issuer <issuer> health/latest.json` and get a
valid offline verification.

**Non-goal in Phase 1:** no per-dataset signing yet; no schema change; legacy Ed25519 chain untouched.

---

## Phase 2 — Evidence receipts as DSSE/in-toto statements + datacontract validation

**Goal:** serialize each dataset's evidence receipt in a standards-shaped, agent-consumable format
(`datacontract/cli` + bitol ODCS), and make receipts independently verifiable.

**Adopt:** datacontract/cli (1,050★, MIT) as the contract-validation engine; bitol ODCS schema for
the receipt/contract shape; keep the custom receipt field contract.

**Files (Codex dispatch #2, datapulse-my, terra):**
- Define `datacontract/*.yaml` per dataset (or a generated manifest) encoding freshness SLA,
  expected record count, schema shape, licence — the DataPulse trust contract.
- `scripts/gen_evidence_receipt.py` — extend the existing receipt generator to emit the receipt in
  an ODCS-shaped envelope + register it as an in-toto predicate for the dataset's signature.
- `scripts/run_datacontract_validation.sh` — invoke `datacontract lint`/`test` in CI over generated
  contracts; wire failures into the (now non-blocking-signer) release invariants so a DQ regression
  still fails but signer-down does not.

**Acceptance:** `datacontract test --schema <generated-contract>` passes against the live
`health/latest.json`; contract drift or schema break trips the release gate.

**Non-goal:** no per-dataset cosign signing yet; datacontract is validation/orchestration, not the store.

---

## Phase 3 — Signed evidence receipts per dataset (the moat's cryptographic completion)

**Goal:** agent can verify a *specific dataset's* evidence receipt independently, not just the
whole-snapshot bundle.

**Adopt:** per-dataset DSSE/in-toto statement (subject = `data/<id>/receipt.json` digest or the
health row digest) — signed via cosign keyless in batch per refresh.

**Files (Codex dispatch #3, datapulse-my, sol):**
- Extend `gen_evidence_receipt.py` to emit, for each 389 dataset, a signed in-toto statement
  (+ bundle) whose predicate carries the 10-status health row + freshness signal + licence.
- A batch cosign signing step in the refresh job (single OIDC identity, one SET per dataset or
  one batched statement). Keep the existing MCP `get_evidence_receipt` surface consistent.
- Conservation: verify cost per dataset at ~USD negligible (public Rekor, no self-host).

**Acceptance:** `cosign verify-blob --bundle data/<id>.receipt.sigstore.json` succeeds for a sample
of datasets; `get_evidence_receipt` MCP returns the signed receipt + bundle ref.

**Non-goal:** no distributed signing (Solana/witness chains); no self-hosted transparency log.

---

## Phase 4 — Agent-facing MCP hardening (the wedge's public face)

**Goal:** make DataPulse the only MCP-native "agent consumes MY-data health before trusting it" surface.

**Adopt:** OpenDQV-style MCP-server pattern (write-time validation + MCP), dq-mcp tool vocabulary,
DataQ/DQV provenance-scoring schema as inspiration. Keep custom: 10-status taxonomy,
`verify_dataset`, `get_dataset_health`, `get_freshness`, `get_schema_drift`, `get_evidence_receipt`.

**Files (Codec dispatch #4, datapulse-my, terra):**
- Confirm/advertise the MCP tools align with the signed-receipt output of Phase 3 (each health tool
  returns the bundle ref + offline-verification hint).
- Add an `llms.txt` / agent.json entry documenting "verify before trust": how an agent fetches a
  dataset's signed receipt and independently verifies it.
- Update `mcp.json` advertisement + M8ven/OpenAI directory metadata.

**Acceptance:** an agent using the MCP surface can obtain, for any dataset, health + evidence +
signed-receipt-verification in ≤3 tool calls; directory listings reflect the new capabilities.

---

## Phase 5 — Sovereignty positioning (differentiator, no new build)

**Goal:** convert the empty-OSS-wedge into a defensible position. No code; messaging + docs.

**Artifacts (operator-owned markdown, not code):**
- Draft the "Malaysia/my-governing-data sovereignty" framing (privacy + licence provenance) that no
  Western/EU/US-funded MCPVerify/One/NeuralTrust/Strata/M8ven/c0mm0 entrant can claim.
- One-pager / README section: "verify before trust" + the signed-receipt verification path.
- Gap note: DataPulse's own repo is already the first OSS in `mcp + government-open-data +
  malaysia + ai-agent` — document that first-mover claim.

---

## Sequencing / dependencies

- Phase 1 first (unblocks per-refresh independent verification; highest leverage).
- Phase 2 next (contract validation = the per-dataset DQ gate).
- Phase 3 depends on 1+2 (needs per-dataset receipts + bundle pipeline).
- Phase 4 depends on 3 (MCP must consume signed receipts).
- Phase 5 anytime after 1 (messaging can precede later phases).

Each phase is an independent Codex dispatch with its own acceptance test and commit; push is a
separate operator authorization per phase. No phase re-instates the private signer lane.

## Definition of done (whole plan)

- Every refresh publishes: legacy Ed25519 chain (unchanged) + a Sigstore bundle + per-dataset
  signed evidence receipts + datacontract-validated contracts.
- An agent (human or MCP) can independently verify any dataset's freshness/health evidence
  offline via `cosign verify-blob --bundle`, without trusting a DataPulse server.
- Deploy stays green when the public-Sigstore signer is unavailable (non-blocking, P6-aligned).
- DataPulse is documented + positioned as the only MCP-native trust layer for licensed MY gov data.

## Risks / honest flags

- **cosign keyless requires OIDC** — GitHub OIDC works natively in Actions (free); non-CI runs
  need a token. Contained to the CI refresh job by design.
- **public Rekor = public metadata** — for the *public* health receipts that's acceptable and even
  desirable (transparency). If a future buyer needs private custody, that's a P6.2 decision — the
  adopted stack's bundle format is compatible with later re-signing into a private witness.
- **zero-server is only true if CI time/usage stays within GitHub Actions free tier** — signing 389
  dataset receipts per refresh is a batch cosign call; if it grows, move signing to a minimal KMS
  (Phase 6 candidate) — still not OpenBao HA.
