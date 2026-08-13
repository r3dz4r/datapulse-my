---
id: "ridership_od_komuter_utara"
title: "KTMB Komuter Utara Origin-Destination Ridership"
source_url: "https://storage.data.gov.my/transportation/ktmb/komuter_utara_2026.csv"
source_name: "data.gov.my"
licence: "Creative Commons Attribution 4.0"
refresh_frequency: "daily"
last_checked: 2026-08-12T16:16:35Z
last_observed: 2026-08-11
last_modified: 2026-08-11T19:31:31Z
record_count: 889373
column_count: 5
status: fresh
notes: "Tier-1 wave F newly verified direct-storage source; HTTP 200 and CSV header verified."
dataset_id: ridership_od_komuter_utara
freshness_delta: 1 days
next_expected_update: "daily"
schema_version: 1.0
schema_drift: none
known_quirks: []
breaking_changes: []
attribution: "Keretapi Tanah Melayu Berhad via data.gov.my"
---

# KTMB Komuter Utara Origin-Destination Ridership

## Status

**Status:** Fresh

**Freshness:** 1 days

HTTP 200

## Last checked

2026-08-12 at 16:16:35 UTC.

## File size

The checked resource is 36,469,902 bytes.

## Provenance

Keretapi Tanah Melayu Berhad publishes this dataset through data.gov.my:

- `https://storage.data.gov.my/transportation/ktmb/komuter_utara_2026.csv`

## Coverage

Malaysia. Latest source observation: 2026-08-07.

## Schema

The verified CSV contains 5 columns: `date`, `time`, `origin`, `destination`, `ridership`.

## Known quirks

- The serving filename rotates by UTC year; the health probe resolves it at runtime.

## Reproducibility

```sh
curl -sS -I "https://storage.data.gov.my/transportation/ktmb/komuter_utara_2026.csv"
curl -sS "https://storage.data.gov.my/transportation/ktmb/komuter_utara_2026.csv" | head -1
```

## Licence

Licensed under Creative Commons Attribution 4.0. Attribution: Keretapi Tanah Melayu Berhad via data.gov.my.
