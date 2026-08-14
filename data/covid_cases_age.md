---
dataset_id: dgm_covid_cases_age
last_checked: 2026-08-14T04:59:27Z
last_checked: 2026-08-14T04:59:27Z
status: stale
freshness_delta: 440 days
next_expected_update: daily
record_count: 33218
schema_version: unknown
schema_drift: none
known_quirks: ["Official catalogue caveat: In a small minority (~1.5%) of cases, no age was declared or able to be derived. As such, the total number of cases derived from summing the cases for all age groups in this dataset will be less than the number of cases in the [base dataset](https://data.moh.gov.my/data-catalogue/healthcare_covid_cases)."]
breaking_changes: []
licence: Open Government Licence (Malaysia)
attribution: Ministry of Health Malaysia via data.gov.my
---

# Daily COVID-19 Cases by Age Group & State

## Status

**Status:** Stale

**Freshness:** 440 days

HTTP 200

## Last checked

2026-08-14 at 04:59:27 UTC.

## File size

The checked resource is 10,079,621 bytes.

## Provenance

Ministry of Health Malaysia publishes this dataset through data.gov.my (OpenAPI).

- Source: https://api.data.gov.my/data-catalogue?id=covid_cases_age
- [Official catalogue metadata](https://data.gov.my/data-catalogue/covid_cases_age)

## Coverage

Malaysia.

## Schema

Refer to the [official catalogue field definitions](https://data.gov.my/data-catalogue/covid_cases_age) before analysis. The machine-readable envelope records fields observed from the source.

## Known quirks

- Official catalogue caveat: In a small minority (~1.5%) of cases, no age was declared or able to be derived. As such, the total number of cases derived from summing the cases for all age groups in this dataset will be less than the number of cases in the [base dataset](https://data.moh.gov.my/data-catalogue/healthcare_covid_cases).

## Breaking changes

None observed.

## Reproducibility

    curl -sS --max-time 30 "https://api.data.gov.my/data-catalogue?id=covid_cases_age" | head

## Licence

Licensed under Open Government Licence (Malaysia).
Attribution: Ministry of Health Malaysia via data.gov.my.
