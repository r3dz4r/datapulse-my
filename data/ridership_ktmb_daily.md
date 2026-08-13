---
id: "ridership_ktmb_daily"
title: "Daily KTMB Ridership"
source_url: "https://storage.data.gov.my/transportation/ktmb/ridership_ktmb_daily.csv"
source_name: "data.gov.my"
licence: "Creative Commons Attribution 4.0"
refresh_frequency: "daily"
last_checked: 2026-08-12T16:16:35Z
last_observed: 2026-08-11
last_modified: 2026-08-11T19:31:34Z
record_count: 8963
column_count: 3
status: fresh
notes: "Tier-1 wave C already-active confirmation; HTTP 200 and CSV header verified."
dataset_id: ridership_ktmb_daily
freshness_delta: 1 days
next_expected_update: "daily"
schema_version: 1.0
schema_drift: none
known_quirks: []
breaking_changes: []
attribution: "Keretapi Tanah Melayu Berhad via data.gov.my"
---

# Daily KTMB Ridership

## Status

**Status:** Fresh

**Freshness:** 1 days

HTTP 200

## Last checked

2026-08-12 at 16:16:35 UTC.

## File size

The checked resource is 237,260 bytes.

## Provenance

Keretapi Tanah Melayu Berhad publishes this dataset through data.gov.my:

- `https://storage.data.gov.my/transportation/ktmb/ridership_ktmb_daily.csv`

## Coverage

Malaysia. Latest source observation: 2026-08-07.

## Schema

The verified CSV contains 3 columns: `date`, `service`, `ridership`.

## Known quirks

- No additional source-specific quirks were established during reachability verification.

## Reproducibility

```sh
curl -sS -I "https://storage.data.gov.my/transportation/ktmb/ridership_ktmb_daily.csv"
curl -sS "https://storage.data.gov.my/transportation/ktmb/ridership_ktmb_daily.csv" | head -1
```

## Licence

Licensed under Creative Commons Attribution 4.0. Attribution: Keretapi Tanah Melayu Berhad via data.gov.my.
