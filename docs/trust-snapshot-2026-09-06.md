# DataPulse MY Trust Snapshot — Week 36, 2026

**Dates covered:** 2026-08-31 to 2026-09-06 (UTC)
**Snapshot date:** 2026-09-06
**Source commit:** `988991ee4f652db8a717a576cd4191a98e2b2a16`

## Status distribution

| Status | Count | Percent |
| --- | --- | --- |
| `fresh` | 86 | 20.6% |
| `aging` | 115 | 27.5% |
| `stale` | 188 | 45.0% |
| `discontinued` | 1 | 0.2% |
| `degraded` | 0 | 0.0% |
| `browser-dependent` | 5 | 1.2% |
| `unreachable` | 0 | 0.0% |
| `unknown` | 0 | 0.0% |
| `unknown-freshness` | 9 | 2.2% |
| `reference` | 14 | 3.3% |
| **Total** | **418** | **100.0%** |

## New breaks

| Dataset | Old status | New status | Last checked |
| --- | --- | --- | --- |
| `dgm_payments_transactions_fpx` | fresh | stale | 2026-09-06T05:22:25Z |
| `gtfs_realtime_ktmb` | fresh | stale | 2026-09-06T20:36:28Z |
| `gtfs_realtime_mybas_alor_setar` | fresh | stale | 2026-09-06T20:36:28Z |
| `gtfs_realtime_mybas_ipoh` | fresh | stale | 2026-09-06T20:36:28Z |
| `gtfs_realtime_mybas_johor` | fresh | stale | 2026-09-06T20:36:28Z |
| `gtfs_realtime_mybas_kangar` | fresh | stale | 2026-09-06T20:36:28Z |
| `gtfs_realtime_mybas_kota_bharu` | fresh | stale | 2026-09-06T20:36:28Z |
| `gtfs_realtime_mybas_kuala_terengganu` | fresh | stale | 2026-09-06T20:36:28Z |
| `gtfs_realtime_mybas_kuching` | fresh | stale | 2026-09-06T20:36:28Z |
| `gtfs_realtime_mybas_melaka` | fresh | stale | 2026-09-06T20:36:28Z |
| `gtfs_realtime_mybas_seremban_a` | fresh | stale | 2026-09-06T20:36:28Z |
| `gtfs_realtime_prasarana_bus_kl` | fresh | stale | 2026-09-06T20:36:28Z |
| `gtfs_realtime_prasarana_bus_penang` | fresh | stale | 2026-09-06T20:36:28Z |
| `trnsc_daily_fpx` | fresh | stale | 2026-09-06T05:22:25Z |
| `trnsc_daily_jompay` | fresh | stale | 2026-09-06T05:22:25Z |
| `trnsc_daily_san` | fresh | stale | 2026-09-06T05:22:25Z |

## Recovered

| Dataset | Old status | New status | Last checked |
| --- | --- | --- | --- |
| `blood_donations` | aging | fresh | 2026-09-06T05:22:25Z |
| `hansard_mps` | stale | fresh | 2026-09-05T02:34:56Z |
| `hansard_parliamentary_terms` | stale | fresh | 2026-09-05T02:34:56Z |
| `hansard_sittings` | stale | fresh | 2026-09-05T02:34:56Z |
| `ridership_ktmb_daily` | stale | fresh | 2026-09-06T05:22:25Z |
| `ridership_ktmb_monthly` | aging | fresh | 2026-09-05T02:34:56Z |
| `ridership_od_ets` | stale | fresh | 2026-09-06T05:22:25Z |
| `ridership_od_intercity` | stale | fresh | 2026-09-06T05:22:25Z |
| `ridership_od_komuter` | stale | fresh | 2026-09-06T05:22:25Z |
| `ridership_od_komuter_utara` | stale | fresh | 2026-09-06T05:22:25Z |
| `ridership_od_shuttle_tebrau` | stale | fresh | 2026-09-06T05:22:25Z |

## Schema and record-count changes

| Dataset | Old records | New records | Old columns | New columns | Last checked |
| --- | --- | --- | --- | --- | --- |
| `blood_donations` | 37725 | 37765 | 3 | 3 | 2026-09-06T05:22:25Z |
| `blood_donations_state` | 490490 | 490945 | 4 | 4 | 2026-09-06T05:22:25Z |
| `cosmetic_notifications` | 242457 | 242139 | 4 | 4 | 2026-09-05T02:34:56Z |
| `dgm_ktmb_ridership_monthly` | 290 | 295 | 3 | 3 | 2026-09-05T02:34:56Z |
| `dgm_payments_transactions_fpx` | 7293 | 7302 | 4 | 4 | 2026-09-06T05:22:25Z |
| `dosm_lookup_premise` | 3893 | 3908 | 6 | 6 | 2026-09-05T02:34:56Z |
| `dosm_ppi` | 581 | 584 | 4 | 4 | 2026-09-05T02:34:56Z |
| `dosm_ppi_1d` | 2905 | 2920 | 5 | 5 | 2026-09-05T02:34:56Z |
| `dosm_ppi_sitc` | 5229 | 5256 | 4 | 4 | 2026-09-05T02:34:56Z |
| `dosm_trade_sitc_1d` | 3498 | 3509 | 4 | 4 | 2026-09-05T02:34:56Z |
| `exchangerates_daily_0900` | 17159 | 17171 | 29 | 29 | 2026-09-06T20:36:28Z |
| `exchangerates_daily_1130` | 11416 | 11424 | 9 | 9 | 2026-09-06T20:36:28Z |
| `exchangerates_daily_1200` | 18724 | 18736 | 29 | 29 | 2026-09-06T20:36:28Z |
| `exchangerates_daily_1700` | 17193 | 17205 | 29 | 29 | 2026-09-06T20:36:28Z |
| `fuelprice` | 951 | 953 | 10 | 10 | 2026-09-05T02:34:56Z |
| `gtfs_realtime_ktmb` | 17 | 1 | None | None | 2026-09-06T20:36:28Z |
| `gtfs_realtime_mybas_alor_setar` | 38 | 8 | None | None | 2026-09-06T20:36:28Z |
| `gtfs_realtime_mybas_ipoh` | 14 | 22 | None | None | 2026-09-06T20:36:28Z |
| `gtfs_realtime_mybas_johor` | 75 | 18 | None | None | 2026-09-06T20:36:28Z |
| `gtfs_realtime_mybas_kangar` | 23 | 1 | None | None | 2026-09-06T20:36:28Z |
| `gtfs_realtime_mybas_kota_bharu` | 54 | 1 | None | None | 2026-09-06T20:36:28Z |
| `gtfs_realtime_mybas_kuala_terengganu` | 25 | 1 | None | None | 2026-09-06T20:36:28Z |
| `gtfs_realtime_mybas_kuching` | 44 | 3 | None | None | 2026-09-06T20:36:28Z |
| `gtfs_realtime_mybas_melaka` | 21 | 1 | None | None | 2026-09-06T20:36:28Z |
| `gtfs_realtime_mybas_seremban_a` | 36 | 0 | None | None | 2026-09-06T20:36:28Z |
| `gtfs_realtime_mybas_seremban_b` | 25 | 0 | None | None | 2026-09-06T20:36:28Z |
| `gtfs_realtime_prasarana_bus_kl` | 98 | 0 | None | None | 2026-09-06T20:36:28Z |
| `gtfs_realtime_prasarana_bus_mrtfeeder` | 100 | 1 | None | None | 2026-09-06T20:36:28Z |
| `gtfs_realtime_prasarana_bus_penang` | 147 | 0 | None | None | 2026-09-06T20:36:28Z |
| `gtfs_static_ktmb` | 5373 | 5269 | None | None | 2026-09-06T05:22:25Z |
| `gtfs_static_mybas_alor_setar` | 0 | 35388 | None | None | 2026-09-05T02:34:56Z |
| `gtfs_static_mybas_johor` | 76731 | 76930 | None | None | 2026-09-05T02:34:56Z |
| `gtfs_static_mybas_kangar` | 0 | 16160 | None | None | 2026-09-05T02:34:56Z |
| `gtfs_static_mybas_kota_bharu` | 0 | 47556 | None | None | 2026-09-05T02:34:56Z |
| `gtfs_static_mybas_kuala_terengganu` | 0 | 20616 | None | None | 2026-09-05T02:34:56Z |
| `gtfs_static_mybas_kuching` | 0 | 17170 | None | None | 2026-09-05T02:34:56Z |
| `gtfs_static_prasarana_bus_penang` | 520570 | 308171 | None | None | 2026-09-05T02:34:56Z |
| `metrics_content` | 36 | 37 | 3 | 3 | 2026-09-05T02:34:56Z |
| `pekab40_screenings` | 2682 | 2697 | 2 | 2 | 2026-09-06T05:22:25Z |
| `pekab40_screenings_state` | 43088 | 43216 | 3 | 3 | 2026-09-06T05:22:25Z |
| `pharmaceutical_manufacturers` | 288 | 289 | 8 | 8 | 2026-09-05T02:34:56Z |
| `ppi` | 581 | 584 | 4 | 4 | 2026-09-05T02:34:56Z |
| `ppi_2d` | 11228 | 11312 | 4 | 4 | 2026-09-05T02:34:56Z |
| `ppi_3d` | 37044 | 37260 | 4 | 4 | 2026-09-05T02:34:56Z |
| `ppi_sop` | 12134 | 12221 | 4 | 4 | 2026-09-05T02:34:56Z |
| `pricecatcher` | 19861 | 1573 | None | None | 2026-09-05T02:34:56Z |
| `ridership_ktmb_daily` | 9018 | 9088 | 3 | 3 | 2026-09-06T05:22:25Z |
| `ridership_ktmb_monthly` | 290 | 295 | 3 | 3 | 2026-09-05T02:34:56Z |
| `ridership_od_ets` | 541335 | 574127 | 5 | 5 | 2026-09-06T05:22:25Z |
| `ridership_od_intercity` | 128973 | 137340 | 5 | 5 | 2026-09-06T05:22:25Z |
| `ridership_od_komuter` | 1193106 | 1247634 | 5 | 5 | 2026-09-06T05:22:25Z |
| `ridership_od_komuter_utara` | 933944 | 993088 | 5 | 5 | 2026-09-06T05:22:25Z |
| `ridership_od_shuttle_tebrau` | 6452 | 6840 | 5 | 5 | 2026-09-06T05:22:25Z |
| `trade_sitc_1d` | 3498 | 3509 | 4 | 4 | 2026-09-05T02:34:56Z |
| `trnsc_daily_directdebit` | 1220 | 1221 | 3 | 3 | 2026-09-06T05:22:25Z |
| `trnsc_daily_fpx` | 7293 | 7302 | 4 | 4 | 2026-09-06T05:22:25Z |
| `trnsc_daily_jompay` | 2429 | 2432 | 3 | 3 | 2026-09-06T05:22:25Z |
| `trnsc_daily_san` | 7288 | 7297 | 4 | 4 | 2026-09-06T05:22:25Z |
| `usage_metrics` | 1078 | 1085 | 4 | 4 | 2026-09-06T05:22:25Z |
| `usage_metrics_openapi` | 18260 | 18477 | 3 | 3 | 2026-09-06T05:22:25Z |

## Newly probed datasets

- `kkmnow_bedutil` — unknown-freshness
- `kkmnow_blood` — stale
- `kkmnow_covidepid` — unknown-freshness
- `kkmnow_covidnow` — stale
- `kkmnow_covidvax` — unknown-freshness
- `kkmnow_facilities` — unknown-freshness
- `kkmnow_organ` — fresh
- `kkmnow_pekab40` — fresh
- `mbpp_weather_stations` — fresh
- `sg_datagov_coe_bidding` — fresh
- `sg_datagov_hdb_metadata` — unknown-freshness
- `sg_datagov_hdb_resale_prices` — unknown-freshness
- `sg_datagov_taxi_availability` — unknown-freshness
- `sg_datagov_weather_readings` — unknown-freshness
- `st_cogenerators` — stale
- `st_consumers` — stale
- `st_current_cogen_licensees` — fresh
- `st_current_ipp_licensees` — fresh
- `st_current_lss_licensees` — fresh
- `st_current_re_licensees` — fresh
- `st_elesca` — stale
- `st_energy_balance_pdf` — fresh
- `st_generation_mix_gwh` — stale
- `st_installed_capacity_mw` — stale
- `st_ipps` — stale
- `st_max_demand_mw` — stale
- `st_re_projects` — stale
- `st_sales_unit_gwh` — stale
- `st_sales_value_rm_million` — stale

## Newly added datasets

- `kkmnow_bedutil` — unknown-freshness
- `kkmnow_blood` — stale
- `kkmnow_covidepid` — unknown-freshness
- `kkmnow_covidnow` — stale
- `kkmnow_covidvax` — unknown-freshness
- `kkmnow_facilities` — unknown-freshness
- `kkmnow_organ` — fresh
- `kkmnow_pekab40` — fresh
- `mbpp_weather_stations` — fresh
- `sg_datagov_coe_bidding` — fresh
- `sg_datagov_hdb_metadata` — unknown-freshness
- `sg_datagov_hdb_resale_prices` — unknown-freshness
- `sg_datagov_taxi_availability` — unknown-freshness
- `sg_datagov_weather_readings` — unknown-freshness
- `st_cogenerators` — stale
- `st_consumers` — stale
- `st_current_cogen_licensees` — fresh
- `st_current_ipp_licensees` — fresh
- `st_current_lss_licensees` — fresh
- `st_current_re_licensees` — fresh
- `st_elesca` — stale
- `st_energy_balance_pdf` — fresh
- `st_generation_mix_gwh` — stale
- `st_installed_capacity_mw` — stale
- `st_ipps` — stale
- `st_max_demand_mw` — stale
- `st_re_projects` — stale
- `st_sales_unit_gwh` — stale
- `st_sales_value_rm_million` — stale

## Source-level staleness

_No source families met the staleness threshold._

## Coverage

- Total datasets: **418**

### By namespace

| Namespace | Datasets |
| --- | --- |
| `economy` | 147 |
| `environment` | 14 |
| `government_open_data` | 85 |
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
| Open Government Licence (Malaysia) | 115 |
| Publisher licence not stated; portal disclaimer applies | 4 |
| Singapore Open Data Licence v1.0 (attribution required) | 5 |

## Honest caveats

- **9** datasets have unknown freshness and **0** are unreachable. These are explicit trust gaps, not silent green checks.
- Compared with manifest and health baselines fbfbcccae556 / 8de2f2732590.

## Reproducibility

Generated by `bash scripts/gen_trust_snapshot.sh`. License: MIT. Cite: https://www.data-pulse.my/trust-snapshot-2026-09-06.md
