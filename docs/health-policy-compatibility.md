# Full-probe health policy compatibility canary

- Date: `2026-08-09T20:03:55+08:00`
- Source SHA: `108150568b92d5dff3e0e2912cd045258f0189c9`
- Live `health/latest.json` commit SHA: `108150568b92d5dff3e0e2912cd045258f0189c9`
- Live `health/latest.json` last commit timestamp: `2026-08-09T20:02:05+08:00`
- Canary SHA-256: `1c2e029d56afe91d51c55737c7d080773e4d416ebeffba43c0e6afef0c43b891`
- Full-probe duration: `228.91 seconds`

## Summary

- Total datasets: **335**
- Approved changes: **338**
- Blockers: **8**
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

## Record-count changes

| Classification | Dataset ID | Field | Before | After | Reason |
|---|---|---|---|---|---|
| Blocker | `gtfs_realtime_ktmb` | `record_count` | `2` | `0` | record count changed by more than 10% |
| Blocker | `gtfs_realtime_mybas_ipoh` | `record_count` | `17` | `12` | record count changed by more than 10% |
| Approved | `gtfs_realtime_mybas_johor` | `record_count` | `93` | `84` | record count changed within the 10% tolerance |
| Blocker | `gtfs_realtime_mybas_kangar` | `record_count` | `24` | `18` | record count changed by more than 10% |
| Blocker | `gtfs_realtime_mybas_kota_bharu` | `record_count` | `26` | `15` | record count changed by more than 10% |
| Blocker | `gtfs_realtime_mybas_kuala_terengganu` | `record_count` | `17` | `12` | record count changed by more than 10% |
| Blocker | `gtfs_realtime_mybas_kuching` | `record_count` | `15` | `8` | record count changed by more than 10% |
| Blocker | `gtfs_realtime_mybas_melaka` | `record_count` | `31` | `26` | record count changed by more than 10% |
| Approved | `gtfs_realtime_mybas_seremban_a` | `record_count` | `25` | `26` | record count changed within the 10% tolerance |
| Blocker | `gtfs_realtime_mybas_seremban_b` | `record_count` | `24` | `28` | record count changed by more than 10% |
| Approved | `gtfs_realtime_prasarana_bus_mrtfeeder` | `record_count` | `117` | `112` | record count changed within the 10% tolerance |
| Approved | `gtfs_realtime_prasarana_bus_penang` | `record_count` | `151` | `156` | record count changed within the 10% tolerance |

## Schema changes

_None._

## Approved

| Classification | Dataset ID | Field | Before | After | Reason |
|---|---|---|---|---|---|
| Approved | `air_pollution` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `bop_balance` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `cosmetic_notifications` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `cosmetic_notifications_cancelled` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `covid_deaths_linelist` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `cpi_3d` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `cpi_4d` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `cpi_5d` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `cpi_core` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `cpi_core_inflation` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `dgm_almanak_astronomi` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `dgm_arrivals` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `dgm_arrivals_soe` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `dgm_births` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `dgm_blood_donations` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `dgm_blood_donations_state` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `dgm_cellular_subscribers` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `dgm_completion_school_state` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `dgm_cosmetics_manufacturers` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `dgm_covid_cases` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `dgm_covid_cases_age` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `dgm_covid_cases_vaxstatus` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `dgm_crops_state` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `dgm_currency_codes` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `dgm_currency_in_circulation` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `dgm_currency_in_circulation_annual` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `dgm_datasets` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `dgm_domains` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `dgm_domains_dnssec` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `dgm_domains_idn` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `dgm_domains_ipv6` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `dgm_drug_addicts_age` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `dgm_drug_addicts_drugtype` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `dgm_drug_addicts_education` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `dgm_drug_addicts_occupation` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `dgm_drug_arrests_age` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `dgm_drug_arrests_ethnicity` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `dgm_electricity_access` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `dgm_electricity_consumption` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `dgm_electricity_supply` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `dgm_enrolment_school_district` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `dgm_epf_dividend` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `dgm_federal_budget_moe` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `dgm_federal_budget_moh` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `dgm_federal_finance_qtr` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `dgm_federal_finance_qtr_oe` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `dgm_federal_finance_qtr_revenue` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `dgm_federal_finance_year` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `dgm_federal_finance_year_de` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `dgm_federal_finance_year_oe` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `dgm_fish_landings` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `dgm_government_apps` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `dgm_government_apps_active` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `dgm_government_apps_downloads` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `dgm_government_apps_reviews` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `dgm_healthcare_staff` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `dgm_hospital_beds` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `dgm_infant_immunisation` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `dgm_interest_rates` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `dgm_interest_rates_annual` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `dgm_interestrates_annual` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `dgm_ktmb_ridership_monthly` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `dgm_lecturers_uni` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `dgm_local_authority_sex` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `dgm_lookup_federal_finance` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `dgm_lookup_money_banking` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `dgm_metrics_content` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `dgm_metrics_dataset_cumul` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `dgm_mnha` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `dgm_mnha_moh` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `dgm_money_aggregates` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `dgm_nutrition_children_sex` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `dgm_nutrition_children_strata` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `dgm_organ_pledges` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `dgm_organ_pledges_state` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `dgm_parliament_sex` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `dgm_passports` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `dgm_payments_channels` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `dgm_payments_instruments` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `dgm_payments_systems` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `dgm_payments_transactions_fpx` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `dgm_pekab40_screenings` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `dgm_pekab40_screenings_state` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `dgm_poskod` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `dgm_prisoners_prison` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `dgm_prisoners_state` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `dgm_registrations_type_fuel` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `dgm_ridership_headline` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `dgm_sanitation_access` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `dgm_schools_district` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `dgm_state_finance_expenditure` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `dgm_state_finance_revenue` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `dgm_std_state` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `dgm_teachers_district` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `dgm_trnsc_daily_directdebit` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `dgm_trnsc_daily_fpx` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `dgm_trnsc_daily_jompay` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `dgm_trnsc_daily_san` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `dgm_usage_metrics` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `dgm_usage_metrics_openapi` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `dgm_usage_metrics_openapi_cumul` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `dgm_vaxreg_covid` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `dgm_vehicle_registrations_type_fuel` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `dgm_water_access` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `dgm_water_consumption` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `dgm_water_pollution_basin` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `dgm_water_production` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `doe_apims` | `last_checked` | `"2026-08-09T11:30:58Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `doe_mqims` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `doe_rqims` | `last_checked` | `"2026-08-09T11:30:58Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `dosm_arc_dosm` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `dosm_bec` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `dosm_birth_state` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `dosm_births_annual` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `dosm_births_annual_sex_ethnic` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `dosm_births_annual_sex_ethnic_state` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `dosm_births_annual_state` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `dosm_births_district_sex` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `dosm_cpi_annual` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `dosm_cpi_annual_inflation` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `dosm_cpi_core_inflation` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `dosm_cpi_headline` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `dosm_cpi_headline_inflation` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `dosm_cpi_inflation` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `dosm_cpi_lowincome` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `dosm_cpi_state` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `dosm_cpi_state_inflation` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `dosm_cpi_strata` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `dosm_crime_district` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `dosm_crops_district_area` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `dosm_crops_district_production` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `dosm_death_district_sex` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `dosm_death_maternal` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `dosm_death_maternal_state` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `dosm_death_state` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `dosm_deaths` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `dosm_deaths_district_sex` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `dosm_deaths_early_childhood` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `dosm_deaths_early_childhood_sex` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `dosm_deaths_early_childhood_state` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `dosm_deaths_early_childhood_state_sex` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `dosm_deaths_maternal` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `dosm_deaths_maternal_state` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `dosm_deaths_sex_ethnic` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `dosm_deaths_sex_ethnic_state` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `dosm_deaths_state` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `dosm_economic_indicators` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `dosm_employment_sector` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `dosm_fertility` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `dosm_fertility_state` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `dosm_forest_reserve` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `dosm_forest_reserve_state` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `dosm_gdp_annual_nominal_demand` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `dosm_gdp_annual_nominal_demand_granular` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `dosm_gdp_annual_nominal_income` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `dosm_gdp_annual_nominal_supply` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `dosm_gdp_annual_nominal_supply_granular` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `dosm_gdp_annual_real_demand` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `dosm_gdp_annual_real_demand_granular` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `dosm_gdp_annual_real_supply` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `dosm_gdp_annual_real_supply_granular` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `dosm_gdp_district_real_supply` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `dosm_gdp_gni_annual_nominal` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `dosm_gdp_gni_annual_real` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `dosm_gdp_lookup` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `dosm_gdp_qtr_nominal` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `dosm_gdp_qtr_nominal_demand` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `dosm_gdp_qtr_nominal_demand_granular` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `dosm_gdp_qtr_nominal_supply` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `dosm_gdp_qtr_nominal_supply_granular` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `dosm_gdp_qtr_real` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `dosm_gdp_qtr_real_demand` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `dosm_gdp_qtr_real_demand_granular` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `dosm_gdp_qtr_real_sa` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `dosm_gdp_qtr_real_sa_demand` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `dosm_gdp_qtr_real_sa_supply` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `dosm_gdp_qtr_real_supply` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `dosm_gdp_qtr_real_supply_granular` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `dosm_gdp_state_real_supply` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `dosm_hh_access_amenities` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `dosm_hh_expenditure_dun` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `dosm_hh_expenditure_parlimen` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `dosm_hh_income` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `dosm_hh_income_district` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `dosm_hh_income_dun` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `dosm_hh_income_parlimen` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `dosm_hh_income_state` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `dosm_hh_inequality` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `dosm_hh_inequality_district` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `dosm_hh_inequality_dun` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `dosm_hh_inequality_parlimen` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `dosm_hh_inequality_state` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `dosm_hh_poverty` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `dosm_hh_poverty_district` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `dosm_hh_poverty_dun` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `dosm_hh_poverty_parlimen` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `dosm_hh_poverty_state` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `dosm_hh_profile` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `dosm_hh_profile_state` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `dosm_hies_district` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `dosm_hies_malaysia_percentile` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `dosm_hies_state` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `dosm_hies_state_percentile` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `dosm_iowrt` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `dosm_iowrt_2d` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `dosm_iowrt_3d` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `dosm_ipi` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `dosm_ipi_1d` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `dosm_ipi_domestic` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `dosm_ipi_export` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `dosm_lfs_district` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `dosm_lfs_dun` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `dosm_lfs_month` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `dosm_lfs_month_duration` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `dosm_lfs_month_sa` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `dosm_lfs_month_status` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `dosm_lfs_month_youth` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `dosm_lfs_parlimen` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `dosm_lfs_qtr` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `dosm_lfs_qtr_sru_age` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `dosm_lfs_qtr_sru_sex` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `dosm_lfs_qtr_state` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `dosm_lfs_qtr_tru_age` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `dosm_lfs_qtr_tru_sex` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `dosm_lfs_state_sex` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `dosm_lfs_year` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `dosm_lfs_year_sex` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `dosm_lookup_item` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `dosm_lookup_premise` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `dosm_marriages` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `dosm_marriages_age` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `dosm_marriages_state` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `dosm_marriages_state_age` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `dosm_mcoicop` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `dosm_mineral_extraction` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `dosm_msic` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `dosm_population_malaysia` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `dosm_population_parlimen` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `dosm_population_state` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `dosm_ppi` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `dosm_ppi_1d` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `dosm_ppi_sitc` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `dosm_productivity_annual` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `dosm_productivity_annual_priority` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `dosm_productivity_lookup` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `dosm_productivity_qtr` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `dosm_sitc` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `dosm_sitc_sop` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `dosm_sppi` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `dosm_sppi_1d` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `dosm_sppi_2d` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `dosm_stillbirths` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `dosm_stillbirths_state` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `dosm_timber_production` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `dosm_trade_enduse_bec` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `dosm_trade_headline` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `dosm_trade_sitc_1d` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `exchangerates` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `exchangerates_daily_0900` | `last_checked` | `"2026-08-09T11:01:03Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `exchangerates_daily_1130` | `last_checked` | `"2026-08-09T11:01:03Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `exchangerates_daily_1200` | `last_checked` | `"2026-08-09T11:01:03Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `exchangerates_daily_1700` | `last_checked` | `"2026-08-09T11:01:03Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `fdi_flows` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `federal_finance_qtr_de` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `federal_finance_year_revenue` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `fuelprice` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `ghg_emissions` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `gtfs_realtime_ktmb` | `last_checked` | `"2026-08-09T11:30:58Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `gtfs_realtime_mybas_alor_setar` | `last_checked` | `"2026-08-09T11:30:58Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `gtfs_realtime_mybas_ipoh` | `last_checked` | `"2026-08-09T11:30:58Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `gtfs_realtime_mybas_johor` | `last_checked` | `"2026-08-09T11:30:58Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `gtfs_realtime_mybas_johor` | `record_count` | `93` | `84` | record count changed within the 10% tolerance |
| Approved | `gtfs_realtime_mybas_kangar` | `last_checked` | `"2026-08-09T11:30:58Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `gtfs_realtime_mybas_kota_bharu` | `last_checked` | `"2026-08-09T11:30:58Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `gtfs_realtime_mybas_kuala_terengganu` | `last_checked` | `"2026-08-09T11:30:58Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `gtfs_realtime_mybas_kuching` | `last_checked` | `"2026-08-09T11:30:58Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `gtfs_realtime_mybas_melaka` | `last_checked` | `"2026-08-09T11:30:58Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `gtfs_realtime_mybas_seremban_a` | `last_checked` | `"2026-08-09T11:30:58Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `gtfs_realtime_mybas_seremban_a` | `record_count` | `25` | `26` | record count changed within the 10% tolerance |
| Approved | `gtfs_realtime_mybas_seremban_b` | `last_checked` | `"2026-08-09T11:30:58Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `gtfs_realtime_prasarana_bus_kl` | `last_checked` | `"2026-08-09T11:30:58Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `gtfs_realtime_prasarana_bus_mrtfeeder` | `last_checked` | `"2026-08-09T11:30:58Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `gtfs_realtime_prasarana_bus_mrtfeeder` | `record_count` | `117` | `112` | record count changed within the 10% tolerance |
| Approved | `gtfs_realtime_prasarana_bus_penang` | `last_checked` | `"2026-08-09T11:30:58Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `gtfs_realtime_prasarana_bus_penang` | `record_count` | `151` | `156` | record count changed within the 10% tolerance |
| Approved | `gtfs_static_ktmb` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `gtfs_static_mybas_alor_setar` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `gtfs_static_mybas_ipoh` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `gtfs_static_mybas_johor` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `gtfs_static_mybas_kangar` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `gtfs_static_mybas_kota_bharu` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `gtfs_static_mybas_kuala_terengganu` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `gtfs_static_mybas_kuching` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `gtfs_static_mybas_melaka` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `gtfs_static_mybas_seremban_a` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `gtfs_static_mybas_seremban_b` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `gtfs_static_prasarana_bus_kl` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `gtfs_static_prasarana_bus_kuantan` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `gtfs_static_prasarana_bus_mrtfeeder` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `gtfs_static_prasarana_bus_penang` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `gtfs_static_prasarana_rail_kl` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `hospital_beds` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `interestrates` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `ipi_2d` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `ipi_3d` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `ipi_5d` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `ipi_domestic` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `ipi_export` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `kkm_idengue` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `met_weather` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `monetary_aggregates` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `payment_channels` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `payment_instruments` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `payment_systems` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `pharmaceutical_importers` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `pharmaceutical_manufacturers` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `pharmaceutical_products` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `pharmaceutical_products_cancelled` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `pharmaceutical_wholesalers` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `population_dun` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `population_parlimen` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `ppi_2d` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `ppi_3d` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `pricecatcher` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `registration_transactions_all` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `registration_transactions_car` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `registration_transactions_motorcycle` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `ridership_ktmb_daily` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `ridership_ktmb_monthly` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `ridership_od_brt_daily` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `ridership_od_ets` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `ridership_od_intercity` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `ridership_od_komuter` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `ridership_od_komuter_utara` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `ridership_od_rapidrail_daily` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `ridership_od_shuttle_tebrau` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `sppi_3d` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |
| Approved | `vaxreg_covid_demog` | `last_checked` | `"2026-08-09T08:37:11Z"` | `"2026-08-09T12:03:54Z"` | full probe advanced the observation timestamp |

## Blockers

| Classification | Dataset ID | Field | Before | After | Reason |
|---|---|---|---|---|---|
| Blocker | `gtfs_realtime_ktmb` | `record_count` | `2` | `0` | record count changed by more than 10% |
| Blocker | `gtfs_realtime_mybas_ipoh` | `record_count` | `17` | `12` | record count changed by more than 10% |
| Blocker | `gtfs_realtime_mybas_kangar` | `record_count` | `24` | `18` | record count changed by more than 10% |
| Blocker | `gtfs_realtime_mybas_kota_bharu` | `record_count` | `26` | `15` | record count changed by more than 10% |
| Blocker | `gtfs_realtime_mybas_kuala_terengganu` | `record_count` | `17` | `12` | record count changed by more than 10% |
| Blocker | `gtfs_realtime_mybas_kuching` | `record_count` | `15` | `8` | record count changed by more than 10% |
| Blocker | `gtfs_realtime_mybas_melaka` | `record_count` | `31` | `26` | record count changed by more than 10% |
| Blocker | `gtfs_realtime_mybas_seremban_b` | `record_count` | `24` | `28` | record count changed by more than 10% |

## Pending

_None._

## Reproduction

Run from the repository root. The full probe remains temporary; only this report is written.

```bash
python3 scripts/run_health_canary.py
```
