---
id: "ghg_emissions"
title: "Greenhouse Gas Emissions"
source_url: "https://storage.data.gov.my/environment/ghg_emissions.csv"
source_name: "data.gov.my"
licence: "Creative Commons Attribution 4.0"
refresh_frequency: "annual"
last_checked: 2026-08-09T08:37:11Z
last_observed: 2021-01-01
last_modified: 2024-09-12T15:15:38Z
record_count: 56
column_count: 3
status: stale
notes: "Tier-1 wave A already-active confirmation; HTTP 200 and CSV header verified."
dataset_id: ghg_emissions
freshness_delta: 2046 days
next_expected_update: "annual"
schema_version: 1.0
schema_drift: none
known_quirks: []
breaking_changes: []
attribution: "Ministry of Natural Resources and Environmental Sustainability via data.gov.my"
---

# Greenhouse Gas Emissions

## Status

**Status:** Stale

**Freshness:** 2046 days

HTTP 200

## Last checked

2026-08-09 at 08:37:11 UTC.

## File size

The checked resource is 1,571 bytes.

## Provenance

Ministry of Natural Resources and Environmental Sustainability publishes this dataset through data.gov.my:

- `https://storage.data.gov.my/environment/ghg_emissions.csv`

## Coverage

Malaysia. Latest source observation: 2021-01-01.

## Schema

The verified CSV contains 3 columns: `date`, `source`, `emissions`.

## Known quirks

- No additional source-specific quirks were established during reachability verification.

## Reproducibility

```sh
curl -sS -I "https://storage.data.gov.my/environment/ghg_emissions.csv"
curl -sS "https://storage.data.gov.my/environment/ghg_emissions.csv" | head -1
```

## Licence

Licensed under Creative Commons Attribution 4.0. Attribution: Ministry of Natural Resources and Environmental Sustainability via data.gov.my.
