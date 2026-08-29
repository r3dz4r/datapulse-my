# DataPulse AI Trust Layer Verification — design and standards research

**Research date:** 2026-08-27
**Scope:** DataPulse’s proposed “AI Trust Layer Verification” niche; agent-first information architecture; Cloudflare, GitHub, Stripe; adopted and emerging standards; implications for the DataPulse landing page.

## Executive verdict

“AI Trust Layer Verification” is a useful internal category label, but it is **not yet an established industry category or standard name**. The underlying market is assembling from several adjacent layers:

1. agent-readable discovery;
2. callable tool and API contracts;
3. data catalog and provenance metadata;
4. runtime observability and auditability;
5. identity, authorization, and human approval;
6. payment and settlement reliability.

DataPulse should not claim to verify that an AI answer is true, or that an agent is trustworthy in the broad security/reputation sense. Its defensible claim is narrower:

> **DataPulse verifies the evidence conditions around public data before an AI agent uses or cites it.**

Recommended external category language:

> **A source-verification layer for agent-consumed Malaysian public data.**

Recommended internal thesis:

> **AI Trust Layer Verification = evidence identity + temporal validity + provenance + reuse context + structural checks + claim limitations + machine-readable delivery.**

## What the big platforms are actually implementing

### Cloudflare: the agent-ready web as a layered interaction model

Cloudflare’s public framing is **readable → discoverable → callable → payable**. Its implementation is not just a visual redesign:

- **Readable:** Markdown for Agents via `Accept: text/markdown`, token-size signalling, preserved security/cache headers, and Content Signals.
- **Discoverable:** `robots.txt`, sitemap, `llms.txt`, link headers, API catalogs, agent skills, and agent-readiness diagnostics.
- **Callable:** WebMCP exposes site actions as structured tools; Cloudflare’s Code Mode reduces large APIs to progressive `search()` + `execute()` discovery.
- **Payable:** machine-payment and agent-commerce flows are treated as protocol surfaces, not checkout-page copy.
- **Operationally trustworthy:** Agent Readiness reports pass/fail/neutral checks with the exact request/response evidence; Browser Run adds Live View, session recordings, and human handoff.
- **Failure-aware:** RFC 9457-style structured error responses provide retryability, retry-after, escalation, error category, timestamp, and correlation identifiers instead of forcing an agent to parse HTML.

**Design lesson for DataPulse:** Cloudflare treats agent readiness as a multi-layer contract with diagnostics, not as “put an AI button on the homepage.” The strongest reusable pattern is **progressive disclosure plus an evidence-backed readiness report**.

**Important maturity boundary:** WebMCP is early preview/proposed browser functionality, not a settled web standard. Do not make it a DataPulse critical path yet.

Sources:

- [Cloudflare: The Agentic Internet](https://blog.cloudflare.com/the-agentic-internet/)
- [Cloudflare: Agent Readiness](https://blog.cloudflare.com/agent-readiness/)
- [Cloudflare: WebMCP](https://blog.cloudflare.com/webmcp/)
- [Cloudflare: Markdown for Agents](https://developers.cloudflare.com/fundamentals/reference/markdown-for-agents/)
- [Cloudflare: structured agent error responses](https://blog.cloudflare.com/rfc-9457-agent-error-pages/)
- [Chrome WebMCP status](https://developer.chrome.com/docs/ai/webmcp)

### GitHub: agent work as a controlled, reviewable workflow

GitHub’s implementation centers on **delegation, isolation, review, and steering**:

- A task can move through plan → execution → branch/PR → review → merge.
- Copilot cloud agent works asynchronously in an isolated environment and exposes progress, files read, changes, and test activity.
- Users choose between Ask, Plan, Agent, Interactive, and Autopilot modes depending on autonomy and risk.
- GitHub supports third-party agents such as Claude and Codex rather than forcing one model path.
- MCP is a shared capability layer across IDE, CLI, Copilot app, cloud agent, and code review.
- Repository-level MCP configuration supports explicit tool allowlists; GitHub strongly recommends allowing specific read-only tools because configured MCP tools may run autonomously without approval.
- GitHub provides a curated MCP Registry and an Agent Finder for progressive, runtime capability discovery.
- GitHub’s MCP security posture includes scoped tokens, secret protection, code scanning, and reviewable session logs.
- `AGENTS.md` is now an open, cross-tool project-context convention stewarded under the Linux Foundation’s Agentic AI Foundation.

**Design lesson for DataPulse:** the agent should not be presented as an opaque magic consumer. A trustworthy agent workflow exposes **what was requested, which capability was used, what evidence was returned, what changed, and where a human can review or stop**.

**Direct DataPulse analogue:** replace GitHub’s code diff/PR review with a dataset evidence receipt and a `use / warn / stop` decision. The receipt is the review surface.

Sources:

- [GitHub Copilot Agents](https://github.com/features/copilot/agents)
- [GitHub: MCP in Copilot](https://docs.github.com/en/copilot/concepts/context/mcp)
- [GitHub: repository MCP configuration](https://docs.github.com/en/copilot/how-tos/copilot-on-github/customize-copilot/configure-mcp-servers)
- [AGENTS.md](https://agents.md/)
- [Agentic AI Foundation announcement](https://www.linuxfoundation.org/press/linux-foundation-announces-the-formation-of-the-agentic-ai-foundation)

### Stripe: machine-readable commerce plus operational correctness

Stripe’s agent strategy has three distinct surfaces:

1. **Agent developer tooling:** agent plugins, skills, CLI, MCP, plain-text `.md` documentation, and a machine-readable skills index.
2. **Agentic commerce:** catalog feeds, agent discovery, delegated checkout/authentication, webhooks, and explicit sandbox/live separation.
3. **Machine payments:** HTTP `402` challenges, payment credentials, retry, and a receipt for the paid resource.

Stripe’s reliability practices are particularly relevant:

- Idempotency keys make retried writes safe and replay the original result, including errors.
- Webhooks represent lifecycle transitions rather than requiring indefinite polling.
- Sandbox validation is recommended before enabling live updates.
- The agent payment protocol returns a structured challenge first; access follows only after payment verification.
- Stripe distinguishes public documentation, machine-readable documentation, tools, skills, account data, and transactional APIs rather than collapsing them into one page.

**Design lesson for DataPulse:** do not advertise “Payable” as a product capability before there is a real paid, metered operation. Borrow Stripe’s **explicit state machine, receipt, idempotency, sandbox/live distinction, and canonical machine documentation**.

Sources:

- [Stripe: Agents and AI](https://docs.stripe.com/agents)
- [Stripe: MCP](https://docs.stripe.com/mcp)
- [Stripe: Agentic Commerce](https://docs.stripe.com/agentic-commerce)
- [Stripe: Idempotent requests](https://docs.stripe.com/api/idempotent_requests)
- [Stripe: Machine Payments Protocol](https://docs.stripe.com/payments/machine/mpp)

## Standards and maturity classification

### Adopt now: established standards and conventions

| Layer | Standard/practice | DataPulse implication |
|---|---|---|
| Web accessibility and structure | WCAG 2.2, semantic HTML, labelled landmarks, consistent navigation | Keep one predictable human/agent page; headings, nav, tables, skip links, keyboard paths, and readable initial HTML are part of agentability. |
| Dataset cataloguing | W3C DCAT 3 | Model dataset, distribution, data service, version, and catalog record distinctly; do not conflate the abstract dataset with one file/API representation. |
| Dataset structured data | Schema.org `Dataset`, `DataCatalog`, `DataDownload`; JSON-LD | Make publisher, identifier, licence, distribution, citation, temporal coverage, and access path explicit. |
| Provenance | W3C PROV-DM / PROV-O | Represent entities, activities, agents, derivation, responsibility, and provenance-of-provenance. |
| API contracts | OpenAPI, JSON Schema, HTTP semantics | Make inputs, outputs, error states, and operation scope explicit; avoid prose-only contracts. |
| HTTP error semantics | RFC 9457 Problem Details | Return machine-readable error type, title, status, detail, and instance; add retry/escalation fields only as a documented extension. |
| Web accessibility | WCAG 2.2 | Treat accessibility and agent readability as reinforcing constraints, not competing modes. |
| Identity/authorization | OAuth 2.1 patterns, PKCE, resource indicators, scoped credentials | Relevant if/when DataPulse adds protected or paid MCP/API access; not needed for the current public read-only surface. |
| Observability | OpenTelemetry direction for GenAI/tool/retrieval spans | Future engine/API telemetry should capture tool, data source, result, latency, and failure context without logging secrets or unnecessary payloads. |

Sources:

- [WCAG 2.2](https://www.w3.org/TR/WCAG22/)
- [W3C DCAT 3](https://www.w3.org/TR/vocab-dcat-3/)
- [Schema.org Dataset](https://schema.org/Dataset)
- [Schema.org DataCatalog](https://schema.org/DataCatalog)
- [W3C PROV-DM](https://www.w3.org/TR/prov-dm/)
- [OpenTelemetry GenAI semantic conventions](https://github.com/open-telemetry/semantic-conventions-genai)

### Adopt where the use case fits: mature ecosystem specifications

| Standard | What it proves | What it does not prove |
|---|---|---|
| MCP | A structured way to expose tools, resources, prompts, schemas, and results to compatible clients | That a server is safe, honest, or authoritative; tool annotations are hints and are untrusted unless the server is trusted. |
| SLSA/in-toto | Provenance about how an artifact was produced and how a verifier can compare it with expectations | That the underlying source data is true. |
| C2PA | Tamper-evident provenance and signer identity for an asset/manifest | That the assertions are objectively true; the spec explicitly avoids value judgements. |
| A2A | Agent capability discovery and agent-to-agent communication through an Agent Card | That a discovered agent’s outputs are correct or suitable for a particular decision. |
| W3C VC Data Integrity | Cryptographic integrity/authenticity mechanisms for constrained credentials/documents | That the issuer’s assertion is substantively correct. |

**DataPulse fit:** use the semantics of these standards, but do not add cryptography merely to appear standards-compliant. DataPulse’s current public evidence layer needs claim-level provenance and temporal validity first; signing/witnessing remains additive and must not become the publication critical path.

### Emerging or informal: useful signals, not foundations

| Item | Status | DataPulse posture |
|---|---|---|
| `llms.txt` | Open community proposal; publication does not prove clients consume it | Keep it as a curated orientation surface alongside sitemap/robots/JSON-LD, not as the only discovery mechanism. |
| WebMCP | Early preview/proposed browser API | Track and experiment later; do not depend on it for core access. |
| Cloudflare Agent Readiness score | Vendor diagnostic product | Borrow the diagnostic/evidence pattern, not the score or Cloudflare-specific taxonomy. |
| Content Signals | Emerging machine-readable usage preferences | Useful if DataPulse needs to express training/search/input preferences; not a trust verdict. |
| OpenTelemetry agent extensions | Active/development semantic-convention work | Treat as directionally valuable; do not claim full standard conformance without a versioned implementation matrix. |
| “Agent UX/AUX” and “agentability” | Emerging design language and research area | Use as research vocabulary, not as an established certification or market category. |

## What “verification” must mean for DataPulse

The word “verified” must always be scoped to an evidence claim. A DataPulse verification receipt should separate:

1. **Identity** — stable dataset ID, publisher/steward, source URL, distribution/service URL.
2. **Observation** — when DataPulse observed the source and by which transport/access method.
3. **Temporal validity** — source content date, last-modified date where available, freshness status, and cadence context.
4. **Structural condition** — schema, record-count, shape, parse, or drift evidence where the pipeline actually measured it.
5. **Reuse context** — licence, attribution, access dependency, and known restrictions.
6. **Integrity** — digest/signature/attestation status where available, clearly separated from substantive correctness.
7. **Cross-source context** — agreement, discrepancy, reconciliation group, and tolerance; discrepancy is a review signal, not proof that either source is wrong.
8. **Claim scope** — what the evidence supports and what it does not support.
9. **Decision posture** — `use`, `warn`, or `stop`, with a reason and links to the underlying evidence.
10. **Reproducibility** — stable artifact/reference URL, methodology version, and enough metadata for a later verifier to repeat the check.

A signature can prove that DataPulse signed a statement. It cannot prove that an agency’s upstream value, licence interpretation, or real-world claim is true. This distinction is central to the niche.

## Recommended DataPulse information architecture

### Primary navigation

Use one consistent site navigation for humans and agents:

```text
Dashboard | Evidence | MCP | Methodology | NPRA | Source
```

- **Dashboard:** browse the catalogue and status distribution.
- **Evidence:** explain the receipt and open a real example.
- **MCP:** connect a compatible agent; link to canonical `agent.json`, `mcp.json`, and endpoint.
- **Methodology:** explain what is measured, what is not, and version history.
- **NPRA:** show one concrete vertical application without duplicating generated facts.
- **Source:** repository, licence, issues, and implementation.

Do not create a separate “AI-only” visual site. Use progressive disclosure: semantic HTML and readable copy first, machine surfaces next, protocol tools after that.

### Landing-page sequence

1. **Outcome hero:** `Verify Malaysian data before your AI agent uses it.`
2. **Short trust contract:** read-only; official publisher remains source of record; DataPulse reports observed evidence and limitations.
3. **One real workflow:** discover → inspect → verify evidence → use/warn/stop → cite.
4. **Evidence receipt visual:** show identity, observed time, freshness, licence, structural signal, evidence reference, scope, and limitation.
5. **Capability rails:** Readable → Discoverable → Callable → Verifiable; show Payable only as future/conditional.
6. **Machine surfaces:** link to canonical files; never manually reproduce the complete MCP tool list on the landing page.
7. **Human supervision:** explain that agents can consume the result, but humans/agent runtimes decide whether the evidence is fit for the task.
8. **Vertical proof:** NPRA link as an example, not a second catalogue.
9. **Two CTAs:** `Inspect one dataset` and `Connect your agent`.

### Agent-first navigation pattern to borrow

Borrow Cloudflare’s **progressive capability discovery**:

```text
short orientation
→ canonical manifest/card
→ selected capability/tool
→ structured result
→ evidence reference
→ human review or next action
```

Do not lead with 16 tool names. That caused the current 13-versus-16 landing-page drift. The canonical machine surfaces should own capability enumeration.

## Proposed product/market boundary

### DataPulse should own

- public-source identity and catalog normalization;
- observed freshness and cadence evidence;
- schema/record-count/shape/drift evidence;
- provenance and licence context;
- claim-level evidence receipts;
- conservative `use / warn / stop` decision support;
- machine-readable delivery through manifest, JSON-LD, health, evidence, and MCP surfaces;
- a repeatable verification methodology and history.

### DataPulse should not claim to own yet

- agent identity or reputation;
- model truthfulness or reasoning correctness;
- enterprise authorization policy;
- generic MCP server security certification;
- payment rails or agent wallets;
- universal source-of-truth status;
- regulatory certification;
- a WebMCP-first runtime;
- a universal trust score that collapses missing evidence into a mid-scale number.

## Design principles for the niche

1. **Evidence before adjectives.** Every trust claim should open a receipt or method explanation.
2. **Scope every verdict.** “Verified” must say what was verified, when, and against which source.
3. **Separate integrity from correctness.** A valid signature is not proof of substantive truth.
4. **Make unknowns visible.** Missing freshness, licence ambiguity, inaccessible sources, and conflicts must remain explicit.
5. **One source of truth for capabilities.** Generate machine-surface descriptions; do not hand-copy tool lists into marketing pages.
6. **Progressive disclosure.** Humans see the reason first; agents can fetch structured detail without parsing decorative UI.
7. **Human agency at consequential boundaries.** Any future write, purchase, publication, or high-impact decision needs explicit approval and an audit trail.
8. **Fail closed for evidence-dependent claims.** If the required evidence cannot be obtained, return `warn` or `stop`, never an optimistic default.
9. **Use standards, do not cosplay standards.** Adopt DCAT/PROV/Schema.org/JSON Schema/MCP semantics where they fit; do not add C2PA/SLSA/WebMCP solely for branding.
10. **Measure agentability empirically.** Test real tasks, models, tool clients, latency, token cost, partial outcomes, and human correction—not only HTML validity.

## Decision on the “AI Trust Layer Verification” name

### Keep as an internal strategic category

It is useful because it points toward the gap between:

```text
raw public data
→ agent consumption
→ evidence-qualified decision
```

### Do not use it unqualified as the external headline yet

Reasons:

- “Trust layer” already means different things in Salesforce, agent-security, identity, observability, and model-governance markets.
- “AI verification” can imply model evaluation, identity verification, content authenticity, or cybersecurity.
- DataPulse verifies source/evidence conditions, not an agent’s intent or the truth of the world.
- The label has no established buyer vocabulary or standard certification behind it.

### Recommended external wording

Primary:

> **A source-verification layer for AI agents using Malaysian public data.**

Secondary:

> **Evidence receipts for data agents can discover, inspect, and cite.**

Short category explanation:

> DataPulse does not decide whether an agency or model is “trustworthy.” It records what a public source exposed, when it was observed, how its structure and freshness behaved, what reuse context applies, and what an agent should treat as usable, uncertain, or blocked.

## Immediate recommendation

Do not dispatch the landing-page redesign from the earlier brief unchanged. Amend it to:

1. replace generic “agent economy” language with the evidence-verification outcome;
2. move the five rails below the proof workflow;
3. make the receipt the central visual object;
4. remove all manually enumerated MCP tools;
5. add a standards-aware but non-credentialist trust boundary;
6. reserve `Payable` for a future/conditional section;
7. use one real dataset example and a real evidence link;
8. validate the page with a browser-agent task, a raw HTTP/Markdown fetch, a JSON/JSON-LD check, and a human accessibility pass.

## Research limitations

- Vendor pages describe their own products and should not be read as neutral market evidence.
- `llms.txt`, WebMCP, Agent Readiness, A2A, and OpenTelemetry agent extensions have different maturity levels; publication or preview availability is not proof of broad adoption.
- The research establishes design and standards implications, not buyer willingness to pay. A separate buyer/competitor validation gate is still required before monetization claims or payment implementation.
