---
dataset_id: dgm_arrivals_soe
last_checked: 2026-08-09T05:30:41Z
last_checked: 2026-08-09T05:30:41Z
status: stale
freshness_delta: 612 days
next_expected_update: monthly
record_count: 92674
schema_version: unknown
schema_drift: none
known_quirks: ["Official catalogue caveat: This data is based solely on records in MyIMMS. Furthermore, it should be noted that approximately 0.01% of arrivals do not have a nationality specified, including stateless individuals and refugees."]
breaking_changes: []
licence: Open Government Licence (Malaysia)
attribution: Immigration Department of Malaysia via data.gov.my
---

# Monthly Arrivals by State of Entry, Nationality & Sex

## Status

**Status:** Stale

**Freshness:** 612 days

HTTP 200

## Last checked

2026-08-09 at 05:30:41 UTC.

## File size

The checked resource is 2,791,067 bytes.

## Provenance

Immigration Department of Malaysia publishes this dataset through data.gov.my (storage).

- Source: https://storage.data.gov.my/demography/arrivals_soe.csv
- [Official catalogue metadata](https://data.gov.my/data-catalogue/arrivals_soe)

## Coverage

Malaysia.

## Schema

Refer to the [official catalogue field definitions](https://data.gov.my/data-catalogue/arrivals_soe) before analysis. The machine-readable envelope records fields observed from the source.

## Known quirks

- Official catalogue caveat: This data is based solely on records in MyIMMS. Furthermore, it should be noted that approximately 0.01% of arrivals do not have a nationality specified, including stateless individuals and refugees.

## Breaking changes

None observed.

## Reproducibility

    curl -sS --max-time 30 "https://storage.data.gov.my/demography/arrivals_soe.csv" | head

## Licence

Licensed under Open Government Licence (Malaysia).
Attribution: Immigration Department of Malaysia via data.gov.my.
