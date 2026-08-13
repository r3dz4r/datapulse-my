---
id: "payment_channels"
title: "Monthly Payment Channels"
source_url: "https://storage.data.gov.my/finsector/payments/channels.csv"
source_name: "data.gov.my"
licence: "Creative Commons Attribution 4.0"
refresh_frequency: "monthly"
last_checked: 2026-08-13T02:46:04Z
last_observed: 2026-02-01
last_modified: 2026-04-05T20:29:19Z
record_count: 430
column_count: 4
status: stale
notes: "Tier-1 wave B already-active confirmation; HTTP 200 and CSV header verified."
dataset_id: payment_channels
freshness_delta: 193 days
next_expected_update: "monthly"
schema_version: 1.0
schema_drift: none
known_quirks: []
breaking_changes: []
attribution: "Bank Negara Malaysia via data.gov.my"
---

# Monthly Payment Channels

## Status

**Status:** Stale

**Freshness:** 193 days

HTTP 200

## Last checked

2026-08-13 at 02:46:04 UTC.

## File size

The checked resource is 20,990 bytes.

## Provenance

Bank Negara Malaysia publishes this dataset through data.gov.my:

- `https://storage.data.gov.my/finsector/payments/channels.csv`

## Coverage

Malaysia. Latest source observation: 2026-02-01.

## Schema

The verified CSV contains 4 columns: `date`, `channel`, `value`, `volume`.

## Known quirks

- No additional source-specific quirks were established during reachability verification.

## Reproducibility

```sh
curl -sS -I "https://storage.data.gov.my/finsector/payments/channels.csv"
curl -sS "https://storage.data.gov.my/finsector/payments/channels.csv" | head -1
```

## Licence

Licensed under Creative Commons Attribution 4.0. Attribution: Bank Negara Malaysia via data.gov.my.
