# Full-probe health policy compatibility canary

- Date: `2026-08-09T20:16:10+08:00`
- Source SHA: `4bb07feb54f8a6be5881b9d2e7bd06a770736aad`
- Live `health/latest.json` commit SHA: `4bb07feb54f8a6be5881b9d2e7bd06a770736aad`
- Live `health/latest.json` last commit timestamp: `2026-08-09T20:16:02+08:00`
- Canary SHA-256: `fe84d27d5355d246b7c1a1778f779853e6e555bc2a771647a80b60ce6e012f6b`
- Full-probe duration: `123.29 seconds`

## Summary

- Total datasets: **335**
- Approved changes: **339**
- Blockers: **1**
- Volatile notes: **9**
- Pending review: **0**

## Per-status distribution

| Status | Live | Canary | Delta |
|---|---:|---:|---:|
| `aging` | 97 | 97 | +0 |
| `browser_dependent` | 5 | 5 | +0 |
| `degraded` | 0 | 0 | +0 |
| `fresh` | 85 | 85 | +0 |
| `stale` | 128 | 128 | +0 |
| `unknown` | 0 | 0 | +0 |
| `unknown_freshness` | 19 | 19 | +0 |
| `unreachable` | 1 | 1 | +0 |

## Status flips

_None._

## Schema changes

_None._

## Record-count changes

| Classification | Category | Dataset ID | Field | Before | After | Reason |
|---|---|---|---|---|---|---|
| Blocker | Operational | `gtfs_realtime_ktmb` | `record_count` | `0` | `2` | record count changed by more than 50% |
| Approved | Operational | `gtfs_realtime_mybas_alor_setar` | `record_count` | `44` | `43` | record count changed within the 50% gtfs-realtime tolerance |
| Volatile | Volatile | `gtfs_realtime_mybas_ipoh` | `record_count` | `11` | `13` | GTFS-realtime record count changed by at least 10% but less than 50%; expected operational noise |
| Approved | Operational | `gtfs_realtime_mybas_johor` | `record_count` | `84` | `86` | record count changed within the 50% gtfs-realtime tolerance |
| Volatile | Volatile | `gtfs_realtime_mybas_kangar` | `record_count` | `18` | `15` | GTFS-realtime record count changed by at least 10% but less than 50%; expected operational noise |
| Volatile | Volatile | `gtfs_realtime_mybas_kota_bharu` | `record_count` | `15` | `11` | GTFS-realtime record count changed by at least 10% but less than 50%; expected operational noise |
| Volatile | Volatile | `gtfs_realtime_mybas_kuala_terengganu` | `record_count` | `12` | `9` | GTFS-realtime record count changed by at least 10% but less than 50%; expected operational noise |
| Volatile | Volatile | `gtfs_realtime_mybas_kuching` | `record_count` | `8` | `7` | GTFS-realtime record count changed by at least 10% but less than 50%; expected operational noise |
| Volatile | Volatile | `gtfs_realtime_mybas_melaka` | `record_count` | `26` | `20` | GTFS-realtime record count changed by at least 10% but less than 50%; expected operational noise |
| Volatile | Volatile | `gtfs_realtime_mybas_seremban_a` | `record_count` | `28` | `25` | GTFS-realtime record count changed by at least 10% but less than 50%; expected operational noise |
| Volatile | Volatile | `gtfs_realtime_mybas_seremban_b` | `record_count` | `25` | `21` | GTFS-realtime record count changed by at least 10% but less than 50%; expected operational noise |
| Volatile | Volatile | `gtfs_realtime_prasarana_bus_mrtfeeder` | `record_count` | `112` | `88` | GTFS-realtime record count changed by at least 10% but less than 50%; expected operational noise |
| Approved | Operational | `gtfs_realtime_prasarana_bus_penang` | `record_count` | `156` | `153` | record count changed within the 50% gtfs-realtime tolerance |
| Approved | Structural | `pricecatcher` | `record_count` | `5061` | `5334` | record count changed within the 10% direct tolerance |

## Approved

| Classification | Category | Dataset ID | Field | Before | After | Reason |
|---|---|---|---|---|---|---|
| Approved | Field | `air_pollution` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `bop_balance` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `cosmetic_notifications` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `cosmetic_notifications_cancelled` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `covid_deaths_linelist` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `cpi_3d` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `cpi_4d` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `cpi_5d` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `cpi_core` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `cpi_core_inflation` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `dgm_almanak_astronomi` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `dgm_arrivals` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `dgm_arrivals_soe` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `dgm_births` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `dgm_blood_donations` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `dgm_blood_donations_state` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `dgm_cellular_subscribers` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `dgm_completion_school_state` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `dgm_cosmetics_manufacturers` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `dgm_covid_cases` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `dgm_covid_cases_age` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `dgm_covid_cases_vaxstatus` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `dgm_crops_state` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `dgm_currency_codes` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `dgm_currency_in_circulation` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `dgm_currency_in_circulation_annual` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `dgm_datasets` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `dgm_domains` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `dgm_domains_dnssec` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `dgm_domains_idn` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `dgm_domains_ipv6` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `dgm_drug_addicts_age` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `dgm_drug_addicts_drugtype` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `dgm_drug_addicts_education` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `dgm_drug_addicts_occupation` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `dgm_drug_arrests_age` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `dgm_drug_arrests_ethnicity` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `dgm_electricity_access` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `dgm_electricity_consumption` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `dgm_electricity_supply` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `dgm_enrolment_school_district` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `dgm_epf_dividend` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `dgm_federal_budget_moe` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `dgm_federal_budget_moh` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `dgm_federal_finance_qtr` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `dgm_federal_finance_qtr_oe` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `dgm_federal_finance_qtr_revenue` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `dgm_federal_finance_year` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `dgm_federal_finance_year_de` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `dgm_federal_finance_year_oe` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `dgm_fish_landings` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `dgm_government_apps` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `dgm_government_apps_active` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `dgm_government_apps_downloads` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `dgm_government_apps_reviews` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `dgm_healthcare_staff` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `dgm_hospital_beds` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `dgm_infant_immunisation` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `dgm_interest_rates` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `dgm_interest_rates_annual` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `dgm_interestrates_annual` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `dgm_ktmb_ridership_monthly` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `dgm_lecturers_uni` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `dgm_local_authority_sex` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `dgm_lookup_federal_finance` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `dgm_lookup_money_banking` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `dgm_metrics_content` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `dgm_metrics_dataset_cumul` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `dgm_mnha` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `dgm_mnha_moh` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `dgm_money_aggregates` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `dgm_nutrition_children_sex` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `dgm_nutrition_children_strata` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `dgm_organ_pledges` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `dgm_organ_pledges_state` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `dgm_parliament_sex` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `dgm_passports` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `dgm_payments_channels` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `dgm_payments_instruments` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `dgm_payments_systems` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `dgm_payments_transactions_fpx` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `dgm_pekab40_screenings` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `dgm_pekab40_screenings_state` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `dgm_poskod` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `dgm_prisoners_prison` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `dgm_prisoners_state` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `dgm_registrations_type_fuel` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `dgm_ridership_headline` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `dgm_sanitation_access` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `dgm_schools_district` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `dgm_state_finance_expenditure` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `dgm_state_finance_revenue` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `dgm_std_state` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `dgm_teachers_district` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `dgm_trnsc_daily_directdebit` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `dgm_trnsc_daily_fpx` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `dgm_trnsc_daily_jompay` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `dgm_trnsc_daily_san` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `dgm_usage_metrics` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `dgm_usage_metrics_openapi` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `dgm_usage_metrics_openapi_cumul` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `dgm_vaxreg_covid` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `dgm_vehicle_registrations_type_fuel` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `dgm_water_access` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `dgm_water_consumption` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `dgm_water_pollution_basin` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `dgm_water_production` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `doe_apims` | `last_checked` | `"2026-08-09T12:01:15Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `doe_mqims` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `doe_rqims` | `last_checked` | `"2026-08-09T12:01:15Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `dosm_arc_dosm` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `dosm_bec` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `dosm_birth_state` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `dosm_births_annual` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `dosm_births_annual_sex_ethnic` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `dosm_births_annual_sex_ethnic_state` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `dosm_births_annual_state` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `dosm_births_district_sex` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `dosm_cpi_annual` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `dosm_cpi_annual_inflation` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `dosm_cpi_core_inflation` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `dosm_cpi_headline` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `dosm_cpi_headline_inflation` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `dosm_cpi_inflation` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `dosm_cpi_lowincome` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `dosm_cpi_state` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `dosm_cpi_state_inflation` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `dosm_cpi_strata` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `dosm_crime_district` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `dosm_crops_district_area` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `dosm_crops_district_production` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `dosm_death_district_sex` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `dosm_death_maternal` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `dosm_death_maternal_state` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `dosm_death_state` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `dosm_deaths` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `dosm_deaths_district_sex` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `dosm_deaths_early_childhood` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `dosm_deaths_early_childhood_sex` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `dosm_deaths_early_childhood_state` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `dosm_deaths_early_childhood_state_sex` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `dosm_deaths_maternal` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `dosm_deaths_maternal_state` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `dosm_deaths_sex_ethnic` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `dosm_deaths_sex_ethnic_state` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `dosm_deaths_state` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `dosm_economic_indicators` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `dosm_employment_sector` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `dosm_fertility` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `dosm_fertility_state` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `dosm_forest_reserve` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `dosm_forest_reserve_state` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `dosm_gdp_annual_nominal_demand` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `dosm_gdp_annual_nominal_demand_granular` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `dosm_gdp_annual_nominal_income` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `dosm_gdp_annual_nominal_supply` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `dosm_gdp_annual_nominal_supply_granular` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `dosm_gdp_annual_real_demand` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `dosm_gdp_annual_real_demand_granular` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `dosm_gdp_annual_real_supply` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `dosm_gdp_annual_real_supply_granular` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `dosm_gdp_district_real_supply` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `dosm_gdp_gni_annual_nominal` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `dosm_gdp_gni_annual_real` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `dosm_gdp_lookup` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `dosm_gdp_qtr_nominal` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `dosm_gdp_qtr_nominal_demand` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `dosm_gdp_qtr_nominal_demand_granular` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `dosm_gdp_qtr_nominal_supply` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `dosm_gdp_qtr_nominal_supply_granular` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `dosm_gdp_qtr_real` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `dosm_gdp_qtr_real_demand` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `dosm_gdp_qtr_real_demand_granular` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `dosm_gdp_qtr_real_sa` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `dosm_gdp_qtr_real_sa_demand` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `dosm_gdp_qtr_real_sa_supply` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `dosm_gdp_qtr_real_supply` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `dosm_gdp_qtr_real_supply_granular` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `dosm_gdp_state_real_supply` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `dosm_hh_access_amenities` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `dosm_hh_expenditure_dun` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `dosm_hh_expenditure_parlimen` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `dosm_hh_income` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `dosm_hh_income_district` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `dosm_hh_income_dun` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `dosm_hh_income_parlimen` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `dosm_hh_income_state` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `dosm_hh_inequality` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `dosm_hh_inequality_district` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `dosm_hh_inequality_dun` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `dosm_hh_inequality_parlimen` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `dosm_hh_inequality_state` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `dosm_hh_poverty` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `dosm_hh_poverty_district` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `dosm_hh_poverty_dun` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `dosm_hh_poverty_parlimen` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `dosm_hh_poverty_state` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `dosm_hh_profile` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `dosm_hh_profile_state` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `dosm_hies_district` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `dosm_hies_malaysia_percentile` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `dosm_hies_state` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `dosm_hies_state_percentile` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `dosm_iowrt` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `dosm_iowrt_2d` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `dosm_iowrt_3d` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `dosm_ipi` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `dosm_ipi_1d` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `dosm_ipi_domestic` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `dosm_ipi_export` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `dosm_lfs_district` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `dosm_lfs_dun` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `dosm_lfs_month` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `dosm_lfs_month_duration` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `dosm_lfs_month_sa` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `dosm_lfs_month_status` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `dosm_lfs_month_youth` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `dosm_lfs_parlimen` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `dosm_lfs_qtr` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `dosm_lfs_qtr_sru_age` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `dosm_lfs_qtr_sru_sex` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `dosm_lfs_qtr_state` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `dosm_lfs_qtr_tru_age` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `dosm_lfs_qtr_tru_sex` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `dosm_lfs_state_sex` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `dosm_lfs_year` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `dosm_lfs_year_sex` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `dosm_lookup_item` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `dosm_lookup_premise` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `dosm_marriages` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `dosm_marriages_age` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `dosm_marriages_state` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `dosm_marriages_state_age` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `dosm_mcoicop` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `dosm_mineral_extraction` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `dosm_msic` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `dosm_population_malaysia` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `dosm_population_parlimen` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `dosm_population_state` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `dosm_ppi` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `dosm_ppi_1d` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `dosm_ppi_sitc` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `dosm_productivity_annual` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `dosm_productivity_annual_priority` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `dosm_productivity_lookup` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `dosm_productivity_qtr` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `dosm_sitc` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `dosm_sitc_sop` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `dosm_sppi` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `dosm_sppi_1d` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `dosm_sppi_2d` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `dosm_stillbirths` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `dosm_stillbirths_state` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `dosm_timber_production` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `dosm_trade_enduse_bec` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `dosm_trade_headline` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `dosm_trade_sitc_1d` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `eperolehan-diklankan` | `last_checked` | `"2026-08-09T12:01:15Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `exchangerates` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `exchangerates_daily_0900` | `last_checked` | `"2026-08-09T11:01:03Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `exchangerates_daily_1130` | `last_checked` | `"2026-08-09T11:01:03Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `exchangerates_daily_1200` | `last_checked` | `"2026-08-09T11:01:03Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `exchangerates_daily_1700` | `last_checked` | `"2026-08-09T11:01:03Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `fdi_flows` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `federal_finance_qtr_de` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `federal_finance_year_revenue` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `fuelprice` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `ghg_emissions` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `gtfs_realtime_ktmb` | `last_checked` | `"2026-08-09T12:01:15Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `gtfs_realtime_mybas_alor_setar` | `last_checked` | `"2026-08-09T12:01:15Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Operational | `gtfs_realtime_mybas_alor_setar` | `record_count` | `44` | `43` | record count changed within the 50% gtfs-realtime tolerance |
| Approved | Field | `gtfs_realtime_mybas_ipoh` | `last_checked` | `"2026-08-09T12:01:15Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `gtfs_realtime_mybas_johor` | `last_checked` | `"2026-08-09T12:01:15Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Operational | `gtfs_realtime_mybas_johor` | `record_count` | `84` | `86` | record count changed within the 50% gtfs-realtime tolerance |
| Approved | Field | `gtfs_realtime_mybas_kangar` | `last_checked` | `"2026-08-09T12:01:15Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `gtfs_realtime_mybas_kota_bharu` | `last_checked` | `"2026-08-09T12:01:15Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `gtfs_realtime_mybas_kuala_terengganu` | `last_checked` | `"2026-08-09T12:01:15Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `gtfs_realtime_mybas_kuching` | `last_checked` | `"2026-08-09T12:01:15Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `gtfs_realtime_mybas_melaka` | `last_checked` | `"2026-08-09T12:01:15Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `gtfs_realtime_mybas_seremban_a` | `last_checked` | `"2026-08-09T12:01:15Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `gtfs_realtime_mybas_seremban_b` | `last_checked` | `"2026-08-09T12:01:15Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `gtfs_realtime_prasarana_bus_kl` | `last_checked` | `"2026-08-09T12:01:15Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `gtfs_realtime_prasarana_bus_mrtfeeder` | `last_checked` | `"2026-08-09T12:01:15Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `gtfs_realtime_prasarana_bus_penang` | `last_checked` | `"2026-08-09T12:01:15Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Operational | `gtfs_realtime_prasarana_bus_penang` | `record_count` | `156` | `153` | record count changed within the 50% gtfs-realtime tolerance |
| Approved | Field | `gtfs_static_ktmb` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `gtfs_static_mybas_alor_setar` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `gtfs_static_mybas_ipoh` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `gtfs_static_mybas_johor` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `gtfs_static_mybas_kangar` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `gtfs_static_mybas_kota_bharu` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `gtfs_static_mybas_kuala_terengganu` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `gtfs_static_mybas_kuching` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `gtfs_static_mybas_melaka` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `gtfs_static_mybas_seremban_a` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `gtfs_static_mybas_seremban_b` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `gtfs_static_prasarana_bus_kl` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `gtfs_static_prasarana_bus_kuantan` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `gtfs_static_prasarana_bus_mrtfeeder` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `gtfs_static_prasarana_bus_penang` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `gtfs_static_prasarana_rail_kl` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `hospital_beds` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `interestrates` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `ipi_2d` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `ipi_3d` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `ipi_5d` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `ipi_domestic` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `ipi_export` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `kkm_idengue` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `met_weather` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `monetary_aggregates` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `payment_channels` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `payment_instruments` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `payment_systems` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `pharmaceutical_importers` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `pharmaceutical_manufacturers` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `pharmaceutical_products` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `pharmaceutical_products_cancelled` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `pharmaceutical_wholesalers` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `population_dun` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `population_parlimen` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `ppi_2d` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `ppi_3d` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `pricecatcher` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Structural | `pricecatcher` | `record_count` | `5061` | `5334` | record count changed within the 10% direct tolerance |
| Approved | Field | `registration_transactions_all` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `registration_transactions_car` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `registration_transactions_motorcycle` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `ridership_ktmb_daily` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `ridership_ktmb_monthly` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `ridership_od_brt_daily` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `ridership_od_ets` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `ridership_od_intercity` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `ridership_od_komuter` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `ridership_od_komuter_utara` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `ridership_od_rapidrail_daily` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `ridership_od_shuttle_tebrau` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `sppi_3d` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |
| Approved | Field | `vaxreg_covid_demog` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:16:09Z"` | full probe advanced the observation timestamp |

## Volatile (gtfs-realtime)

| Classification | Category | Dataset ID | Field | Before | After | Reason |
|---|---|---|---|---|---|---|
| Volatile | Volatile | `gtfs_realtime_mybas_ipoh` | `record_count` | `11` | `13` | GTFS-realtime record count changed by at least 10% but less than 50%; expected operational noise |
| Volatile | Volatile | `gtfs_realtime_mybas_kangar` | `record_count` | `18` | `15` | GTFS-realtime record count changed by at least 10% but less than 50%; expected operational noise |
| Volatile | Volatile | `gtfs_realtime_mybas_kota_bharu` | `record_count` | `15` | `11` | GTFS-realtime record count changed by at least 10% but less than 50%; expected operational noise |
| Volatile | Volatile | `gtfs_realtime_mybas_kuala_terengganu` | `record_count` | `12` | `9` | GTFS-realtime record count changed by at least 10% but less than 50%; expected operational noise |
| Volatile | Volatile | `gtfs_realtime_mybas_kuching` | `record_count` | `8` | `7` | GTFS-realtime record count changed by at least 10% but less than 50%; expected operational noise |
| Volatile | Volatile | `gtfs_realtime_mybas_melaka` | `record_count` | `26` | `20` | GTFS-realtime record count changed by at least 10% but less than 50%; expected operational noise |
| Volatile | Volatile | `gtfs_realtime_mybas_seremban_a` | `record_count` | `28` | `25` | GTFS-realtime record count changed by at least 10% but less than 50%; expected operational noise |
| Volatile | Volatile | `gtfs_realtime_mybas_seremban_b` | `record_count` | `25` | `21` | GTFS-realtime record count changed by at least 10% but less than 50%; expected operational noise |
| Volatile | Volatile | `gtfs_realtime_prasarana_bus_mrtfeeder` | `record_count` | `112` | `88` | GTFS-realtime record count changed by at least 10% but less than 50%; expected operational noise |

## Blockers

| Classification | Category | Dataset ID | Field | Before | After | Reason |
|---|---|---|---|---|---|---|
| Blocker | Operational | `gtfs_realtime_ktmb` | `record_count` | `0` | `2` | record count changed by more than 50% |

## Pending

_None._

## Reproduction

Run from the repository root. The full probe remains temporary; only this report is written.

```bash
python3 scripts/run_health_canary.py
```
