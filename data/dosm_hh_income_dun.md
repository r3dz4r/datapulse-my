---
dataset_id: dosm_hh_income_dun
last_checked: 2026-08-16T02:09:20Z
last_checked: 2026-08-16T02:09:20Z
status: aging
freshness_delta: 958 days
next_expected_update: annual
record_count: 1800
schema_version: unknown
schema_drift: none
known_quirks: ["Official catalogue caveat: This data presents nominal values, i.e. they have not been adjusted for inflation. Furthermore, DUN-level data is only published from 2019 (relative to [state-level data](https://open.dosm.gov.my/data-catalogue/hh_income_state) which is available from 1970) as prior HIES samples were not sufficient to support DUN-level granularity."]
breaking_changes: []
licence: Creative Commons Attribution 4.0
attribution: Department of Statistics Malaysia via data.gov.my
---

# Household Income by DUN

## Status

**Status:** Aging

**Freshness:** 958 days

HTTP 200

## Last checked

2026-08-16 at 02:09:20 UTC.

## File size

The checked resource is 258,939 bytes.

## Provenance

Department of Statistics Malaysia publishes this dataset through DOSM via data.gov.my.

- Source: https://api.data.gov.my/data-catalogue?id=hh_income_dun
- [Official catalogue metadata](https://data.gov.my/data-catalogue/hh_income_dun)

## Coverage

Malaysia.

## Schema

Refer to the [official catalogue field definitions](https://data.gov.my/data-catalogue/hh_income_dun) before analysis. The machine-readable envelope records fields observed from the source.

## Known quirks

- Official catalogue caveat: This data presents nominal values, i.e. they have not been adjusted for inflation. Furthermore, DUN-level data is only published from 2019 (relative to [state-level data](https://open.dosm.gov.my/data-catalogue/hh_income_state) which is available from 1970) as prior HIES samples were not sufficient to support DUN-level granularity.

## Breaking changes

None observed.

## Reproducibility

    curl -sS --max-time 30 "https://api.data.gov.my/data-catalogue?id=hh_income_dun" | head

## Licence

Licensed under Creative Commons Attribution 4.0.
Attribution: Department of Statistics Malaysia via data.gov.my.
