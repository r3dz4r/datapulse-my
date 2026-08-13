---
dataset_id: dosm_deaths_state
last_checked: 2026-08-11T14:21:08Z
last_checked: 2026-08-11T14:21:08Z
status: aging
freshness_delta: 953 days
next_expected_update: annual
record_count: 390
schema_version: unknown
schema_drift: none
known_quirks: ["Official catalogue caveat: This data is derived based on deaths registered with JPN. Therefore, if a death is not registered with JPN (for instance, if the death of a foreigner is registered in their home country, or the death of resident in a remote area is not registered), it will generally not count in this dataset. However, adjustment has been made to the number of deaths in Sabah to account for the under-reporting of deaths detected based on the 'Study of Under Reporting of Deaths in Sabah', which was conducted by DOSM and approved by the Steering Committee on Implementation of Civil Registration and Vital Statistics in 2016."]
breaking_changes: []
licence: Creative Commons Attribution 4.0
attribution: National Registration Department and Department of Statistics Malaysia via data.gov.my
---

# Annual Deaths by State

## Status

**Status:** Aging

**Freshness:** 953 days

HTTP 200

## Last checked

2026-08-11 at 14:21:08 UTC.

## File size

The checked resource is 28,058 bytes.

## Provenance

National Registration Department and Department of Statistics Malaysia publishes this dataset through DOSM via data.gov.my.

- Source: https://api.data.gov.my/data-catalogue?id=deaths_state
- [Official catalogue metadata](https://data.gov.my/data-catalogue/deaths_state)

## Coverage

Malaysia.

## Schema

Refer to the [official catalogue field definitions](https://data.gov.my/data-catalogue/deaths_state) before analysis. The machine-readable envelope records fields observed from the source.

## Known quirks

- Official catalogue caveat: This data is derived based on deaths registered with JPN. Therefore, if a death is not registered with JPN (for instance, if the death of a foreigner is registered in their home country, or the death of resident in a remote area is not registered), it will generally not count in this dataset. However, adjustment has been made to the number of deaths in Sabah to account for the under-reporting of deaths detected based on the 'Study of Under Reporting of Deaths in Sabah', which was conducted by DOSM and approved by the Steering Committee on Implementation of Civil Registration and Vital Statistics in 2016.

## Breaking changes

None observed.

## Reproducibility

    curl -sS --max-time 30 "https://api.data.gov.my/data-catalogue?id=deaths_state" | head

## Licence

Licensed under Creative Commons Attribution 4.0.
Attribution: National Registration Department and Department of Statistics Malaysia via data.gov.my.
