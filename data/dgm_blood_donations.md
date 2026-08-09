---
dataset_id: dgm_blood_donations
last_checked: 2026-08-09T05:30:41Z
last_checked: 2026-08-09T05:30:41Z
status: unknown-freshness
freshness_delta: unknown
next_expected_update: daily
record_count: 37625
schema_version: unknown
schema_drift: none
known_quirks: ["Official catalogue caveat: The true number of daily blood donations is higher than the number recorded in this dataset, which does not reflect donations made at locations other than the 22 main sites integrated with BBISv2. However, the 22 main sites cover the large majority of blood donations in Malaysia (~80%), and therefore provide a representative view of blood donation trends."]
breaking_changes: []
licence: Open Government Licence (Malaysia)
attribution: National Blood Centre and Ministry of Health Malaysia via data.gov.my
---

# Daily Blood Donations by Blood Group

## Status

**Status:** Unknown freshness

**Freshness:** unknown

HTTP 200

## Last checked

2026-08-09 at 05:30:41 UTC.

## File size

The checked resource is 2,316,671 bytes.

## Provenance

National Blood Centre and Ministry of Health Malaysia publishes this dataset through data.gov.my (OpenAPI).

- Source: https://api.data.gov.my/data-catalogue?id=blood_donations
- [Official catalogue metadata](https://data.gov.my/data-catalogue/blood_donations)

## Coverage

Malaysia.

## Schema

Refer to the [official catalogue field definitions](https://data.gov.my/data-catalogue/blood_donations) before analysis. The machine-readable envelope records fields observed from the source.

## Known quirks

- Official catalogue caveat: The true number of daily blood donations is higher than the number recorded in this dataset, which does not reflect donations made at locations other than the 22 main sites integrated with BBISv2. However, the 22 main sites cover the large majority of blood donations in Malaysia (~80%), and therefore provide a representative view of blood donation trends.

## Breaking changes

None observed.

## Reproducibility

    curl -sS --max-time 30 "https://api.data.gov.my/data-catalogue?id=blood_donations" | head

## Licence

Licensed under Open Government Licence (Malaysia).
Attribution: National Blood Centre and Ministry of Health Malaysia via data.gov.my.
