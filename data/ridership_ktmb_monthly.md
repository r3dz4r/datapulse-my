---
id: "ridership_ktmb_monthly"
title: "Monthly KTMB Ridership"
source_url: "https://storage.data.gov.my/transportation/ktmb/ridership_ktmb_monthly.csv"
source_name: "data.gov.my"
licence: "Creative Commons Attribution 4.0"
refresh_frequency: "monthly"
last_checked: 2026-08-13T02:46:04Z
last_observed: 2026-07-01
last_modified: 2026-08-12T19:31:37Z
record_count: 290
column_count: 3
status: fresh
notes: "Tier-1 wave C already-active confirmation; HTTP 200 and CSV header verified."
dataset_id: ridership_ktmb_monthly
freshness_delta: 43 days
next_expected_update: "monthly"
schema_version: 1.0
schema_drift: none
known_quirks: []
breaking_changes: []
attribution: "Keretapi Tanah Melayu Berhad via data.gov.my"
---

# Monthly KTMB Ridership

## Status

**Status:** Fresh

**Freshness:** 43 days

HTTP 200

## Last checked

2026-08-13 at 02:46:04 UTC.

## File size

The checked resource is 8,136 bytes.

## Provenance

Keretapi Tanah Melayu Berhad publishes this dataset through data.gov.my:

- `https://storage.data.gov.my/transportation/ktmb/ridership_ktmb_monthly.csv`

## Coverage

Malaysia. Latest source observation: 2026-07-01.

## Schema

The verified CSV contains 3 columns: `date`, `service`, `ridership`.

## Known quirks

- No additional source-specific quirks were established during reachability verification.

## Reproducibility

```sh
curl -sS -I "https://storage.data.gov.my/transportation/ktmb/ridership_ktmb_monthly.csv"
curl -sS "https://storage.data.gov.my/transportation/ktmb/ridership_ktmb_monthly.csv" | head -1
```

## Licence

Licensed under Creative Commons Attribution 4.0. Attribution: Keretapi Tanah Melayu Berhad via data.gov.my.
