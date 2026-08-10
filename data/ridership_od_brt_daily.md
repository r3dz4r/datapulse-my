---
dataset_id: ridership_od_brt_daily
last_checked: 2026-08-10T10:07:26Z
last_checked: 2026-08-10T10:07:26Z
status: aging
freshness_delta: 3 days
next_expected_update: daily
record_count: 13578
schema_version: unknown
schema_drift: none
known_quirks: ["The serving filename rotates by UTC year; the health probe resolves it at runtime."]
breaking_changes: []
licence: Open Government Licence (Malaysia)
attribution: Prasarana Malaysia Berhad and Ministry of Transport via data.gov.my
---

# Daily Origin-Destination Ridership: BRT Sunway Line

## Status

**Status:** Aging

**Freshness:** 3 days

HTTP 200

## Last checked

2026-08-10 at 10:07:26 UTC.

## File size

The checked resource is 710,742 bytes.

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
