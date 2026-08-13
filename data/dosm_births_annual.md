---
dataset_id: dosm_births_annual
last_checked: 2026-08-13T02:46:04Z
last_checked: 2026-08-13T02:46:04Z
status: aging
freshness_delta: 955 days
next_expected_update: annual
record_count: 25
schema_version: unknown
schema_drift: none
known_quirks: ["Official catalogue caveat: This data is derived based on births registered with JPN. Accordingly, if a birth is not registered with JPN (for instance, if a foreigner chooses to register their child in their home country, or if a resident in a remote area does not register the birth of their child), it will not count in this dataset."]
breaking_changes: []
licence: Creative Commons Attribution 4.0
attribution: National Registration Department and Department of Statistics Malaysia via data.gov.my
---

# Annual Live Births

## Status

**Status:** Aging

**Freshness:** 955 days

HTTP 200

## Last checked

2026-08-13 at 02:46:04 UTC.

## File size

The checked resource is 1,325 bytes.

## Provenance

National Registration Department and Department of Statistics Malaysia publishes this dataset through DOSM via data.gov.my.

- Source: https://api.data.gov.my/data-catalogue?id=births_annual
- [Official catalogue metadata](https://data.gov.my/data-catalogue/births_annual)

## Coverage

Malaysia.

## Schema

Refer to the [official catalogue field definitions](https://data.gov.my/data-catalogue/births_annual) before analysis. The machine-readable envelope records fields observed from the source.

## Known quirks

- Official catalogue caveat: This data is derived based on births registered with JPN. Accordingly, if a birth is not registered with JPN (for instance, if a foreigner chooses to register their child in their home country, or if a resident in a remote area does not register the birth of their child), it will not count in this dataset.

## Breaking changes

None observed.

## Reproducibility

    curl -sS --max-time 30 "https://api.data.gov.my/data-catalogue?id=births_annual" | head

## Licence

Licensed under Creative Commons Attribution 4.0.
Attribution: National Registration Department and Department of Statistics Malaysia via data.gov.my.
