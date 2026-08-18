# AGENTS.md — `scripts/` (DataPulse MY pipeline)

Working agreement for AI agents editing the 42 Python scripts that drive the datapulse-my pipeline.

## What this is

`scripts/` contains the build pipeline. Each script does one thing:
- `gen_*.py` regenerate artifacts from upstream sources (timer-tick runs them)
- `verify_*.py` enforce invariants (release-blocking)
- `validate_*.py` check schema/content
- `embed_*.py` render the dashboard HTML
- `check*.py` operator smoke-test entry points

Scripts are **read-and-execute**: every commit triggers the deterministic-safety-net gate which runs all `*tests*.py`. A bad script breaks the deploy pipeline within 5 minutes.

## Hard rules

1. **One script = one job.** If a script does two unrelated things, split it. `gen_health_history.py` regenerates `health/history.jsonl`; it does not also regenerate `changelog.json`. (That's `gen_changelog.py`'s job.)
2. **Pipeline outputs are gitignored, hand-authored inputs are committed.** `health/`, `record-evidence/`, `.attestations/latest/`, `data/<id>.md` (after first gen), `docs/index.html` are generated. `datapulse.json`, `health.schema.json`, `datapulse.schema.json`, `.attestations/chain_head.json`, source templates under `templates/` are hand-authored.
3. **Never bypass `--quick-test`.** `gen_health_history.py` and similar long-running scripts have a `--quick-test` flag for fast iteration. The flag is mandatory during dispatch — a 60-min full run wastes Codex quota.
4. **The 10-status taxonomy is hard-coded across 6+ files.** If you change it, you MUST update: `embed_dashboard_data.py` (status display), `gen_changelog.py` (status sections), `gen_dashboard_filters.py`, `gen_dashboard_sections.py`, `health.schema.json`, and `mcp/server.py` (status enums). Use a shared constant — don't repeat the tuple.
5. **Attestation chain integrity is non-negotiable.** `gen_attestations.py` is the only writer to `.attestations/chain_head.json`. Re-running with different inputs produces a different chain head — that's expected, but **never edit chain_head.json directly**. The release pipeline (`.github/workflows/release-please.yml`) asserts the chain head is stamped on each release; manual edits will break release attestation.
6. **`git add` order matters for the safety-net gate.** The gate compares pre/post SHAs to determine diff scope. If you regenerate artifacts and then commit them in the same dispatch, the diff scope includes your source change + regenerated artifacts. This is fine for the timer; for operator commits, separate the source change from the regen into two commits.
7. **Determinism is load-bearing.** Two runs of any `gen_*.py` on the same inputs must produce byte-identical output. If your script introduces non-determinism (random IDs, timestamps, sort instability), the deterministic-safety-net fails and the release is blocked.
8. **Output paths go to a small allowlist** (`scripts/_artifact_paths.py` or equivalent). New output paths must be added there before the safety-net accepts them.

## Style conventions

- **Shebang:** `#!/usr/bin/env python3` on every file.
- **Imports:** `from __future__ import annotations` then stdlib/third-party/local in 3 groups, alphabetised within each group. Absolute imports preferred.
- **Type hints:** required on all public functions; `mypy --strict` clean for new code. Internal helpers can use less strict typing.
- **CLI:** `argparse` with `--quick-test`, `--out <path>`, `--in <path>` consistently. No `sys.argv` slicing.
- **Logging:** stdlib `logging` with module-level logger named after the script (`logging.getLogger(__name__)`). Never `print()` in pipeline scripts — operators want log levels.
- **Errors:** raise typed exceptions (`ConfigError`, `SourceError`, `SchemaError`) with descriptive messages. The deterministic-safety-net reports failures via test output, not Python tracebacks.
- **Atomic writes:** every generator writes to `<path>.tmp` then `os.rename(<path>.tmp, <path>)`. Partial writes must never be visible at `<path>`.
- **Schema validation:** every generator validates input JSON against `health.schema.json` or `datapulse.schema.json` before reading. Failed validation = explicit error, not silent coercion.

## Script-by-script taxonomy

| File | Pattern | Inputs | Outputs | Test command |
|---|---|---|---|---|
| `gen_changelog.py` | gen | `datapulse.json`, `health/latest.json` | `changelog.json` | `python3 scripts/gen_changelog.py --quick-test` |
| `gen_health_history.py` | gen | `health/latest.json` history | `health/history.jsonl` | `--quick-test` runs on 30 rows |
| `gen_dataset_deltas.py` | gen | `health/history.jsonl` | `health/deltas/<cycle>.json` | `--quick-test` skips >1000 cycles |
| `gen_drift.py` | gen | `health/history.jsonl` | `health/drift.json` | -- |
| `gen_attestations.py` | gen | `health/latest.json`, prior chain head | `.attestations/latest/<date>.json`, `chain_head.json` | `--quick-test` skips signing |
| `gen_anomaly.py` | gen | `health/history.jsonl` | `health/anomalies.json` | -- |
| `gen_catalog_snapshot.py` | gen | `datapulse.json` | `catalog-snapshot.json` | -- |
| `gen_catalog_graph.py` | gen | `datapulse.json` | `data/catalog-graph.json` | -- |
| `gen_dashboard_filters.py` | gen | `datapulse.json` | `docs/.dashboard_filters.json` | -- |
| `gen_dashboard_sections.py` | gen | `datapulse.json` | `docs/.dashboard_sections.json` | -- |
| `gen_health_methodology.py` | gen | `health/methodology.json` | `docs/health-methodology.html` | -- |
| `gen_mcp_reference.py` | gen | `mcp/server.py` AST | `mcp.json` at repo root | -- |
| `embed_dashboard_data.py` | embed | `datapulse.json`, `health/latest.json`, `docs/.dashboard_*.json` | `docs/index.html` | `python3 -m pytest scripts/tests/test_embed_dashboard_data_shell.py -v` |
| `verify_release_reproducible.py` | verify | all generated artifacts | exit 0/1 | `--rebuild-and-diff` |
| `verify_repository_contract.py` | verify | repo invariants | exit 0/1 | -- |
| `verify_mcp_deployment.py` | verify | live MCP endpoint | exit 0/1 | -- |
| `validate_policy_schema.py` | validate | `~/.config/datapulse/policy.yaml` | exit 0/1 | -- |
| `validate_at_runtime.py` | validate | various | exit 0/1 | -- |
| `compare_health.py` | compare | two `health/latest.json` | exit 0/1 | -- |
| `check.py` | check | repo state | exit 0/1 | -- |
| `check_heartbeat.py` | check | timer activity | exit 0/1 | -- |
| `check_url_drift.py` | check | upstream URLs | exit 0/1 | -- |
| `fact_lint.py` | lint | docs/ claims | exit 0/1 | -- |
| `lint_docs_against_units.py` | lint | docs/ vs units | exit 0/1 | -- |
| `shape_fingerprint.py` | util | dataset CSV | fingerprint dict | -- |
| `probe_gtfs.py` | probe | GTFS feeds | health probe | -- |
| `run_health_canary.py` | probe | smoke test | exit 0/1 | -- |
| `init_keys.py` | bootstrap | (none) | Ed25519 keypair | idempotent |
| `bump_mcp_source_version.py` | bump | mcp.json | mcp.json (bumped) | -- |
| `verify_mcp_deployment.py` | verify | live MCP endpoint | exit 0/1 | -- |
| `verify_release_reproducible.py` | verify | full pipeline re-run | exit 0/1 | `--rebuild-and-diff` |

(Full file list is in `ls scripts/*.py`; this table covers the load-bearing ones.)

## What is NOT in `scripts/`

- **The pipeline state machine** — there's no orchestrator; the systemd timer invokes scripts in dependency order via `datapulse-pipeline.sh` (in dotfiles `system/`).
- **The deploy flow** — `.github/workflows/deploy-pages.yml` (separate concern)
- **The public MCP server code** — that's `mcp/server.py`, not scripts

## Out of scope

- **Anything that touches upstream data** (the probe scripts are read-only by design)
- **Anything that writes outside the `health/`, `record-evidence/`, `.attestations/`, `data/`, `docs/`, `changelog.json`, `mcp.json`, `catalog-snapshot.json` allowlist**
- **New long-running scripts without a `--quick-test` flag** — the deterministic-safety-net will fail if you can prove determinism in <5 minutes

## Pre-flight checklist (for dispatch briefs)

When writing a codex brief that touches any `scripts/*.py`:

- **Which script(s) change?** file + line range + which inputs/outputs are affected
- **What does the regeneration cascade look like?** list downstream consumers (e.g. `embed_dashboard_data.py` reads `gen_dashboard_*.json`)
- **Does the change touch the 10-status taxonomy?** STOP and surface to operator first
- **Is the script deterministic?** brief must explicitly state "two runs on same input → byte-identical output"
- **What's the `--quick-test` plan?** brief must include the command
- **What does the deterministic-safety-net gate look like after the change?** brief must include the expected `pytest scripts/tests/` output
- **Workdir:** absolute path to this repo