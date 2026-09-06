# Four-call recipe — citing Malaysian public data via DataPulse MY

Any agent platform that cites a Malaysian public dataset should run the following
four-call workflow before publishing the citation. Each call is read-only. The
recipe is identical to the canonical sequence already exercised by DataPulse's own
narrative and is verified by `scripts/tests/test_agent_workflow_recipe.py` against
the live `mcp/server.py` AST and `mcp.json` tool list.

## The four calls

Step 1  `search_datasets(query, licence?, source?, limit?)`
        Find a candidate Malaysian dataset.

Step 2  `get_dataset(dataset_id)`
        Inspect metadata and current health, including
        `content_freshness_date` and `freshness_signal_source`.

Step 3  `verify_dataset(dataset_id, include_proof_steps?)`
        Fail-closed Sigstore per-dataset receipt check with artifact references.

Step 4  `get_provenance([dataset_id])`
        Emit citation-ready provenance: probe time, HTTP status, request URL,
        access dependency, freshness source, content date, record count,
        shape fingerprint, anomaly flag, status.

## Refusal rule

`trust_verdict(dataset_id)` returns one of `USE`, `WARN`, `REFERENCE-USE`, or `STOP`.
If the verdict is `WARN` or `STOP`, do not cite without a human-readable reason;
do not invent provenance; do not omit the verdict from the citation block.

## Offline verification one-liner

The same health attestation can be verified offline against a Sigstore bundle
without calling the MCP server. This is the citation anchor for any pipeline that
needs to prove its evidence after the MCP endpoint is unreachable:

    cosign verify-blob-attestation \
      --bundle https://www.data-pulse.my/signatures/health.latest.sigstore.json \
      --certificate-identity https://github.com/r3dz4r/datapulse-my/.github/workflows/deploy-cloudflare-pages.yml@refs/heads/main \
      --certificate-oidc-issuer https://token.actions.githubusercontent.com \
      --type https://www.data-pulse.my/predicates/health-snapshot/v1 \
      https://www.data-pulse.my/health/latest.json

## Citation block (datapulse/v1/citation)

The smallest audit-grade citation contains these fields:

| Field | Source |
|---|---|
| `dataset_id` | caller's chosen identifier from step 1 |
| `evidence_url` | `https://www.data-pulse.my/data/<dataset_id>.md` |
| `observed_at` | from step 4 result |
| `source_url` | canonical upstream URL from manifest |
| `status` | from `health/latest.json` |
| `methodology_version` | from `health/latest.json` |
| `licence` | from manifest |
| `fingerprint` | `shape-v1:sha256` from `health/latest.json` |
| `datapulse_verdict` | one of `USE`, `WARN`, `REFERENCE-USE`, `STOP` (from step refusal rule) |
| `limitations` | free-text string; never empty |

## Boundary

DataPulse observes Malaysian public sources and produces evidence; it does not
certify legal compliance, substantive upstream truth, or regulatory outcomes.
The citation block is evidence for the *decision*, not a replacement for it.
