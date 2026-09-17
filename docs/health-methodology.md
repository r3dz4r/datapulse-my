# Health methodology

DataPulse MY reports evidence, not a promise that upstream data is correct.

## Schema version

<!-- BEGIN EXTRACTED: schema-version -->
The current health snapshot schema is `datapulse/v0.4/dataset-health`.
<!-- END EXTRACTED: schema-version -->

The schema identifier is a top-level field. `_trust_summary` does not duplicate the schema identifier.

## Longitudinal telemetry

<!-- BEGIN EXTRACTED: history-schema -->
Each `health/history.jsonl` row contains:

- `dataset_id`
- `observed_at`
- `cycle`
- `status`
- `freshness_signal`
- `last_modified`
- `content_date`
- `record_count`
- `record_count_estimated`
- `http_status`
- `latency_ms`
- `probe_outcome`
- `message`

`probe_outcome` is one of `success`, `error`, `timeout`. The optional
fields `name`, `url`, `shape_hash`, `column_count`, and `anomaly_detected`
are written only when the corresponding source data is available.

The compact daily aggregate schema is `datapulse/v1/health-history-daily`.
<!-- END EXTRACTED: history-schema -->

<!-- BEGIN EXTRACTED: probe-outcomes -->
The probe classifies every observation as one of `success`, `error`, `timeout`.
<!-- END EXTRACTED: probe-outcomes -->

Re-running a cycle replaces the matching `(dataset_id, cycle)` object instead of creating a duplicate. Status changes are represented by successive observations and can therefore be queried without changing the ten-status snapshot taxonomy.

The existing probe snapshot does not currently expose request duration, so `latency_ms` is explicitly `null` rather than estimated. The writer will carry through a numeric `latency_ms` when the validated probe output provides one.

<!-- BEGIN EXTRACTED: retention-and-archives -->
Raw observations are kept in `health/history.jsonl` for **7 days**.
On expiry, observations are compacted into `health/history_daily.json`
(per-dataset, per-day aggregates: counts, status distribution, availability
percentage, min/mean/max record counts, mean latency). Observations that
fall outside the retention window are also archived to `~/runtime/datapulse-history/health-YYYY-MM.jsonl.gz`
(monthly gzip files, append-only).
<!-- END EXTRACTED: retention-and-archives -->

## Dataset delta ledger

`scripts/gen_dataset_deltas.py` runs after the history writer and creates one immutable `deltas/<cycle>.json` file. Catalog additions and removals compare membership with the immediately preceding recorded cycle. For every value-bearing dataset, status, manifest URL, shape hash, and direct (not estimated) record count compare with that dataset's latest earlier history row whose `probe_outcome` is `success`. This per-dataset baseline may be older than the preceding cycle when a probe was skipped or failed; every change records its `from_cycle`. A first cycle has `no_history_baseline_yet` and emits no changes. Re-running identical inputs verifies the existing bytes, while an attempt to change an existing cycle file fails instead of overwriting it.

Each ledger records SHA-256 digests of the manifest, current health snapshot, and current-cycle history segment. `catalog-snapshot.json` is the canonical current-state summary. `changelog.json` is a byte-identical deprecated alias for one release and is not a delta ledger.

## Per-record evidence

Dataset health answers whether an upstream file is reachable, timely, and structurally plausible as one opaque unit. `record-evidence/v1` is a fourth, deeper layer for explicitly opted-in verticals: it hashes the observed raw CSV, validates each row, classifies each row with the same ten-status vocabulary, and attaches a stable digest to that row's freshness, structural, linkage, and alternative evidence.

The envelope does not replace `health/latest.json`, and a fresh dataset-level probe does not imply every row is valid. Conversely, one degraded row does not rewrite the dataset-health result. Aggregate record counts and the full daily record list live under `record-evidence/<dataset-id>/`; `latest.json` contains a bounded representative excerpt. See [`record-evidence-v1.md`](record-evidence-v1.md) for the binding contract and pilot caveats.

## Production classification (T33, 2026-08-09)

<!-- BEGIN EXTRACTED: probe-cadence -->
The probe timer fires every **5 minutes** (systemd `OnCalendar=*:0/5`).

The due policy in `scripts/check.sh` uses these cadence thresholds:

| Frequency | Tier | Due after (minutes) |
| --- | --- | ---: |
| 30 seconds; hourly | `realtime` | 15 |
| daily (weekdays…) | `daily` | 60 |
| daily | `daily` | 1440 |
| weekly; monthly; quarterly | `weekly-monthly` | 10080 |
| annual; survey-year; as-required | `slow` | 43200 |
<!-- END EXTRACTED: probe-cadence -->

The full-probe canary (`docs/health-policy-compatibility.md`) reviewed on 2026-08-09 confirms the `--due` policy is consistent with the approved freshness policy. Status flips in the canary preserve the reviewed G2/G3/G4 outcomes: generated health remains the single production snapshot, a valid configured content signal takes precedence with the approved fallback, and classification uses the cadence-specific freshness windows below.

## Rollback path

`scripts/check.sh --compare-health` runs a full probe to a temp file and diffs the result without modifying the live `health/latest.json`. It exits 0 when the comparison report is produced successfully, including when that report lists differences, and exits 1 if comparison fails. The 2026-08-09 canary is the reference diff. To revert a classification change, edit `datapulse.json` directly (for example, flip `real_status` back to `"live"`) and wait for the next `--due` probe.

## Schema/version changes

The version history and migration rationale remain maintained prose; the current schema identifier above is generated from the snapshot builder.

## Status taxonomy

<!-- BEGIN EXTRACTED: status-taxonomy -->
| Status | Meaning |
| --- | --- |
| `fresh` | Reachable, structurally usable, and within the freshness window. |
| `aging` | Freshness age is over 1.5× baseline and at most 3× baseline. |
| `stale` | Freshness age is over 3× baseline. |
| `discontinued` | The publisher has stopped updating the dataset; the last known content is retained. |
| `degraded` | Reachable, but probe, schema, shape, or record-count checks failed. |
| `browser-dependent` | Assessment requires rendered browser state. |
| `unreachable` | The source request failed or returned a non-2xx response. |
| `unknown` | No reliable classification is available. |
| `unknown-freshness` | Reachable and structurally usable, but no freshness evidence exists. |
| `reference` | Versioned reference data is reachable; date-based freshness does not apply. |
<!-- END EXTRACTED: status-taxonomy -->

## Freshness anomaly signal

`anomaly_detected` is orthogonal to the ten-status taxonomy and never changes a dataset's status.

<!-- BEGIN EXTRACTED: anomaly-mode -->
During warm-up, a freshness delta is anomalous if strictly greater than three
times the declared cadence. With at least 12 distinct successful prior UTC-day observations in the 14-day window, a delta is strictly greater
than the population mean plus two population standard deviations.
The current observation is excluded from the baseline.
<!-- END EXTRACTED: anomaly-mode -->

`anomaly_detection` records the mode, sample count, threshold, and current value; missing evidence, `as-required`, reference, and discontinued rows are `not_evaluated` and false.

## Freshness and reachability

<!-- BEGIN EXTRACTED: freshness-baselines -->
Reachability is not freshness. The probe chooses the newest defensible signal
from an HTTP `Last-Modified` header or parsed content date.

| Frequency | Baseline | Fresh / aging / stale |
| --- | --- | --- |
| `30 seconds` | 30 seconds | ≤1.5× / >1.5×–≤3× / >3× |
| `hourly` | 1 hour | ≤1.5× / >1.5×–≤3× / >3× |
| `daily` | 1 day | ≤1.5× / >1.5×–≤3× / >3× |
| `weekly` | 7 days | ≤1.5× / >1.5×–≤3× / >3× |
| `monthly` | 30 days | ≤1.5× / >1.5×–≤3× / >3× |
| `quarterly` | 90 days | ≤1.5× / >1.5×–≤3× / >3× |
| `annual` | 365 days | ≤1.5× / >1.5×–≤3× / >3× |

Weekday-daily frequencies use the daily baseline. Survey-year verification uses 45-day and 90-day boundaries; as-required datasets do not infer a freshness window.
<!-- END EXTRACTED: freshness-baselines -->

## Conventions, refusals and limits

<!-- BEGIN EXTRACTED: freshness-conventions -->
### Which of this is measurement, and which is convention

The observation layer is measurement. A freshness verdict is produced by comparing
a measured age against a boundary that was chosen. This section states which is which,
so that no reader has to infer it.

**Measured.** `last_checked` records when the row was last actually observed, and
`content_freshness_date` records the newest date parsed out of the content itself.
`staleness_days` is an operational definition, not a natural quantity: the greater of
the age of the publication and the age of the newest observation in the file.

**Chosen.** The 1.5x and 3x cadence multiples that separate fresh, aging and stale are
conventions, applied uniformly and revised deliberately rather than discovered. They are
not properties of the datasets. A different choice of boundary would move rows between
bands without any dataset having changed, and that is the honest description of them.

### Publication lag is not publisher silence

A series that is genuinely lagged can never reach fresh if its age is judged against zero
from the moment of publication. A dataset may therefore declare
`freshness_policy.expected_observation_lag_days`. When present and numeric it takes
precedence over the cadence-derived observation age, and it offsets the observation-age
component only. It never offsets the
publication-age component, so a publisher that stops publishing still crosses the 1.5x and
3x boundaries and is still reported as stale. The allowance accommodates a known cadence;
it does not excuse an absent publisher.

### Refusals

Two rules constrain what this system will claim, and both are deliberate:

1. Evidence that is stale, discontinued, unreachable or degraded must not be used to
   support a currentness claim.
2. A row whose shape basis is untyped, and which therefore has no `first_row_hash`, has no
   verifiable row set. A date alone does not entitle such a row to a currentness verdict, so
   it is reported as browser-dependent rather than assigned a freshness status.

The second rule is a refusal to claim rather than a failure to measure, and it is load
bearing: relaxing it would publish currentness verdicts for rows whose contents cannot be
verified. Where a row cannot be measured the outcome is `unknown-freshness`, which is a
first-class result and never a silent default.

### Known limits

- A row carried over from an earlier cycle retains the measurement time in `last_checked`,
  which may be older than the artifact's own publication time. Consumers needing the
  measurement instant must read `last_checked`, not the publication timestamp.
- Cadence-extreme datasets are judged against their declared cadence, so a boundary that is
  correct for a daily series can misclassify a series that changes by the minute or by the
  second, and a boundary that suits a realtime feed is meaningless for a monthly series.
- Frequency declarations are publisher statements and are trusted as such; a wrong declared
  cadence produces a wrong verdict, and the declared value is published alongside the verdict
  so that it can be challenged.
<!-- END EXTRACTED: freshness-conventions -->

Future content dates are rejected. A 200 response without either signal becomes `unknown-freshness`, not `fresh`, unless the manifest identifies the dataset as versioned `reference` data.

BNM content dates are date-only. The dashboard adds the MYT time declared in each manifest `refresh_frequency` for display; that time is presentation metadata, not a timestamp parsed from the response.

## Content integrity

Record counts are compared with `expected_record_count` when it is known. A result below half the expectation is degraded; capped or estimated results are marked incomplete. Column-count or first-row-shape changes are also degraded so schema drift cannot appear green.

Browser-backed sources always remain `browser-dependent`, even after a successful Camofox snapshot. In due mode, unprobed rows and a previous `last_checked` value are preserved. A probe that produces no measurement does not erase the last successful measurement.

## Blind spots

- HTTP and sampled content checks do not prove semantic accuracy or completeness.
- Generic row counting can be fooled by undocumented pagination or wrappers.
- Browser snapshots depend on client rendering, timing, and selector-free text.
- A stable first-row hash cannot detect changes elsewhere in a dataset.
- Licence and attribution are verified metadata, not legal advice.
