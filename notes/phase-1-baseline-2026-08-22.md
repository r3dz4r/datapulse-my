# Phase 1 baseline — flagship trust cohort

Date: 2026-08-22
Status: phase-start baseline; internal working note

## Objective

Prove the narrow claim that DataPulse can separate **what a publisher declares**, **what a probe observes**, and **what an agent should conclude**. This phase is not a catalogue-expansion exercise and does not yet define a numeric trust score.

## Locked cohort

| Role | Dataset ID | Publisher declaration | Current observed state | Initial verdict |
|---|---|---|---|---|
| Realtime transport | `gtfs_realtime_prasarana_bus_kl` | Vehicle-position feeds update every 30 seconds.[1] | Local health snapshot `2026-08-21T23:11:15Z`: HTTP 200, valid protobuf, 84 vehicles, fresh, content-date signal, no shape change.[3] | Fresh and populated at observation time; longitudinal reliability not yet proven. |
| Realtime transport | `gtfs_realtime_prasarana_bus_penang` | Vehicle-position feeds update every 30 seconds; the official page documents known trip/route-ID issues for Rapid Penang.[1] | Local health snapshot `2026-08-21T23:11:15Z`: HTTP 200, valid protobuf, 123 vehicles, fresh, content-date signal, no shape change.[3] | Fresh and populated at observation time; declared semantic caveats remain relevant. |
| Daily financial | `exchangerates_daily_0900` | BNM daily weekday reference-rate dataset, nominally updated at 0900 MYT.[4] | Last checked `2026-08-21T22:31:11Z`: HTTP 200, fresh, content date `2026-08-21`, 17,147 records, 29 columns, no shape change.[3] | Fresh direct response; cadence adherence needs a time-series window. |
| Daily forecast | `met_weather` | MET Malaysia weather forecast, daily cadence.[4] | Last checked `2026-08-21T02:30:56Z`: HTTP 200, fresh, content date `2026-08-21`, 3,101 records, 9 columns, no shape change.[3] | Fresh direct response; forecast semantics and publication lag need a time-series window. |
| Monthly official statistics | `dosm_trade_headline` | OpenDOSM monthly trade headline dataset.[4] | Last checked `2026-08-16T02:09:20Z`: HTTP 200, stale, content date `2026-04-01`, 743 records, header-based freshness signal, anomaly detected.[3] | Evidence of a stale or insufficiently refreshed source; do not treat HTTP 200 as current data. |
| Browser-dependent government source | `doe_mqims` | DOE MyEQMS marine-water-quality source, monthly cadence; row extraction is explicitly uncertain.[4] | Last checked `2026-08-16T03:00:49Z`: browser check succeeded, content date `2026-08-15`, browser-dependent, no record count, 7,317-character snapshot.[3] | Reachable through the browser path, but not yet structurally quantified. |

## Evidence contract

Every flagship observation must preserve three distinct layers:

1. **Declared by source** — cadence, publisher, known limitations, and intended semantics.
2. **Observed by DataPulse** — access method, observation time, HTTP/browser result, parser result, freshness signal, record count where available, shape change, and anomaly state.
3. **Decision verdict** — a bounded conclusion such as `fresh and populated at observation time`, `reachable but structurally unquantified`, or `stale; do not treat as current`.

The verdict must not silently upgrade a source declaration into a reliability claim. A `fresh` observation is not a longitudinal reliability grade.

## First baseline finding

The cohort already demonstrates why the proof needs multiple signal classes:

- GTFS and MET can be directly reachable and structurally parsed.
- BNM is fresh but requires a cadence-history check to prove adherence rather than a single successful request.
- OpenDOSM Trade is HTTP 200 yet stale, showing why reachability is not currency.
- DOE MQIMS is browser-reachable but not row-quantified, showing why browser success is not structural verification.

The first phase therefore has a real test surface without adding datasets.

## Publication-lag finding

The local health file reports `checked_at: 2026-08-21T23:11:15Z`.[3] The public GitHub Pages health artifact served at the same investigation time reports `checked_at: 2026-08-21T16:31:14Z`.[2] The public artifact is therefore an older snapshot than the local operational source. The local health envelope remains the operational source of truth; public-surface lag must be measured as a separate signal, not hidden.

## What is proven now

- The flagship cohort is explicit and small enough to inspect deeply.
- The source-declared / observed / verdict separation is implementable using existing manifest and health fields.
- The cohort contains useful positive and negative cases: fresh direct feeds, stale HTTP-200 data, and browser-reachable but structurally incomplete data.
- The public surface can lag the local observation pipeline and must be tested independently.

## What remains unproven

- Observed cadence versus declared cadence over a longitudinal window.
- Distribution of empty or low-volume GTFS responses across operating periods.
- Semantic validity beyond the parser and the publisher's documented validator scope.
- Whether public generated surfaces converge with local health observations within an acceptable publication window.
- Whether browser-dependent observations can become repeatable, structured evidence rather than snapshots only.

## Phase 1 acceptance gate

Do not move to a verdict API wedge until the cohort has:

- a repeatable observation history;
- at least one declared-vs-observed cadence comparison;
- explicit handling for stale HTTP-200 data;
- explicit handling for reachable-but-unquantified browser data;
- a measured local-to-public publication-lag signal; and
- a written list of claims that remain `unproven`.

## Sources

[1] https://developer.data.gov.my/realtime-api/gtfs-realtime
[2] https://r3dz4r.github.io/datapulse-my/health/latest.json
[3] `/home/redza/datapulse-my/health/latest.json` — locally verified snapshot at `2026-08-21T23:11:15Z`.
[4] `/home/redza/datapulse-my/datapulse.json` — locally verified manifest declarations for the six selected datasets.
