---
id: "population_dun"
title: "Annual Population by State Constituency"
source_url: "https://storage.dosm.gov.my/population/population_dun.csv"
source_name: "OpenDOSM"
licence: "Creative Commons Attribution 4.0"
refresh_frequency: "annual"
last_checked: 2026-08-10T04:08:14Z
last_observed: 2024-01-01
last_modified: 2026-07-05T22:39:19Z
record_count: 15000
column_count: 8
status: aging
notes: "Tier-1 wave G newly verified direct-storage source; HTTP 200 and CSV header verified."
dataset_id: population_dun
freshness_delta: 952 days
next_expected_update: "annual"
schema_version: 1.0
schema_drift: none
known_quirks: []
breaking_changes: []
attribution: "Department of Statistics Malaysia via OpenDOSM"
---

# Annual Population by State Constituency

## Status

**Status:** Aging

**Freshness:** 952 days

HTTP 200

## Last checked

2026-08-10 at 04:08:14 UTC.

## File size

The checked resource is 1,148,085 bytes.

## Provenance

Department of Statistics Malaysia publishes this dataset through OpenDOSM:

- `https://storage.dosm.gov.my/population/population_dun.csv`

## Coverage

Malaysia. Latest source observation: 2024-01-01.

## Schema

The verified CSV contains 8 columns: `date`, `state`, `parlimen`, `dun`, `sex`, `age`, `ethnicity`, `population`.

## Known quirks

- No additional source-specific quirks were established during reachability verification.

## Reproducibility

```sh
curl -sS -I "https://storage.dosm.gov.my/population/population_dun.csv"
curl -sS "https://storage.dosm.gov.my/population/population_dun.csv" | head -1
```

## Licence

Licensed under Creative Commons Attribution 4.0. Attribution: Department of Statistics Malaysia via OpenDOSM.
