---
id: "payment_instruments"
title: "Monthly Payment Instruments"
source_url: "https://storage.data.gov.my/finsector/payments/instruments.csv"
source_name: "data.gov.my"
licence: "Creative Commons Attribution 4.0"
refresh_frequency: "monthly"
last_checked: 2026-08-10T04:08:14Z
last_observed: 2026-02-01
last_modified: 2026-04-05T20:29:22Z
record_count: 688
column_count: 4
status: stale
notes: "Tier-1 wave B already-active confirmation; HTTP 200 and CSV header verified."
dataset_id: payment_instruments
freshness_delta: 190 days
next_expected_update: "monthly"
schema_version: 1.0
schema_drift: none
known_quirks: []
breaking_changes: []
attribution: "Bank Negara Malaysia via data.gov.my"
---

# Monthly Payment Instruments

## Status

**Status:** Stale

**Freshness:** 190 days

HTTP 200

## Last checked

2026-08-10 at 04:08:14 UTC.

## File size

The checked resource is 32,818 bytes.

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
