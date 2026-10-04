---
id: "air_pollution"
title: "Air Pollutant Concentrations"
source_url: "https://storage.data.gov.my/environment/air_pollution.csv"
source_name: "data.gov.my"
licence: "Creative Commons Attribution 4.0"
refresh_frequency: "monthly"
last_checked: 2026-10-03T10:36:37Z
last_observed: 2024-12-01
last_modified: 2026-09-30T07:14:47Z
record_count: 576
column_count: 3
status: stale
notes: "Tier-1 wave B already-active confirmation; HTTP 200 and CSV header verified."
dataset_id: air_pollution
freshness_delta: 672 days
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

**Freshness:** 672 days

HTTP 200

## Last checked

2026-10-03 at 10:36:37 UTC.

## File size

The checked resource is 12,373 bytes.

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
