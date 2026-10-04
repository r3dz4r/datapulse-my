# DataPulse MY Trust Snapshot — Week 40, 2026

**Dates covered:** 2026-09-28 to 2026-10-04 (UTC)
**Snapshot date:** 2026-10-04
**Source commit:** `03e3036a1e5c36e7660b54282764d7aad774960f`

## Status distribution

| Status | Count | Percent |
| --- | --- | --- |
| `fresh` | 133 | 31.3% |
| `aging` | 129 | 30.4% |
| `stale` | 135 | 31.8% |
| `discontinued` | 1 | 0.2% |
| `degraded` | 1 | 0.2% |
| `browser-dependent` | 0 | 0.0% |
| `unreachable` | 0 | 0.0% |
| `unknown` | 0 | 0.0% |
| `unknown-freshness` | 5 | 1.2% |
| `reference` | 21 | 4.9% |
| **Total** | **425** | **100.0%** |

## New breaks

| Dataset | Old status | New status | Last checked |
| --- | --- | --- | --- |
| `eperolehan-diklankan` | fresh | stale | 2026-10-04T03:50:43Z |

## Recovered

| Dataset | Old status | New status | Last checked |
| --- | --- | --- | --- |
| `arrivals_soe` | stale | fresh | 2026-10-03T10:36:37Z |
| `doe_mqims` | browser-dependent | fresh | 2026-10-03T10:36:37Z |
| `exchangerates` | aging | fresh | 2026-10-03T10:36:37Z |
| `mbpp_weather_stations` | unreachable | fresh | 2026-10-04T03:50:43Z |
| `pekab40_screenings_state` | aging | fresh | 2026-10-03T15:47:47Z |
| `ridership_ktmb_monthly` | aging | fresh | 2026-10-03T10:36:37Z |

## Schema and record-count changes

| Dataset | Old records | New records | Old columns | New columns | Last checked |
| --- | --- | --- | --- | --- | --- |
| `air_pollution` | 432 | 576 | 3 | 3 | 2026-10-03T10:36:37Z |
| `arrivals` | 13050 | 18240 | 5 | 5 | 2026-10-03T10:36:37Z |
| `arrivals_soe` | 92674 | 117236 | 6 | 6 | 2026-10-03T10:36:37Z |
| `blood_donations` | 37870 | 37900 | 3 | 3 | 2026-10-03T15:47:47Z |
| `blood_donations_state` | 492310 | 492700 | 4 | 4 | 2026-10-03T15:47:47Z |
| `cosmetic_notifications` | 242942 | 243017 | 4 | 4 | 2026-10-03T10:36:37Z |
| `dgm_ktmb_ridership_monthly` | 295 | 300 | 3 | 3 | 2026-10-03T10:36:37Z |
| `dgm_payments_transactions_fpx` | 7377 | 7395 | 4 | 4 | 2026-10-03T15:47:47Z |
| `dosm_arc_dosm` | 309 | 311 | 12 | 12 | 2026-10-03T15:47:47Z |
| `dosm_ppi` | 584 | 587 | 4 | 4 | 2026-10-03T10:36:37Z |
| `dosm_ppi_1d` | 2920 | 2935 | 5 | 5 | 2026-10-03T10:36:37Z |
| `dosm_ppi_sitc` | 5256 | 5283 | 4 | 4 | 2026-10-03T10:36:37Z |
| `economic_indicators` | 426 | 427 | 6 | 6 | 2026-10-03T10:36:37Z |
| `exchangerates` | 1780 | 1785 | 29 | 29 | 2026-10-03T10:36:37Z |
| `exchangerates_daily_0900` | 17213 | 17228 | 29 | 29 | 2026-10-04T03:40:24Z |
| `exchangerates_daily_1130` | 11452 | 11462 | 9 | 9 | 2026-10-04T03:40:24Z |
| `exchangerates_daily_1200` | 18778 | 18793 | 29 | 29 | 2026-10-04T03:40:24Z |
| `exchangerates_daily_1700` | 17247 | 17262 | 29 | 29 | 2026-10-04T03:40:24Z |
| `fuelprice` | 959 | 961 | 10 | 10 | 2026-10-03T10:36:37Z |
| `gtfs_realtime_ktmb` | 7 | 8 | None | None | 2026-10-04T03:50:43Z |
| `gtfs_realtime_mybas_alor_setar` | 38 | 43 | None | None | 2026-10-04T03:50:43Z |
| `gtfs_realtime_mybas_ipoh` | 27 | 16 | None | None | 2026-10-04T03:50:43Z |
| `gtfs_realtime_mybas_johor` | 80 | 82 | None | None | 2026-10-04T03:50:43Z |
| `gtfs_realtime_mybas_kangar` | 21 | 22 | None | None | 2026-10-04T03:50:43Z |
| `gtfs_realtime_mybas_kota_bharu` | 51 | 62 | None | None | 2026-10-04T03:50:43Z |
| `gtfs_realtime_mybas_kuching` | 43 | 45 | None | None | 2026-10-04T03:50:43Z |
| `gtfs_realtime_mybas_melaka` | 24 | 23 | None | None | 2026-10-04T03:50:43Z |
| `gtfs_realtime_mybas_seremban_a` | 11 | 17 | None | None | 2026-10-04T03:50:43Z |
| `gtfs_realtime_mybas_seremban_b` | 27 | 18 | None | None | 2026-10-04T03:50:43Z |
| `gtfs_realtime_prasarana_bus_kl` | 123 | 76 | None | None | 2026-10-04T03:50:43Z |
| `gtfs_realtime_prasarana_bus_mrtfeeder` | 148 | 96 | None | None | 2026-10-04T03:50:43Z |
| `gtfs_realtime_prasarana_bus_penang` | 172 | 140 | None | None | 2026-10-04T03:50:43Z |
| `gtfs_static_ktmb` | 5229 | 5155 | None | None | 2026-10-03T15:47:47Z |
| `kkmnow_organ` | 1688 | 1691 | None | None | 2026-10-03T15:47:47Z |
| `kkmnow_pekab40` | 1224 | 1219 | None | None | 2026-10-03T15:47:47Z |
| `mbpp_weather_stations` | None | 28 | None | 50 | 2026-10-04T03:50:43Z |
| `metrics_content` | 37 | 38 | 3 | 3 | 2026-10-03T10:36:37Z |
| `organ_pledges` | 6465 | 6471 | 2 | 2 | 2026-10-03T15:47:47Z |
| `organ_pledges_state` | 103440 | 103536 | 3 | 3 | 2026-10-03T15:47:47Z |
| `passports` | 5684 | 7920 | 4 | 4 | 2026-10-03T10:36:37Z |
| `pekab40_screenings_state` | 43504 | 43648 | 3 | 3 | 2026-10-03T15:47:47Z |
| `pharmaceutical_products` | 28228 | 28196 | 16 | 16 | 2026-10-03T10:36:37Z |
| `pharmaceutical_wholesalers` | 1012 | 1014 | 10 | 10 | 2026-10-03T10:36:37Z |
| `ppi` | 584 | 587 | 4 | 4 | 2026-10-03T10:36:37Z |
| `ppi_2d` | 11312 | 11396 | 4 | 4 | 2026-10-03T10:36:37Z |
| `ppi_3d` | 37260 | 37476 | 4 | 4 | 2026-10-03T10:36:37Z |
| `ppi_sop` | 12221 | 12271 | 4 | 4 | 2026-10-03T10:36:37Z |
| `ridership_ktmb_daily` | 9193 | 9223 | 3 | 3 | 2026-10-03T15:47:47Z |
| `ridership_ktmb_monthly` | 295 | 300 | 3 | 3 | 2026-10-03T10:36:37Z |
| `ridership_od_brt_daily` | 16678 | 17050 | 4 | 4 | 2026-10-03T15:47:47Z |
| `ridership_od_ets` | 622969 | 636996 | 5 | 5 | 2026-10-03T15:47:47Z |
| `ridership_od_intercity` | 148386 | 151619 | 5 | 5 | 2026-10-03T15:47:47Z |
| `ridership_od_komuter` | 1330508 | 1355591 | 5 | 5 | 2026-10-03T15:47:47Z |
| `ridership_od_komuter_utara` | 1078922 | 1103758 | 5 | 5 | 2026-10-03T15:47:47Z |
| `ridership_od_rapidrail_daily` | 4667688 | 4771800 | 4 | 4 | 2026-10-03T15:47:47Z |
| `ridership_od_shuttle_tebrau` | 7416 | 7580 | 5 | 5 | 2026-10-03T15:47:47Z |
| `sg_datagov_weather_readings` | 1 | 1 | 2 | 2 | 2026-10-04T02:35:45Z |
| `trnsc_daily_directdebit` | 1238 | 1243 | 3 | 3 | 2026-10-03T15:47:47Z |
| `trnsc_daily_fpx` | 7377 | 7395 | 4 | 4 | 2026-10-03T15:47:47Z |
| `trnsc_daily_jompay` | 2822 | 2828 | 3 | 3 | 2026-10-03T15:47:47Z |
| `trnsc_daily_san` | 7372 | 7390 | 4 | 4 | 2026-10-03T15:47:47Z |
| `usage_metrics` | 1106 | 1115 | 4 | 4 | 2026-10-03T15:47:47Z |
| `usage_metrics_openapi` | 19128 | 19376 | 3 | 3 | 2026-10-03T15:47:47Z |

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
- Compared with manifest and health baselines 274bae948c1e / 0793d321551e.

## Reproducibility

Generated by `bash scripts/gen_trust_snapshot.sh`. License: MIT. Cite: https://www.data-pulse.my/trust-snapshot-2026-10-04.md
