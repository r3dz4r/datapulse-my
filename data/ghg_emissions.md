---
id: "ghg_emissions"
title: "Greenhouse Gas Emissions"
source_url: "https://storage.data.gov.my/environment/ghg_emissions.csv"
source_name: "data.gov.my"
licence: "Creative Commons Attribution 4.0"
refresh_frequency: "annual"
last_checked: 2026-11-05T03:33:57Z
last_observed: 2023-01-01
last_modified: 2026-10-11T04:28:49Z
record_count: 238
column_count: 3
status: stale
notes: "Tier-1 wave A already-active confirmation; HTTP 200 and CSV header verified."
dataset_id: ghg_emissions
freshness_delta: 1406 days
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

**Freshness:** 1406 days

HTTP 200

## Last checked

2026-11-05 at 03:33:57 UTC.

## File size

The checked resource is 6,968 bytes.

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
