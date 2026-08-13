---
dataset_id: dgm_arrivals
last_checked: 2026-08-11T14:21:08Z
last_checked: 2026-08-11T14:21:08Z
status: stale
freshness_delta: 679 days
next_expected_update: monthly
record_count: 13050
schema_version: unknown
schema_drift: none
known_quirks: ["Official catalogue caveat: This data is based solely on records in MyIMMS. Furthermore, it should be noted that approximately 0.01% of arrivals do not have a nationality specified, including stateless individuals and refugees."]
breaking_changes: []
licence: Open Government Licence (Malaysia)
attribution: Immigration Department of Malaysia via data.gov.my
---

# Monthly Arrivals by Nationality & Sex

## Status

**Status:** Stale

**Freshness:** 679 days

HTTP 200

## Last checked

2026-08-11 at 14:21:08 UTC.

## File size

The checked resource is 1,327,635 bytes.

## Provenance

Immigration Department of Malaysia publishes this dataset through data.gov.my (OpenAPI).

- Source: https://api.data.gov.my/data-catalogue?id=arrivals
- [Official catalogue metadata](https://data.gov.my/data-catalogue/arrivals)

## Coverage

Malaysia.

## Schema

Refer to the [official catalogue field definitions](https://data.gov.my/data-catalogue/arrivals) before analysis. The machine-readable envelope records fields observed from the source.

## Known quirks

- Official catalogue caveat: This data is based solely on records in MyIMMS. Furthermore, it should be noted that approximately 0.01% of arrivals do not have a nationality specified, including stateless individuals and refugees.

## Breaking changes

None observed.

## Reproducibility

    curl -sS --max-time 30 "https://api.data.gov.my/data-catalogue?id=arrivals" | head

## Licence

Licensed under Open Government Licence (Malaysia).
Attribution: Immigration Department of Malaysia via data.gov.my.
