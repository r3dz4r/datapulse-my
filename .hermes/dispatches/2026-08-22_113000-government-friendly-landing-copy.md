Workdir: /home/redza/datapulse-my
Goal: Rewrite the public landing-page copy so DataPulse MY is government-friendly, collaborative, and suitable for data stewards, while preserving the evidence-based trust-layer positioning and all existing functionality.
Failure mode: The current landing copy frames public-data publishers as silently failing, uses stale hardcoded counts, and presents DataPulse as a broad judge of data safety rather than a complementary read-only observation layer.
Acceptance test: Both public pages use collaborative source-of-record language, contain no retired adversarial phrases or stale tool-count copy, preserve all public-source/read-only/legal boundaries and NPRA checkout behavior, pass the repository and focused page tests, and produce no unreviewed data or embedded-script drift.
Recommended execution model: terra

Implementation authority: You are the designated Codex implementer for this dispatch. The repository rule requiring Hermes to dispatch Codex has already been fulfilled; it does not prohibit you from editing the explicitly scoped files below. Edit the scoped files directly. Do not call codex-run, codex-run-bg, delegate_task, or any other agent recursively.

## Scope

Primary public pages:

- `docs/landing.html` — main landing page; hand-authored copy and page-local JavaScript fallback text.
- `docs/npra.html` — NPRA public vertical page; preserve embedded runtime data and checkout behavior.

Allowed supporting change only if required for deterministic generation:

- `scripts/embed_dashboard_data.py`
- `scripts/gen_site_nav.py` output only if the existing nav generator requires regeneration.

Do not touch:

- `docs/index.html` dashboard data or dashboard UI
- `mcp/server.py` or MCP behavior
- health methodology, status taxonomy, scoring, probe policy, or data artifacts
- Paddle checkout logic, price IDs, tokens, or API behavior
- CSS, layout, colors, assets, navigation structure, or URLs unless a copy link is demonstrably wrong
- README, llms.txt, API docs, or historical audit notes
- credentials, services, deployment configuration

## Positioning to implement

DataPulse MY should read as a **complementary, read-only visibility and quality-improvement layer for Malaysian public data**.

The tone should be:

- respectful toward agencies and data stewards;
- practical and public-service oriented;
- neutral about institutional performance;
- clear that official publishers remain the source of record;
- useful to researchers, programme teams, data stewards, and AI systems;
- honest about evidence gaps without using accusatory or sensational language.

Use language such as:

- “shared visibility layer”;
- “publication health and reuse signals”;
- “helps teams review what is currently observable”;
- “complements the official source”;
- “supports correction, documentation, and reuse”;
- “independent, read-only observation”;
- “source of record remains with the publisher.”

Avoid or replace these current phrases:

- “Malaysian open data is silently breaking”;
- “Stale by default”;
- “No freshness signal”;
- “Licences unclear”;
- “The honest difference”;
- “Not optimistic”;
- “is this safe to use right now?” as a broad quality or safety judgement;
- adversarial framing that implies agencies are careless, hiding problems, or being ranked.

Do not use promotional superlatives, endorsements, or unsupported claims. Do not imply that DataPulse certifies the correctness of official data, evaluates agency performance, or replaces an official catalogue.

## Required copy direction

### Main landing page

Revise the visible prose toward this structure, using natural copy rather than copying these lines mechanically:

1. Hero:
   - headline centred on “a shared visibility layer for Malaysian public data”;
   - explain that DataPulse helps data stewards, researchers, and AI systems understand availability, freshness, provenance, licence/reuse context, and observed evidence;
   - explicitly state that official publishers remain the source of record.
2. Path cards:
   - “Review dataset health” or equivalent;
   - “Connect an AI system”;
   - “Use machine-readable surfaces”;
   - “Inspect or extend the checks”.
3. Dashboard section:
   - call it a public view of publication health or observable signals;
   - say that DataPulse does not alter upstream data and does not turn an observed signal into a judgement about the agency or programme.
4. MCP section:
   - position MCP as cited, read-only public-data context for AI systems;
   - describe the tool coverage by function (search, freshness, drift, reconciliation, provenance, evidence) rather than stale hardcoded tool counts.
5. Catalogue surfaces:
   - frame them as shared machine-readable surfaces for review and reuse.
6. Replace “Three things this is not” with a constructive section such as “How DataPulse complements public-data work”:
   - not a replacement for the official publisher;
   - not a data warehouse or upstream mutation layer;
   - not an agency ranking or compliance judgement.
7. Add or strengthen a short data-steward paragraph:
   - maintainers can suggest a cadence correction, exclusion, access-method correction, licence clarification, or removal through the public issue path;
   - DataPulse will document evidence and keep the publisher as source of record.
8. Preserve the existing legal/read-only/public-source boundaries where present. Keep the GitHub, methodology, catalogue, and MCP links.

### NPRA page

Make the NPRA page collaborative and steward-friendly without changing its product behavior:

- frame it as a reviewable companion view of NPRA public registry data;
- state that NPRA/data.gov.my remain the official sources of record;
- replace “one visible health signal” with language such as “one reviewable publication signal”;
- describe the cards as helping users review freshness, provenance, and reuse context;
- describe the MCP section as providing AI systems with cited NPRA catalogue context;
- keep the NPRA Pro section and all checkout behavior unchanged.

## Stale-copy cleanup

The current main page contains stale static values and tool-count language:

- `385 datasets`;
- `15 MCP tools`;
- `Thirteen tools`;
- `13 surfaces`.

Do not replace these with new hardcoded marketing numbers unless the value is guaranteed by an existing generator. Prefer neutral labels such as “live dataset health”, “read-only MCP access”, and “machine-readable surfaces”. The page-local `live-counters` JavaScript must continue to render current health totals from `/health/latest.json`; do not break that behavior.

Current verified repository values are 389 datasets and 16 MCP tools, but avoid introducing another stale static copy when a dynamic or neutral label is practical.

## Generated-page discipline

- Do not hand-edit or remove the `embedded-data` block.
- Run the existing generator for NPRA after visible-copy edits:

```bash
python3 scripts/embed_dashboard_data.py --html docs/npra.html
```

- Run the site-nav generator if needed:

```bash
python3 scripts/gen_site_nav.py
```

- If a generator-side change is required, keep it limited to deterministic copy handling and explain why.

## Verification

Run:

```bash
python3 scripts/check.py
python3 scripts/verify_repository_contract.py
python3 scripts/gen_site_nav.py --check
python3 -m pytest scripts/tests/test_site_nav.py scripts/tests/test_embed_dashboard_data_shell.py scripts/tests/test_npra_paid_control_plane.py -q
git diff --check
```

Also perform a deterministic copy audit over `docs/landing.html` and `docs/npra.html` confirming:

- retired adversarial phrases are absent;
- no new unsupported numbers or “official endorsement” claims appear;
- official source-of-record language is present;
- read-only and public-source limitations remain present;
- MCP endpoint, dashboard, methodology, and correction/issue links remain valid;
- embedded-data content is unchanged except for generator-required refreshes;
- Paddle checkout code, tokens, price IDs, and API paths are byte-for-byte unchanged.

Do not commit or push. Return exact changed files, copy-audit results, tests, and `Pushed: NO`.
