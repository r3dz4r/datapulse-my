---
id: "exchangerates"
title: "Monthly Exchange Rates"
source_url: "https://storage.data.gov.my/finsector/exr/monthly.csv"
source_name: "data.gov.my"
licence: "Creative Commons Attribution 4.0"
refresh_frequency: "monthly"
last_checked: 2026-10-03T10:36:37Z
last_observed: 2026-09-01
last_modified: 2026-09-30T18:30:05Z
record_count: 1785
column_count: 29
status: fresh
notes: "Tier-1 wave A already-active confirmation; HTTP 200 and CSV header verified."
dataset_id: exchangerates
freshness_delta: 36 days
next_expected_update: "monthly"
schema_version: 1.0
schema_drift: none
known_quirks: []
breaking_changes: []
attribution: "Bank Negara Malaysia via data.gov.my"
---

# Monthly Exchange Rates

## Status

**Status:** Fresh

**Freshness:** 36 days

HTTP 200

## Last checked

2026-10-03 at 10:36:37 UTC.

## File size

The checked resource is 346,229 bytes.

## Provenance

Bank Negara Malaysia publishes this dataset through data.gov.my:

- `https://storage.data.gov.my/finsector/exr/monthly.csv`

## Coverage

Malaysia. Latest source observation: 2026-03-01.

## Schema

The verified CSV contains 29 columns: `date`, `indicator`, `USD`, `EUR`, `JPY`, `GBP`, `SGD`, `AUD`, `CAD`, `CNY`, `CHF`, `THB`, `IDR`, `VND`, `KHR`, `MMK`, `PHP`, `BND`, `KRW`, `HKD`, `TWD`, `INR`, `PKR`, `NPR`, `SAR`, `AED`, `EGP`, `NZD`, `XDR`.

## Known quirks

- No additional source-specific quirks were established during reachability verification.

## Reproducibility

```sh
curl -sS -I "https://storage.data.gov.my/finsector/exr/monthly.csv"
curl -sS "https://storage.data.gov.my/finsector/exr/monthly.csv" | head -1
```

## Licence

Licensed under Creative Commons Attribution 4.0. Attribution: Bank Negara Malaysia via data.gov.my.
