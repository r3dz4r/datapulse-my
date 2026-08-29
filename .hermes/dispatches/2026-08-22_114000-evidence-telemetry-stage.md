Workdir: /home/redza/datapulse-my
Goal: Complete telemetry registration for the new longitudinal evidence stage so production health cycles record `evidence: success` instead of emitting a non-fatal enum error.
Failure mode: The health pipeline publishes current trend/drift/reconciliation artifacts but silently loses telemetry for the evidence stage, weakening cycle observability and making the new stage look failed or absent to monitoring.
Acceptance test: `check_heartbeat.py` accepts and persists `--stage evidence`; focused heartbeat tests and the full scripts suite pass; existing stage choices and telemetry schema remain backward-compatible; no generated artifacts, public docs, services, or credentials change.
Recommended execution model: luna

Implementation authority: You are the designated Codex implementer for this dispatch. The repository rule requiring Hermes to dispatch Codex has already been fulfilled; it does not prohibit you from editing the explicitly scoped files below. Edit the scoped files directly. Do not call codex-run, codex-run-bg, delegate_task, or any other agent recursively.

## Scope

Modify only:

- `scripts/check_heartbeat.py`
- `scripts/tests/test_heartbeat.py`

Existing untracked paths are operator-owned and must remain untouched:

- `.hermes/`
- `notes/2026-08-22-gtfs-declared-vs-observed.md`
- `notes/2026-08-22-roadmap-reconciliation-followup.md`
- `notes/2026-08-22-roadmap-reconciliation-gate.md`
- `notes/phase-1-baseline-2026-08-22.md`

## Required change

1. Add `"evidence"` to the existing `STAGES` set in `scripts/check_heartbeat.py`.
2. Add focused regression coverage in `scripts/tests/test_heartbeat.py` that invokes the CLI with `--stage evidence`, writes to a temporary telemetry log, and verifies the structured row has:
   - `stage == "evidence"`;
   - the requested duration and success status;
   - the existing event schema fields.
3. Do not alter event retention, rotation, timestamps, status choices, JSON shape, or any existing stage names.
4. Do not commit, push, run the production health service, or modify generated health artifacts.

## Verification

Run from `/home/redza/datapulse-my`:

```bash
python3 -m pytest scripts/tests/test_heartbeat.py -q
python3 -m pytest scripts/tests/ -q
python3 -m py_compile scripts/check_heartbeat.py scripts/tests/test_heartbeat.py
python3 scripts/check_heartbeat.py append --stage evidence --duration 1 --status success --extra-json '{"fixture":true}'
```

The CLI smoke test must use a temporary `DATAPULSE_TELEMETRY_FILE`, not the production telemetry path. Confirm `git diff --check`, exact changed files, and `Pushed: NO`.
