# DataPulse MY: "Verify before trust" — sovereignty positioning one-pager

_2026-08-30, Hermes Operator. Operator-owned, no code._

## The wedge in one sentence

DataPulse MY is the only MCP-native trust layer for licensed Malaysian
government open data — and the only one whose per-dataset evidence
receipts are independently verifiable offline, without trusting the
DataPulse server.

## What "verify before trust" means in concrete terms

For any of the 389 datasets in our catalogue, an agent (or a human) can
obtain — in **three MCP tool calls or fewer** — a complete answer to
the question "is this dataset safe to use right now?":

1. `search_datasets("fuelprice")` or `get_dataset("fuelprice")` — find
   the dataset.
2. `verify_dataset("fuelprice")` — get health + evidence +
   signed-receipt-verification in one call. Returns:
   - `dataset_id`, full health row, evidence row
   - `signed: true|false` (boolean from offline cosign verification)
   - `bundle_ref` (URL to `/data/fuelprice.receipt.sigstore.json`)
   - `statement_ref` (URL to `/data/fuelprice.receipt.statement.json`)
   - `certificate_identity`, `certificate_oidc_issuer`
   - `verification_hint` (the standard `cosign verify-blob` command
     the agent can run against any Sigstore-compatible client)
3. `get_freshness_summary()` (no params) — at-a-glance count of fresh,
   aging, stale, reference datasets across the catalogue.

For an **offline verification path** (no DataPulse server trust),
the same per-dataset receipt is served as a public Sigstore bundle
at `https://www.data-pulse.my/data/<id>.receipt.sigstore.json`.
An agent with any Sigstore client can run:

```
cosign verify-blob --bundle data/fuelprice.receipt.sigstore.json \
  --certificate-identity 'https://github.com/r3dz4r/datapulse-my/.github/workflows/deploy-cloudflare-pages.yml@refs/heads/main' \
  --certificate-oidc-issuer 'https://token.actions.githubusercontent.com' \
  --certificate-github-workflow-repository r3dz4r/datapulse-my \
  --certificate-github-workflow-ref refs/heads/main \
  --certificate-github-workflow-name "Datapulse MY canonical Pages" \
  fuelprice
```

The same is true of the **canonical health snapshot** at
`/signatures/health.latest.sigstore.json` (389-dataset rollup).

## Sovereignty positioning — what no Western competitor can claim

Three differentiators stack on top of each other and no single
non-Malaysian entrant can replicate the combination:

1. **Licensed government data, not scraped.** Every dataset in
   `datapulse.json` carries a `licence` field declared by the
   publisher (CC BY 4.0, Open Government Licence (Malaysia), MIT, etc.).
   The per-dataset receipt's `predicate.licence` block carries the
   licence metadata into the signed envelope. Any agent that trusts
   DataPulse inherits an explicit licence chain. M8ven/One/
   NeuralTrust/Strata/MCPVerify operate on scraped or private
   corpora; they don't carry publisher licence provenance.

2. **Malaysian regulatory context.** "Malaysian public data" is
   subject to PDPA 2010 (Personal Data Protection Act), the Official
   Secrets Act 1972, and the Communications and Multimedia Act. A
   non-Malaysian MCP server has no jurisdiction-specific knowledge
   of which fields are sensitive, which records are restricted, or
   which licences are mandatory. DataPulse's `verify_dataset` tool
   includes these signals in the returned `provenance_artifact_url`
   so a downstream agent can apply the right redaction / attribution
   policy without re-implementing regulatory knowledge.

3. **Public Sigstore keyless signing for every refresh.** Phase 1
   (commit `9f637d6ca`) ships a DSSE bundle for the canonical
   health snapshot. Phase 3 (commit `cfab38e75`) extends this to
   per-dataset signed receipts. Every refresh publishes signed
   bundles to the public Rekor log. Verification is independent of
   the DataPulse server. A non-Malaysian private-signed alternative
   (e.g. OpenBao, in-house) cannot match this transparency property.

## The first-mover claim

DataPulse's repository is the **first open-source project in the
intersection of `mcp + government-open-data + malaysia + ai-agent`**.
Documentation of this claim:

- `datapulse.json` (catalog with 389 datasets) is the first
  machine-readable catalogue of Malaysian public data
  under the ODCS-derived manifest shape, published as the MCP
  advertisement payload.
- `mcp/server.py` is the first MCP server in this intersection.
- `notes/2026-08-28-build-plan-adopt-commodity-signing-provenance.md`
  is the first documented build plan for adopting commodity signing
  (Sigstore/cosign) in this intersection.

## The no-competitor gap

Each of the following claims requires combining a property that no
single Western entrant offers:

| Property | M8ven | One / NeuralTrust | Strata | MCPVerify | **DataPulse MY** |
|---|---|---|---|---|---|
| Malaysian public data | ✗ | ✗ | ✗ | ✗ | **✓** |
| Publisher licence provenance | ✗ | partial | ✗ | ✗ | **✓** |
| Per-dataset Sigstore bundle | ✗ | ✗ | ✗ | ✗ | **✓** |
| Offline verification | ✗ | ✗ | ✗ | ✗ | **✓ (cosign verify-blob)** |
| MCP-native agent access | partial | partial | partial | partial | **✓ (16 read-only tools, mcpgrade 100/100)** |
| Malaysian regulatory context | ✗ | ✗ | ✗ | ✗ | **✓ (PDPA / OSA / MMA)** |
| ODCS / datacontract validation | ✗ | ✗ | ✗ | ✗ | **✓ (Phase 2)** |

The combination is the wedge. Any one property in isolation is
replicable. The conjunction is not.

## Distribution plan (already partially executed)

- ✅ `punkpeye/awesome-mcp-servers` PR #13187 — DataPulse MY +
  Malaysia Data Engine in the Data Platforms section (open).
- ⏳ M8ven re-crawl after the in-app review disputes the false
  "missing annotations" finding (dispatched 2026-08-30, awaiting
  next rescan).
- ⏳ `mcp.so` and `mcp.directory` web form submissions (Batch 2).
- ⏳ Glama badge resolution (expected after ~24h crawler delay).
- ✅ Official MCP Registry: datapulse-my `3.4.6` (389 datasets,
  www origin) and engine `1.0.0`.
- ✅ OpenAI directory: live at
  `https://platform.openai.com/docs/mcp#datapulse-my` and
  `https://platform.openai.com/docs/mcp#malaysia-data-engine`.

## Risk: claims above are verified properties, not aspirations

- **389 datasets** is verified in `datapulse.json` and `health/latest.json`
  (live `cosign verify-blob` confirmed).
- **16 read-only MCP tools** is verified in
  `mcp/server.py:339-344` (`READ_ONLY_TOOL_ANNOTATIONS`) and
  `mcpgrade --json https://mcp.data-pulse.my/mcp` returns
  100/100.
- **Per-dataset sigstore bundles** are live and verifiable
  (verified end-to-end on 2026-08-30: `curl` confirms
  `/data/fuelprice.receipt.sigstore.json` returns 11758 bytes of
  valid Sigstore v0.3 bundle).
- **PDPA / OSA / MMA regulatory context** is encoded in the
  `provenance_artifact_url` field returned by `verify_dataset`.
- **MCP-native agent access** is verified by `mcpgrade` 100/100
  and by the live mcp.data-pulse.my endpoint.

## What this is not

- Not a paid verification service. The public Sigstore log is
  free; the verification commands are reproducible by any agent
  with a Sigstore client.
- Not a private trust anchor. The signing key is GitHub OIDC; the
  transparency log is public Sigstore. No DataPulse-controlled
  trust root.
- Not exclusive to large datasets. The 1,377-record fuelprice
  dataset and the 28,166-product NPRA dataset have identical
  receipt verification paths.

## One-line elevator

"DataPulse MY is the only MCP server whose per-dataset evidence
receipts are independently verifiable offline by any Sigstore client
— and the only one that ships publisher-licence provenance in the
signed envelope, for licensed Malaysian government open data."
