---
id: "air_pollution"
title: "Air Pollutant Concentrations"
source_url: "https://storage.data.gov.my/environment/air_pollution.csv"
source_name: "data.gov.my"
licence: "Creative Commons Attribution 4.0"
refresh_frequency: "monthly"
last_checked: 2026-08-11T14:21:08Z
last_observed: 2022-12-01
last_modified: 2024-09-12T14:45:12Z
record_count: 432
column_count: 3
status: stale
notes: "Tier-1 wave B already-active confirmation; HTTP 200 and CSV header verified."
dataset_id: air_pollution
freshness_delta: 1349 days
next_expected_update: "monthly"
schema_version: 1.0
schema_drift: none
known_quirks: []
breaking_changes: []
attribution: "Department of Environment Malaysia via data.gov.my"
---

# Air Pollutant Concentrations

## Status

**Status:** Stale

**Freshness:** 1349 days

HTTP 200

## Last checked

2026-08-11 at 14:21:08 UTC.

## File size

The checked resource is 9,299 bytes.

## Provenance

Department of Environment Malaysia publishes this dataset through data.gov.my:

- `https://storage.data.gov.my/environment/air_pollution.csv`

## Coverage

Malaysia. Latest source observation: 2022-12-01.

## Schema

The verified CSV contains 3 columns: `date`, `pollutant`, `concentration`.

## Known quirks

- No additional source-specific quirks were established during reachability verification.

## Reproducibility

```sh
curl -sS -I "https://storage.data.gov.my/environment/air_pollution.csv"
curl -sS "https://storage.data.gov.my/environment/air_pollution.csv" | head -1
```

## Licence

Licensed under Creative Commons Attribution 4.0. Attribution: Department of Environment Malaysia via data.gov.my.
