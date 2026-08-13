---
id: "pharmaceutical_products_cancelled"
title: "Cancelled Pharmaceutical Product Registrations"
source_url: "https://storage.data.gov.my/healthcare/pharmaceutical_products_cancelled.csv"
source_name: "data.gov.my"
licence: "Creative Commons Attribution 4.0"
refresh_frequency: "monthly"
last_checked: 2026-08-13T02:46:04Z
last_observed: 2026-02-19
last_modified: 2026-08-08T09:55:58Z
record_count: 1594
column_count: 7
status: stale
notes: "Tier-1 wave E newly verified direct-storage source; HTTP 200 and CSV header verified."
dataset_id: pharmaceutical_products_cancelled
freshness_delta: 175 days
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

**Freshness:** 175 days

HTTP 200

## Last checked

2026-08-13 at 02:46:04 UTC.

## File size

The checked resource is 219,471 bytes.

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
