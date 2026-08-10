---
id: "pharmaceutical_products"
title: "Registered Pharmaceutical Products"
source_url: "https://storage.data.gov.my/healthcare/pharmaceutical_products.csv"
source_name: "data.gov.my"
licence: "Creative Commons Attribution 4.0"
refresh_frequency: "monthly"
last_checked: 2026-08-09T08:37:11Z
last_observed: null
last_modified: 2026-08-08T09:55:45Z
record_count: 28073
column_count: 16
status: fresh
notes: "Tier-1 wave E newly verified direct-storage source; HTTP 200 and CSV header verified."
dataset_id: pharmaceutical_products
freshness_delta: 0 days
next_expected_update: "monthly"
schema_version: 1.0
schema_drift: none
known_quirks: []
breaking_changes: []
attribution: "National Pharmaceutical Regulatory Agency via data.gov.my"
---

# Registered Pharmaceutical Products

## Status

**Status:** Fresh

**Freshness:** 0 days

HTTP 200

## Last checked

2026-08-09 at 08:37:11 UTC.

## File size

The checked resource is 10,574,285 bytes.

## Provenance

National Pharmaceutical Regulatory Agency publishes this dataset through data.gov.my:

- `https://storage.data.gov.my/healthcare/pharmaceutical_products.csv`

## Coverage

Malaysia. Latest source observation: 2026-12-23.

## Schema

The verified CSV contains 16 columns: `reg_no`, `ref_no`, `product`, `status`, `description`, `holder`, `holder_osa`, `manufacturer`, `manufacturer_osa`, `importer`, `importer_osa`, `date_reg`, `date_end`, `active_ingredient`, `mdc_code`, `generic_name`.

## Known quirks

- No additional source-specific quirks were established during reachability verification.

## Reproducibility

```sh
curl -sS -I "https://storage.data.gov.my/healthcare/pharmaceutical_products.csv"
curl -sS "https://storage.data.gov.my/healthcare/pharmaceutical_products.csv" | head -1
```

## Licence

Licensed under Creative Commons Attribution 4.0. Attribution: National Pharmaceutical Regulatory Agency via data.gov.my.
