---
id: "hospital_beds"
title: "Hospital Beds by State and Hospital Type"
source_url: "https://storage.data.gov.my/healthcare/hospital_beds.csv"
source_name: "data.gov.my"
licence: "Creative Commons Attribution 4.0"
refresh_frequency: "annual"
last_checked: 2026-11-05T03:33:57Z
last_observed: 2024-01-01
last_modified: 2026-10-10T17:25:00Z
record_count: 6828
column_count: 5
status: aging
notes: "Tier-1 wave B already-active confirmation; HTTP 200 and CSV header verified."
dataset_id: hospital_beds
freshness_delta: 1041 days
next_expected_update: "annual"
schema_version: 1.0
schema_drift: none
known_quirks: []
breaking_changes: []
attribution: "Ministry of Health Malaysia via data.gov.my"
---

# Hospital Beds by State and Hospital Type

## Status

**Status:** Aging

**Freshness:** 1041 days

HTTP 200

## Last checked

2026-11-05 at 03:33:57 UTC.

## File size

The checked resource is 325,576 bytes.

## Provenance

Ministry of Health Malaysia publishes this dataset through data.gov.my:

- `https://storage.data.gov.my/healthcare/hospital_beds.csv`

## Coverage

Malaysia. Latest source observation: 2022-01-01.

## Schema

The verified CSV contains 5 columns: `date`, `state`, `district`, `type`, `beds`.

## Known quirks

- No additional source-specific quirks were established during reachability verification.

## Reproducibility

```sh
curl -sS -I "https://storage.data.gov.my/healthcare/hospital_beds.csv"
curl -sS "https://storage.data.gov.my/healthcare/hospital_beds.csv" | head -1
```

## Licence

Licensed under Creative Commons Attribution 4.0. Attribution: Ministry of Health Malaysia via data.gov.my.
