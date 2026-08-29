# DataPulse agent-economy landing-page brief — 2026-08-27

## Reconciled current state

### Served public entry points

- `/` — dashboard and primary trust/data surface.
- `/landing.html` — hand-authored overview page; current positioning is shared visibility for Malaysian public data.
- `/npra.html` — generated NPRA vertical surface; do not hand-edit.
- `/health-methodology.html` — generated methodology surface; do not hand-edit.
- `/llms.txt`, `/agent.json`, `/mcp.json` — machine-readable discovery/capability surfaces.

### Current capability drift

The local and served machine surfaces report 16 MCP tools through `llms.txt`, `agent.json`, and `mcp.json`. The landing page manually lists only 13 tools. This is a contract-drift risk; the redesigned page must not maintain a manually enumerated tool catalogue. Link to the canonical machine surfaces and describe the workflow at a capability level instead.

### Current claims to retain

- 389 official Malaysian public datasets.
- Read-only observation; official publishers remain the source of record.
- Provenance, licence/reuse context, freshness, schema/record evidence, anomalies, trends, drift, reconciliation, and citation-ready outputs.
- MCP delivery through the public Streamable HTTP endpoint.
- Machine-readable manifest, health, discovery, and evidence surfaces.
- Honest distinction between observed evidence and objective truth.

### Claims to avoid

- source of truth;
- guaranteed accuracy;
- verified truth;
- safe MCP server;
- Cloudflare-for-Malaysian-data framing;
- global/SEA data-layer claims before country contracts exist;
- active agent payments or x402 demand claims.

## Positioning

Public category sentence:

> **Verify Malaysian data before your AI agent uses it.**

Supporting line:

> DataPulse checks what a public source exposes, when it was observed, how it has behaved, what licence applies, and what your agent can safely claim—then returns the evidence through machine-readable surfaces and MCP.

Internal category:

> **AI Trust Layer Verification — source-verification infrastructure for agent-consumed Malaysian public data.**

External category wording:

> **A source-verification layer for AI agents using Malaysian public data.**

## Page architecture

The page should make the agent journey explicit, with the evidence decision before any future commercial rail:

```text
Readable → Discoverable → Callable → Verifiable → (Future) Payable
```

DataPulse owns the data-side `Verifiable` step. It complements—not replaces—the runtime, discovery, MCP, identity, and payment rails built by other platforms.

**Primary design object:** an evidence receipt that lets a human or agent decide `use`, `warn`, or `stop`.

### Section 1 — Hero

- Headline: `Verify Malaysian data before your AI agent uses it.`
- Subheadline: explain official-source context, observed freshness, provenance, licensing, evidence, and limitations.
- Primary CTA: `Inspect one evidence receipt` → a real dataset/evidence surface, not a simulated chat.
- Secondary CTA: `Connect via MCP` → canonical MCP endpoint/config.
- Supporting proof: 389 datasets, read-only, citeable evidence.
- Do not headline “agent economy,” “AI trust layer,” or payment; those are context, not the user outcome.

### Section 2 — The evidence preflight workflow

Show one concrete agent workflow, using a real verified dataset such as `fuelprice`:

```text
1. Discover a relevant Malaysian dataset
2. Inspect publisher, licence, source, and current state
3. Check the available evidence and limitations
4. Decide: use, warn, or stop
5. Return a citation-ready result
```

Make the receipt visible before explaining the protocol rails. The page should link to the real manifest/report/health/evidence surfaces. It must not invent a chat transcript or imply that a signature proves upstream truth.

### Section 3 — Five agent-web rails

Use the five rails as supporting architecture, not as the primary hero narrative. The evidence receipt and `use / warn / stop` decision come first:

| Rail | DataPulse expression |
|---|---|
| Readable | concise human and machine-readable dataset context |
| Discoverable | `llms.txt`, `agent.json`, manifest, public catalogue |
| Callable | read-only MCP tools and resources |
| Verifiable | freshness, provenance, licence, schema, evidence, drift, reconciliation, and explicit limitations |
| Payable | future metered verification operations; label as future/conditional and do not imply an active payment product |

### Section 4 — Evidence receipt

Show the shape of one real evidence result:

```text
source identity
publisher
licence
observed time
content date
freshness state
schema/record state
evidence reference
verification level
claim scope
limitations
```

Use a real linked artifact or live surface. Do not hardcode mutable health counts or timestamps into hand-authored copy.

### Section 5 — Machine access

Do not enumerate tools manually. Explain the canonical surfaces:

- `agent.json` for capability discovery;
- `mcp.json` for MCP advertisement and schemas;
- `llms.txt` for agent-readable orientation;
- `datapulse.json` for the manifest;
- `health/latest.json` for current published observation;
- evidence/provenance resources for citation support.

Link to the canonical files and the MCP endpoint. The page may name workflow categories, but tool names/descriptions must remain generator-owned elsewhere.

### Section 6 — Boundaries and supervision

State clearly:

- official publishers remain the source of record;
- DataPulse is read-only;
- observed source health is not an objective-truth guarantee;
- unknown, stale, degraded, or conflicting signals must remain visible;
- agents and humans decide whether a claim is fit for their use;
- enterprise MCP security/admission is complementary, not a current DataPulse claim.

### Section 7 — Vertical proof

Link to the NPRA page as a concrete Malaysia-domain example, but do not duplicate its generated facts. Explain that domain products can sit downstream of the public source-verification layer.

### Section 8 — Final CTA

Offer two paths:

- `Inspect one dataset` → real report/evidence surface.
- `Connect your agent` → canonical MCP setup.

Keep payment language future-oriented unless a validated metered workflow exists.

## Research amendment — implementation posture

The design research confirms that “AI Trust Layer Verification” is an internal category hypothesis, not an established industry standard. The page must therefore sell the concrete outcome—evidence-qualified data decisions—rather than an abstract trust platform.

Implementation must:

- make the evidence receipt the primary visual object;
- put the real `discover → inspect → check evidence → use / warn / stop → cite` workflow before the five rails;
- remove every manually maintained MCP tool list from the page;
- describe MCP, `agent.json`, `mcp.json`, `llms.txt`, JSON-LD, and health/evidence resources as canonical surfaces;
- preserve the distinction between integrity, provenance, freshness, and substantive correctness;
- expose unknowns and limitations instead of rendering a universal trust score;
- keep `Payable` future/conditional;
- avoid WebMCP, agent reputation, regulatory certification, and payment implementation in this slice;
- validate the final page with raw HTTP/Markdown, JSON/JSON-LD, link checks, browser-agent task execution, and human accessibility review.

Reference: `notes/2026-08-27-ai-trust-layer-verification-design-research.md`.

## Canonical source-of-truth and self-healing contract

There must be no loose hand-crafted landing-page artifact. The implementation must establish one explicit ownership chain:

```text
canonical landing content/config
+ canonical HTML template
+ canonical runtime artifacts
→ deterministic generator
→ generated docs/landing.html
→ release-build regeneration
→ invariant/drift verification
→ served-page verification
```

Required ownership:

- `config/landing-page.json` — canonical page information architecture, stable copy, CTA intent, canonical links, claim boundaries, rail definitions, and example dataset reference. It must not duplicate mutable health counts, timestamps, MCP tool names, or runtime capability lists.
- `scripts/templates/landing.html.tmpl` — canonical presentation template. It is a source input, not a deployed artifact; it must contain no mutable runtime facts that can drift.
- `scripts/gen_landing_page.py` — sole generator for the complete `docs/landing.html` output. It must validate inputs, render atomically, fail closed on malformed/missing inputs, and produce byte-identical output on two runs with identical inputs.
- `docs/landing.html` — generated output only, with an explicit generated-file marker/header.
- `scripts/generate.sh` — include the landing generator in `release-build` before `gen_site_nav.py` and list its owned output.
- `scripts/contract-scope.json` — register `docs/landing.html` as a full-output generated surface with canonical inputs, generator, fixture, and invariant.
- `scripts/tests/test_landing_page.py` — verify config validity, canonical links, generated ownership, no manual MCP enumeration, no unsupported claims, dynamic runtime sourcing, deterministic second run, and no generated-page drift outside scope.
- `scripts/verify_release_invariants.sh` and `scripts/verify_release_reproducible.py` — include the landing output in release and reproducibility checks.

Self-healing requirements:

- Health-only refreshes must not require hand-editing `docs/landing.html`.
- Mutable counters and timestamps must come from canonical runtime artifacts or existing no-store page logic.
- Missing/stale runtime input must fail generation or render an explicit unknown state, never a fabricated healthy default.
- All inputs must be validated before any output is written; writes must be atomic.
- The release path must regenerate the page whenever canonical inputs change.
- Post-deploy verification must fetch `/landing.html` and compare its generated identity, canonical links, and freshness contract against the served machine surfaces.

This overrides the earlier “target `docs/landing.html` only” wording: the target is the source/config/template/generator/contract chain, with `docs/landing.html` as a generated derivative.

## Source and generation constraints

- Target: the canonical landing config/template/generator/contract chain above; `docs/landing.html` is generated output only.
- `docs/index.html` and `docs/npra.html` are generated by `scripts/embed_dashboard_data.py`; do not hand-edit them.
- Preserve or regenerate the generated site-nav block through `scripts/gen_site_nav.py` if navigation changes.
- Preserve current shared CSS/assets unless a bounded design change is explicitly approved.
- Verify all mutable numbers from current canonical artifacts during implementation.
- No methodology-version change.
- No new public page or route.
- No MCP tool-count copy in the landing page.

## Acceptance gate for implementation

- Canonical config, template, generator, contract registration, and generated output all exist and are connected in `release-build`.
- `docs/landing.html` is reproducibly generated and contains an explicit generated-file marker; direct hand edits are detected as drift.
- Two generator runs on identical inputs produce byte-identical output.
- Landing page presents the evidence receipt as the primary design object, followed by the five-rail architecture and one real evidence workflow.
- No retired superlatives or unsupported payment/adoption claims.
- No manually maintained MCP tool enumeration remains on the page or in the canonical landing config.
- Existing source/official-publisher/read-only boundaries remain explicit.
- All current links resolve to canonical surfaces.
- `docs/index.html` and `docs/npra.html` remain unchanged unless a generator-owned regeneration is explicitly part of the approved scope.
- Focused generator/config/HTML/link/claim tests pass, release reproducibility checks pass, and a rendered browser check verifies the actual served page after deployment.

## Implementation result — local commit, not deployed

The canonical landing chain and follow-up style/honesty correction are committed locally in `dff2420c` (`feat(datapulse): generate trust verification landing page`). The commit contains exactly the ten approved config/template/generator/output/shared-CSS/contract/test paths.

Verification: landing `8` tests passed; public-discovery `2` passed; embed `8` passed; generator `18` passed; repository contract passed for 389 datasets; local release invariants passed; generator determinism and sibling-page guard passed; all landing classes are owned by the shared stylesheet; the receipt is visibly a schema preview rather than verified evidence; no manual MCP enumeration or mutable runtime facts are in stable landing config/output.

`docs/index.html`, `docs/npra.html`, and `docs/health-methodology.html` remain unchanged. Unrelated notes and `.hermes/` remain untracked and untouched. The full release reproducibility path was previously exercised through attestation generation; the Codex follow-up reported it passed, while the current operator session did not rerun the secret-backed path. Camofox browser rendering previously returned HTTP 500, so visual verification remains open. No push, deployment, publication, service restart, or production-data mutation occurred.
