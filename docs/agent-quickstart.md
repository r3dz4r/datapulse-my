---
title: Agent Quickstart — DataPulse
description: 5-minute onboarding for AI agents. Connect via MCP, fetch evidence, and cite it correctly.
version: 1.1
last_updated: 2026-09-01
audience: AI agents and their operators
visibility: public, read-only, no auth
---

<!-- BEGIN agent-quickstart-identity -->
# DataPulse — Agent Quickstart

> DataPulse is a **read-only evidence layer** for Malaysian public datasets. The live catalogue and machine advertisements are authoritative for current coverage.
<!-- END agent-quickstart-identity -->

This document is the 5-minute onboarding for any agent that wants to **cite Malaysian data correctly** without scraping, fabricating, or overclaiming.

**Read this first** if your agent is about to claim knowledge about any
dataset hosted at `data.gov.my`, `BNM`, `DOSM`, `DOE`, `KKM`, `KPDN`,
`MET Malaysia`, `eperolehan`, or `pricerunner`-class official sources.

---

## What DataPulse will and won't do

**Will:**
- Tell you the **observed** status of a dataset right now (fresh / aging / stale
  / discontinued / browser-dependent / reference).
- Hand you a **cited evidence receipt** with source identity, publisher,
  licence, observed time, content date, freshness state, schema signal,
  evidence reference, claim scope, and limitations.
- Give you a **decision posture** per dataset: `USE`, `WARN`, or `STOP`.
- Stay **read-only** forever — official publishers remain source of record.

**Will not:**
- Write to any upstream source. (DataPulse is observation-only.)
- Certify, vouch, or rate any publisher as "trustworthy" in absolute terms.
- Issue a universal trust score for a dataset (no `n/100` number to anchor).
- Serve paid data on this public surface. (Future: Malaysia Data Engine.)

---

## Step 1 — Read the manifest

The first URL an agent should hit: curated Markdown describing
every machine surface, what to cite, and what not to claim.

```bash
curl -sSL https://www.data-pulse.my/llms.txt | head -80
```

Or just `GET https://www.data-pulse.my/llms.txt` from inside your agent.

---

<!-- BEGIN agent-quickstart-mcp -->
## Step 2 — Connect to the MCP server

DataPulse exposes 19 read-only tools over 418 datasets at `https://mcp.data-pulse.my/mcp`.
Transport: **Streamable HTTP**. The live `mcp.json` advertisement is the authority for the current capability set.

**Connector config** (Claude / Cursor / OpenAI / generic agents):

```json
{
  "mcpServers": {
    "datapulse": {
      "url": "https://mcp.data-pulse.my/mcp",
      "transport": "streamable-http",
      "description": "DataPulse — read-only evidence layer for Malaysian public datasets"
    }
  }
}
```

### Current tools

| Tool | Use when |
| --- | --- |
| `search_datasets` | Use for discovery only: find DataPulse's 418 Malaysian public datasets by topic, source, or licence—for example, 'Malaysian public data inflation', licence and attribution, or a government dataset source. Returns ranked matches with id, title, source, licence, published status, and score. This is not trust verification: a status is published pipeline context, not proof that a dataset is current or reliable. For 'is this dataset current?' or verify before relying on data, use search_datasets → verify_dataset → get_provenance. |
| `get_dataset` | Return full detail for one dataset id, including its latest health status and last-verified timestamp, content_freshness_date, and freshness_signal_source (last_modified, content_parse, or none). Use to fetch the provenance/citation metadata for a dataset found via search_datasets and distinguish unknown-freshness from proven stale data. |
| `get_data_passport` | Return one bounded, machine-readable Dataset Passport v1 for a canonical dataset ID. It reads the published Passport artifact only; it does not fetch an upstream source or create evidence. The Passport describes observed metadata and evidence availability, not semantic truth, completeness, certification, legal permission, safety, or AI admission. |
| `find_stale` | Return datasets whose status is aging, stale, or degraded, plus datasets missing from the latest health snapshot. Use when an agent needs to know which data has a freshness or schema-validity risk. |
| `find_anomalies` | Return datasets flagged by the latest published anomaly detection (anomalies), ranked by how far the observed update interval exceeds its threshold. Optionally require a minimum publish-reliability grade; includes pipeline-computed anomaly and reliability evidence so agents do not recompute it. |
| `find_deteriorating` | Return datasets whose published freshness trend is deteriorating, ranked by staleness slope. Optionally require a minimum historical anomaly rate; includes pipeline-computed trend and reliability evidence so agents do not recompute it. |
| `find_recovering` | Return datasets whose published freshness trend is recovering, with the fastest staleness reductions first. Includes pipeline-computed trend and publish-reliability evidence. |
| `find_unreliable` | Return datasets whose evaluated publish-reliability grade is at or below a threshold (the unreliable ones), with the worst grades and lowest on-time percentages first. Reliability measures timeliness of successful freshness observations, not uptime; sample days are included so agents can judge evidence depth. |
| `find_schema_drift` | Return datasets with published structural or record-count drift evidence, ranked with structural changes first. Optionally require a minimum number of structural transitions; includes pipeline-computed evidence so agents do not infer drift from freshness alone. |
| `check_reconciliation` | Return the published cross-source reconciliation group for a dataset name or id, including per-member counts, dates, statuses, tolerances, and contextual deltas. A discrepancy requires human review and does not prove either source is wrong. |
| `get_provenance` | Use when asked 'can I cite this source?', for licence and attribution, or for citation-ready provenance. Returns source, steward, licence/attribution context, canonical URL, and compact published evidence context: probe time, transport, access dependency, freshness signal, schema drift / record-count drift context, anomaly flag, and status. Bind a citation to dataset identity, source/evidence URL, observed-at or last-checked time, DataPulse status/verdict, licence/attribution, and a receipt/evidence digest when available. You may cite the returned provenance and describe its published evidence; it is not a freshness guarantee and does not itself verify the source is current. For pre-trust use search_datasets → verify_dataset → get_provenance. |
| `get_evidence` | Use for a deep evidence audit or to inspect a provenance and evidence receipt. Returns the complete published evidence receipt for one dataset: probe time, transport, access dependency, freshness, schema drift / record-count drift, tolerance, status, anomaly fields, and receipt/evidence references. It reads published pipeline evidence, not a live source fetch: you may report what the pipeline observed, but must not infer the source is currently reachable or semantically true. Use it for a deep audit before or alongside verification. search_datasets → get_evidence → verify_evidence → verify_attestation. |
| `verify_dataset` | This is the preferred single-call pre-trust check for 'is this dataset current?', stale, unknown-freshness, degraded, or browser-dependent questions, and whenever an agent must verify before relying on data. Returns dataset metadata, published evidence and fail-closed signed receipt verification with artifact references. It verifies published artifacts, not a live source check: you may infer whether their receipt verifies, but must not infer current upstream availability or semantic truth. Use search_datasets → verify_dataset → get_provenance. |
| `get_freshness_summary` | Return a freshness-at-a-glance summary of the published catalogue: fresh, aging, stale, and reference counts plus the latest health check time. |
| `verify_evidence` | Use when a fresh, rate-limited live-vs-published comparison is needed for a direct-access dataset, for example after asking whether a government dataset is reachable now. Performs a rate-limited live GET and returns comparable transport receipts plus a match, mismatch, unreachable, or not_verifiable verdict. This live check is an observation, not semantic truth: it does not recompute content dates, record counts, or shape fingerprints. Results are ephemeral and do not update published health artifacts. For a deep audit use search_datasets → get_evidence → verify_evidence → verify_attestation. |
| `trust_verdict` | Return published attestation facts, the unsigned methodology-versioned trust score, numeric components, and component_availability reasons, plus existing health/trend/drift/reconciliation evidence for one canonical dataset id, e.g. 'fuelprice'. This tool does not re-probe or verify the signature; call verify_attestation separately. |
| `verify_attestation` | Use to verify a signed published probe attestation after an evidence audit. Returns L1 signature, key, time, and chain-link checks; optional L2 replay of daily heads to a Git-tag anchor; and L3 scope, which requires verify_evidence for live transport. A valid signature proves attestation integrity and scope, not upstream semantic truth or currentness. For a deep audit use search_datasets → get_evidence → verify_evidence → verify_attestation. |
| `find_by_licence` | Return all datasets with the given licence, summarised. Use to enumerate what's available under a specific licence for compliance/reuse scoping. |
| `usage_summary` | Aggregate anonymous tool usage for an inclusive ISO date range, e.g. 2026-08-01 to 2026-08-07. Returns `total_calls`, `by_outcome`, `by_tool`, `by_dataset`, `trust_distribution` (per-status counts of cited datasets) for the inclusive range. Legacy identity fields are ignored. |

**Raw HTTP clients:** use the protocol-valid initialize → initialized → tools/list sequence in [MCP deployment](mcp-deploy.md). Do not send a legacy one-step tool-request payload directly to the Streamable HTTP endpoint.
<!-- END agent-quickstart-mcp -->

---

## Step 3 — Fetch one evidence receipt

Pick one dataset (e.g. `fuelprice`) and ask for its evidence:

```bash
curl -sS https://www.data-pulse.my/data/fuelprice.md
```

Or via MCP: call the `get_evidence` tool with `dataset_id: "fuelprice"`.
Use the generated [MCP reference](mcp-reference.md) for the current protocol
and input schema rather than copying a legacy raw-HTTP payload.

**A receipt exposes evidence fields**, which should be quoted with their scope and timestamp:

1. Source identity and publisher
2. Licence and reuse context
3. Observed/retrieved time
4. Content date and freshness signal
5. Freshness/status classification
6. Schema or record signal
7. Evidence and provenance references
8. Claim scope
9. Limitations and unresolved uncertainty

The [evidence receipt specification](evidence-receipt-spec.md) is canonical for
field semantics. Do not infer missing values.

---

## Step 4 — Cite it correctly

The right way to cite a receipt in your answer:

> *"Per DataPulse (retrieved YYYY-MM-DDTHH:MMZ), the dataset `<id>` is
> currently `<status>`, with source identity `<id>` published by `<publisher>`
> under `<licence>`, `<N>` records observed. Decision posture: USE."*

**Never do these things:**
- Do not call the dataset "verified" or "accurate" or "true". Call it "observed".
- Do not paraphrase the source identity.
- Do not skip the retrieved-at timestamp.
- Do not invent field values when the receipt says "not observed."
- Do not report a freshness beyond `last_checked`. The publisher's own last-update
  is one input; DataPulse's `last_checked` is the *observation timestamp* your claim is
  anchored to, not a guarantee about the publisher's calendar.

---

## Worked examples

### Example A — "What fuel prices were charged yesterday?"

1. `GET https://www.data-pulse.my/llms.txt` → manifest points to `fuelprice`.
2. MCP call: `get_evidence` with `dataset_id: "fuelprice"`.
3. Inspect the returned status, observed time, record signal, and `Open Government Licence (Malaysia)` context if present.
4. Cite the receipt in the answer with the observed timestamp.
5. If the receipt says `WARN` or `STOP`, do not assert content; instead say the
   receipt's claim scope and limitations.

### Example B — "Is dataset X still being updated?"

1. MCP: call `get_dataset` for the canonical identifier `X`.
2. Inspect its status, `last_checked`, content date, and freshness signal.
3. Use `get_freshness_summary` or `find_stale` when a portfolio-level comparison is needed.
4. Cite `last_checked` (observation timestamp) and `content_date` (publisher's own
   timestamp). These are different and both should be quoted.

### Example C — "Will you auto-merge DataPulse receipts into my KB?"

- DataPulse receipts are written so they can be cited verbatim. They can be stored,
  summarised, or vector-searched.
- The licence on the receipt (e.g. `Open Government Licence (Malaysia)`) tells you
  what you may redistribute. Quoting is fine; do not claim the receipt itself
  is a license to redistribute the underlying publisher data without honouring
  the publisher's own licence.

### Example D — "Should I redact personal identifiers in this Malaysian dataset?"

- DataPulse's manifest (`/datapulse.json`) names `schema.documented_fields` for
  each dataset. Use that as ground truth on what the dataset exposes.
- Cross-reference with the publisher's own privacy page.
- If the publisher's policy is unclear, **refuse** the operation. DataPulse is
  read-only; it will not help you decide whether to publish data, only to verify
  the data you already cited.

---

## Machine surface inventory

| Surface | Purpose |
| --- | --- |
| `https://www.data-pulse.my/llms.txt` | Curated machine-readable discovery index. |
| `https://www.data-pulse.my/mcp.json` | Current MCP advertisement and schemas. |
| `https://www.data-pulse.my/agent.json` | Agent-purpose capability profile. |
| `https://www.data-pulse.my/datapulse.json` | Canonical dataset manifest. |
| `https://www.data-pulse.my/health/latest.json` | Latest observed health snapshot. |
| `https://www.data-pulse.my/data/<id>.md` | Human-readable dataset evidence/report path when available. |
| `https://mcp.data-pulse.my/mcp` | Read-only MCP server. |

For route coverage and current formats, use the live machine advertisements
and the [source-of-truth map](source-of-truth-map.md).

---

## Failure modes — what to do when something looks wrong

| Symptom | Likely cause | Action |
| --- | --- | --- |
| Receipt says `not observed` for a field | The pipeline didn't probe that signal (intentional honest surface) | Quote "not observed" verbatim. Do not infer. |
| Receipt says `WARN` or `STOP` | Dataset is degraded or unreachable right now | Quote the receipt's `Limitations`. Reduce confidence in the answer. |
| Dataset listing says `404` for `/data/<id>.md` | Receipt doesn't exist yet (newly added or de-scoped dataset) | Use `/datapulse.json` to check the manifest, then MCP `get_evidence`. |
| MCP endpoint unreachable | Live site incident | Check `/health/latest.json` — even if MCP is down, the latest health snapshot is still served. Cite from JSON. |
| Two receipts disagree | One is stale; one is fresh | Trust the one whose `retrieved_at` is more recent. |

---

## Honest posture — what to repeat to your user

When your agent cites DataPulse:

1. **Always cite the retrieved-at timestamp.**
2. **Use the literal field names** the receipt uses (`Source identity`, `Publisher`,
   `Licence and reuse context`, `Observed time`, `Content date`, `Freshness state`,
   `Schema or record signal`, `Evidence reference`, `Claim scope`, `Limitations`).
3. **Repeat the decision posture** (`USE`, `WARN`, `STOP`) verbatim.
4. **Never upgrade** "observed" to "verified", nor present a last-fetched value as
   definitive currency, without re-fetching.
5. **Defer to the publisher** if their licence is more restrictive than the
   receipt implies.

---

## Canonical guidance

- [Trust contract](trust-contract.md) — what DataPulse can and cannot establish.
- [Status semantics](status-semantics.md) — how to interpret every current status.
- [Evidence receipt specification](evidence-receipt-spec.md) — receipt fields and verification boundaries.
- [Agent workflows](agent-workflows.md) — complete discover/inspect/verify/cite jobs.
- [Glossary](glossary.md) — canonical terminology.
- [Source-of-truth map](source-of-truth-map.md) — which live or generated surface owns each fact.
