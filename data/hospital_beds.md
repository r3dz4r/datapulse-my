---
id: "hospital_beds"
title: "Hospital Beds by State and Hospital Type"
source_url: "https://storage.data.gov.my/healthcare/hospital_beds.csv"
source_name: "data.gov.my"
licence: "Creative Commons Attribution 4.0"
refresh_frequency: "annual"
last_checked: 2026-08-10T04:08:14Z
last_observed: 2022-01-01
last_modified: 2024-09-27T01:28:51Z
record_count: 5468
column_count: 5
status: stale
notes: "Tier-1 wave B already-active confirmation; HTTP 200 and CSV header verified."
dataset_id: hospital_beds
freshness_delta: 1682 days
next_expected_update: "annual"
schema_version: 1.0
schema_drift: none
known_quirks: []
breaking_changes: []
attribution: "Ministry of Health Malaysia via data.gov.my"
---

# Hospital Beds by State and Hospital Type

## Status

**Status:** Stale

**Freshness:** 1682 days

HTTP 200

## Last checked

2026-08-10 at 04:08:14 UTC.

## File size

The checked resource is 260,704 bytes.

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
