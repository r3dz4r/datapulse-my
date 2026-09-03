---
title: "DataPulse MY — a practical introduction"
description: What DataPulse is, why it exists, and a hands-on tour of what the MCP lets you do. Teaches the shape of each answer and points to live values rather than snapshotting figures.
version: 1.1
last_updated: 2026-09-03
audience: learners curious about DataPulse, and developers/AI agents wanting to use it
visibility: public, read-only, no auth
---

# DataPulse MY — a practical introduction

**What you will learn:** what DataPulse MY is, the problem it solves, and a
hands-on feel for its capabilities by driving the live MCP server through real
queries.

By the end you should be able to answer three questions:

1. What is DataPulse MY?
2. What does it do that a raw open-data portal does not?
3. How do you ask it questions and how do you read its answers?

The services and dataset identifiers named below are stable. Their
**health state is not**: DataPulse re-probes on a schedule, so freshness values,
record counts, and statuses change continuously. This page deliberately does not
pin those numbers; it shows the *shape* of each answer and points you to where
you can read the live values yourself.

- Live catalogue and health: `https://www.data-pulse.my/health/latest.json`
- Live tool schemas and value semantics: the [MCP reference](https://www.data-pulse.my/mcp-reference.html)
- Live aggregate freshness: call `get_freshness_summary()` (shown below)

---

## 1. What DataPulse MY is

DataPulse MY is an **open, read-only trust and evidence layer** for Malaysian
public datasets. It continuously watches the official datasets published by
`data.gov.my`, `BNM`, `DOSM`, `DOE`, `KKM`, `KPDN`, `MET Malaysia` and similar
agencies, and answers one question those agencies' own portals do not:

> Is this dataset **fresh**, and can I **prove** what state it was in when I
> looked at it?

A data portal tells you a CSV exists. DataPulse tells you — with machine-checked
evidence — that the dataset is reachable, how old its newest row is relative to
the cadence its publisher declares, whether its shape or record count has
drifted, and it packages that observation so a third party can **verify** it
independently rather than taking DataPulse's word.

**One sentence:** DataPulse MY turns "Malaysian open data exists" into
"Malaysian open data can be trusted at a point in time."

The catalogue's dataset count is maintained as a live manifest (read the
authoritative number from `datapulse.json` or the `dataset_total` field of
`health/latest.json`). Each dataset is classified against a 10-status taxonomy
(`fresh | aging | stale | discontinued | degraded | browser_dependent |
unreachable | unknown | unknown_freshness | reference`).

| Property | What it is |
|---|---|
| Monitoring scope | Official Malaysian public datasets across multiple agencies |
| Freshness classification | 10-status taxonomy (listed above) |
| Access | read-only, no auth, public |
| MCP endpoint | `https://mcp.data-pulse.my/mcp` |
| MCP tools | 18 read-only tools (canonical list in `mcp.json`) |

---

## 2. Why this exists

Open-data portals publish files; they rarely tell you whether a file is
**current**. A shared CSV can sit stale for months. An AI agent that answers
from it will confidently quote outdated figures. DataPulse exists so that
"the number says X" becomes "the number says X, and the source was last fresh
on this date, with this evidence."

It is intentionally **read-only**. It does not write to any upstream agency. It
observes, classifies, signs its observations, and serves them — so consumers
get a verdict they can act on and a trail they can check.

For the full freshness methodology and the meaning of each status, see
[health-methodology](https://www.data-pulse.my/health-methodology).

---

## 3. Tour of the core capabilities

The MCP server exposes 18 read-only tools in four clusters. For each, this
section shows the call and explains the **shape** of what comes back — every
value is an illustration of structure, not a current claim. Read the
[MCP reference](https://www.data-pulse.my/mcp-reference.html) for exact schemas
and read the live endpoints for current values.

### 3.1 Find datasets — `search_datasets`

Ask in natural language what you are looking for; DataPulse returns **ranked
matches**, each with an id, title, source, licence, and a freshness status.

```text
TOOL: search_datasets(query: "fuel price")
```

What you get back is a list shaped like this (ids, titles, sources and licenses
are stable catalogue facts; the per-row `status` is live and changes):

| id | title | source | Licence family | status |
|---|---|---|---|---|
| `fuelprice` | Malaysian Fuel Prices | data.gov.my | Open Government Licence (Malaysia) | *live* |
| … | … | … | … | *live* |

The rows are ordered by relevance (a score field). For a fuel-price query you
should expect `fuelprice` (Malaysian Fuel Prices) and `pricecatcher` (KPDN
grocery prices) among the top matches, plus price-index datasets from DOSM —
but which exact set is ranked first reflects the live catalogue at query time.

`search_datasets` also accepts optional `source`, `licence`, and `limit`
filters, useful when you must restrict an answer to a specific agency or to
content you may reuse under a specific licence.

### 3.2 Inspect one dataset — `get_dataset`

Drill into a single dataset's stored record.

```text
TOOL: get_dataset(dataset_id: "fuelprice")
```

The response carries the dataset's **identity, license, custodianship, and
refresh contract** (stable) alongside its **current freshness verdict** (live).
For `fuelprice` you will reliably see fields like:

- **name:** Malaysian Fuel Prices
- **steward / attribution:** Ministry of Finance Malaysia via data.gov.my
- **refresh_frequency:** weekly
- **licence:** Open Government Licence (Malaysia)
- **url:** the catalogue URL on data.gov.my
- **status:** the live verdict (`fresh`/`aging`/… at runtime)
- **staleness_days:** days since the newest observed row (live)
- **record_count:** the observed row count, and whether it is inside the
  expected-tolerance band (live)
- **anomaly_detected:** whether DataPulse's freshness-anomaly detection flagged
  an irregular gap (live)

This is how you get the "is it current" question answered with attributable
fields — the identity fields are stable, the freshness fields are the live
observation.

### 3.3 Verify one dataset — `verify_dataset`

This is DataPulse's differentiator. `verify_dataset` returns the dataset record
**plus** its health observation **plus** the Sigstore bundle references that let
you prove the evidence was not tampered with.

```text
TOOL: verify_dataset(dataset_id: "fuelprice")
```

The response is the same `get_dataset` payload **re-grouped** into `dataset`
(identity), `health` (live observation), and `evidence` (the machine-checked
fields), augmented with:

- **signed + verifier_output:** the live result of an in-process
  `cosign verify-blob-attestation` against the served Sigstore bundle. When it
  runs, `signed` is `true` and `verifier_output` quotes `Verified OK`. If the
  verifier cannot run, the tool fails **closed** — `signed` is `false` rather
  than silently claiming a validity it could not check.
- **bundle_ref / statement_ref / provenance_artifact_url:** the served HTTPS
  artifact URLs for this dataset's signed evidence.
- **verification_hint:** an exact `cosign verify-blob-attestation` command you
  can run yourself against those artifacts.

Because the bundle is served as a normal HTTPS artifact, you can verify
DataPulse's evidence with the same tooling used for software supply-chain
signatures — and the live MCP already does this on your behalf. You do not have
to trust DataPulse; you can check it either way.

### 3.4 Summarise health coverage

Quick, aggregate questions about the whole catalogue:

- `get_freshness_summary()` returns the total dataset count and the count per
  freshness status **as of the latest published snapshot** — always current when
  you call it.
- `find_stale()`, `find_anomalies()`, `find_deteriorating()`,
  `find_recovering()`, `find_unreliable()`, `find_schema_drift()` return the
  datasets meeting each criterion, ranked with evidence.
- `trust_verdict()` and `verify_attestation()` expose the trust-plane posture.
- `get_provenance()` and `get_evidence()` return citation-ready provenance and
  evidence receipts.

Call `get_freshness_summary()` yourself — it is the single fastest way to see
the current state of the whole catalogue in one line:

```text
TOOL: get_freshness_summary()
# returns e.g.: fresh=N, aging=N, stale=N, reference=N; dataset_total=N
# checked_at=<the latest observation timestamp>
```

The exact counts change continuously; the field names and the `checked_at`
timestamp are the parts you should rely on.

---

## 4. Worked pattern: "find something current about fuel"

Put the pieces together. To answer "what fuel-related datasets can I cite
against, and is the main one fresh?"

1. `search_datasets("fuel price")` → narrows to a ranked set you can inspect.
   Expect a fuel-price catalogue entry at or near the top.
2. `get_dataset(<that id>)` → read its identity + live freshness verdict (status,
   staleness, cadence).
3. `verify_dataset(<same id>)` → get the evidence artifact URLs so the claim is
   independently checkable.

That is the whole shape of a defensible answer: **find → inspect → verify.**

---

## 5. Where to go next

- [MCP reference](https://www.data-pulse.my/mcp-reference.html) — the generated
  schema and signature for every one of the 18 tools; the exact field semantics.
- [Live health](https://www.data-pulse.my/health/latest.json) — the current
  freshness snapshot these tools read (and no-auth, so you can compare tool
  output to the raw JSON).
- [Agent quickstart](https://www.data-pulse.my/agent-quickstart.html) —
  five-minute onboarding for AI agents that must cite Malaysian data correctly.
- [Agent workflows](https://www.data-pulse.my/agent-workflows.html) — deeper
  integration patterns.
- [Evidence receipt spec](https://www.data-pulse.my/evidence-receipt-spec.html) —
  the format of the signed evidence artefacts.
- [The trust-layer notebook](https://github.com/r3dz4r/datapulse-my/blob/main/docs/trust-layer-notebook.ipynb) —
  a Colab tutorial that verifies a receipt end-to-end with cosign.

## 6. Try it yourself

The server needs no auth key. In a client that speaks MCP, connect to
`https://mcp.data-pulse.my/mcp` and run `search_datasets` on a topic you care
about (try `geography`, `health`, `economy`, `transport`, or an agency you
follow). Then `get_dataset` the top result and read its identity and freshness
verdict. Then `verify_dataset` the same id and inspect the evidence artifact
URLs and `verification_hint` it returns. Every value you see is the live current
state — no number in this page will disagree with what the tools answer, because
this page does not pin any.
