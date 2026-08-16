---
id: "pharmaceutical_products_cancelled"
title: "Cancelled Pharmaceutical Product Registrations"
source_url: "https://storage.data.gov.my/healthcare/pharmaceutical_products_cancelled.csv"
source_name: "data.gov.my"
licence: "Creative Commons Attribution 4.0"
refresh_frequency: "monthly"
last_checked: 2026-08-16T02:09:20Z
last_observed: 2026-04-24
last_modified: 2026-08-15T23:50:56Z
record_count: 1597
column_count: 7
status: stale
notes: "Tier-1 wave E newly verified direct-storage source; HTTP 200 and CSV header verified."
dataset_id: pharmaceutical_products_cancelled
freshness_delta: 114 days
next_expected_update: "monthly"
schema_version: 1.0
schema_drift: none
known_quirks: []
breaking_changes: []
attribution: "National Pharmaceutical Regulatory Agency via data.gov.my"
---

# Cancelled Pharmaceutical Product Registrations

## Status

**Status:** Stale

**Freshness:** 114 days

HTTP 200

## Last checked

2026-08-16 at 02:09:20 UTC.

## File size

The checked resource is 219,907 bytes.

## Provenance

National Pharmaceutical Regulatory Agency publishes this dataset through data.gov.my:

- `https://storage.data.gov.my/healthcare/pharmaceutical_products_cancelled.csv`

## Coverage

Malaysia. Latest source observation: 2026-02-19.

## Schema

The verified CSV contains 7 columns: `reg_no`, `product`, `description`, `holder`, `manufacturer`, `date_reg`, `date_end`.

## Known quirks

- No additional source-specific quirks were established during reachability verification.

## Reproducibility

```sh
curl -sS -I "https://storage.data.gov.my/healthcare/pharmaceutical_products_cancelled.csv"
curl -sS "https://storage.data.gov.my/healthcare/pharmaceutical_products_cancelled.csv" | head -1
```

## Licence

Licensed under Creative Commons Attribution 4.0. Attribution: National Pharmaceutical Regulatory Agency via data.gov.my.
