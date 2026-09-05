---
id: "monetary_aggregates"
title: "Monthly Monetary Aggregates"
source_url: "https://storage.data.gov.my/finsector/money_aggregates.csv"
source_name: "data.gov.my"
licence: "Creative Commons Attribution 4.0"
refresh_frequency: "monthly"
last_checked: 2026-08-30T02:16:30Z
last_observed: 2026-06-01
last_modified: 2026-08-20T09:23:25Z
record_count: 1944
column_count: 3
status: aging
notes: "Tier-1 wave A already-active confirmation; HTTP 200 and CSV header verified."
dataset_id: monetary_aggregates
freshness_delta: 90 days
next_expected_update: "monthly"
schema_version: 1.0
schema_drift: none
known_quirks: []
breaking_changes: []
attribution: "Bank Negara Malaysia via data.gov.my"
---

# Monthly Monetary Aggregates

## Status

**Status:** Aging

**Freshness:** 90 days

HTTP 200

## Last checked

2026-08-30 at 02:16:30 UTC.

## File size

The checked resource is 77,493 bytes.

## Provenance

Bank Negara Malaysia publishes this dataset through data.gov.my:

- `https://storage.data.gov.my/finsector/money_aggregates.csv`

## Coverage

Malaysia. Latest source observation: 2026-02-01.

## Schema

The verified CSV contains 3 columns: `date`, `measure`, `value`.

## Known quirks

- No additional source-specific quirks were established during reachability verification.

## Reproducibility

```sh
curl -sS -I "https://storage.data.gov.my/finsector/money_aggregates.csv"
curl -sS "https://storage.data.gov.my/finsector/money_aggregates.csv" | head -1
```

## Licence

Licensed under Creative Commons Attribution 4.0. Attribution: Bank Negara Malaysia via data.gov.my.
