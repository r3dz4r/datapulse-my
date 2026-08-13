---
dataset_id: registration_transactions_car
last_checked: 2026-08-12T16:16:35Z
last_checked: 2026-08-12T16:16:35Z
status: stale
freshness_delta: 12 days
next_expected_update: daily
record_count: 489340
schema_version: unknown
schema_drift: none
known_quirks: ["Official catalogue caveat: This dataset captures the registration of cars, not the sale or import or any other transaction. Therefore, if a car is not registered for use on the road, it will not be present in this dataset (e.g. cars which are purchased purely for private display). Furthermore, it should be noted that this dataset was extremely difficult to prepare, especially for data from the early 2000s when data collection systems were not as sophisticated as they are now. Accordingly, if you spot any errors in the dataset or have any suggestions to improve its quality, please write to help.dtsa@jdn.gov.my so the data.gov.my team can work with JPJ to fix or improve it as soon as possible.", "The serving filename rotates by UTC year; the health probe resolves it at runtime."]
breaking_changes: []
licence: Open Government Licence (Malaysia)
attribution: Road Transport Department Malaysia and Ministry of Transport via data.gov.my
---

# Car Registration Transactions

## Status

**Status:** Stale

**Freshness:** 12 days

HTTP 200

## Last checked

2026-08-12 at 16:16:35 UTC.

## File size

The checked resource is 28,186,891 bytes.

## Provenance

Road Transport Department Malaysia and Ministry of Transport publishes this dataset through data.gov.my (storage).

- Source: https://storage.data.gov.my/transportation/cars_2026.csv
- [Official catalogue metadata](https://data.gov.my/data-catalogue/registration_transactions_car)

## Coverage

Malaysia.

## Schema

Refer to the [official catalogue field definitions](https://data.gov.my/data-catalogue/registration_transactions_car) before analysis. The machine-readable envelope records fields observed from the source.

## Known quirks

- Official catalogue caveat: This dataset captures the registration of cars, not the sale or import or any other transaction. Therefore, if a car is not registered for use on the road, it will not be present in this dataset (e.g. cars which are purchased purely for private display). Furthermore, it should be noted that this dataset was extremely difficult to prepare, especially for data from the early 2000s when data collection systems were not as sophisticated as they are now. Accordingly, if you spot any errors in the dataset or have any suggestions to improve its quality, please write to help.dtsa@jdn.gov.my so the data.gov.my team can work with JPJ to fix or improve it as soon as possible.
- The serving filename rotates by UTC year; the health probe resolves it at runtime.

## Breaking changes

None observed.

## Reproducibility

    curl -sS --max-time 30 "https://storage.data.gov.my/transportation/cars_2026.csv" | head

## Licence

Licensed under Open Government Licence (Malaysia).
Attribution: Road Transport Department Malaysia and Ministry of Transport via data.gov.my.
