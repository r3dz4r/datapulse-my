---
dataset_id: registration_transactions_motorcycle
last_checked: 2026-08-09T05:30:41Z
last_checked: 2026-08-09T05:30:41Z
status: stale
freshness_delta: 40 days
next_expected_update: daily
record_count: 391481
schema_version: unknown
schema_drift: none
known_quirks: ["Official catalogue caveat: This dataset captures the registration of motorcycles, not the sale or import or any other transaction. Therefore, if a motorcycle is not registered for use on the road, it will not be present in this dataset (e.g. motorcycles which are purchased purely for private display). Furthermore, it should be noted that this dataset was extremely difficult to prepare, especially for data from the early 2000s when data collection systems were not as sophisticated as they are now. Accordingly, if you spot any errors in the dataset or have any suggestions to improve its quality, please write to help.dtsa@jdn.gov.my so the data.gov.my team can work with JPJ to fix or improve it as soon as possible.", "The serving filename rotates by UTC year; the health probe resolves it at runtime."]
breaking_changes: []
licence: Open Government Licence (Malaysia)
attribution: Road Transport Department Malaysia and Ministry of Transport via data.gov.my
---

# Motorcycle Registration Transactions

## Status

**Status:** Stale

**Freshness:** 40 days

HTTP 200

## Last checked

2026-08-09 at 05:30:41 UTC.

## File size

The checked resource is 20,468,271 bytes.

## Provenance

Road Transport Department Malaysia and Ministry of Transport publishes this dataset through data.gov.my (storage).

- Source: https://storage.data.gov.my/transportation/motorcycles_2026.csv
- [Official catalogue metadata](https://data.gov.my/data-catalogue/registration_transactions_motorcycle)

## Coverage

Malaysia.

## Schema

Refer to the [official catalogue field definitions](https://data.gov.my/data-catalogue/registration_transactions_motorcycle) before analysis. The machine-readable envelope records fields observed from the source.

## Known quirks

- Official catalogue caveat: This dataset captures the registration of motorcycles, not the sale or import or any other transaction. Therefore, if a motorcycle is not registered for use on the road, it will not be present in this dataset (e.g. motorcycles which are purchased purely for private display). Furthermore, it should be noted that this dataset was extremely difficult to prepare, especially for data from the early 2000s when data collection systems were not as sophisticated as they are now. Accordingly, if you spot any errors in the dataset or have any suggestions to improve its quality, please write to help.dtsa@jdn.gov.my so the data.gov.my team can work with JPJ to fix or improve it as soon as possible.
- The serving filename rotates by UTC year; the health probe resolves it at runtime.

## Breaking changes

None observed.

## Reproducibility

    curl -sS --max-time 30 "https://storage.data.gov.my/transportation/motorcycles_2026.csv" | head

## Licence

Licensed under Open Government Licence (Malaysia).
Attribution: Road Transport Department Malaysia and Ministry of Transport via data.gov.my.
