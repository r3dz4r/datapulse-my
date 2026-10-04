# DataPulse MY Trust Snapshot — Week 40, 2026

**Dates covered:** 2026-09-27 to 2026-10-03 (UTC)
**Snapshot date:** 2026-10-03
**Source commit:** `0bf1916f055e4389d5d2af4337005b4f3f021fdf`

## Status distribution

| Status | Count | Percent |
| --- | --- | --- |
| `fresh` | 138 | 32.5% |
| `aging` | 111 | 26.1% |
| `stale` | 148 | 34.9% |
| `discontinued` | 1 | 0.2% |
| `degraded` | 0 | 0.0% |
| `browser-dependent` | 1 | 0.2% |
| `unreachable` | 0 | 0.0% |
| `unknown` | 0 | 0.0% |
| `unknown-freshness` | 5 | 1.2% |
| `reference` | 21 | 4.9% |
| **Total** | **425** | **100.0%** |

## New breaks

| Dataset | Old status | New status | Last checked |
| --- | --- | --- | --- |
| `eperolehan-diklankan` | fresh | stale | 2026-10-03T01:45:56Z |

## Recovered

| Dataset | Old status | New status | Last checked |
| --- | --- | --- | --- |
| `mbpp_weather_stations` | unreachable | fresh | 2026-10-03T01:45:56Z |
| `pekab40_screenings_state` | aging | fresh | 2026-10-02T15:40:53Z |
| `sg_datagov_weather_readings` | degraded | fresh | 2026-10-02T02:20:53Z |

## Schema and record-count changes

| Dataset | Old records | New records | Old columns | New columns | Last checked |
| --- | --- | --- | --- | --- | --- |
| `blood_donations` | 37865 | 37895 | 3 | 3 | 2026-10-02T15:40:53Z |
| `blood_donations_state` | 492245 | 492635 | 4 | 4 | 2026-10-02T15:40:53Z |
| `dgm_payments_transactions_fpx` | 7374 | 7392 | 4 | 4 | 2026-10-02T15:40:53Z |
| `dosm_arc_dosm` | 309 | 311 | 12 | 12 | 2026-10-02T15:40:53Z |
| `exchangerates_daily_0900` | 17213 | 17228 | 29 | 29 | 2026-10-03T01:45:56Z |
| `exchangerates_daily_1130` | 11452 | 11462 | 9 | 9 | 2026-10-03T01:45:56Z |
| `exchangerates_daily_1200` | 18778 | 18793 | 29 | 29 | 2026-10-03T01:45:56Z |
| `exchangerates_daily_1700` | 17247 | 17262 | 29 | 29 | 2026-10-03T01:45:56Z |
| `gtfs_realtime_ktmb` | 24 | 0 | None | None | 2026-10-03T01:45:56Z |
| `gtfs_realtime_mybas_alor_setar` | 37 | 43 | None | None | 2026-10-03T01:45:56Z |
| `gtfs_realtime_mybas_ipoh` | 14 | 19 | None | None | 2026-10-03T01:45:56Z |
| `gtfs_realtime_mybas_johor` | 70 | 77 | None | None | 2026-10-03T01:45:56Z |
| `gtfs_realtime_mybas_kota_bharu` | 53 | 57 | None | None | 2026-10-03T01:45:56Z |
| `gtfs_realtime_mybas_kuching` | 40 | 44 | None | None | 2026-10-03T01:45:56Z |
| `gtfs_realtime_mybas_melaka` | 26 | 25 | None | None | 2026-10-03T01:45:56Z |
| `gtfs_realtime_mybas_seremban_a` | 19 | 17 | None | None | 2026-10-03T01:45:56Z |
| `gtfs_realtime_mybas_seremban_b` | 22 | 19 | None | None | 2026-10-03T01:45:56Z |
| `gtfs_realtime_prasarana_bus_kl` | 84 | 77 | None | None | 2026-10-03T01:45:56Z |
| `gtfs_realtime_prasarana_bus_mrtfeeder` | 103 | 104 | None | None | 2026-10-03T01:45:56Z |
| `gtfs_realtime_prasarana_bus_penang` | 141 | 154 | None | None | 2026-10-03T01:45:56Z |
| `gtfs_static_ktmb` | 5229 | 5155 | None | None | 2026-10-02T15:40:53Z |
| `kkmnow_organ` | 1688 | 1691 | None | None | 2026-10-02T15:40:53Z |
| `kkmnow_pekab40` | 1224 | 1222 | None | None | 2026-10-02T15:40:53Z |
| `mbpp_weather_stations` | None | 28 | None | 50 | 2026-10-03T01:45:56Z |
| `organ_pledges` | 6464 | 6470 | 2 | 2 | 2026-10-02T15:40:53Z |
| `organ_pledges_state` | 103424 | 103520 | 3 | 3 | 2026-10-02T15:40:53Z |
| `pekab40_screenings_state` | 43504 | 43632 | 3 | 3 | 2026-10-02T15:40:53Z |
| `ridership_ktmb_daily` | 9188 | 9218 | 3 | 3 | 2026-10-02T15:40:53Z |
| `ridership_od_brt_daily` | 16616 | 16988 | 4 | 4 | 2026-10-02T15:40:53Z |
| `ridership_od_ets` | 620346 | 634486 | 5 | 5 | 2026-10-02T15:40:53Z |
| `ridership_od_intercity` | 147851 | 151049 | 5 | 5 | 2026-10-02T15:40:53Z |
| `ridership_od_komuter` | 1327189 | 1350719 | 5 | 5 | 2026-10-02T15:40:53Z |
| `ridership_od_komuter_utara` | 1074739 | 1099035 | 5 | 5 | 2026-10-02T15:40:53Z |
| `ridership_od_rapidrail_daily` | 4649800 | 4754448 | 4 | 4 | 2026-10-02T15:40:53Z |
| `ridership_od_shuttle_tebrau` | 7388 | 7552 | 5 | 5 | 2026-10-02T15:40:53Z |
| `sg_datagov_weather_readings` | 1 | 1 | 2 | 2 | 2026-10-02T02:20:53Z |
| `trnsc_daily_directdebit` | 1238 | 1242 | 3 | 3 | 2026-10-02T15:40:53Z |
| `trnsc_daily_fpx` | 7374 | 7392 | 4 | 4 | 2026-10-02T15:40:53Z |
| `trnsc_daily_jompay` | 2821 | 2827 | 3 | 3 | 2026-10-02T15:40:53Z |
| `trnsc_daily_san` | 7369 | 7387 | 4 | 4 | 2026-10-02T15:40:53Z |
| `usage_metrics` | 1105 | 1114 | 4 | 4 | 2026-10-02T15:40:53Z |
| `usage_metrics_openapi` | 19097 | 19345 | 3 | 3 | 2026-10-02T15:40:53Z |

## Newly probed datasets

- `dosm_boundary_district` — reference
- `dosm_boundary_district_lookup` — reference
- `dosm_boundary_dun` — reference
- `dosm_boundary_malaysia` — reference
- `dosm_boundary_parlimen` — reference
- `dosm_boundary_parlimen_dun_lookup` — reference
- `dosm_boundary_state` — reference

## Newly added datasets

- `dosm_boundary_district` — reference
- `dosm_boundary_district_lookup` — reference
- `dosm_boundary_dun` — reference
- `dosm_boundary_malaysia` — reference
- `dosm_boundary_parlimen` — reference
- `dosm_boundary_parlimen_dun_lookup` — reference
- `dosm_boundary_state` — reference

## Source-level staleness

_No source families met the staleness threshold._

## Coverage

- Total datasets: **425**

### By namespace

| Namespace | Datasets |
| --- | --- |
| `economy` | 147 |
| `environment` | 14 |
| `government_open_data` | 92 |
| `healthcare` | 36 |
| `other` | 84 |
| `transport` | 49 |
| `weather` | 3 |

### By licence

| Licence | Datasets |
| --- | --- |
| Creative Commons Attribution 4.0 | 285 |
| MBPP Government Open Data Terms (attribution required) | 1 |
| MIT License | 8 |
| Open Data License | 7 |
| Open Government Licence (Malaysia) | 115 |
| Publisher licence not stated; portal disclaimer applies | 4 |
| Singapore Open Data Licence v1.0 (attribution required) | 5 |

## Honest caveats

- **5** datasets have unknown freshness and **0** are unreachable. These are explicit trust gaps, not silent green checks.
- Compared with manifest and health baselines 274bae948c1e / 352049f5d960.

## Reproducibility

Generated by `bash scripts/gen_trust_snapshot.sh`. License: MIT. Cite: https://www.data-pulse.my/trust-snapshot-2026-10-03.md
