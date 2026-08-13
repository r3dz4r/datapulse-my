---
id: "pharmaceutical_wholesalers"
title: "Licensed Pharmaceutical Wholesalers"
source_url: "https://storage.data.gov.my/healthcare/pharmaceutical_wholesalers.csv"
source_name: "data.gov.my"
licence: "Creative Commons Attribution 4.0"
refresh_frequency: "monthly"
last_checked: 2026-08-11T14:21:08Z
last_observed: null
last_modified: 2026-08-08T09:55:38Z
record_count: 989
column_count: 10
status: fresh
notes: "Tier-1 wave E newly verified direct-storage source; HTTP 200 and CSV header verified."
dataset_id: pharmaceutical_wholesalers
freshness_delta: 3 days
next_expected_update: "monthly"
schema_version: 1.0
schema_drift: none
known_quirks: []
breaking_changes: []
attribution: "National Pharmaceutical Regulatory Agency via data.gov.my"
---

# Licensed Pharmaceutical Wholesalers

## Status

**Status:** Fresh

**Freshness:** 3 days

HTTP 200

## Last checked

2026-08-11 at 14:21:08 UTC.

## File size

The checked resource is 108,412 bytes.

## Provenance

National Pharmaceutical Regulatory Agency publishes this dataset through data.gov.my:

- `https://storage.data.gov.my/healthcare/pharmaceutical_wholesalers.csv`

## Coverage

Malaysia. Latest source observation: not encoded in a date field.

## Schema

The verified CSV contains 10 columns: `company`, `state`, `postcode`, `address`, `poison`, `non_poison`, `traditional`, `health_supplement`, `poison_vet`, `non_poison_vet`.

## Known quirks

- No additional source-specific quirks were established during reachability verification.

## Reproducibility

```sh
curl -sS -I "https://storage.data.gov.my/healthcare/pharmaceutical_wholesalers.csv"
curl -sS "https://storage.data.gov.my/healthcare/pharmaceutical_wholesalers.csv" | head -1
```

## Licence

Licensed under Creative Commons Attribution 4.0. Attribution: National Pharmaceutical Regulatory Agency via data.gov.my.
