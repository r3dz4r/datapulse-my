---
id: "payment_instruments"
title: "Monthly Payment Instruments"
source_url: "https://storage.data.gov.my/finsector/payments/instruments.csv"
source_name: "data.gov.my"
licence: "Creative Commons Attribution 4.0"
refresh_frequency: "monthly"
last_checked: 2026-08-30T02:16:30Z
last_observed: 2026-06-01
last_modified: 2026-08-20T09:32:23Z
record_count: 720
column_count: 4
status: aging
notes: "Tier-1 wave B already-active confirmation; HTTP 200 and CSV header verified."
dataset_id: payment_instruments
freshness_delta: 90 days
next_expected_update: "monthly"
schema_version: 1.0
schema_drift: none
known_quirks: []
breaking_changes: []
attribution: "Bank Negara Malaysia via data.gov.my"
---

# Monthly Payment Instruments

## Status

**Status:** Aging

**Freshness:** 90 days

HTTP 200

## Last checked

2026-08-30 at 02:16:30 UTC.

## File size

The checked resource is 34,368 bytes.

## Provenance

Bank Negara Malaysia publishes this dataset through data.gov.my:

- `https://storage.data.gov.my/finsector/payments/instruments.csv`

## Coverage

Malaysia. Latest source observation: 2026-02-01.

## Schema

The verified CSV contains 4 columns: `date`, `instrument`, `value`, `volume`.

## Known quirks

- No additional source-specific quirks were established during reachability verification.

## Reproducibility

```sh
curl -sS -I "https://storage.data.gov.my/finsector/payments/instruments.csv"
curl -sS "https://storage.data.gov.my/finsector/payments/instruments.csv" | head -1
```

## Licence

Licensed under Creative Commons Attribution 4.0. Attribution: Bank Negara Malaysia via data.gov.my.
