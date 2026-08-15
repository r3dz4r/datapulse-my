# Health methodology

DataPulse MY reports evidence, not a promise that upstream data is correct.

## Schema version

`health/latest.json.schema = "datapulse/v0.4/dataset-health"`

The schema identifier is a top-level field. `_trust_summary` does not duplicate
the schema identifier.

## Longitudinal telemetry

`health/history.jsonl` records one observation for every dataset in every
published probe cycle. Each JSONL object contains `dataset_id`, `observed_at`,
`cycle`, `status`, `anomaly_detected`, `freshness_signal`, `last_modified`, `content_date`,
`record_count`, `record_count_estimated`, `http_status`, `latency_ms`,
`probe_outcome`, and `message`, plus `name`, manifest `url`, and `shape_hash`
when available. Re-running a cycle replaces the matching
`(dataset_id, cycle)` object instead of creating a duplicate. Status changes
are represented by successive observations and can therefore be queried
without changing the ten-status snapshot taxonomy.

The existing probe snapshot does not currently expose request duration, so
`latency_ms` is explicitly `null` rather than estimated. The writer will carry
through a numeric `latency_ms` when the validated probe output provides one.
`probe_outcome` is `success` for a 2xx response, `timeout` when the probe
message identifies a timeout, and `error` otherwise.

`python3 scripts/gen_health_history.py --compact` enforces the default 90-day
raw retention window. Expired observations are rolled into per-dataset,
per-calendar-day entries in `health/history_daily.json` with observation and
probe-outcome counts, status distribution, availability percentage, record
count min/mean/max, and mean latency. A compact cycle index prevents an old
cycle rerun from inflating an aggregate. Compacted cycles are immutable; a
correction must be made while the raw observation is inside the retention
window.

## Dataset delta ledger

`scripts/gen_dataset_deltas.py` runs after the history writer and creates one
immutable `deltas/<cycle>.json` file. Catalog additions and removals compare
membership with the immediately preceding recorded cycle. For every
value-bearing dataset, status, manifest URL, shape hash, and direct (not
estimated) record count compare with that dataset's latest earlier history row
whose `probe_outcome` is `success`. This per-dataset baseline may be older than
the preceding cycle when a probe was skipped or failed; every change records
its `from_cycle`. A first cycle has `no_history_baseline_yet` and emits no
changes. Re-running identical inputs verifies the existing bytes, while an
attempt to change an existing cycle file fails instead of overwriting it.

Each ledger records SHA-256 digests of the manifest, current health snapshot,
and current-cycle history segment. `catalog-snapshot.json` is the canonical
current-state summary. `changelog.json` is a byte-identical deprecated alias
for one release and is not a delta ledger.

## Per-record evidence

Dataset health answers whether an upstream file is reachable, timely, and
structurally plausible as one opaque unit. `record-evidence/v1` is a fourth,
deeper layer for explicitly opted-in verticals: it hashes the observed raw CSV,
validates each row, classifies each row with the same ten-status vocabulary,
and attaches a stable digest to that row's freshness, structural, linkage, and
alternative evidence.

The envelope does not replace `health/latest.json`, and a fresh dataset-level
probe does not imply every row is valid. Conversely, one degraded row does not
rewrite the dataset-health result. Aggregate record counts and the full daily
record list live under `record-evidence/<dataset-id>/`; `latest.json` contains a
bounded representative excerpt. See [`record-evidence-v1.md`](record-evidence-v1.md)
for the binding contract and pilot caveats.

## Production classification (T33, 2026-08-09)

The 15-minute timer invokes `bash scripts/check.sh --due`. The full-probe
canary (`docs/health-policy-compatibility.md`) reviewed on 2026-08-09 confirms
the `--due` policy is consistent with the approved freshness policy:

- Due-probe thresholds from `scripts/check.sh` lines 111–129 are 15 minutes
  for realtime (`30 seconds` and `hourly`), 60 minutes for weekday-daily,
  1,440 minutes for daily, 10,080 minutes for weekly/monthly/quarterly, and
  43,200 minutes for annual/survey-year/as-required datasets.
- Fixed-window freshness baselines from `scripts/health_policy.py` are 30
  seconds, 1 hour, 1 day, 7 days, 30 days, 90 days, and 365 days for
  `30 seconds`, hourly, daily, weekly, monthly, quarterly, and annual
  frequencies respectively. Fresh is age ≤1.5× baseline, aging is >1.5× and
  ≤3×, and stale is >3×. Survey-year verification uses 45-day and 90-day
  boundaries; as-required datasets do not infer a freshness window.
- Status flips in the canary: 22 fresh→aging transitions + 3 fresh→stale
  transitions were classified as "Approved" because they reflect datasets
  legitimately aging past their cadence.
- 5 GTFS static myBAS feeds were marked `real_status: discontinued` after
  upstream stopped publishing real data. The canary's "record count changed by
  more than 10%" classification moves these from "Blocker" to "Approved"
  because discontinued zero-count is the policy reason.

These preserve the reviewed G2/G3/G4 outcomes: generated health remains the
single production snapshot, a valid configured content signal takes precedence
with the approved fallback, and classification uses the cadence-specific
freshness windows above.

## Rollback path

`scripts/check.sh --compare-health` runs a full probe to a temp file and diffs
the result without modifying the live `health/latest.json`. It exits 0 when the
comparison report is produced successfully, including when that report lists
differences, and exits 1 if comparison fails. The 2026-08-09 canary is the
reference diff. To revert a classification change, edit `datapulse.json`
directly (for example, flip `real_status` back to `"live"`) and wait for the
next `--due` probe.

## Schema/version changes

The current health schema identifier is `datapulse/v0.4/dataset-health`.

## Status taxonomy

| Status | Meaning |
| --- | --- |
| `fresh` | Reachable, structurally usable, and within the freshness window. |
| `aging` | Freshness age is over 1.5× cadence and at most 3× cadence. |
| `stale` | Freshness age is over 3× cadence. |
| `discontinued` | The publisher has stopped updating the dataset; the last known content is retained. |
| `degraded` | Reachable, but schema/shape or record-count checks failed. |
| `browser-dependent` | Assessment requires rendered browser state. |
| `unreachable` | The source request failed or returned non-2xx. |
| `unknown` | No reliable classification is available. |
| `unknown-freshness` | Reachable and structurally usable, but no freshness evidence exists. |
| `reference` | Versioned reference/lookup data is reachable and countable; date-based freshness does not apply. |

## Freshness anomaly signal

`anomaly_detected` is orthogonal to the ten-status taxonomy and never changes a
dataset's status. During warm-up, it flags a freshness delta strictly greater
than three times the declared cadence. With at least twelve distinct successful
prior UTC-day observations in the fourteen-day window, it flags a delta strictly
greater than the available observations' population mean plus two population
standard deviations. The current snapshot is excluded from that baseline.
`anomaly_detection` records the mode, sample count, threshold, and current value;
missing evidence, `as-required`, reference, and discontinued rows are
`not_evaluated` and false.

## Freshness and reachability

Reachability is not freshness. The probe chooses the newest defensible signal
from an HTTP `Last-Modified` header or parsed content date. Daily, weekly,
monthly, quarterly, and annual cadences use 1, 7, 30, 90, and 365-day baselines.
Future content dates are rejected. A 200 response without either signal becomes
`unknown-freshness`, not `fresh`, unless the manifest identifies the dataset as
versioned `reference` data.

BNM content dates are date-only. The dashboard adds the MYT time declared in
each manifest `refresh_frequency` for display; that time is presentation
metadata, not a timestamp parsed from the response.

## Content integrity

Record counts are compared with `expected_record_count` when it is known. A
result below half the expectation is degraded; capped or estimated results are
marked incomplete. Column-count or first-row-shape changes are also degraded so
schema drift cannot appear green.

Browser-backed sources always remain `browser-dependent`, even after a
successful Camofox snapshot. In due mode, unprobed rows and a previous
`last_checked` value are preserved. A probe that produces no measurement does
not erase the last successful measurement.

## Blind spots

- HTTP and sampled content checks do not prove semantic accuracy or completeness.
- Generic row counting can be fooled by undocumented pagination or wrappers.
- Browser snapshots depend on client rendering, timing, and selector-free text.
- A stable first-row hash cannot detect changes elsewhere in a dataset.
- Licence and attribution are verified metadata, not legal advice.
