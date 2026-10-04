---
id: "ridership_od_komuter"
title: "KTMB Komuter Origin-Destination Ridership"
source_url: "https://storage.data.gov.my/transportation/ktmb/komuter_2026.csv"
source_name: "data.gov.my"
licence: "Creative Commons Attribution 4.0"
refresh_frequency: "daily"
last_checked: 2026-10-03T15:47:47Z
last_observed: 2026-10-02
last_modified: 2026-10-02T19:31:32Z
record_count: 1355591
column_count: 5
status: aging
notes: "Tier-1 wave F newly verified direct-storage source; HTTP 200 and CSV header verified."
dataset_id: ridership_od_komuter
freshness_delta: 2 days
next_expected_update: "daily"
schema_version: 1.0
schema_drift: none
known_quirks: []
breaking_changes: []
attribution: "Keretapi Tanah Melayu Berhad via data.gov.my"
---

# KTMB Komuter Origin-Destination Ridership

## Status

**Status:** Aging

**Freshness:** 2 days

HTTP 200

## Last checked

2026-10-03 at 15:47:47 UTC.

## File size

The checked resource is 55,963,716 bytes.

## Provenance

Keretapi Tanah Melayu Berhad publishes this dataset through data.gov.my:

- `https://storage.data.gov.my/transportation/ktmb/komuter_2026.csv`

## Coverage

Malaysia. Latest source observation: 2026-08-07.

## Schema

The verified CSV contains 5 columns: `date`, `time`, `origin`, `destination`, `ridership`.

## Known quirks

- The serving filename rotates by UTC year; the health probe resolves it at runtime.

## Reproducibility

```sh
curl -sS -I "https://storage.data.gov.my/transportation/ktmb/komuter_2026.csv"
curl -sS "https://storage.data.gov.my/transportation/ktmb/komuter_2026.csv" | head -1
```

## Licence

Licensed under Creative Commons Attribution 4.0. Attribution: Keretapi Tanah Melayu Berhad via data.gov.my.
