---
id: "interestrates"
title: "Monthly Interest Rates"
source_url: "https://storage.data.gov.my/finsector/interest_rates.csv"
source_name: "data.gov.my"
licence: "Creative Commons Attribution 4.0"
refresh_frequency: "monthly"
last_checked: 2026-08-16T02:09:20Z
last_observed: 2026-02-01
last_modified: 2026-04-05T20:22:59Z
record_count: 5712
column_count: 4
status: stale
notes: "Tier-1 wave A already-active confirmation; HTTP 200 and CSV header verified."
dataset_id: interestrates
freshness_delta: 196 days
next_expected_update: "monthly"
schema_version: 1.0
schema_drift: none
known_quirks: []
breaking_changes: []
attribution: "Bank Negara Malaysia via data.gov.my"
---

# Monthly Interest Rates

## Status

**Status:** Stale

**Freshness:** 196 days

HTTP 200

## Last checked

2026-08-16 at 02:09:20 UTC.

## File size

The checked resource is 228,401 bytes.

## Provenance

Bank Negara Malaysia publishes this dataset through data.gov.my:

- `https://storage.data.gov.my/finsector/interest_rates.csv`

## Coverage

Malaysia. Latest source observation: 2026-02-01.

## Schema

The verified CSV contains 4 columns: `date`, `bank`, `rate`, `value`.

## Known quirks

- No additional source-specific quirks were established during reachability verification.

## Reproducibility

```sh
curl -sS -I "https://storage.data.gov.my/finsector/interest_rates.csv"
curl -sS "https://storage.data.gov.my/finsector/interest_rates.csv" | head -1
```

## Licence

Licensed under Creative Commons Attribution 4.0. Attribution: Bank Negara Malaysia via data.gov.my.
