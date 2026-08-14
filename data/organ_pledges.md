---
dataset_id: dgm_organ_pledges
last_checked: 2026-08-14T04:59:27Z
last_checked: 2026-08-14T04:59:27Z
status: stale
freshness_delta: 40 days
next_expected_update: daily
record_count: 6382
schema_version: unknown
schema_drift: none
known_quirks: ["Official catalogue caveat: The digital organ donation pledge process allows an individual to pledge their organs, and subsequently withdraw their pledge if they so choose. Therefore, the data shown here is dynamic; the number of pledges for a specific date may reduce (but not increase) in future if pledges are withdrawn."]
breaking_changes: []
licence: Open Government Licence (Malaysia)
attribution: National Transplant Resource Centre and Ministry of Health Malaysia via data.gov.my
---

# Daily Organ Donation Pledges

## Status

**Status:** Stale

**Freshness:** 40 days

HTTP 200

## Last checked

2026-08-14 at 04:59:27 UTC.

## File size

The checked resource is 248,976 bytes.

## Provenance

National Transplant Resource Centre and Ministry of Health Malaysia publishes this dataset through data.gov.my (OpenAPI).

- Source: https://api.data.gov.my/data-catalogue?id=organ_pledges
- [Official catalogue metadata](https://data.gov.my/data-catalogue/organ_pledges)

## Coverage

Malaysia.

## Schema

Refer to the [official catalogue field definitions](https://data.gov.my/data-catalogue/organ_pledges) before analysis. The machine-readable envelope records fields observed from the source.

## Known quirks

- Official catalogue caveat: The digital organ donation pledge process allows an individual to pledge their organs, and subsequently withdraw their pledge if they so choose. Therefore, the data shown here is dynamic; the number of pledges for a specific date may reduce (but not increase) in future if pledges are withdrawn.

## Breaking changes

None observed.

## Reproducibility

    curl -sS --max-time 30 "https://api.data.gov.my/data-catalogue?id=organ_pledges" | head

## Licence

Licensed under Open Government Licence (Malaysia).
Attribution: National Transplant Resource Centre and Ministry of Health Malaysia via data.gov.my.
