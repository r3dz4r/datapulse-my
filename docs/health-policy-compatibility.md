# Full-probe health policy compatibility canary

- Date: `2026-08-09T10:14:33+08:00`
- Source SHA: `f6be1b4215333772cab104359bb0ea56c8f7202e`
- Live `health/latest.json` commit SHA: `7aed3bd45e100e96ccc77fdeceba0f4c35d80de5`
- Live `health/latest.json` last commit timestamp: `2026-08-09T09:46:13+08:00`
- Canary SHA-256: `1b7f4628f81dbe0934b58a453c269a443c41a8b9bc838939b70f6cad93c28621`
- Full-probe duration: `80.56 seconds`

## Summary

- Total datasets: **166**
- Approved changes: **258**
- Blockers: **9**
- Pending review: **0**

## Per-status distribution

| Status | Live | Canary | Delta |
|---|---:|---:|---:|
| `aging` | 15 | 35 | +20 |
| `browser_dependent` | 5 | 5 | +0 |
| `degraded` | 0 | 0 | +0 |
| `fresh` | 89 | 66 | -23 |
| `stale` | 55 | 58 | +3 |
| `unknown` | 0 | 0 | +0 |
| `unknown_freshness` | 1 | 1 | +0 |
| `unreachable` | 1 | 1 | +0 |

## Status flips

| Classification | Dataset ID | Field | Before | After | Reason |
|---|---|---|---|---|---|
| Approved | `dosm_birth_state` | `status` | `"fresh"` | `"aging"` | freshness-window transition consistent with policy |
| Approved | `dosm_cpi_core_inflation` | `status` | `"fresh"` | `"aging"` | freshness-window transition consistent with policy |
| Approved | `dosm_cpi_inflation` | `status` | `"fresh"` | `"aging"` | freshness-window transition consistent with policy |
| Approved | `dosm_cpi_state` | `status` | `"fresh"` | `"aging"` | freshness-window transition consistent with policy |
| Approved | `dosm_cpi_state_inflation` | `status` | `"fresh"` | `"aging"` | freshness-window transition consistent with policy |
| Approved | `dosm_death_district_sex` | `status` | `"fresh"` | `"aging"` | freshness-window transition consistent with policy |
| Approved | `dosm_death_maternal` | `status` | `"fresh"` | `"aging"` | freshness-window transition consistent with policy |
| Approved | `dosm_death_maternal_state` | `status` | `"fresh"` | `"aging"` | freshness-window transition consistent with policy |
| Approved | `dosm_death_state` | `status` | `"fresh"` | `"aging"` | freshness-window transition consistent with policy |
| Approved | `dosm_fertility` | `status` | `"fresh"` | `"aging"` | freshness-window transition consistent with policy |
| Approved | `dosm_gdp_annual_nominal_supply` | `status` | `"fresh"` | `"aging"` | freshness-window transition consistent with policy |
| Approved | `dosm_gdp_annual_real_supply` | `status` | `"fresh"` | `"aging"` | freshness-window transition consistent with policy |
| Approved | `dosm_gdp_gni_annual_nominal` | `status` | `"fresh"` | `"aging"` | freshness-window transition consistent with policy |
| Approved | `dosm_gdp_qtr_nominal` | `status` | `"fresh"` | `"aging"` | freshness-window transition consistent with policy |
| Approved | `dosm_gdp_qtr_real` | `status` | `"fresh"` | `"aging"` | freshness-window transition consistent with policy |
| Approved | `dosm_gdp_qtr_real_sa` | `status` | `"fresh"` | `"aging"` | freshness-window transition consistent with policy |
| Approved | `dosm_gdp_state_real_supply` | `status` | `"fresh"` | `"aging"` | freshness-window transition consistent with policy |
| Approved | `dosm_ipi_domestic` | `status` | `"fresh"` | `"stale"` | freshness aged across the policy stale boundary |
| Approved | `dosm_ipi_export` | `status` | `"fresh"` | `"stale"` | freshness aged across the policy stale boundary |
| Approved | `dosm_lfs_month` | `status` | `"fresh"` | `"stale"` | freshness aged across the policy stale boundary |
| Approved | `dosm_population_parlimen` | `status` | `"fresh"` | `"aging"` | freshness-window transition consistent with policy |
| Approved | `dosm_ppi` | `status` | `"fresh"` | `"aging"` | freshness-window transition consistent with policy |
| Approved | `dosm_trade_sitc_1d` | `status` | `"fresh"` | `"aging"` | freshness-window transition consistent with policy |

## Record-count changes

| Classification | Dataset ID | Field | Before | After | Reason |
|---|---|---|---|---|---|
| Approved | `cosmetic_notifications` | `record_count` | `241538` | `241749` | record count changed within the 10% tolerance |
| Approved | `dgm_blood_donations_state` | `record_count` | `488995` | `489060` | record count changed within the 10% tolerance |
| Approved | `dgm_payments_transactions_fpx` | `record_count` | `7221` | `7224` | record count changed within the 10% tolerance |
| Approved | `dgm_pekab40_screenings_state` | `record_count` | `42720` | `42752` | record count changed within the 10% tolerance |
| Blocker | `gtfs_realtime_ktmb` | `record_count` | `9` | `7` | record count changed by more than 10% |
| Approved | `gtfs_realtime_mybas_ipoh` | `record_count` | `20` | `19` | record count changed within the 10% tolerance |
| Approved | `gtfs_realtime_mybas_johor` | `record_count` | `75` | `81` | record count changed within the 10% tolerance |
| Approved | `gtfs_realtime_mybas_kuala_terengganu` | `record_count` | `24` | `25` | record count changed within the 10% tolerance |
| Approved | `gtfs_realtime_mybas_kuching` | `record_count` | `44` | `45` | record count changed within the 10% tolerance |
| Blocker | `gtfs_realtime_mybas_melaka` | `record_count` | `27` | `30` | record count changed by more than 10% |
| Blocker | `gtfs_realtime_mybas_seremban_a` | `record_count` | `20` | `25` | record count changed by more than 10% |
| Blocker | `gtfs_realtime_mybas_seremban_b` | `record_count` | `19` | `23` | record count changed by more than 10% |
| Approved | `gtfs_realtime_prasarana_bus_mrtfeeder` | `record_count` | `100` | `92` | record count changed within the 10% tolerance |
| Approved | `gtfs_realtime_prasarana_bus_penang` | `record_count` | `155` | `162` | record count changed within the 10% tolerance |
| Blocker | `gtfs_static_mybas_alor_setar` | `record_count` | `35388` | `0` | record count changed by more than 10% |
| Approved | `gtfs_static_mybas_ipoh` | `record_count` | `18788` | `18518` | record count changed within the 10% tolerance |
| Blocker | `gtfs_static_mybas_kangar` | `record_count` | `16160` | `0` | record count changed by more than 10% |
| Blocker | `gtfs_static_mybas_kota_bharu` | `record_count` | `47556` | `0` | record count changed by more than 10% |
| Blocker | `gtfs_static_mybas_kuala_terengganu` | `record_count` | `20616` | `0` | record count changed by more than 10% |
| Blocker | `gtfs_static_mybas_kuching` | `record_count` | `17170` | `0` | record count changed by more than 10% |
| Approved | `gtfs_static_mybas_seremban_a` | `record_count` | `16517` | `16057` | record count changed within the 10% tolerance |
| Approved | `gtfs_static_mybas_seremban_b` | `record_count` | `24467` | `23555` | record count changed within the 10% tolerance |
| Approved | `pharmaceutical_products` | `record_count` | `28024` | `28073` | record count changed within the 10% tolerance |
| Approved | `pricecatcher` | `record_count` | `5151` | `5061` | record count changed within the 10% tolerance |
| Approved | `ridership_ktmb_daily` | `record_count` | `8943` | `8948` | record count changed within the 10% tolerance |
| Approved | `ridership_od_ets` | `record_count` | `507504` | `509757` | record count changed within the 10% tolerance |
| Approved | `ridership_od_intercity` | `record_count` | `121386` | `121962` | record count changed within the 10% tolerance |
| Approved | `ridership_od_komuter` | `record_count` | `1132375` | `1135989` | record count changed within the 10% tolerance |
| Approved | `ridership_od_komuter_utara` | `record_count` | `873130` | `877379` | record count changed within the 10% tolerance |
| Approved | `ridership_od_shuttle_tebrau` | `record_count` | `6040` | `6068` | record count changed within the 10% tolerance |

## Schema changes

_None._

## Approved

| Classification | Dataset ID | Field | Before | After | Reason |
|---|---|---|---|---|---|
| Approved | `air_pollution` | `last_checked` | `"2026-08-08T05:49:42Z"` | `"2026-08-09T02:14:33Z"` | full probe advanced the observation timestamp |
| Approved | `bop_balance` | `last_checked` | `"2026-08-08T05:49:42Z"` | `"2026-08-09T02:14:33Z"` | full probe advanced the observation timestamp |
| Approved | `cosmetic_notifications` | `last_checked` | `"2026-08-08T05:49:42Z"` | `"2026-08-09T02:14:33Z"` | full probe advanced the observation timestamp |
| Approved | `cosmetic_notifications` | `record_count` | `241538` | `241749` | record count changed within the 10% tolerance |
| Approved | `cosmetic_notifications_cancelled` | `last_checked` | `"2026-08-08T05:49:42Z"` | `"2026-08-09T02:14:33Z"` | full probe advanced the observation timestamp |
| Approved | `covid_deaths_linelist` | `last_checked` | `"2026-08-08T05:49:42Z"` | `"2026-08-09T02:14:33Z"` | full probe advanced the observation timestamp |
| Approved | `cpi_3d` | `last_checked` | `"2026-08-08T05:49:42Z"` | `"2026-08-09T02:14:33Z"` | full probe advanced the observation timestamp |
| Approved | `cpi_4d` | `last_checked` | `"2026-08-08T05:49:42Z"` | `"2026-08-09T02:14:33Z"` | full probe advanced the observation timestamp |
| Approved | `cpi_5d` | `last_checked` | `"2026-08-08T05:49:42Z"` | `"2026-08-09T02:14:33Z"` | full probe advanced the observation timestamp |
| Approved | `cpi_core` | `last_checked` | `"2026-08-08T05:49:42Z"` | `"2026-08-09T02:14:33Z"` | full probe advanced the observation timestamp |
| Approved | `cpi_core_inflation` | `last_checked` | `"2026-08-08T05:49:42Z"` | `"2026-08-09T02:14:33Z"` | full probe advanced the observation timestamp |
| Approved | `dgm_blood_donations_state` | `last_checked` | `"2026-08-08T07:30:47Z"` | `"2026-08-09T02:14:33Z"` | full probe advanced the observation timestamp |
| Approved | `dgm_blood_donations_state` | `record_count` | `488995` | `489060` | record count changed within the 10% tolerance |
| Approved | `dgm_cellular_subscribers` | `last_checked` | `"2026-08-07T07:25:52Z"` | `"2026-08-09T02:14:33Z"` | full probe advanced the observation timestamp |
| Approved | `dgm_crops_state` | `last_checked` | `"2026-08-07T07:25:52Z"` | `"2026-08-09T02:14:33Z"` | full probe advanced the observation timestamp |
| Approved | `dgm_currency_in_circulation` | `last_checked` | `"2026-08-07T07:25:52Z"` | `"2026-08-09T02:14:33Z"` | full probe advanced the observation timestamp |
| Approved | `dgm_drug_addicts_age` | `last_checked` | `"2026-08-07T07:25:52Z"` | `"2026-08-09T02:14:33Z"` | full probe advanced the observation timestamp |
| Approved | `dgm_electricity_consumption` | `last_checked` | `"2026-08-07T07:25:52Z"` | `"2026-08-09T02:14:33Z"` | full probe advanced the observation timestamp |
| Approved | `dgm_electricity_supply` | `last_checked` | `"2026-08-07T07:25:52Z"` | `"2026-08-09T02:14:33Z"` | full probe advanced the observation timestamp |
| Approved | `dgm_epf_dividend` | `last_checked` | `"2026-08-07T07:25:52Z"` | `"2026-08-09T02:14:33Z"` | full probe advanced the observation timestamp |
| Approved | `dgm_federal_finance_qtr_oe` | `last_checked` | `"2026-08-07T07:25:52Z"` | `"2026-08-09T02:14:33Z"` | full probe advanced the observation timestamp |
| Approved | `dgm_federal_finance_qtr_revenue` | `last_checked` | `"2026-08-07T07:25:52Z"` | `"2026-08-09T02:14:33Z"` | full probe advanced the observation timestamp |
| Approved | `dgm_fish_landings` | `last_checked` | `"2026-08-07T07:25:52Z"` | `"2026-08-09T02:14:33Z"` | full probe advanced the observation timestamp |
| Approved | `dgm_healthcare_staff` | `last_checked` | `"2026-08-07T07:25:52Z"` | `"2026-08-09T02:14:33Z"` | full probe advanced the observation timestamp |
| Approved | `dgm_hospital_beds` | `last_checked` | `"2026-08-07T07:25:52Z"` | `"2026-08-09T02:14:33Z"` | full probe advanced the observation timestamp |
| Approved | `dgm_infant_immunisation` | `last_checked` | `"2026-08-07T07:25:52Z"` | `"2026-08-09T02:14:33Z"` | full probe advanced the observation timestamp |
| Approved | `dgm_interest_rates` | `last_checked` | `"2026-08-07T07:25:52Z"` | `"2026-08-09T02:14:33Z"` | full probe advanced the observation timestamp |
| Approved | `dgm_interest_rates_annual` | `last_checked` | `"2026-08-07T07:25:52Z"` | `"2026-08-09T02:14:33Z"` | full probe advanced the observation timestamp |
| Approved | `dgm_ktmb_ridership_monthly` | `last_checked` | `"2026-08-07T07:25:52Z"` | `"2026-08-09T02:14:33Z"` | full probe advanced the observation timestamp |
| Approved | `dgm_local_authority_sex` | `last_checked` | `"2026-08-07T07:25:52Z"` | `"2026-08-09T02:14:33Z"` | full probe advanced the observation timestamp |
| Approved | `dgm_mnha` | `last_checked` | `"2026-08-07T07:25:52Z"` | `"2026-08-09T02:14:33Z"` | full probe advanced the observation timestamp |
| Approved | `dgm_money_aggregates` | `last_checked` | `"2026-08-07T07:25:52Z"` | `"2026-08-09T02:14:33Z"` | full probe advanced the observation timestamp |
| Approved | `dgm_parliament_sex` | `last_checked` | `"2026-08-07T07:25:52Z"` | `"2026-08-09T02:14:33Z"` | full probe advanced the observation timestamp |
| Approved | `dgm_payments_channels` | `last_checked` | `"2026-08-07T07:25:52Z"` | `"2026-08-09T02:14:33Z"` | full probe advanced the observation timestamp |
| Approved | `dgm_payments_instruments` | `last_checked` | `"2026-08-07T07:25:52Z"` | `"2026-08-09T02:14:33Z"` | full probe advanced the observation timestamp |
| Approved | `dgm_payments_systems` | `last_checked` | `"2026-08-07T07:25:52Z"` | `"2026-08-09T02:14:33Z"` | full probe advanced the observation timestamp |
| Approved | `dgm_payments_transactions_fpx` | `last_checked` | `"2026-08-08T07:30:47Z"` | `"2026-08-09T02:14:33Z"` | full probe advanced the observation timestamp |
| Approved | `dgm_payments_transactions_fpx` | `record_count` | `7221` | `7224` | record count changed within the 10% tolerance |
| Approved | `dgm_pekab40_screenings_state` | `last_checked` | `"2026-08-08T07:30:47Z"` | `"2026-08-09T02:14:33Z"` | full probe advanced the observation timestamp |
| Approved | `dgm_pekab40_screenings_state` | `record_count` | `42720` | `42752` | record count changed within the 10% tolerance |
| Approved | `dgm_prisoners_state` | `last_checked` | `"2026-08-07T07:25:52Z"` | `"2026-08-09T02:14:33Z"` | full probe advanced the observation timestamp |
| Approved | `dgm_ridership_headline` | `last_checked` | `"2026-08-08T07:30:47Z"` | `"2026-08-09T02:14:33Z"` | full probe advanced the observation timestamp |
| Approved | `dgm_schools_district` | `last_checked` | `"2026-08-07T07:25:52Z"` | `"2026-08-09T02:14:33Z"` | full probe advanced the observation timestamp |
| Approved | `dgm_state_finance_expenditure` | `last_checked` | `"2026-08-07T07:25:52Z"` | `"2026-08-09T02:14:33Z"` | full probe advanced the observation timestamp |
| Approved | `dgm_std_state` | `last_checked` | `"2026-08-07T07:25:52Z"` | `"2026-08-09T02:14:33Z"` | full probe advanced the observation timestamp |
| Approved | `dgm_vehicle_registrations_type_fuel` | `last_checked` | `"2026-08-07T07:25:52Z"` | `"2026-08-09T02:14:33Z"` | full probe advanced the observation timestamp |
| Approved | `dgm_water_access` | `last_checked` | `"2026-08-07T07:25:52Z"` | `"2026-08-09T02:14:33Z"` | full probe advanced the observation timestamp |
| Approved | `dgm_water_consumption` | `last_checked` | `"2026-08-07T07:25:52Z"` | `"2026-08-09T02:14:33Z"` | full probe advanced the observation timestamp |
| Approved | `dgm_water_production` | `last_checked` | `"2026-08-07T07:25:52Z"` | `"2026-08-09T02:14:33Z"` | full probe advanced the observation timestamp |
| Approved | `doe_apims` | `last_checked` | `"2026-08-09T01:45:54Z"` | `"2026-08-09T02:14:33Z"` | full probe advanced the observation timestamp |
| Approved | `doe_mqims` | `last_checked` | `"2026-08-07T07:25:52Z"` | `"2026-08-09T02:14:33Z"` | full probe advanced the observation timestamp |
| Approved | `doe_mqims` | `content_freshness_date` | `"2026-08-07"` | `"2026-08-08"` | publisher freshness date advanced |
| Approved | `doe_rqims` | `last_checked` | `"2026-08-09T01:45:54Z"` | `"2026-08-09T02:14:33Z"` | full probe advanced the observation timestamp |
| Approved | `dosm_birth_state` | `status` | `"fresh"` | `"aging"` | freshness-window transition consistent with policy |
| Approved | `dosm_birth_state` | `last_checked` | `"2026-08-07T07:25:52Z"` | `"2026-08-09T02:14:33Z"` | full probe advanced the observation timestamp |
| Approved | `dosm_birth_state` | `content_freshness_date` | `null` | `"2024-01-01"` | full probe supplied new freshness evidence |
| Approved | `dosm_cpi_core_inflation` | `status` | `"fresh"` | `"aging"` | freshness-window transition consistent with policy |
| Approved | `dosm_cpi_core_inflation` | `last_checked` | `"2026-08-07T07:25:52Z"` | `"2026-08-09T02:14:33Z"` | full probe advanced the observation timestamp |
| Approved | `dosm_cpi_core_inflation` | `content_freshness_date` | `null` | `"2026-06-01"` | full probe supplied new freshness evidence |
| Approved | `dosm_cpi_inflation` | `status` | `"fresh"` | `"aging"` | freshness-window transition consistent with policy |
| Approved | `dosm_cpi_inflation` | `last_checked` | `"2026-08-07T07:25:52Z"` | `"2026-08-09T02:14:33Z"` | full probe advanced the observation timestamp |
| Approved | `dosm_cpi_inflation` | `content_freshness_date` | `null` | `"2026-06-01"` | full probe supplied new freshness evidence |
| Approved | `dosm_cpi_state` | `status` | `"fresh"` | `"aging"` | freshness-window transition consistent with policy |
| Approved | `dosm_cpi_state` | `last_checked` | `"2026-08-07T07:25:52Z"` | `"2026-08-09T02:14:33Z"` | full probe advanced the observation timestamp |
| Approved | `dosm_cpi_state` | `content_freshness_date` | `null` | `"2026-06-01"` | full probe supplied new freshness evidence |
| Approved | `dosm_cpi_state_inflation` | `status` | `"fresh"` | `"aging"` | freshness-window transition consistent with policy |
| Approved | `dosm_cpi_state_inflation` | `last_checked` | `"2026-08-07T07:25:52Z"` | `"2026-08-09T02:14:33Z"` | full probe advanced the observation timestamp |
| Approved | `dosm_cpi_state_inflation` | `content_freshness_date` | `null` | `"2026-06-01"` | full probe supplied new freshness evidence |
| Approved | `dosm_crime_district` | `last_checked` | `"2026-08-07T07:25:52Z"` | `"2026-08-09T02:14:33Z"` | full probe advanced the observation timestamp |
| Approved | `dosm_death_district_sex` | `status` | `"fresh"` | `"aging"` | freshness-window transition consistent with policy |
| Approved | `dosm_death_district_sex` | `last_checked` | `"2026-08-07T07:25:52Z"` | `"2026-08-09T02:14:33Z"` | full probe advanced the observation timestamp |
| Approved | `dosm_death_district_sex` | `content_freshness_date` | `null` | `"2024-01-01"` | full probe supplied new freshness evidence |
| Approved | `dosm_death_maternal` | `status` | `"fresh"` | `"aging"` | freshness-window transition consistent with policy |
| Approved | `dosm_death_maternal` | `last_checked` | `"2026-08-07T07:25:52Z"` | `"2026-08-09T02:14:33Z"` | full probe advanced the observation timestamp |
| Approved | `dosm_death_maternal` | `content_freshness_date` | `null` | `"2024-01-01"` | full probe supplied new freshness evidence |
| Approved | `dosm_death_maternal_state` | `status` | `"fresh"` | `"aging"` | freshness-window transition consistent with policy |
| Approved | `dosm_death_maternal_state` | `last_checked` | `"2026-08-07T07:25:52Z"` | `"2026-08-09T02:14:33Z"` | full probe advanced the observation timestamp |
| Approved | `dosm_death_maternal_state` | `content_freshness_date` | `null` | `"2024-01-01"` | full probe supplied new freshness evidence |
| Approved | `dosm_death_state` | `status` | `"fresh"` | `"aging"` | freshness-window transition consistent with policy |
| Approved | `dosm_death_state` | `last_checked` | `"2026-08-07T07:25:52Z"` | `"2026-08-09T02:14:33Z"` | full probe advanced the observation timestamp |
| Approved | `dosm_death_state` | `content_freshness_date` | `null` | `"2024-01-01"` | full probe supplied new freshness evidence |
| Approved | `dosm_employment_sector` | `last_checked` | `"2026-08-07T07:25:52Z"` | `"2026-08-09T02:14:33Z"` | full probe advanced the observation timestamp |
| Approved | `dosm_fertility` | `status` | `"fresh"` | `"aging"` | freshness-window transition consistent with policy |
| Approved | `dosm_fertility` | `last_checked` | `"2026-08-07T07:25:52Z"` | `"2026-08-09T02:14:33Z"` | full probe advanced the observation timestamp |
| Approved | `dosm_fertility` | `content_freshness_date` | `null` | `"2024-01-01"` | full probe supplied new freshness evidence |
| Approved | `dosm_gdp_annual_nominal_supply` | `status` | `"fresh"` | `"aging"` | freshness-window transition consistent with policy |
| Approved | `dosm_gdp_annual_nominal_supply` | `last_checked` | `"2026-08-07T07:25:52Z"` | `"2026-08-09T02:14:33Z"` | full probe advanced the observation timestamp |
| Approved | `dosm_gdp_annual_nominal_supply` | `content_freshness_date` | `null` | `"2025-01-01"` | full probe supplied new freshness evidence |
| Approved | `dosm_gdp_annual_real_supply` | `status` | `"fresh"` | `"aging"` | freshness-window transition consistent with policy |
| Approved | `dosm_gdp_annual_real_supply` | `last_checked` | `"2026-08-07T07:25:52Z"` | `"2026-08-09T02:14:33Z"` | full probe advanced the observation timestamp |
| Approved | `dosm_gdp_annual_real_supply` | `content_freshness_date` | `null` | `"2025-01-01"` | full probe supplied new freshness evidence |
| Approved | `dosm_gdp_gni_annual_nominal` | `status` | `"fresh"` | `"aging"` | freshness-window transition consistent with policy |
| Approved | `dosm_gdp_gni_annual_nominal` | `last_checked` | `"2026-08-07T07:25:52Z"` | `"2026-08-09T02:14:33Z"` | full probe advanced the observation timestamp |
| Approved | `dosm_gdp_gni_annual_nominal` | `content_freshness_date` | `null` | `"2025-01-01"` | full probe supplied new freshness evidence |
| Approved | `dosm_gdp_qtr_nominal` | `status` | `"fresh"` | `"aging"` | freshness-window transition consistent with policy |
| Approved | `dosm_gdp_qtr_nominal` | `last_checked` | `"2026-08-07T07:25:52Z"` | `"2026-08-09T02:14:33Z"` | full probe advanced the observation timestamp |
| Approved | `dosm_gdp_qtr_nominal` | `content_freshness_date` | `null` | `"2026-01-01"` | full probe supplied new freshness evidence |
| Approved | `dosm_gdp_qtr_real` | `status` | `"fresh"` | `"aging"` | freshness-window transition consistent with policy |
| Approved | `dosm_gdp_qtr_real` | `last_checked` | `"2026-08-07T07:25:52Z"` | `"2026-08-09T02:14:33Z"` | full probe advanced the observation timestamp |
| Approved | `dosm_gdp_qtr_real` | `content_freshness_date` | `null` | `"2026-01-01"` | full probe supplied new freshness evidence |
| Approved | `dosm_gdp_qtr_real_sa` | `status` | `"fresh"` | `"aging"` | freshness-window transition consistent with policy |
| Approved | `dosm_gdp_qtr_real_sa` | `last_checked` | `"2026-08-07T07:25:52Z"` | `"2026-08-09T02:14:33Z"` | full probe advanced the observation timestamp |
| Approved | `dosm_gdp_qtr_real_sa` | `content_freshness_date` | `null` | `"2026-01-01"` | full probe supplied new freshness evidence |
| Approved | `dosm_gdp_state_real_supply` | `status` | `"fresh"` | `"aging"` | freshness-window transition consistent with policy |
| Approved | `dosm_gdp_state_real_supply` | `last_checked` | `"2026-08-07T07:25:52Z"` | `"2026-08-09T02:14:33Z"` | full probe advanced the observation timestamp |
| Approved | `dosm_gdp_state_real_supply` | `content_freshness_date` | `null` | `"2025-01-01"` | full probe supplied new freshness evidence |
| Approved | `dosm_hh_expenditure_dun` | `last_checked` | `"2026-08-07T07:25:52Z"` | `"2026-08-09T02:14:33Z"` | full probe advanced the observation timestamp |
| Approved | `dosm_hh_expenditure_dun` | `content_freshness_date` | `null` | `"2024-01-01"` | full probe supplied new freshness evidence |
| Approved | `dosm_hh_expenditure_parlimen` | `last_checked` | `"2026-08-07T07:25:52Z"` | `"2026-08-09T02:14:33Z"` | full probe advanced the observation timestamp |
| Approved | `dosm_hh_expenditure_parlimen` | `content_freshness_date` | `null` | `"2024-01-01"` | full probe supplied new freshness evidence |
| Approved | `dosm_hh_income` | `last_checked` | `"2026-08-07T07:25:52Z"` | `"2026-08-09T02:14:33Z"` | full probe advanced the observation timestamp |
| Approved | `dosm_hh_income` | `content_freshness_date` | `null` | `"2024-01-01"` | full probe supplied new freshness evidence |
| Approved | `dosm_hh_income_district` | `last_checked` | `"2026-08-07T07:25:52Z"` | `"2026-08-09T02:14:33Z"` | full probe advanced the observation timestamp |
| Approved | `dosm_hh_income_district` | `content_freshness_date` | `null` | `"2024-01-01"` | full probe supplied new freshness evidence |
| Approved | `dosm_hh_income_state` | `last_checked` | `"2026-08-07T07:25:52Z"` | `"2026-08-09T02:14:33Z"` | full probe advanced the observation timestamp |
| Approved | `dosm_hh_income_state` | `content_freshness_date` | `null` | `"2024-01-01"` | full probe supplied new freshness evidence |
| Approved | `dosm_hh_inequality` | `last_checked` | `"2026-08-07T07:25:52Z"` | `"2026-08-09T02:14:33Z"` | full probe advanced the observation timestamp |
| Approved | `dosm_hh_inequality` | `content_freshness_date` | `null` | `"2024-01-01"` | full probe supplied new freshness evidence |
| Approved | `dosm_hh_inequality_district` | `last_checked` | `"2026-08-07T07:25:52Z"` | `"2026-08-09T02:14:33Z"` | full probe advanced the observation timestamp |
| Approved | `dosm_hh_inequality_district` | `content_freshness_date` | `null` | `"2024-01-01"` | full probe supplied new freshness evidence |
| Approved | `dosm_hh_inequality_state` | `last_checked` | `"2026-08-07T07:25:52Z"` | `"2026-08-09T02:14:33Z"` | full probe advanced the observation timestamp |
| Approved | `dosm_hh_inequality_state` | `content_freshness_date` | `null` | `"2024-01-01"` | full probe supplied new freshness evidence |
| Approved | `dosm_hh_poverty` | `last_checked` | `"2026-08-07T07:25:52Z"` | `"2026-08-09T02:14:33Z"` | full probe advanced the observation timestamp |
| Approved | `dosm_hh_poverty` | `content_freshness_date` | `null` | `"2024-01-01"` | full probe supplied new freshness evidence |
| Approved | `dosm_hh_poverty_district` | `last_checked` | `"2026-08-07T07:25:52Z"` | `"2026-08-09T02:14:33Z"` | full probe advanced the observation timestamp |
| Approved | `dosm_hh_poverty_district` | `content_freshness_date` | `null` | `"2024-01-01"` | full probe supplied new freshness evidence |
| Approved | `dosm_hh_poverty_state` | `last_checked` | `"2026-08-07T07:25:52Z"` | `"2026-08-09T02:14:33Z"` | full probe advanced the observation timestamp |
| Approved | `dosm_hh_poverty_state` | `content_freshness_date` | `null` | `"2024-01-01"` | full probe supplied new freshness evidence |
| Approved | `dosm_ipi_domestic` | `status` | `"fresh"` | `"stale"` | freshness aged across the policy stale boundary |
| Approved | `dosm_ipi_domestic` | `last_checked` | `"2026-08-07T07:25:52Z"` | `"2026-08-09T02:14:33Z"` | full probe advanced the observation timestamp |
| Approved | `dosm_ipi_domestic` | `content_freshness_date` | `null` | `"2026-05-01"` | full probe supplied new freshness evidence |
| Approved | `dosm_ipi_export` | `status` | `"fresh"` | `"stale"` | freshness aged across the policy stale boundary |
| Approved | `dosm_ipi_export` | `last_checked` | `"2026-08-07T07:25:52Z"` | `"2026-08-09T02:14:33Z"` | full probe advanced the observation timestamp |
| Approved | `dosm_ipi_export` | `content_freshness_date` | `null` | `"2026-05-01"` | full probe supplied new freshness evidence |
| Approved | `dosm_lfs_month` | `status` | `"fresh"` | `"stale"` | freshness aged across the policy stale boundary |
| Approved | `dosm_lfs_month` | `last_checked` | `"2026-08-07T07:25:52Z"` | `"2026-08-09T02:14:33Z"` | full probe advanced the observation timestamp |
| Approved | `dosm_lfs_month` | `content_freshness_date` | `null` | `"2026-05-01"` | full probe supplied new freshness evidence |
| Approved | `dosm_lfs_qtr` | `last_checked` | `"2026-08-07T07:25:52Z"` | `"2026-08-09T02:14:33Z"` | full probe advanced the observation timestamp |
| Approved | `dosm_lfs_qtr_state` | `last_checked` | `"2026-08-07T07:25:52Z"` | `"2026-08-09T02:14:33Z"` | full probe advanced the observation timestamp |
| Approved | `dosm_lfs_year` | `last_checked` | `"2026-08-07T07:25:52Z"` | `"2026-08-09T02:14:33Z"` | full probe advanced the observation timestamp |
| Approved | `dosm_marriages_state` | `last_checked` | `"2026-08-07T07:25:52Z"` | `"2026-08-09T02:14:33Z"` | full probe advanced the observation timestamp |
| Approved | `dosm_marriages_state_age` | `last_checked` | `"2026-08-07T07:25:52Z"` | `"2026-08-09T02:14:33Z"` | full probe advanced the observation timestamp |
| Approved | `dosm_population_malaysia` | `last_checked` | `"2026-08-07T07:25:52Z"` | `"2026-08-09T02:14:33Z"` | full probe advanced the observation timestamp |
| Approved | `dosm_population_malaysia` | `content_freshness_date` | `null` | `"2026-01-01"` | full probe supplied new freshness evidence |
| Approved | `dosm_population_parlimen` | `status` | `"fresh"` | `"aging"` | freshness-window transition consistent with policy |
| Approved | `dosm_population_parlimen` | `last_checked` | `"2026-08-07T07:25:52Z"` | `"2026-08-09T02:14:33Z"` | full probe advanced the observation timestamp |
| Approved | `dosm_population_parlimen` | `content_freshness_date` | `null` | `"2024-01-01"` | full probe supplied new freshness evidence |
| Approved | `dosm_population_state` | `last_checked` | `"2026-08-07T07:25:52Z"` | `"2026-08-09T02:14:33Z"` | full probe advanced the observation timestamp |
| Approved | `dosm_population_state` | `content_freshness_date` | `null` | `"2026-01-01"` | full probe supplied new freshness evidence |
| Approved | `dosm_ppi` | `status` | `"fresh"` | `"aging"` | freshness-window transition consistent with policy |
| Approved | `dosm_ppi` | `last_checked` | `"2026-08-07T07:25:52Z"` | `"2026-08-09T02:14:33Z"` | full probe advanced the observation timestamp |
| Approved | `dosm_ppi` | `content_freshness_date` | `null` | `"2026-06-01"` | full probe supplied new freshness evidence |
| Approved | `dosm_trade_enduse_bec` | `last_checked` | `"2026-08-07T07:25:52Z"` | `"2026-08-09T02:14:33Z"` | full probe advanced the observation timestamp |
| Approved | `dosm_trade_headline` | `last_checked` | `"2026-08-07T07:25:52Z"` | `"2026-08-09T02:14:33Z"` | full probe advanced the observation timestamp |
| Approved | `dosm_trade_sitc_1d` | `status` | `"fresh"` | `"aging"` | freshness-window transition consistent with policy |
| Approved | `dosm_trade_sitc_1d` | `last_checked` | `"2026-08-07T07:25:52Z"` | `"2026-08-09T02:14:33Z"` | full probe advanced the observation timestamp |
| Approved | `dosm_trade_sitc_1d` | `content_freshness_date` | `null` | `"2026-06-01"` | full probe supplied new freshness evidence |
| Approved | `eperolehan-diklankan` | `last_checked` | `"2026-08-09T01:45:54Z"` | `"2026-08-09T02:14:33Z"` | full probe advanced the observation timestamp |
| Approved | `exchangerates` | `last_checked` | `"2026-08-08T05:49:42Z"` | `"2026-08-09T02:14:33Z"` | full probe advanced the observation timestamp |
| Approved | `exchangerates_daily_0900` | `last_checked` | `"2026-08-09T01:45:54Z"` | `"2026-08-09T02:14:33Z"` | full probe advanced the observation timestamp |
| Approved | `exchangerates_daily_1130` | `last_checked` | `"2026-08-09T01:45:54Z"` | `"2026-08-09T02:14:33Z"` | full probe advanced the observation timestamp |
| Approved | `exchangerates_daily_1200` | `last_checked` | `"2026-08-09T01:45:54Z"` | `"2026-08-09T02:14:33Z"` | full probe advanced the observation timestamp |
| Approved | `exchangerates_daily_1700` | `last_checked` | `"2026-08-09T01:45:54Z"` | `"2026-08-09T02:14:33Z"` | full probe advanced the observation timestamp |
| Approved | `fdi_flows` | `last_checked` | `"2026-08-08T05:49:42Z"` | `"2026-08-09T02:14:33Z"` | full probe advanced the observation timestamp |
| Approved | `federal_finance_qtr_de` | `last_checked` | `"2026-08-08T05:49:42Z"` | `"2026-08-09T02:14:33Z"` | full probe advanced the observation timestamp |
| Approved | `federal_finance_year_revenue` | `last_checked` | `"2026-08-08T05:49:42Z"` | `"2026-08-09T02:14:33Z"` | full probe advanced the observation timestamp |
| Approved | `fuelprice` | `last_checked` | `"2026-08-07T07:25:52Z"` | `"2026-08-09T02:14:33Z"` | full probe advanced the observation timestamp |
| Approved | `ghg_emissions` | `last_checked` | `"2026-08-08T05:49:42Z"` | `"2026-08-09T02:14:33Z"` | full probe advanced the observation timestamp |
| Approved | `gtfs_realtime_ktmb` | `last_checked` | `"2026-08-09T01:45:54Z"` | `"2026-08-09T02:14:33Z"` | full probe advanced the observation timestamp |
| Approved | `gtfs_realtime_mybas_alor_setar` | `last_checked` | `"2026-08-09T01:45:54Z"` | `"2026-08-09T02:14:33Z"` | full probe advanced the observation timestamp |
| Approved | `gtfs_realtime_mybas_ipoh` | `last_checked` | `"2026-08-09T01:45:54Z"` | `"2026-08-09T02:14:33Z"` | full probe advanced the observation timestamp |
| Approved | `gtfs_realtime_mybas_ipoh` | `record_count` | `20` | `19` | record count changed within the 10% tolerance |
| Approved | `gtfs_realtime_mybas_johor` | `last_checked` | `"2026-08-09T01:45:54Z"` | `"2026-08-09T02:14:33Z"` | full probe advanced the observation timestamp |
| Approved | `gtfs_realtime_mybas_johor` | `record_count` | `75` | `81` | record count changed within the 10% tolerance |
| Approved | `gtfs_realtime_mybas_kangar` | `last_checked` | `"2026-08-09T01:45:54Z"` | `"2026-08-09T02:14:33Z"` | full probe advanced the observation timestamp |
| Approved | `gtfs_realtime_mybas_kota_bharu` | `last_checked` | `"2026-08-09T01:45:54Z"` | `"2026-08-09T02:14:33Z"` | full probe advanced the observation timestamp |
| Approved | `gtfs_realtime_mybas_kuala_terengganu` | `last_checked` | `"2026-08-09T01:45:54Z"` | `"2026-08-09T02:14:33Z"` | full probe advanced the observation timestamp |
| Approved | `gtfs_realtime_mybas_kuala_terengganu` | `record_count` | `24` | `25` | record count changed within the 10% tolerance |
| Approved | `gtfs_realtime_mybas_kuching` | `last_checked` | `"2026-08-09T01:45:54Z"` | `"2026-08-09T02:14:33Z"` | full probe advanced the observation timestamp |
| Approved | `gtfs_realtime_mybas_kuching` | `record_count` | `44` | `45` | record count changed within the 10% tolerance |
| Approved | `gtfs_realtime_mybas_melaka` | `last_checked` | `"2026-08-09T01:45:54Z"` | `"2026-08-09T02:14:33Z"` | full probe advanced the observation timestamp |
| Approved | `gtfs_realtime_mybas_seremban_a` | `last_checked` | `"2026-08-09T01:45:54Z"` | `"2026-08-09T02:14:33Z"` | full probe advanced the observation timestamp |
| Approved | `gtfs_realtime_mybas_seremban_b` | `last_checked` | `"2026-08-09T01:45:54Z"` | `"2026-08-09T02:14:33Z"` | full probe advanced the observation timestamp |
| Approved | `gtfs_realtime_prasarana_bus_kl` | `last_checked` | `"2026-08-09T01:45:54Z"` | `"2026-08-09T02:14:33Z"` | full probe advanced the observation timestamp |
| Approved | `gtfs_realtime_prasarana_bus_mrtfeeder` | `last_checked` | `"2026-08-09T01:45:54Z"` | `"2026-08-09T02:14:33Z"` | full probe advanced the observation timestamp |
| Approved | `gtfs_realtime_prasarana_bus_mrtfeeder` | `record_count` | `100` | `92` | record count changed within the 10% tolerance |
| Approved | `gtfs_realtime_prasarana_bus_penang` | `last_checked` | `"2026-08-09T01:45:54Z"` | `"2026-08-09T02:14:33Z"` | full probe advanced the observation timestamp |
| Approved | `gtfs_realtime_prasarana_bus_penang` | `record_count` | `155` | `162` | record count changed within the 10% tolerance |
| Approved | `gtfs_static_ktmb` | `last_checked` | `"2026-08-08T07:30:47Z"` | `"2026-08-09T02:14:33Z"` | full probe advanced the observation timestamp |
| Approved | `gtfs_static_ktmb` | `content_freshness_date` | `"2026-08-08"` | `"2026-08-09"` | publisher freshness date advanced |
| Approved | `gtfs_static_mybas_alor_setar` | `last_checked` | `"2026-08-07T07:25:52Z"` | `"2026-08-09T02:14:33Z"` | full probe advanced the observation timestamp |
| Approved | `gtfs_static_mybas_ipoh` | `last_checked` | `"2026-08-07T07:25:52Z"` | `"2026-08-09T02:14:33Z"` | full probe advanced the observation timestamp |
| Approved | `gtfs_static_mybas_ipoh` | `content_freshness_date` | `"2026-08-06"` | `"2026-08-08"` | publisher freshness date advanced |
| Approved | `gtfs_static_mybas_ipoh` | `record_count` | `18788` | `18518` | record count changed within the 10% tolerance |
| Approved | `gtfs_static_mybas_johor` | `last_checked` | `"2026-08-07T07:25:52Z"` | `"2026-08-09T02:14:33Z"` | full probe advanced the observation timestamp |
| Approved | `gtfs_static_mybas_kangar` | `last_checked` | `"2026-08-07T07:25:52Z"` | `"2026-08-09T02:14:33Z"` | full probe advanced the observation timestamp |
| Approved | `gtfs_static_mybas_kota_bharu` | `last_checked` | `"2026-08-07T07:25:52Z"` | `"2026-08-09T02:14:33Z"` | full probe advanced the observation timestamp |
| Approved | `gtfs_static_mybas_kuala_terengganu` | `last_checked` | `"2026-08-07T07:25:52Z"` | `"2026-08-09T02:14:33Z"` | full probe advanced the observation timestamp |
| Approved | `gtfs_static_mybas_kuching` | `last_checked` | `"2026-08-07T07:25:52Z"` | `"2026-08-09T02:14:33Z"` | full probe advanced the observation timestamp |
| Approved | `gtfs_static_mybas_melaka` | `last_checked` | `"2026-08-07T07:25:52Z"` | `"2026-08-09T02:14:33Z"` | full probe advanced the observation timestamp |
| Approved | `gtfs_static_mybas_seremban_a` | `last_checked` | `"2026-08-07T07:25:52Z"` | `"2026-08-09T02:14:33Z"` | full probe advanced the observation timestamp |
| Approved | `gtfs_static_mybas_seremban_a` | `content_freshness_date` | `"2026-08-06"` | `"2026-08-08"` | publisher freshness date advanced |
| Approved | `gtfs_static_mybas_seremban_a` | `record_count` | `16517` | `16057` | record count changed within the 10% tolerance |
| Approved | `gtfs_static_mybas_seremban_b` | `last_checked` | `"2026-08-07T07:25:52Z"` | `"2026-08-09T02:14:33Z"` | full probe advanced the observation timestamp |
| Approved | `gtfs_static_mybas_seremban_b` | `content_freshness_date` | `"2026-08-06"` | `"2026-08-08"` | publisher freshness date advanced |
| Approved | `gtfs_static_mybas_seremban_b` | `record_count` | `24467` | `23555` | record count changed within the 10% tolerance |
| Approved | `gtfs_static_prasarana_bus_kl` | `last_checked` | `"2026-08-07T07:25:52Z"` | `"2026-08-09T02:14:33Z"` | full probe advanced the observation timestamp |
| Approved | `gtfs_static_prasarana_bus_kuantan` | `last_checked` | `"2026-08-07T07:25:52Z"` | `"2026-08-09T02:14:33Z"` | full probe advanced the observation timestamp |
| Approved | `gtfs_static_prasarana_bus_mrtfeeder` | `last_checked` | `"2026-08-07T07:25:52Z"` | `"2026-08-09T02:14:33Z"` | full probe advanced the observation timestamp |
| Approved | `gtfs_static_prasarana_bus_penang` | `last_checked` | `"2026-08-07T07:25:52Z"` | `"2026-08-09T02:14:33Z"` | full probe advanced the observation timestamp |
| Approved | `gtfs_static_prasarana_rail_kl` | `last_checked` | `"2026-08-07T07:25:52Z"` | `"2026-08-09T02:14:33Z"` | full probe advanced the observation timestamp |
| Approved | `hospital_beds` | `last_checked` | `"2026-08-08T05:49:42Z"` | `"2026-08-09T02:14:33Z"` | full probe advanced the observation timestamp |
| Approved | `interestrates` | `last_checked` | `"2026-08-08T05:49:42Z"` | `"2026-08-09T02:14:33Z"` | full probe advanced the observation timestamp |
| Approved | `ipi_2d` | `last_checked` | `"2026-08-08T05:49:42Z"` | `"2026-08-09T02:14:33Z"` | full probe advanced the observation timestamp |
| Approved | `ipi_3d` | `last_checked` | `"2026-08-08T05:49:42Z"` | `"2026-08-09T02:14:33Z"` | full probe advanced the observation timestamp |
| Approved | `ipi_5d` | `last_checked` | `"2026-08-08T05:49:42Z"` | `"2026-08-09T02:14:33Z"` | full probe advanced the observation timestamp |
| Approved | `ipi_domestic` | `last_checked` | `"2026-08-08T05:49:42Z"` | `"2026-08-09T02:14:33Z"` | full probe advanced the observation timestamp |
| Approved | `ipi_export` | `last_checked` | `"2026-08-08T05:49:42Z"` | `"2026-08-09T02:14:33Z"` | full probe advanced the observation timestamp |
| Approved | `kkm_idengue` | `last_checked` | `"2026-08-08T07:30:47Z"` | `"2026-08-09T02:14:33Z"` | full probe advanced the observation timestamp |
| Approved | `met_weather` | `last_checked` | `"2026-08-08T07:30:47Z"` | `"2026-08-09T02:14:33Z"` | full probe advanced the observation timestamp |
| Approved | `met_weather` | `content_freshness_date` | `"2026-08-08"` | `"2026-08-09"` | publisher freshness date advanced |
| Approved | `monetary_aggregates` | `last_checked` | `"2026-08-08T05:49:42Z"` | `"2026-08-09T02:14:33Z"` | full probe advanced the observation timestamp |
| Approved | `payment_channels` | `last_checked` | `"2026-08-08T05:49:42Z"` | `"2026-08-09T02:14:33Z"` | full probe advanced the observation timestamp |
| Approved | `payment_instruments` | `last_checked` | `"2026-08-08T05:49:42Z"` | `"2026-08-09T02:14:33Z"` | full probe advanced the observation timestamp |
| Approved | `payment_systems` | `last_checked` | `"2026-08-08T05:49:42Z"` | `"2026-08-09T02:14:33Z"` | full probe advanced the observation timestamp |
| Approved | `pharmaceutical_importers` | `last_checked` | `"2026-08-08T05:49:42Z"` | `"2026-08-09T02:14:33Z"` | full probe advanced the observation timestamp |
| Approved | `pharmaceutical_manufacturers` | `last_checked` | `"2026-08-08T05:49:42Z"` | `"2026-08-09T02:14:33Z"` | full probe advanced the observation timestamp |
| Approved | `pharmaceutical_products` | `last_checked` | `"2026-08-08T05:49:42Z"` | `"2026-08-09T02:14:33Z"` | full probe advanced the observation timestamp |
| Approved | `pharmaceutical_products` | `record_count` | `28024` | `28073` | record count changed within the 10% tolerance |
| Approved | `pharmaceutical_products_cancelled` | `last_checked` | `"2026-08-08T05:49:42Z"` | `"2026-08-09T02:14:33Z"` | full probe advanced the observation timestamp |
| Approved | `pharmaceutical_wholesalers` | `last_checked` | `"2026-08-08T05:49:42Z"` | `"2026-08-09T02:14:33Z"` | full probe advanced the observation timestamp |
| Approved | `population_dun` | `last_checked` | `"2026-08-08T05:49:42Z"` | `"2026-08-09T02:14:33Z"` | full probe advanced the observation timestamp |
| Approved | `population_parlimen` | `last_checked` | `"2026-08-08T05:49:42Z"` | `"2026-08-09T02:14:33Z"` | full probe advanced the observation timestamp |
| Approved | `ppi_2d` | `last_checked` | `"2026-08-08T05:49:42Z"` | `"2026-08-09T02:14:33Z"` | full probe advanced the observation timestamp |
| Approved | `ppi_3d` | `last_checked` | `"2026-08-08T05:49:42Z"` | `"2026-08-09T02:14:33Z"` | full probe advanced the observation timestamp |
| Approved | `pricecatcher` | `last_checked` | `"2026-08-07T07:25:52Z"` | `"2026-08-09T02:14:33Z"` | full probe advanced the observation timestamp |
| Approved | `pricecatcher` | `record_count` | `5151` | `5061` | record count changed within the 10% tolerance |
| Approved | `ridership_ktmb_daily` | `last_checked` | `"2026-08-08T05:49:42Z"` | `"2026-08-09T02:14:33Z"` | full probe advanced the observation timestamp |
| Approved | `ridership_ktmb_daily` | `content_freshness_date` | `"2026-08-07"` | `"2026-08-08"` | publisher freshness date advanced |
| Approved | `ridership_ktmb_daily` | `record_count` | `8943` | `8948` | record count changed within the 10% tolerance |
| Approved | `ridership_ktmb_monthly` | `last_checked` | `"2026-08-08T05:49:42Z"` | `"2026-08-09T02:14:33Z"` | full probe advanced the observation timestamp |
| Approved | `ridership_od_ets` | `last_checked` | `"2026-08-08T05:49:42Z"` | `"2026-08-09T02:14:33Z"` | full probe advanced the observation timestamp |
| Approved | `ridership_od_ets` | `content_freshness_date` | `"2026-08-07"` | `"2026-08-08"` | publisher freshness date advanced |
| Approved | `ridership_od_ets` | `record_count` | `507504` | `509757` | record count changed within the 10% tolerance |
| Approved | `ridership_od_intercity` | `last_checked` | `"2026-08-08T05:49:42Z"` | `"2026-08-09T02:14:33Z"` | full probe advanced the observation timestamp |
| Approved | `ridership_od_intercity` | `content_freshness_date` | `"2026-08-07"` | `"2026-08-08"` | publisher freshness date advanced |
| Approved | `ridership_od_intercity` | `record_count` | `121386` | `121962` | record count changed within the 10% tolerance |
| Approved | `ridership_od_komuter` | `last_checked` | `"2026-08-08T05:49:42Z"` | `"2026-08-09T02:14:33Z"` | full probe advanced the observation timestamp |
| Approved | `ridership_od_komuter` | `content_freshness_date` | `"2026-08-07"` | `"2026-08-08"` | publisher freshness date advanced |
| Approved | `ridership_od_komuter` | `record_count` | `1132375` | `1135989` | record count changed within the 10% tolerance |
| Approved | `ridership_od_komuter_utara` | `last_checked` | `"2026-08-08T05:49:42Z"` | `"2026-08-09T02:14:33Z"` | full probe advanced the observation timestamp |
| Approved | `ridership_od_komuter_utara` | `content_freshness_date` | `"2026-08-07"` | `"2026-08-08"` | publisher freshness date advanced |
| Approved | `ridership_od_komuter_utara` | `record_count` | `873130` | `877379` | record count changed within the 10% tolerance |
| Approved | `ridership_od_shuttle_tebrau` | `last_checked` | `"2026-08-08T05:49:42Z"` | `"2026-08-09T02:14:33Z"` | full probe advanced the observation timestamp |
| Approved | `ridership_od_shuttle_tebrau` | `content_freshness_date` | `"2026-08-07"` | `"2026-08-08"` | publisher freshness date advanced |
| Approved | `ridership_od_shuttle_tebrau` | `record_count` | `6040` | `6068` | record count changed within the 10% tolerance |
| Approved | `sppi_3d` | `last_checked` | `"2026-08-08T05:49:42Z"` | `"2026-08-09T02:14:33Z"` | full probe advanced the observation timestamp |
| Approved | `vaxreg_covid_demog` | `last_checked` | `"2026-08-08T05:49:42Z"` | `"2026-08-09T02:14:33Z"` | full probe advanced the observation timestamp |

## Blockers

| Classification | Dataset ID | Field | Before | After | Reason |
|---|---|---|---|---|---|
| Blocker | `gtfs_realtime_ktmb` | `record_count` | `9` | `7` | record count changed by more than 10% |
| Blocker | `gtfs_realtime_mybas_melaka` | `record_count` | `27` | `30` | record count changed by more than 10% |
| Blocker | `gtfs_realtime_mybas_seremban_a` | `record_count` | `20` | `25` | record count changed by more than 10% |
| Blocker | `gtfs_realtime_mybas_seremban_b` | `record_count` | `19` | `23` | record count changed by more than 10% |
| Blocker | `gtfs_static_mybas_alor_setar` | `record_count` | `35388` | `0` | record count changed by more than 10% |
| Blocker | `gtfs_static_mybas_kangar` | `record_count` | `16160` | `0` | record count changed by more than 10% |
| Blocker | `gtfs_static_mybas_kota_bharu` | `record_count` | `47556` | `0` | record count changed by more than 10% |
| Blocker | `gtfs_static_mybas_kuala_terengganu` | `record_count` | `20616` | `0` | record count changed by more than 10% |
| Blocker | `gtfs_static_mybas_kuching` | `record_count` | `17170` | `0` | record count changed by more than 10% |

## Pending

_None._

## Reproduction

Run from the repository root. The full probe remains temporary; only this report is written.

```bash
python3 scripts/run_health_canary.py
```
