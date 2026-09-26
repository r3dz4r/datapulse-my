---
audience: everyone, including procurement and press
canonical: true
volatility: stable
owner: operator
review_trigger: when the product boundary, the status taxonomy, or the verification path changes
last_verified: 2026-09-26
---

# DataPulse in one page

## The canonical description

This paragraph is the single product description. Any surface that describes DataPulse in one paragraph quotes it verbatim rather than paraphrasing it.

> DataPulse is an open, read-only verification layer for Malaysian public data. It continuously observes Malaysia's official open datasets — those published through data.gov.my, Bank Negara Malaysia, DOSM, the Department of Environment, the Ministry of Health, KPDN and MET Malaysia — and publishes machine-readable evidence about each one: whether the source is reachable, how fresh its content is, which licence applies, whether its structure or record count has changed, and when the observation was signed. Every dataset carries one of ten explicit statuses instead of a blanket green tick, and each published observation can be checked by a third party: receipts are signed, the signing keys are published with validity windows and rotation history, and a single-file verifier reproduces the check with no DataPulse installation. DataPulse does not replace the official source and does not certify that a publisher's data is substantively correct — it makes the condition of the source observable, and the observation reproducible.

Surfaces that quote it: this page, the repository README, the agent manifest, the MCP advertisement, and the LLM index. If they disagree with this page, this page wins.

For surfaces with a hard length limit, the short canonical form is:

> DataPulse — an open, read-only verification layer for Malaysian public data, publishing per-dataset freshness, licence, structure and signed-observation evidence for AI agents, analysts and auditors.

Both forms describe the same product with the same boundaries. Neither claims that a publisher's data is true.

## The expensive failure it prevents

An answer that cites a Malaysian public figure is only as good as the state of the source behind it. The common failures are quiet ones: the dataset stopped updating months ago and nobody noticed, the licence does not permit the reuse being proposed, the schema changed and a downstream pipeline is now reading the wrong column, two agencies publish the same indicator and disagree, or the page being cited returns a successful response while serving year-old content.

None of those are model hallucinations. They are unobservable source conditions, and they surface in production rather than in review. DataPulse exists to make them observable before they are relied on.

## What you receive, per dataset

| Field | What it tells you |
|---|---|
| Status | One of ten explicit states, with the reason for it |
| Freshness | Content age measured against the source's declared cadence, plus the age of the last successful observation |
| Structure | Observed schema shape and record count against the recorded baseline |
| Licence | The declared licence, and whether reuse is permitted |
| Provenance | The custodian, the steward, and the exact source URL observed |
| Evidence | A signed receipt with a digest, and a transparency-log entry where that layer applies |

## What DataPulse explicitly does not do

- It does not replace, mirror, or write to any official source. It is read-only by design.
- It does not assert that a publisher's data is semantically true, complete, or fit for a particular use.
- It does not certify an arbitrary third-party server's safety, nor act as an admission controller.
- It does not give legal advice on licence interpretation.
- It does not guarantee that any dataset is current. A source that cannot be proven fresh is labelled as such, not silently treated as healthy.

The full boundary is owned by [Trust contract](trust-contract.md); the status vocabulary is owned by [Status semantics](status-semantics.md).

## Verify it yourself

Two commands, no DataPulse installation and no account:

```bash
curl -fsSLO https://raw.githubusercontent.com/r3dz4r/datapulse-my/main/scripts/verify_external.py
```

```bash
python3 verify_external.py
```

That reproduces the published signature, source-of-record and transparency-log layers, printing one result line per layer. The per-dataset receipt path, its expected output, its failure output, and the trust anchors are in [Verify a DataPulse claim](verify.md).

## Start here

- Build something with it: [Quickstart](quickstart.md)
- Check a claim independently: [Verify a DataPulse claim](verify.md)
- Understand the boundaries: [Trust contract](trust-contract.md)
- Read the statuses: [Status semantics](status-semantics.md)
- Navigate everything: [Documentation map](documentation-map.md)

## Corrections

A wrong observation, a source that has changed shape, or a licence we have recorded incorrectly can be reported through the repository's issue tracker. Corrections are published as a new dated observation; earlier observations are not rewritten.
