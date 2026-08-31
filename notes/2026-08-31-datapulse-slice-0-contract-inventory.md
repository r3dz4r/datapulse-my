# DataPulse Slice 0 — public-surface contract inventory

**Date:** 2026-08-31
**Status:** Reconciliation complete; implementation not started
**Scope:** Read-only inventory of the current DataPulse public-surface, generator, machine-surface, and contract-test chain
**Product:** `r3dz4r/datapulse-my`

---

## Roadmap reconciliation

**Main lane:** DataPulse v0.1 public-surface redesign, beginning with Slice 0 contract inventory.

**Background lanes:**

- Five-minute DataPulse health observation continues.
- Daily Malaysia Data Engine NPRA output continues.
- Current automatic health commits and their CI/deploy workflows continue.

**Deferred lanes:**

- NPRA public publication and payment/buyer-access work remain deferred; NPRA is an internal redesign target only for this alpha.
- P6 private signer custody/reanimation remains deferred without a buyer or regulatory requirement.
- x402/payment work remains deferred behind its checklist.
- Engine graph handoff and other unrelated product lanes remain untouched.

**Phase justification:** operator-directed continuation of the approved register-first redesign. Slice 0 is an inventory and contract-reconciliation gate, not a new product phase and not an implementation authorization.

**Next gate:** approve a bounded Codex implementation brief for the first production slice after this inventory; do not dispatch a whole-site rewrite.

---

## Evidence snapshot

Verified from the repository on 2026-08-31:

| Evidence | Current result |
|---|---|
| Repository HEAD during inventory | `0763e79ab0c381da197f3de37f370340fabc6d7e` (`chore(health): update due dataset health [skip deploy]`) |
| `datapulse.json` | 389 dataset records |
| `health/latest.json` | checked at `2026-08-31T10:51:05Z` during the initial Slice 0 probe |
| Current health distribution | fresh 84; aging 141; stale 147; browser-dependent 5; discontinued 1; reference 11; degraded 0; unknown 0; unknown-freshness 0; unreachable 0 |
| `mcp.json` | 18 declared tools |
| Public configuration | 5 pages and 15 public artifact paths |
| Repository contract | passed; 389 datasets |
| Targeted surface tests | 39 passed in 11.50 seconds |
| Worktree after inventory | clean; no generated output or code changed by Slice 0 |

The health artifact and repository HEAD are moving operational data. Future implementation briefs must refresh these values immediately before dispatch rather than treating this note as a permanent live snapshot.

---

## Canonical public surface inventory

### Human-facing pages in `config/public-surfaces.json`

| Path | Current role | Slice 0 classification |
|---|---|---|
| `/` | Dashboard/homepage | **Main redesign target:** live verified register |
| `/landing.html` | Source-verification landing page | **Compatibility alias target:** should resolve/redirect to `/` rather than remain a second prose wall |
| `/npra.html` | NPRA vertical page | **Internal redesign target:** keep unlinked and excluded from public discovery for this alpha |
| `/health-methodology.html` | Generated methodology page | **Public supporting surface:** de-emphasize, preserve taxonomy/method semantics |
| `/learn.html` | Builder onboarding page | **Public supporting surface:** concise Verify → Fetch → Build path |

The current public configuration still includes `/npra.html` in `pages`, and the current landing configuration contains an NPRA link. This is an identified contract gap against the operator decision “redesign NPRA internally, but keep it unlinked and excluded from public discovery.” The implementation slice must resolve this through canonical configuration/generator behavior and tests, not by hand-editing generated HTML.

### Public artifacts in `config/public-surfaces.json`

- `/buyer-api-reference.md`
- `/llms.txt`
- `/datapulse.json`
- `/datapulse.schema.json`
- `/health/latest.json`
- `/health/trends.json`
- `/health/drift.json`
- `/health/reconciliation.json`
- `/feed.xml`
- `/changelog.json`
- `/agent.json`
- `/mcp.json`
- `/data/jsonld/catalog.json`
- `/badges/`

The machine plane is part of the redesign contract. It must remain aligned with the visible pages and must not be maintained by copied counts or hand-written tool lists.

### Supporting public documentation

The repository also contains public supporting documentation including:

- `docs/agent-quickstart.md`
- `docs/mcp-reference.md`
- `docs/buyer-api-reference.md`
- `docs/architecture.md`
- `docs/operations.md`
- `docs/release-verification.md`
- `docs/troubleshooting.md`
- notebook and contract/reference documents

Not every supporting document requires a full visual rewrite in the first implementation slice. The shared shell, canonical links, terminology, and machine-discoverability references must remain consistent.

---

## Generator and ownership map

### Existing source-to-surface chain

| Surface/output | Canonical source or inputs | Current generator/owner | Existing verification evidence |
|---|---|---|---|
| `docs/index.html` | `datapulse.json`, `health/latest.json`, dashboard sections/filters | `scripts/embed_dashboard_data.py` | dashboard/embed tests; generated-output contract |
| `docs/npra.html` | manifest, health, dashboard sections/filters, marker-owned facts | `scripts/embed_dashboard_data.py` | dashboard/embed tests; generated-output contract |
| `docs/landing.html` | `config/landing-page.json`, `config/public-surfaces.json`, `scripts/templates/landing.html.tmpl`, shared nav | `scripts/gen_landing_page.py` | `scripts/tests/test_landing_page.py` |
| `docs/health-methodology.md` | methodology source | `scripts/gen_health_methodology.py` | health-methodology tests |
| `docs/health-methodology.html` | generated methodology Markdown/template | `scripts/gen_health_methodology_html.py` and methodology template chain | `scripts/tests/test_gen_health_methodology_html.py` |
| shared navigation | `docs/assets/site-nav.html` and public-surface routes | `scripts/gen_site_nav.py` | `scripts/tests/test_site_nav.py` |
| `mcp.json`, `agent.json`, MCP reference blocks | `mcp/server.py` AST, source identity inputs | `scripts/gen_mcp_reference.py` | `scripts/tests/test_mcp_source_sync.py`, generator harness |
| `llms.txt` catalogue/discovery blocks | manifest, public-surface config, MCP metadata | `scripts/gen_llms_summary.py` | `scripts/tests/test_gen_llms_summary.py` |
| `sitemap.xml`, `robots.txt`, discovery blocks | public-surface config | `scripts/gen_public_discovery.py` | `scripts/tests/test_public_discovery.py` |
| JSON-LD catalogue | manifest and generated catalogue inputs | `scripts/gen_jsonld_catalog.py` | JSON-LD/generator tests |
| API reference | MCP/server/runtime-derived inputs | `scripts/gen_api_reference.py` | API public-contract tests |
| health/data/evidence artifacts | health-cycle inputs and pipeline outputs | `scripts/generate.sh` release/health profiles plus individual generators | repository, release, and pipeline tests |

### Current release-build order

`bash scripts/generate.sh release-build --list` currently places public-surface validation and generation in this order:

1. MCP source/version identity and reference validation;
2. manifest origin stamping;
3. MCP reference/discovery generation;
4. LLM summary and public discovery generation;
5. dashboard sections;
6. health/data/evidence/catalogue artifacts;
7. JSON-LD and dashboard filters;
8. dashboard embedding for `docs/index.html` and `docs/npra.html`;
9. API reference and trust snapshot;
10. methodology HTML;
11. landing page;
12. shared site navigation.

The future register generator must be inserted into this chain with an explicit owned-output entry and deterministic verification. The register must not be added as an ad-hoc post-build script.

---

## Canonical MCP capability inventory

The current `mcp.json` declares these 18 tools:

1. `search_datasets`
2. `get_dataset`
3. `find_stale`
4. `find_anomalies`
5. `find_deteriorating`
6. `find_recovering`
7. `find_unreliable`
8. `find_schema_drift`
9. `check_reconciliation`
10. `get_provenance`
11. `get_evidence`
12. `verify_dataset`
13. `get_freshness_summary`
14. `verify_evidence`
15. `trust_verdict`
16. `verify_attestation`
17. `find_by_licence`
18. `usage_summary`

Earlier research referred to 16 tools. The current canonical manifest is the authority for the redesign; the page must not copy either number manually. The first implementation slice should preserve the existing MCP signatures and behavior while making all references derive from the canonical machine surface.

---

## Existing status-to-presentation mapping

` scripts/gen_landing_page.py` currently defines this presentation map:

| Existing status | Existing decision chip |
|---|---|
| `fresh` | `use` |
| `aging` | `warn` |
| `stale` | `stop` |
| `degraded` | `stop` |
| `browser_dependent` | `stop` |
| `unreachable` | `stop` |
| `reference` | `reference-use` |
| `discontinued` | `stop` |
| `unknown` | `stop` |
| `unknown_freshness` | `stop` |

This is a presentation layer, not a new status taxonomy. It is a useful starting point for the register but must be reviewed against the evidence semantics before production implementation. In particular:

- all ten existing statuses remain visible and text-labelled;
- `use`, `warn`, `stop`, and `reference-use` must not replace the underlying status;
- no universal trust score may be introduced;
- stale, unknown, inaccessible, and incomplete signals remain visible rather than filtered away;
- color is never the only status signal.

---

## Identified contract gaps and implementation risks

### 1. Register output has no canonical owner yet

The current production chain has a dashboard embedder and a bounded landing-page evidence receipt, but no canonical full-register generator/output contract. The next implementation slice must define the register source/config schema, generator, template, output path, and deterministic test before changing the homepage.

### 2. `/landing.html` currently remains a full page

`gen_landing_page.py` generates a substantial source-verification page with its own hero, receipt, bounded register, machine-surface links, boundaries, and NPRA vertical link. The approved direction is to make `/` the register and `/landing.html` a compatibility alias. This requires a route/canonical decision in source configuration and tests; it is not safe to hand-edit the generated HTML.

### 3. NPRA discovery state conflicts with the approved alpha boundary

The current public-surface config includes `/npra.html`, and the landing configuration links to it. The implementation brief must distinguish:

- internal visual consistency work;
- public navigation;
- sitemap/discovery inclusion;
- direct route availability;
- machine-surface claims.

“Unlinked and excluded from public discovery” does not automatically mean “delete or block the route.” The exact route behavior must be implemented deliberately and tested.

### 4. MCP reference validation has an explicit source-identity contract

`gen_mcp_reference.py --validate-only` fails unless it receives:

- `--source-commit-sha <40 lowercase hex characters>`;
- `--source-commit-date <YYYY-MM-DD>`.

The release-build profile injects these values. Standalone validation must reproduce that contract. A bare `--validate-only` invocation is not a valid acceptance command.

### 5. Existing auto-generated health commits can move HEAD during work

The current repository receives automatic health-cycle commits. A future Codex brief must:

- record the starting SHA;
- permit only documented health-cycle drift where appropriate;
- refuse unrelated source drift;
- distinguish automatic descendant commits from the implementation diff;
- never reset, stash, or discard operator work.

### 6. Whole-site implementation is too large for one dispatch

The design brief covers every public surface, but implementation must be sliced. Recommended order:

1. contract/schema/source inventory and register ownership;
2. shared shell/tokens and homepage register;
3. Learn and methodology surfaces;
4. machine-plane parity and route/discovery checks;
5. internal NPRA consistency pass;
6. served-state verification.

Each slice requires independent tests and operator review before the next slice.

---

## Slice 0 acceptance record

The Slice 0 inventory is complete when:

- [x] current repository and health artifacts were probed;
- [x] current public pages and artifact paths were enumerated from canonical config;
- [x] current generator ownership was mapped from source and release-build declarations;
- [x] MCP capability count and names were read from `mcp.json`;
- [x] current status-to-presentation mapping was read from the existing generator;
- [x] repository contract validation passed;
- [x] targeted public-surface tests passed (`39 passed`);
- [x] no code, generated public surface, or runtime artifact was changed;
- [x] NPRA discovery conflict and MCP source-identity precondition were recorded;
- [x] implementation was explicitly kept out of this slice.

**Slice 0 result:** `COMPLETE — ready for a bounded implementation brief.`

---

## Next concrete gate

Prepare and review a bounded Codex brief for the first implementation slice. The brief must include:

- absolute workdir and the five-line Codex contract;
- an explicit authority-resolution block so Codex implements rather than defers to the repository’s Hermes-facing coding rule;
- exact allowlisted files and protected dirty paths;
- the canonical source/config/generator/test chain;
- the route and NPRA discovery boundary;
- the no-new-status/no-new-score/no-MCP-behavior-change constraints;
- focused and full verification commands;
- no commit push, publication, service restart, credential operation, or payment action unless separately authorized.
