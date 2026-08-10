---
id: "ridership_od_intercity"
title: "KTMB Intercity Origin-Destination Ridership"
source_url: "https://storage.data.gov.my/transportation/ktmb/intercity_2026.csv"
source_name: "data.gov.my"
licence: "Creative Commons Attribution 4.0"
refresh_frequency: "daily"
last_checked: 2026-08-09T08:37:11Z
last_observed: 2026-08-08
last_modified: 2026-08-08T20:31:20Z
record_count: 121962
column_count: 5
status: fresh
notes: "Tier-1 wave F newly verified direct-storage source; HTTP 200 and CSV header verified."
dataset_id: ridership_od_intercity
freshness_delta: 1 days
next_expected_update: "daily"
schema_version: 1.0
schema_drift: none
known_quirks: []
breaking_changes: []
attribution: "Keretapi Tanah Melayu Berhad via data.gov.my"
---

# KTMB Intercity Origin-Destination Ridership

## Status

**Status:** Fresh

**Freshness:** 1 days

HTTP 200

## Last checked

2026-08-09 at 08:37:11 UTC.

## File size

The checked resource is 4,639,020 bytes.

## Provenance

Keretapi Tanah Melayu Berhad publishes this dataset through data.gov.my:

- `https://storage.data.gov.my/transportation/ktmb/intercity_2026.csv`

## Coverage

Malaysia. Latest source observation: 2026-08-07.

## Schema

The verified CSV contains 5 columns: `date`, `time`, `origin`, `destination`, `ridership`.

## Known quirks

- The serving filename rotates by UTC year; the health probe resolves it at runtime.

## Reproducibility

```sh
curl -sS -I "https://storage.data.gov.my/transportation/ktmb/intercity_2026.csv"
curl -sS "https://storage.data.gov.my/transportation/ktmb/intercity_2026.csv" | head -1
```

## Licence

Licensed under Creative Commons Attribution 4.0. Attribution: Keretapi Tanah Melayu Berhad via data.gov.my.
