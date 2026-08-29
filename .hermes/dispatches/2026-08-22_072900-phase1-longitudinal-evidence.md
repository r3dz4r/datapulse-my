Workdir: /home/redza/datapulse-my
Goal: Make Phase 1 longitudinal evidence possible from the existing bounded raw history plus compacted daily history, so the selected flagship cohort can accumulate cadence, freshness, anomaly, record-count, and structural evidence without retaining unbounded raw probe rows.
Failure mode: DataPulse continues to report `insufficient_data` after history has been compacted, or worse, aggregates lose signal and produce false reliability/drift claims. A wrong implementation would undermine the trust-layer proof.
Acceptance test: Focused history/trends/drift tests prove compacted daily observations are consumed, existing conservative minimum-sample thresholds remain unchanged, malformed input is skipped safely, two runs on identical fixtures are byte-identical, `git diff --check` passes, and the focused pytest command exits 0.
Recommended execution model: terra

Implementation authority: You are the designated Codex implementer for this dispatch. The repository-level rule requiring Hermes to dispatch Codex has already been fulfilled by this invocation; it does not prohibit you from editing the explicitly scoped files below. Do not call `codex-run`, `codex-run-bg`, `delegate_task`, or any other agent recursively. You must make the scoped code/test edits directly, then run the verification commands.

# Phase 1 longitudinal evidence — implementation brief

## Strategic context

Phase 1 has locked this flagship cohort:

- `gtfs_realtime_prasarana_bus_kl`
- `gtfs_realtime_prasarana_bus_penang`
- `exchangerates_daily_0900`
- `met_weather`
- `dosm_trade_headline`
- `doe_mqims`

The baseline artifact is `notes/phase-1-baseline-2026-08-22.md`. It found:

- fresh, directly parsed GTFS and MET observations;
- a fresh BNM direct observation that still lacks cadence history;
- a stale HTTP-200 OpenDOSM observation;
- a browser-reachable but structurally unquantified DOE observation; and
- local health newer than the public Pages health artifact.

Current live state shows the bottleneck: `health/history.jsonl` contains only one comparable observation day for the selected cohort. `health/trends.json` reports `insufficient_data` for all 389 datasets. `gen_health_history.py` already compacts expired raw rows into `health/history_daily.json`, but the daily aggregate currently does not retain enough freshness/structural/anomaly signal for `gen_trends.py` and `gen_drift.py` to consume it.

## In scope — expected source files

Change only the following source/test files unless a narrowly necessary import or test fixture requires an adjacent edit:

- `scripts/gen_health_history.py`
- `scripts/gen_trends.py`
- `scripts/gen_drift.py`
- `scripts/tests/test_health_history.py`
- `scripts/tests/test_trends.py`
- `scripts/tests/test_drift.py`

Do not change the manifest, health taxonomy, MCP server, public docs, deployment workflows, systemd units, or the Phase 1 notes.

## Required behavior

1. Extend the compacted daily aggregate in `gen_health_history.py` with the minimum additional fields needed to reconstruct bounded longitudinal evidence for:
   - freshness delta / staleness samples;
   - anomaly observations, if the existing history row carries `anomaly_detected`;
   - structural shape and column-count observations sufficient for drift evaluation; and
   - existing record-count, latency, status, and probe-outcome information.
2. Preserve backward compatibility with existing `health/history_daily.json` files. Missing new fields must be treated as absent evidence, not as zeroes or false values.
3. Make `gen_trends.py` consume both sources in the correct order:
   - raw `health/history.jsonl` for retained observations;
   - compacted daily history for older observations inside the existing 14-day window.
   Deduplicate to one latest successful/evaluable observation per dataset per UTC day, as the current raw-history logic does.
4. Make `gen_drift.py` consume compacted daily history for older observations inside its existing 30-day window, preserving the current structural and record-count verdict semantics.
5. Keep the existing conservative gates unchanged:
   - trends still require 3 daily samples spanning at least 2 days;
   - drift still requires two comparable structural/record-count observations or an evaluable expected count;
   - no relaxation of `insufficient_data` merely because an aggregate file exists.
6. Keep all existing output schemas backward-compatible unless a new field is strictly required; if a schema/methodology field is added, document it in the generated artifact's methodology metadata, not in public prose.
7. Do not read `/home/redza/runtime/datapulse-history` for this dispatch. The Phase 1 window is covered by compacted daily aggregates, and external archive paths would introduce a VPS/CI mismatch.
8. Keep output deterministic: same fixture inputs and explicit timestamps produce byte-identical JSON output. Use existing atomic-write patterns.
9. Do not run the full production generator cascade, do not modify generated `health/*` artifacts, do not commit, and do not push.

## Edge cases to test

- A dataset with only old raw rows and daily aggregates should use the aggregate evidence.
- A dataset with both raw and daily evidence for the same UTC day must not double-count that day.
- A legacy daily aggregate missing the new fields must remain valid and yield conservative `insufficient_data` where required.
- A compacted aggregate containing failed/timeout observations must not turn them into freshness-evaluable successes.
- Shape or column-count changes crossing the raw-to-daily boundary must be detectable when the aggregate retains enough evidence; otherwise the result must remain `insufficient_data`, not `stable` by default.
- Re-running the history writer with the same input remains idempotent.
- Malformed JSONL lines remain safely skipped by trend/drift consumers as in current tests.

## Verification commands

Run at minimum:

```bash
python3 -m pytest scripts/tests/test_health_history.py scripts/tests/test_trends.py scripts/tests/test_drift.py -q
python3 -m pytest scripts/tests/ -q
python3 -m py_compile scripts/gen_health_history.py scripts/gen_trends.py scripts/gen_drift.py
python3 - <<'PY'
from pathlib import Path
import subprocess
files = [Path('scripts/tests/fixtures/health-history-snapshot.json')]
# The implementer must use deterministic temporary fixtures in tests; this check is only a reminder that production health outputs are out of scope.
print('fixture inputs present:', all(path.exists() for path in files))
PY
git diff --check
```

For determinism, run the relevant generator/test fixture twice and compare the resulting JSON bytes. Report exact commands, exit codes, changed files, and any intentionally unchanged files. `Pushed: NO`.

## Existing dirty paths — explicitly out of scope

At dispatch time, these paths are already dirty/untracked and must not be edited, regenerated, restored, reset, stashed, or discarded:

- `.hermes/` and all existing dispatch briefs under it;
- `notes/2026-08-22-gtfs-declared-vs-observed.md`;
- `notes/phase-1-baseline-2026-08-22.md`;
- any current generated `health/*`, `attestations/*`, `data/*`, or other timer-produced artifacts.

## Expected result

A small, tested change that lets the existing 14-day trend and 30-day drift consumers use compacted daily observations while remaining honest when the evidence is insufficient. This is a substrate change for Phase 1 evidence collection, not a product launch, score change, or deployment.
