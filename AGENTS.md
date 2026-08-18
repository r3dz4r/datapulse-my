# AGENTS.md — `r3dz4r/datapulse-my`

Working agreement for AI agents (Hermes, Codex, Claude Code) operating inside this repository. Read once, then follow on every change.

## What this repo is

`r3dz4r/datapulse-my` — open-source trust layer for Malaysian public data. 389 official datasets from `data.gov.my`, `BNM`, `DOSM`, `DOE`, `KKM`, `KPDN`, `MET Malaysia` continuously probed and classified into a 10-status taxonomy (`fresh | aging | stale | discontinued | degraded | browser_dependent | unreachable | unknown | unknown_freshness | reference`). Live MCP server with 16 read-only tools. Hosted on `https://www.data-pulse.my` and `https://mcp.data-pulse.my`.

**One-line constraint:** every change here is publicly visible. The dashboard auto-deploys on push to main (modulo `[skip deploy]` trailers). Bad data leaks fast.

## Hard rules

1. **Do not write/edit/refactor code.** Dispatch `codex-run` (with a tight brief). You may edit `.gitignore`, commit messages, and markdown files under `docs/` — those are operator-owned.
2. **No `--yolo`, no bypassing preflight gates.** The deterministic-safety-net job in `.github/workflows/ci.yml` must stay green. If it fails, fix the gate (or the brief that fed into it) — don't silence the failure.
3. **Push requires explicit "push".** "Proceed" / "go" / "dispatch codex" authorises only the *immediately preceding, clearly scoped* action. "Push" must be literal.
4. **Never silently rotate credentials, edit firewall rules, or stop `systemd` services** on the public-facing VPS (`https://data-pulse.my`). These are always-ask.
5. **No upstream mutations.** Datapulse MY is read-only by design. New code must NOT write to `data.gov.my`, `BNM`, `DOSM`, or any other upstream. If a use case requires writes, that's a different product — not this repo.
6. **The 10-status taxonomy is stable.** Adding a status requires changing `gen_health_methodology.py`, `embed_dashboard_data.py`, `gen_changelog.py`, the dashboard hero, `mcp/server.py`, AND the public-facing methodology page. If you think you need an 11th status, surface it to the operator first.
7. **All 4 MCP tool annotations are mandatory** on every tool — see `mcp/AGENTS.md` for the canonical list. OpenAI's directory and M8ven both reject tools missing hints.
8. **Tests live next to code.** `mcp/tests/` for the server, `scripts/tests/` for the generators. New code needs new tests; coverage floor is enforced by the deterministic-safety-net gate.
9. **`datapulse.json` and `health/latest.json` are pipeline outputs, not hand-edited.** Hand-edits get overwritten on the next timer tick.
10. **Deploy posture is read-only + fail-closed.** If a probe fails, mark the dataset `stale` or `unreachable` — do not silently retry until it works.

## Repo map

```
datapulse-my/
├── README.md                  # public-facing; badges, agent-quickstart, value prop
├── datapulse.json             # 389-dataset manifest (generated)
├── datapulse.schema.json      # manifest JSON Schema (hand-authored)
├── health.schema.json         # health JSON Schema (hand-authored)
├── agent.json                 # machine-readable agent capability manifest
├── mcp.json                   # MCP server advertisement
├── llms.txt                   # LLM-friendly index of this repo
├── catalog-snapshot.json      # point-in-time snapshot (generated)
├── changelog.json             # release-by-release summary (generated)
│
├── mcp/                       # read-only FastMCP server (1850 lines)
│   ├── server.py              # 16 tools
│   ├── tests/                 # pytest integration tests
│   ├── AGENTS.md              # <-- per-subdir working agreement
│   └── README.md
│
├── docs/                      # public website (auto-deployed)
│   ├── index.html             # dashboard (rendered by embed_dashboard_data.py)
│   ├── npra.html              # NPRA-specific page
│   ├── health-methodology.md  # methodology docs (rendered as HTML)
│   ├── mcp-reference.md       # MCP server docs (generated)
│   ├── trust-layer-notebook.ipynb  # Colab tutorial (12 cells)
│   ├── trust-layer-notebook.AGENTS.md
│   └── ...
│
├── scripts/                   # 42 Python files driving the pipeline
│   ├── gen_*.py               # generators (regenerate artifacts from sources)
│   ├── verify_*.py            # invariants (release-blocking)
│   ├── validate_*.py          # schema + content validators
│   ├── embed_dashboard_data.py  # writes the docs/ index.html
│   └── check.py               # operator smoke-test entry point
│
├── health/                    # generated health artifacts (gitignored)
│   ├── latest.json
│   ├── history.jsonl
│   ├── trends.json
│   ├── drift.json
│   ├── reconciliation.json
│   └── deltas/                # per-cycle immutable delta files
│
├── record-evidence/           # per-tool evidence logs (generated)
│
├── .attestations/             # signed probe attestation chain
│   ├── chain_head.json        # current head pointer
│   └── latest/                # daily digest envelopes
│
├── samples/                   # frozen snapshot of one row per upstream dataset
│
├── data/                      # per-dataset metadata pages (generated)
│
├── .github/workflows/         # CI: ci.yml (deterministic-safety-net),
│                              #     deploy-pages.yml, health-check.yml,
│                              #     release-please.yml, attest.yml
├── openwiki/                  # generated docs (do not hand-edit)
└── archive/                   # historical datasets (deprecated, kept for diff)
```

## Script taxonomy — which scripts regenerate vs hand-author

| Pattern | Examples | Rule |
|---|---|---|
| `gen_*.py` | `gen_changelog`, `gen_health_history`, `gen_dataset_deltas`, `gen_attestations` | **Regenerable.** Timer-tick runs them. Safe to delete + re-run; safe to edit output paths. |
| `verify_*.py` | `verify_release_reproducible`, `verify_mcp_deployment`, `verify_repository_contract` | **Release-blocking invariants.** If they fail, the release is blocked. Changes here require a test of the new invariant. |
| `validate_*.py` | `validate_policy_schema`, `validate_at_runtime` | **Schema/content validators.** Hand-authored. Change the schema → update both validator and consumers. |
| `embed_*.py` | `embed_dashboard_data` | **Renders `docs/index.html`.** Touches only the dashboard hero. The single script that writes to `docs/`. |
| `check.py`, `check_*.py` | `check`, `check_heartbeat`, `check_url_drift` | **Operator smoke-test entry points.** Not part of the timer; invoked manually or by `task.sh status`. |
| `init_keys.py` | `init_keys` | **One-time key registry bootstrap.** Ed25519 keypair generation; idempotent. |
| `bump_*.py` | `bump_mcp_source_version` | **Bump-and-commit helper.** Operator-only. |

## Operational commands

```bash
# Run a single pipeline stage
python3 scripts/gen_health_history.py
python3 scripts/embed_dashboard_data.py

# Run the full invariant suite (release-blocking)
python3 scripts/verify_release_reproducible.py
python3 scripts/verify_repository_contract.py
python3 scripts/verify_mcp_deployment.py

# Run the deterministic-safety-net test gate locally
python3 -m pytest scripts/tests/ mcp/tests/ -v

# Operator smoke tests
python3 scripts/check.py           # health snapshot
python3 scripts/check_heartbeat.py # recent pipeline activity
```

## Style conventions

- **Python:** `from __future__ import annotations` on every file. Type hints required on all public functions. Absolute imports preferred. Stdlib + `requests` + `pydantic` + `cryptography` only — small dep tree.
- **Markdown under `docs/`:** public-facing. Date-stamped changelog entries. Citations to upstream sources where claims are made.
- **Commit messages:** conventional-commit-ish. `[skip deploy]` trailer on chore(health) commits to avoid 8-min deploy on every timer tick. **Without** the trailer on operator commits.
- **Inline comments:** explain *why*, not *what*. The next agent reading should learn the operator's reasoning.

## What is NOT in this repo

- **The deploy VPS state** — `~/.config/systemd/user/datapulse-health.timer`, `~/.config/systemd/system/datapulse-health.service`, env vars in `/etc/systemd/system/datapulse-health.service`
- **Honcho observations** — query via the Honcho API at `http://100.74.84.121:8000/v3/workspaces/redza-prod/...`
- **The MCP deployment** — separate code path through the deploy-pages.yml workflow + the headroom-proxy service
- **datapulse.my Cloudflare config** — DNS, TLS, cache rules (if any); owner is the operator's Cloudflare account
- **Upstream data sources** — `data.gov.my`, `BNM`, `DOSM` etc. are read but never owned

## Out of scope

- **Authenticated writes** to the data layer (paid-product wedge lives elsewhere)
- **State that requires operator secrets beyond `~/.hermes/.env`** and `DATAPULSE_ATTESTATION_PRIVATE_KEY_FILE` (the GitHub Actions secret)
- **New dependencies beyond the approved list** (stdlib, requests, pydantic, cryptography, fastmcp, httpx)
- **Anything that disables or weakens the deterministic-safety-net gate**

## Pre-flight checklist (for dispatch briefs)

When writing a codex brief that touches this repo:

- **Which file(s) change?** path + line range
- **Which scripts regenerate outputs?** list them in the brief
- **Does this touch `docs/`?** add `python3 scripts/embed_dashboard_data.py` to the verify step
- **Does this touch `mcp/server.py`?** add `python3 -m pytest mcp/tests/ -v` and `python3 scripts/gen_mcp_reference.py` to the verify step
- **Does this touch the status taxonomy?** STOP and surface to operator first
- **What's the deploy posture?** full deploy (no trailer) or skip (`[skip deploy]`)
- **Workdir:** absolute path to this repo (most common cross-repo bug — see dotfiles AGENTS.md rule 7)