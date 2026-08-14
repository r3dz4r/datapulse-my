---
dataset_id: ridership_od_rapidrail_daily
last_checked: 2026-08-14T04:59:27Z
status: stale
freshness_delta: 7 days
next_expected_update: daily
record_count: 3656037
schema_version: unknown
schema_drift: none
known_quirks: ["Official catalogue caveat: Because the size of the complete dataset for each year since 2023 exceeds the row limit of Microsoft Excel (1,048,576), we recommend working with the data programatically, preferably using the parquet files provided.", "The serving filename rotates by UTC year; the health probe resolves it at runtime."]
breaking_changes: []
licence: Open Government Licence (Malaysia)
attribution: Prasarana Malaysia Berhad and Ministry of Transport via data.gov.my
---

# Daily Origin-Destination Ridership: Rapid Rail (KV)

## Status

**Status:** Stale

**Freshness:** 7 days

HTTP 200

## Last checked

2026-08-14 at 04:59:27 UTC.

## File size

The checked resource is 183,490,345 bytes.

## Provenance

Prasarana Malaysia Berhad and Ministry of Transport publishes this dataset through data.gov.my (storage).

- Source: https://storage.data.gov.my/transportation/rail/rapidrail_2026_daily.csv
- [Official catalogue metadata](https://data.gov.my/data-catalogue/ridership_od_rapidrail_daily)

## Coverage

Malaysia.

## Schema

Refer to the [official catalogue field definitions](https://data.gov.my/data-catalogue/ridership_od_rapidrail_daily) before analysis. The machine-readable envelope records fields observed from the source.

## Known quirks

- Official catalogue caveat: Because the size of the complete dataset for each year since 2023 exceeds the row limit of Microsoft Excel (1,048,576), we recommend working with the data programatically, preferably using the parquet files provided.
- The serving filename rotates by UTC year; the health probe resolves it at runtime.

## Breaking changes

None observed.

## Reproducibility

    curl -sS --max-time 30 "https://storage.data.gov.my/transportation/rail/rapidrail_2026_daily.csv" | head

## Licence

Licensed under Open Government Licence (Malaysia).
Attribution: Prasarana Malaysia Berhad and Ministry of Transport via data.gov.my.
