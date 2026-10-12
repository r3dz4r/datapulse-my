---
id: "ridership_ktmb_daily"
title: "Daily KTMB Ridership"
source_url: "https://storage.data.gov.my/transportation/ktmb/ridership_ktmb_daily.csv"
source_name: "data.gov.my"
licence: "Creative Commons Attribution 4.0"
refresh_frequency: "daily"
last_checked: 2026-10-11T16:55:05Z
last_observed: 2026-10-10
last_modified: 2026-10-10T19:31:40Z
record_count: 9263
column_count: 3
status: aging
notes: "Tier-1 wave C already-active confirmation; HTTP 200 and CSV header verified."
dataset_id: ridership_ktmb_daily
freshness_delta: 2 days
next_expected_update: "daily"
schema_version: 1.0
schema_drift: none
known_quirks: []
breaking_changes: []
attribution: "Keretapi Tanah Melayu Berhad via data.gov.my"
---

# Daily KTMB Ridership

## Status

**Status:** Aging

**Freshness:** 2 days

HTTP 200

## Last checked

2026-10-11 at 16:55:05 UTC.

## File size

The checked resource is 245,298 bytes.

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
