# AGENTS.md — `docs/` (DataPulse MY public documentation)

Working agreement for AI agents editing the public-facing documentation that auto-deploys to `https://www.data-pulse.my`.

## What this is

`docs/` is the public website. Every `.md` here renders to HTML via GitHub Pages (Jekyll or static passthrough depending on file); every `.html` is served as-is. Most files are **committed hand-authored source-of-truth documentation** that drives the dashboard's content. Changes here are immediately visible to anyone visiting `data-pulse.my`.

**One-line constraint:** the public-facing docs are the public-facing claim. Every word on `data-pulse.my` is part of the trust layer's contract with visitors.

## Hard rules

1. **Read-only-by-implication.** Datapulse MY's docs describe a system that is itself read-only. Do not write prose that suggests writes, mutations, or upstream interactions beyond what the code actually does.
2. **Every external claim must be citeable.** Numbers ("389 datasets", "10-status taxonomy") must be reproducible from `datapulse.json` + `health/latest.json`. The scheduler wakes every 5 minutes but probes only due datasets under tiered cadence; never describe this as all datasets every five minutes.
3. **No fabricated dataset IDs.** When examples cite datasets like `fuelprice`, `gtfs-static/prasarana?category=rapid-bus-kuantan`, `pharmaceutical_product_register`, verify they exist in `datapulse.json` first. See `scripts/check.py` for the verifier.
4. **Methodology changes require an explicit version bump.** `health-methodology.md` and `health-methodology.html` carry a methodology_version field (currently `3`). Changes to the scoring formula, status taxonomy, or signal extraction require bumping this and updating consumers (`mcp/server.py`, dashboard rendering).
5. **The audit docs (`AUDIT-*.md`, `DESIGN-AUDIT-*.md`) are immutable history.** They capture a point-in-time state. Add new audits, never edit old ones — even to fix typos.
6. **`docs/index.html` and `docs/npra.html` are GENERATED, not hand-edited.** Edit `scripts/embed_dashboard_data.py` instead. The deterministic-safety-net gate will reject hand-edits that drift from the embedded data.
7. **Field notes (`docs/field-notes/`) are personal operator logs.** Don't add formal structure (tables of contents, cross-references) — they're meant to be raw.
8. **No marketing superlatives.** "Category-defining", "industry-leading", "first mover", "uncrowded" are all retired framings (see STATE.md 2026-08-17 Path A refresh). Use "intersection-defining" if needed, or stick to verifiable claims.

## Doc taxonomy — which docs are hand-authored vs generated

| File | Type | Source | Rule |
|---|---|---|---|
| `index.html`, `npra.html` | generated | `scripts/embed_dashboard_data.py` | Never hand-edit. The safety-net rejects drift. |
| `health-methodology.html` | generated | `scripts/gen_health_methodology.py` from `health/methodology.json` | Never hand-edit. |
| `mcp-reference.md` | generated | `scripts/gen_mcp_reference.py` from `mcp/server.py` AST | Never hand-edit. |
| `release-verification.md` | generated | `scripts/verify_release_reproducible.py` | Current proof only; includes source SHA, health freshness, dataset/tool counts, and protocol result. |
| `architecture.md`, `branch-protection-handoff.md`, `mcp-deploy.md`, `operations.md`, `release-process.md`, `troubleshooting.md`, `buyer-api-reference.md` | hand-authored | operator + Codex drafts | Stable until the operator explicitly revises. |
| `AUDIT-*.md`, `DESIGN-AUDIT-*.md`, `health-compatibility-report-*.md`, `trust-snapshot-*.md`, `data-json-workspace-proposal-*.md` | hand-authored, immutable | point-in-time audit captures | **Immutable.** Add a new dated audit file; do not edit existing ones. |
| `field-notes/*.md` | operator log | operator's running notes | Personal style; no enforced structure. |
| `health-methodology.md` | hand-authored source-of-truth for the generator | operator | Changes here propagate to `health-methodology.html` via `gen_health_methodology.py`. |
| `myaisafe-contract-inventory.md`, `contract-inventory.md`, `ai-directory-listings.md`, `adoption-seeding.md`, `record-evidence-v1.md`, `health-policy-compatibility.md` | hand-authored, position papers | operator + Codex | Update when the underlying claim changes. Cite sources. |
| `trust-layer-notebook.ipynb` | hand-authored Jupyter | operator | See `trust-layer-notebook.AGENTS.md`. |
| `trust-layer-notebook.AGENTS.md` | hand-authored agent brief | operator | See dedicated file. |

## Style conventions

- **Markdown files:** sentence case headings. **Bold** for the one thing the section is teaching. No emoji in prose.
- **Tables:** use real markdown tables, not bullets-with-em-dashes. Tables degrade to bullet groups when rich rendering is unavailable, but bullets don't degrade to tables.
- **Citations:** link to `https://data-pulse.my/...` for self-references. Link to `https://data.gov.my/...` for upstream sources. Cite the date of the cited claim (`as of 2026-08-17`).
- **Numbers:** always include units. "389" is meaningless; "389 datasets" is meaningful. "5-min" is ambiguous; "every 5 minutes" is unambiguous.
- **Code blocks:** language-tagged (` ```bash `, ` ```python `, ` ```yaml `). Don't use untyped fences.
- **Diagrams:** ASCII for terminal-renderable contexts (Slack, Telegram, mobile browsers); SVG/Mermaid for the website itself, in `assets/`.

## What is NOT in `docs/`

- **The dashboard JavaScript** — that's bundled into `__DATAPULSE_DATA__` inside `index.html` by `embed_dashboard_data.py`
- **Telemetry sinks** — `record-evidence/`, `data/<id>.json`
- **The MCP server code** — `mcp/server.py`
- **Pipeline artifacts** — `health/`, `deltas/`

## Out of scope

- **Adding new public-facing pages without operator approval** — each public page is a new entry in the sitemap and a new inbound URL to defend
- **Editing generated docs by hand** — the deterministic-safety-net gate will fail the next deploy
- **Removing historical audit docs** — they're immutable history
- **Adding "trust us" framing without evidence** — the operator's 2026-08-17 doctrine explicitly retires uncrowded/category-defining framings

## Pre-flight checklist (for dispatch briefs)

When writing a codex brief that touches `docs/`:

- **Which file(s) change?** path + line range
- **Is the doc generated?** if yes, brief must say "regenerate via scripts/<gen>.py" not "edit the file"
- **Is the doc an audit/history file?** if yes, brief must create a NEW dated file, not edit existing
- **Does the change touch methodology_version?** STOP and surface to operator first
- **Are all numbers verifiable from the live data?** brief must include the verification command (`python3 scripts/check.py`)
- **Does the change touch `index.html` or `npra.html`?** brief must include `python3 scripts/embed_dashboard_data.py`
- **Workdir:** absolute path to this repo
