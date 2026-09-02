# Documentation map

DataPulse documentation is part of the public evidence contract. This map tells readers where to start and tells maintainers which document owns each question.

## Start here

| Need | Canonical document |
|---|---|
| Understand the product and its boundaries | [Trust contract](trust-contract.md) |
| Connect an agent | [Agent quickstart](agent-quickstart.md) |
| Complete a real evidence workflow | [Agent workflows](agent-workflows.md) |
| Interpret a health status | [Status semantics](status-semantics.md) |
| Understand a receipt or evidence object | [Evidence receipt specification](evidence-receipt-spec.md) |
| Understand source lineage and integrity | [Trust contract](trust-contract.md) and [Evidence receipt specification](evidence-receipt-spec.md) |
| Add, change, or retire a dataset | [Dataset lifecycle](dataset-lifecycle.md) |
| Respond to a failure | [Incident response](incident-response.md) |
| Reproduce a release or observation | [Reproducibility](reproducibility.md) |
| Assess governance or procurement fit | [Enterprise and governance guide](enterprise-governance.md) |
| Integrate DataPulse into a system | [Integration patterns](integration-patterns.md) |
| Define a term | [Glossary](glossary.md) |
| Inspect the complete MCP surface | [MCP reference](mcp-reference.md) |
| Understand the monitoring method | [Health methodology](health-methodology.md) |
| Operate or release the repository | [Operations](operations.md), [Release process](release-process.md), and [Release verification](release-verification.md) |

## Public surfaces

Canonical pages (other routes are compatibility aliases to these):

| Surface | Purpose |
|---|---|
| [Live dashboard](https://www.data-pulse.my/) (`/`) | Human-readable dataset status cards with embedded health and manifest data. |
| [NPRA page](https://www.data-pulse.my/npra.html) | Focused public NPRA dataset surface. |
| [Health methodology](https://www.data-pulse.my/health-methodology.html) | Status and freshness methodology, including the ten-status taxonomy. |
| [Learn](https://www.data-pulse.my/learn.html) | Verification-first guidance for building with Malaysian public data. |

Root machine artifacts (served at the website origin):

| Artifact | Purpose |
|---|---|
| [`/llms.txt`](https://www.data-pulse.my/llms.txt) | Machine-readable discovery index for AI agents and LLMs. |
| [`/agent.json`](https://www.data-pulse.my/agent.json) | Machine-readable agent capability manifest. |
| [`/mcp.json`](https://www.data-pulse.my/mcp.json) | MCP server advertisement (canonical tool count and schemas). |
| [`/datapulse.json`](https://www.data-pulse.my/datapulse.json) | Full machine-readable dataset manifest. |
| [`/health/latest.json`](https://www.data-pulse.my/health/latest.json) | Current published dataset health snapshot. |
| [`/health/trends.json`](https://www.data-pulse.my/health/trends.json) | Published freshness trend and reliability evidence. |
| [`/health/drift.json`](https://www.data-pulse.my/health/drift.json) | Published structural and record-count drift evidence. |
| [`/health/reconciliation.json`](https://www.data-pulse.my/health/reconciliation.json) | Cross-source publication differences for human review. |
| [`/feed.xml`](https://www.data-pulse.my/feed.xml) | RSS feed of dataset health changes. |
| [`/changelog.json`](https://www.data-pulse.my/changelog.json) | Machine-readable release-by-release summary. |
| [`/badges/`](https://www.data-pulse.my/badges/) | Per-dataset SVG status badges. |
| [`/ai-catalog.json`](https://www.data-pulse.my/ai-catalog.json) | AI resource directory (ARD) catalog of the MCP tool surface. |
| [`/catalog-snapshot.json`](https://www.data-pulse.my/catalog-snapshot.json) | Point-in-time catalog snapshot. |

The freshness-policy vocabulary (the ten statuses and their reference-family
splits) is owned by [health-methodology.md](health-methodology.md) and
[status-semantics.md](status-semantics.md); this map does not redefine it.

## Audience paths

### Agent or application builder

1. [Agent quickstart](agent-quickstart.md)
2. [Agent workflows](agent-workflows.md)
3. [Status semantics](status-semantics.md)
4. [Evidence receipt specification](evidence-receipt-spec.md)
5. [Integration patterns](integration-patterns.md)

### Analyst or researcher

1. [Trust contract](trust-contract.md)
2. [Status semantics](status-semantics.md)
3. [Agent workflows](agent-workflows.md)
4. [Evidence receipt specification](evidence-receipt-spec.md)
5. [Reproducibility](reproducibility.md)

### Auditor or governance reviewer

1. [Trust contract](trust-contract.md)
2. [Evidence receipt specification](evidence-receipt-spec.md)
3. [Reproducibility](reproducibility.md)
4. [Enterprise and governance guide](enterprise-governance.md)
5. [Release verification](release-verification.md)

### Source maintainer or contributor

1. [Dataset lifecycle](dataset-lifecycle.md)
2. [Health methodology](health-methodology.md)
3. [Operations](operations.md)
4. [Incident response](incident-response.md)
5. [Release process](release-process.md)

## Document ownership rules

- **Live facts** come from canonical machine-readable inputs and generated surfaces. Do not copy current counts, status distributions, tool lists, source commits, or timestamps into hand-authored prose unless the statement is explicitly historical and dated.
- **Trust semantics** are owned by `trust-contract.md`, `status-semantics.md`, `evidence-receipt-spec.md`, and `health-methodology.md`. Other documents link to them rather than redefining them.
- **Operational procedures** are owned by `operations.md`, `incident-response.md`, `dataset-lifecycle.md`, and `release-process.md`.
- **MCP tool schemas** are owned by the runtime and generated [MCP reference](mcp-reference.md). This map must not become a second tool inventory.
- **Historical audits** remain immutable. Add a new dated audit instead of editing an old one.
- **Private strategy, claims, partner information, and adoption metrics** stay in `notes/` or private operator analysis, not public documentation.

## Volatility labels

| Label | Meaning | Maintenance rule |
|---|---|---|
| `live` | Changes with health cycles or deployments | Generate or read from the live source |
| `contract` | Changes only through an intentional contract decision | Version and update consumers together |
| `stable` | Explanatory guidance with low change frequency | Review when the underlying behaviour changes |
| `historical` | Point-in-time evidence | Date it and do not rewrite |
| `private` | Operator or strategy material | Keep out of public surfaces |

## Completeness promise

A documentation change is not complete merely because a Markdown file exists. The new or changed surface must have:

1. a named audience;
2. one canonical question it answers;
3. links to its source contracts;
4. a review trigger;
5. tested examples where it gives commands or routes;
6. an entry in this map when it is a canonical public document.
