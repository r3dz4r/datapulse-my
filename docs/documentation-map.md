---
audience: everyone
canonical: true
volatility: stable
owner: operator
review_trigger: when a canonical document is added, merged, or retired
last_verified: 2026-09-26
---

# Documentation map

DataPulse documentation is part of the public evidence contract. This map tells readers where to start, and tells maintainers which document owns each question.

If you read one page: [DataPulse in one page](one-pager.md) is the product description, and [Verify a DataPulse claim](verify.md) is the thing no comparable Malaysian data product publishes.

## Start here

**New to DataPulse** — [One page](one-pager.md), then [Trust contract](trust-contract.md).

**Build with it** — [Quickstart](quickstart.md), then [Agent workflows](agent-workflows.md) and the generated [MCP reference](mcp-reference.md).

**Check a claim** — [Verify a DataPulse claim](verify.md), then [Evidence receipt specification](evidence-receipt-spec.md) and [Reproducibility](reproducibility.md).

**Audit or procure** — [Trust contract](trust-contract.md), [Status semantics](status-semantics.md), [Enterprise and governance guide](enterprise-governance.md), [Release verification](release-verification.md).

**Publish or maintain a source** — [Dataset lifecycle](dataset-lifecycle.md), [Health methodology](health-methodology.md), [Operations](operations.md), [Incident response](incident-response.md).

**Operate the repository** — [Release process](release-process.md), [Source-of-truth map](source-of-truth-map.md), [Integration patterns](integration-patterns.md), [Glossary](glossary.md).

## Who owns which question

| Question | Canonical document |
|---|---|
| What is DataPulse, in one paragraph? | [One page](one-pager.md) |
| What may I infer, and what is explicitly not claimed? | [Trust contract](trust-contract.md) |
| What does each status mean, and what should I do about it? | [Status semantics](status-semantics.md) |
| How is health actually judged? | [Health methodology](health-methodology.md) |
| How do I get to first success? | [Quickstart](quickstart.md), [Agent workflows](agent-workflows.md) |
| How do I verify a claim myself, and what does a pass prove? | [Verify a DataPulse claim](verify.md) |
| What is inside a receipt? | [Evidence receipt specification](evidence-receipt-spec.md) |
| Can I reproduce a release or an observation? | [Reproducibility](reproducibility.md), [Release verification](release-verification.md) |
| How does a dataset enter, change, or leave the catalogue? | [Dataset lifecycle](dataset-lifecycle.md) |
| What do I do when something fails? | [Incident response](incident-response.md), [Troubleshooting](troubleshooting.md) |
| Can we procure this, and what are the boundaries? | [Enterprise and governance guide](enterprise-governance.md) |
| How does it fit an existing system? | [Integration patterns](integration-patterns.md) |
| Where do the machine-readable facts live? | [Source-of-truth map](source-of-truth-map.md) |
| Which tools exist, with what schemas? | Generated [MCP reference](mcp-reference.md); never a hand-written list |
| What does a term mean? | [Glossary](glossary.md) |

## Public surfaces

Canonical human pages: the dataset register at the root route, the [NPRA page](https://www.data-pulse.my/npra.html), the [health methodology](health-methodology.html), [data collection and privacy](privacy.html), and [Learn](https://www.data-pulse.my/learn.html).

The authoritative inventory of public surfaces, including every machine artifact, is the served [sitemap.xml](https://www.data-pulse.my/sitemap.xml) with labels in [llms.txt](https://www.data-pulse.my/llms.txt), and the authority boundaries are in [Source-of-truth map](source-of-truth-map.md). This map does not maintain a second list. Three machine surfaces matter to verification specifically: the dataset manifest, the health snapshot, and the probe key registry at `/.well-known/datapulse-probe-keys.json`.

## Evidence and history

Point-in-time records, kept as published and never rewritten:

| Record | What it captures |
|---|---|
| [Audit 2026-08-05](AUDIT-2026-08-05.md) | Repository contract audit |
| [Design audit 2026-08-14](DESIGN-AUDIT-2026-08-14.md) | Presentation and structure review |
| [Health compatibility report 2026-08-08](health-compatibility-report-2026-08-08.md) | Policy compatibility findings |
| [MCP self-grade 2026-08-08](mcp-self-grade-2026-08-08.md) | Tool-surface self-assessment |
| [Health policy compatibility](health-policy-compatibility.md) | Status policy comparison |
| [Data JSON workspace proposal 2026-08-08](data-json-workspace-proposal-2026-08-08.md) | Proposal record, not a commitment |
| Trust snapshots | [2026-08-09](trust-snapshot-2026-08-09.md), [2026-08-10](trust-snapshot-2026-08-10.md), [2026-08-11](trust-snapshot-2026-08-11.md), [2026-08-13](trust-snapshot-2026-08-13.md), [2026-08-16](trust-snapshot-2026-08-16.md), [2026-09-06](trust-snapshot-2026-09-06.md) |
| [Historical observation](historical-observation.md) and [Observation store](observation-store.md) | How past observations are retained and read |

[DataPulse intro](datapulse-intro.md) and [Verification layer pitch](verification-layer-pitch.md) are earlier position papers. The [one-page description](one-pager.md) supersedes the intro for product wording; the pitch remains a dated position paper, not a contract.

## Also in this directory

Contract and platform records: [Contract inventory](contract-inventory.md), [MyAISafe contract inventory](myaisafe-contract-inventory.md), [Record evidence v1](record-evidence-v1.md), [Branch protection handoff](branch-protection-handoff.md), [AI directory listings](ai-directory-listings.md), [Adoption seeding](adoption-seeding.md), [MCP deployment](mcp-deploy.md), [Architecture](architecture.md). Notebook and its brief: [Trust-layer notebook](trust-layer-notebook.ipynb) with [its agent brief](trust-layer-notebook.AGENTS.md). Agent guidance: [AGENTS.md](AGENTS.md) for contributors to this directory.

## Document ownership metadata

Every canonical page under `docs/` carries front matter so ownership and freshness are machine-checkable rather than remembered:

```
audience: <who this page is for>
canonical: true
volatility: <live | contract | stable | historical>
owner: operator
review_trigger: <what event makes this page wrong>
last_verified: YYYY-MM-DD
```

`last_verified` is a human attestation that someone read the page against the live system. It is not a file modification time, and a bot or a translation must not refresh it. `review_trigger` records what makes the page false, so a reader knows when to check rather than when it was last touched.

## Volatility labels

| Label | Meaning | Maintenance rule |
|---|---|---|
| `live` | Changes with health cycles or deployments | Generate it, or read it from the live source |
| `contract` | Changes only through an intentional contract decision | Version it and update consumers together |
| `stable` | Explanatory guidance with low change frequency | Review when the underlying behaviour changes |
| `historical` | Point-in-time evidence | Date it and do not rewrite it |

## Completeness promise

A documentation change is not complete merely because a Markdown file exists. The new or changed surface must have:

1. a named audience;
2. one canonical question it answers;
3. links to its source contracts;
4. a review trigger;
5. tested examples where it gives commands or routes;
6. an entry in this map, and a place in the served sitemap if it is public.

## What does not belong here

Private strategy, adoption metrics, partner information, and operator claims registers stay outside the public documentation set. Live facts — counts, status distributions, tool inventories, source commits — are read from their canonical machine-readable inputs, never copied into prose unless the statement is explicitly dated and historical.
