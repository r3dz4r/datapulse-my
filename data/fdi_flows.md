---
id: "fdi_flows"
title: "Foreign Direct Investment Flows"
source_url: "https://storage.dosm.gov.my/bop/fdi_flows.csv"
source_name: "OpenDOSM"
licence: "Creative Commons Attribution 4.0"
refresh_frequency: "quarterly"
last_checked: 2026-08-09T08:37:11Z
last_observed: 2025-07-01
last_modified: 2025-11-26T09:18:23Z
record_count: 71
column_count: 4
status: stale
notes: "Tier-1 wave A already-active confirmation; HTTP 200 and CSV header verified."
dataset_id: fdi_flows
freshness_delta: 404 days
next_expected_update: "quarterly"
schema_version: 1.0
schema_drift: none
known_quirks: []
breaking_changes: []
attribution: "Department of Statistics Malaysia via OpenDOSM"
---

# Foreign Direct Investment Flows

## Status

**Status:** Stale

**Freshness:** 404 days

HTTP 200

## Last checked

2026-08-09 at 08:37:11 UTC.

## File size

The checked resource is 3,691 bytes.

## Provenance

Department of Statistics Malaysia publishes this dataset through OpenDOSM:

- `https://storage.dosm.gov.my/bop/fdi_flows.csv`

## Coverage

Malaysia. Latest source observation: 2025-07-01.

## Schema

The verified CSV contains 4 columns: `date`, `inflow`, `outflow`, `net`.

## Known quirks

- No additional source-specific quirks were established during reachability verification.

## Reproducibility

```sh
curl -sS -I "https://storage.dosm.gov.my/bop/fdi_flows.csv"
curl -sS "https://storage.dosm.gov.my/bop/fdi_flows.csv" | head -1
```

## Licence

Licensed under Creative Commons Attribution 4.0. Attribution: Department of Statistics Malaysia via OpenDOSM.
