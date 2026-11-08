---
id: "pharmaceutical_importers"
title: "Licensed Pharmaceutical Importers"
source_url: "https://storage.data.gov.my/healthcare/pharmaceutical_importers.csv"
source_name: "data.gov.my"
licence: "Creative Commons Attribution 4.0"
refresh_frequency: "monthly"
last_checked: 2026-10-31T13:12:59Z
last_observed: null
last_modified: 2026-10-29T19:00:35Z
record_count: 481
column_count: 8
status: fresh
notes: "Tier-1 wave E newly verified direct-storage source; HTTP 200 and CSV header verified."
dataset_id: pharmaceutical_importers
freshness_delta: 8 days
next_expected_update: "monthly"
schema_version: 1.0
schema_drift: none
known_quirks: []
breaking_changes: []
attribution: "National Pharmaceutical Regulatory Agency via data.gov.my"
---

# Licensed Pharmaceutical Importers

## Status

**Status:** Fresh

**Freshness:** 8 days

HTTP 200

## Last checked

2026-10-31 at 13:12:59 UTC.

## File size

The checked resource is 76,154 bytes.

## Provenance

National Pharmaceutical Regulatory Agency publishes this dataset through data.gov.my:

- `https://storage.data.gov.my/healthcare/pharmaceutical_importers.csv`

## Coverage

Malaysia. Latest source observation: 2026.

## Schema

The verified CSV contains 8 columns: `license_no`, `company`, `state`, `postcode`, `phone`, `address`, `license_year`, `osa_code`.

## Known quirks

- No additional source-specific quirks were established during reachability verification.

## Reproducibility

```sh
curl -sS -I "https://storage.data.gov.my/healthcare/pharmaceutical_importers.csv"
curl -sS "https://storage.data.gov.my/healthcare/pharmaceutical_importers.csv" | head -1
```

## Licence

Licensed under Creative Commons Attribution 4.0. Attribution: National Pharmaceutical Regulatory Agency via data.gov.my.
