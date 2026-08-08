---
id: "cpi_core_inflation"
title: "Monthly Core CPI Inflation"
source_url: "https://storage.dosm.gov.my/cpi/cpi_2d_core_inflation.csv"
source_name: "OpenDOSM"
licence: "Creative Commons Attribution 4.0"
refresh_frequency: "monthly"
last_checked: 2026-08-08T05:49:42Z
last_observed: 2026-06-01
last_modified: 2026-07-17T06:26:52Z
record_count: 1414
column_count: 4
status: aging
notes: "Tier-1 wave B already-active confirmation; HTTP 200 and CSV header verified."
dataset_id: cpi_core_inflation
freshness_delta: 68 days
next_expected_update: "monthly"
schema_version: 1.0
schema_drift: none
known_quirks: []
breaking_changes: []
attribution: "Department of Statistics Malaysia via OpenDOSM"
---

# Monthly Core CPI Inflation

## Status

**Status:** Aging

**Freshness:** 68 days

HTTP 200

## Last checked

2026-08-08 at 05:49:42 UTC.

## File size

The checked resource is 30,978 bytes.

## Provenance

Department of Statistics Malaysia publishes this dataset through OpenDOSM:

- `https://storage.dosm.gov.my/cpi/cpi_2d_core_inflation.csv`

## Coverage

Malaysia. Latest source observation: 2026-06-01.

## Schema

The verified CSV contains 4 columns: `date`, `division`, `inflation_yoy`, `inflation_mom`.

## Known quirks

- No additional source-specific quirks were established during reachability verification.

## Reproducibility

```sh
curl -sS -I "https://storage.dosm.gov.my/cpi/cpi_2d_core_inflation.csv"
curl -sS "https://storage.dosm.gov.my/cpi/cpi_2d_core_inflation.csv" | head -1
```

## Licence

Licensed under Creative Commons Attribution 4.0. Attribution: Department of Statistics Malaysia via OpenDOSM.
