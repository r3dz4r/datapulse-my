---
dataset_id: ridership_od_brt_daily
last_checked: 2026-09-06T11:34:39Z
last_checked: 2026-09-06T11:34:39Z
status: stale
freshness_delta: 13 days
next_expected_update: daily
record_count: 14632
schema_version: unknown
schema_drift: none
known_quirks: ["The serving filename rotates by UTC year; the health probe resolves it at runtime."]
breaking_changes: []
licence: Open Government Licence (Malaysia)
attribution: Prasarana Malaysia Berhad and Ministry of Transport via data.gov.my
---

# Daily Origin-Destination Ridership: BRT Sunway Line

## Status

**Status:** Stale

**Freshness:** 13 days

HTTP 200

## Last checked

2026-09-06 at 11:34:39 UTC.

## File size

The checked resource is 765,938 bytes.

## Provenance

Prasarana Malaysia Berhad and Ministry of Transport publishes this dataset through data.gov.my (storage).

- Source: https://storage.data.gov.my/transportation/bus/brt_2026_daily.csv
- [Official catalogue metadata](https://data.gov.my/data-catalogue/ridership_od_brt_daily)

## Coverage

Malaysia.

## Schema

Refer to the [official catalogue field definitions](https://data.gov.my/data-catalogue/ridership_od_brt_daily) before analysis. The machine-readable envelope records fields observed from the source.

## Known quirks

- The serving filename rotates by UTC year; the health probe resolves it at runtime.

## Breaking changes

None observed.

## Reproducibility

    curl -sS --max-time 30 "https://storage.data.gov.my/transportation/bus/brt_2026_daily.csv" | head

## Licence

Licensed under Open Government Licence (Malaysia).
Attribution: Prasarana Malaysia Berhad and Ministry of Transport via data.gov.my.
