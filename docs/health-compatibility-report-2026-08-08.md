# Health compatibility report — 2026-08-08

## Scope and method

This is a read-only comparison of the legacy shell classification in `health/latest.json` with the pure classifier in `scripts/health_policy.py`. It does not change the production classifier, the health envelope, or any published dataset status.

The checked-in snapshot was observed at `2026-08-08T15:46:45Z`. All 166 canonical manifest IDs were compared, with no missing or extra IDs.

Reproduce the machine-readable comparison from the repository root:

```bash
python3 scripts/compare_health.py health/latest.json datapulse.json \
  > /tmp/datapulse-health-comparison.json
jq '{datasets_compared, status_changes}' /tmp/datapulse-health-comparison.json
```

## Result

The comparison contains 40 status changes:

| Transition | Count | Category | Policy basis |
|---|---:|---|---|
| `fresh` → `unknown-freshness` | 14 | Intended correction | G4 and the approved Q2/Q3 as-required rule: without an explicit publisher `date_*` field, freshness is unknown. |
| `fresh` → `aging` | 13 | Intended correction | G3/G4: use the selected content signal and the explicit cadence window instead of treating any parseable age as fresh. |
| `fresh` → `stale` | 13 | Intended correction | G4: realtime freshness is bounded by cadence × 1.5 for fresh and cadence × 3 for aging. |

There are no unexpected changes and no blockers in this snapshot. There are no additional changes categorized separately as bug fixes; the 40 intended corrections are the policy fixes approved by G3/G4/Q2/Q3.

The legacy snapshot has no `status_reason` values. The pure classifier supplies a reason for all 166 rows. Forty reason additions accompany the status changes below; the other 126 are formatting/explainability-only additions whose status is unchanged:

| Reason-only addition | Count |
|---|---:|
| `freshness-stale` | 55 |
| `freshness-within-window` | 42 |
| `survey-verification-current` | 11 |
| `freshness-aging` | 11 |
| `browser-access-required` | 5 |
| `transport-failure` | 1 |
| `no-freshness-signal` | 1 |

## Datasets with status changes

| Dataset | Status transition | Pure-classifier reason |
|---|---|---|
| `exchangerates_daily_0900` | `fresh` → `aging` | `freshness-aging` |
| `exchangerates_daily_1130` | `fresh` → `aging` | `freshness-aging` |
| `exchangerates_daily_1200` | `fresh` → `aging` | `freshness-aging` |
| `exchangerates_daily_1700` | `fresh` → `aging` | `freshness-aging` |
| `dgm_payments_transactions_fpx` | `fresh` → `aging` | `freshness-aging` |
| `dgm_blood_donations_state` | `fresh` → `aging` | `freshness-aging` |
| `dgm_pekab40_screenings_state` | `fresh` → `aging` | `freshness-aging` |
| `gtfs_static_prasarana_rail_kl` | `fresh` → `unknown-freshness` | `as-required-no-publisher-date` |
| `gtfs_static_prasarana_bus_kl` | `fresh` → `unknown-freshness` | `as-required-no-publisher-date` |
| `gtfs_static_prasarana_bus_penang` | `fresh` → `unknown-freshness` | `as-required-no-publisher-date` |
| `gtfs_static_prasarana_bus_mrtfeeder` | `fresh` → `unknown-freshness` | `as-required-no-publisher-date` |
| `gtfs_static_mybas_kangar` | `fresh` → `unknown-freshness` | `as-required-no-publisher-date` |
| `gtfs_static_mybas_alor_setar` | `fresh` → `unknown-freshness` | `as-required-no-publisher-date` |
| `gtfs_static_mybas_kota_bharu` | `fresh` → `unknown-freshness` | `as-required-no-publisher-date` |
| `gtfs_static_mybas_kuala_terengganu` | `fresh` → `unknown-freshness` | `as-required-no-publisher-date` |
| `gtfs_static_mybas_ipoh` | `fresh` → `unknown-freshness` | `as-required-no-publisher-date` |
| `gtfs_static_mybas_seremban_a` | `fresh` → `unknown-freshness` | `as-required-no-publisher-date` |
| `gtfs_static_mybas_seremban_b` | `fresh` → `unknown-freshness` | `as-required-no-publisher-date` |
| `gtfs_static_mybas_melaka` | `fresh` → `unknown-freshness` | `as-required-no-publisher-date` |
| `gtfs_static_mybas_johor` | `fresh` → `unknown-freshness` | `as-required-no-publisher-date` |
| `gtfs_static_mybas_kuching` | `fresh` → `unknown-freshness` | `as-required-no-publisher-date` |
| `gtfs_realtime_ktmb` | `fresh` → `stale` | `freshness-stale` |
| `gtfs_realtime_prasarana_bus_kl` | `fresh` → `stale` | `freshness-stale` |
| `gtfs_realtime_prasarana_bus_penang` | `fresh` → `stale` | `freshness-stale` |
| `gtfs_realtime_mybas_kangar` | `fresh` → `stale` | `freshness-stale` |
| `gtfs_realtime_mybas_alor_setar` | `fresh` → `stale` | `freshness-stale` |
| `gtfs_realtime_mybas_kota_bharu` | `fresh` → `stale` | `freshness-stale` |
| `gtfs_realtime_mybas_kuala_terengganu` | `fresh` → `stale` | `freshness-stale` |
| `gtfs_realtime_mybas_ipoh` | `fresh` → `stale` | `freshness-stale` |
| `gtfs_realtime_mybas_seremban_a` | `fresh` → `stale` | `freshness-stale` |
| `gtfs_realtime_mybas_seremban_b` | `fresh` → `stale` | `freshness-stale` |
| `gtfs_realtime_mybas_melaka` | `fresh` → `stale` | `freshness-stale` |
| `gtfs_realtime_mybas_johor` | `fresh` → `stale` | `freshness-stale` |
| `gtfs_realtime_mybas_kuching` | `fresh` → `stale` | `freshness-stale` |
| `ridership_ktmb_daily` | `fresh` → `aging` | `freshness-aging` |
| `ridership_od_komuter` | `fresh` → `aging` | `freshness-aging` |
| `ridership_od_ets` | `fresh` → `aging` | `freshness-aging` |
| `ridership_od_intercity` | `fresh` → `aging` | `freshness-aging` |
| `ridership_od_komuter_utara` | `fresh` → `aging` | `freshness-aging` |
| `ridership_od_shuttle_tebrau` | `fresh` → `aging` | `freshness-aging` |

The daily/weekday-daily rows become aging because their selected freshness signal falls above the fresh boundary but within cadence × 3. The static GTFS rows become unknown-freshness because their `as-required` manifests do not declare an explicit publisher `date_*` freshness field. The realtime GTFS rows become stale because their selected feed timestamps exceed the 30-second cadence stale boundary.

## Task 33 production-switch review

Before switching production classification, Task 33 should:

1. Re-run the comparison against a newly captured full sweep and require set equality with the canonical manifest.
2. Confirm the 14 as-required GTFS dispositions and whether any publisher-provided `date_*` signal has become available.
3. Review realtime GTFS timestamps and transport evidence so an unreachable/degraded probe cannot be mistaken for ordinary staleness.
4. Review the 13 aging rows against their configured content-date field and fallback evidence.
5. Approve adding `status_reason` to production rows while preserving the existing `health/latest.json` envelope structure and summary arithmetic.
6. Treat any transition outside the three reviewed groups as a blocker requiring a new compatibility report.
