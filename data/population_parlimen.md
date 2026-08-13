---
id: "population_parlimen"
title: "Annual Population by Parliamentary Constituency"
source_url: "https://storage.dosm.gov.my/population/population_parlimen.csv"
source_name: "OpenDOSM"
licence: "Creative Commons Attribution 4.0"
refresh_frequency: "annual"
last_checked: 2026-08-13T02:46:04Z
last_observed: 2024-01-01
last_modified: 2026-07-05T22:39:19Z
record_count: 5550
column_count: 7
status: aging
notes: "Tier-1 wave G newly verified direct-storage source; HTTP 200 and CSV header verified."
dataset_id: population_parlimen
freshness_delta: 955 days
next_expected_update: "annual"
schema_version: 1.0
schema_drift: none
known_quirks: []
breaking_changes: []
attribution: "Department of Statistics Malaysia via OpenDOSM"
---

# Annual Population by Parliamentary Constituency

## Status

**Status:** Aging

**Freshness:** 955 days

HTTP 200

## Last checked

2026-08-13 at 02:46:04 UTC.

## File size

The checked resource is 346,540 bytes.

## Provenance

Department of Statistics Malaysia publishes this dataset through OpenDOSM:

- `https://storage.dosm.gov.my/population/population_parlimen.csv`

## Coverage

Malaysia. Latest source observation: 2024-01-01.

## Schema

The verified CSV contains 7 columns: `date`, `state`, `parlimen`, `sex`, `age`, `ethnicity`, `population`.

## Known quirks

- No additional source-specific quirks were established during reachability verification.

## Reproducibility

```sh
curl -sS -I "https://storage.dosm.gov.my/population/population_parlimen.csv"
curl -sS "https://storage.dosm.gov.my/population/population_parlimen.csv" | head -1
```

## Licence

Licensed under Creative Commons Attribution 4.0. Attribution: Department of Statistics Malaysia via OpenDOSM.
