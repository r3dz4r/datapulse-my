---
dataset_id: dgm_covid_cases_vaxstatus
last_checked: 2026-08-10T10:07:26Z
last_checked: 2026-08-10T10:07:26Z
status: stale
freshness_delta: 436 days
next_expected_update: daily
record_count: 33218
schema_version: unknown
schema_drift: none
known_quirks: ["Official catalogue caveat: It is possible that the number of vaccinated cases exceeds the tabulated number, for instance if an individual was vaccinated under an ID different from the ID used in the COVID-19 test result declaration, or if an individual was vaccinated outside the country and has not yet uploaded their records to MyVAS. However, these issues are negligible in magnitude."]
breaking_changes: []
licence: Open Government Licence (Malaysia)
attribution: Ministry of Health Malaysia via data.gov.my
---

# Daily COVID-19 Cases by Vaccination Status & State

## Status

**Status:** Stale

**Freshness:** 436 days

HTTP 200

## Last checked

2026-08-10 at 10:07:26 UTC.

## File size

The checked resource is 3,894,174 bytes.

## Provenance

Ministry of Health Malaysia publishes this dataset through data.gov.my (OpenAPI).

- Source: https://api.data.gov.my/data-catalogue?id=covid_cases_vaxstatus
- [Official catalogue metadata](https://data.gov.my/data-catalogue/covid_cases_vaxstatus)

## Coverage

Malaysia.

## Schema

Refer to the [official catalogue field definitions](https://data.gov.my/data-catalogue/covid_cases_vaxstatus) before analysis. The machine-readable envelope records fields observed from the source.

## Known quirks

- Official catalogue caveat: It is possible that the number of vaccinated cases exceeds the tabulated number, for instance if an individual was vaccinated under an ID different from the ID used in the COVID-19 test result declaration, or if an individual was vaccinated outside the country and has not yet uploaded their records to MyVAS. However, these issues are negligible in magnitude.

## Breaking changes

None observed.

## Reproducibility

    curl -sS --max-time 30 "https://api.data.gov.my/data-catalogue?id=covid_cases_vaxstatus" | head

## Licence

Licensed under Open Government Licence (Malaysia).
Attribution: Ministry of Health Malaysia via data.gov.my.
