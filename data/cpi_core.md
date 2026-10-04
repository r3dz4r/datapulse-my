---
id: "cpi_core"
title: "Monthly Core Consumer Price Index"
source_url: "https://storage.dosm.gov.my/cpi/cpi_2d_core.csv"
source_name: "OpenDOSM"
licence: "Creative Commons Attribution 4.0"
refresh_frequency: "monthly"
last_checked: 2026-10-03T10:36:37Z
last_observed: 2026-08-01
last_modified: 2026-09-18T04:25:22Z
record_count: 1456
column_count: 3
status: fresh
notes: "Tier-1 wave B already-active confirmation; HTTP 200 and CSV header verified."
dataset_id: cpi_core
freshness_delta: 15 days
next_expected_update: "monthly"
schema_version: 1.0
schema_drift: none
known_quirks: []
breaking_changes: []
attribution: "Department of Statistics Malaysia via OpenDOSM"
---

# Monthly Core Consumer Price Index

## Status

**Status:** Fresh

**Freshness:** 15 days

HTTP 200

## Last checked

2026-10-03 at 10:36:37 UTC.

## File size

The checked resource is 28,932 bytes.

## Provenance

Department of Statistics Malaysia publishes this dataset through OpenDOSM:

- `https://storage.dosm.gov.my/cpi/cpi_2d_core.csv`

## Coverage

Malaysia. Latest source observation: 2026-06-01.

## Schema

The verified CSV contains 3 columns: `date`, `division`, `index`.

## Known quirks

- No additional source-specific quirks were established during reachability verification.

## Reproducibility

```sh
curl -sS -I "https://storage.dosm.gov.my/cpi/cpi_2d_core.csv"
curl -sS "https://storage.dosm.gov.my/cpi/cpi_2d_core.csv" | head -1
```

## Licence

Licensed under Creative Commons Attribution 4.0. Attribution: Department of Statistics Malaysia via OpenDOSM.
