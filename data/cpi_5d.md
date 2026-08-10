---
id: "cpi_5d"
title: "Monthly CPI by Subclass"
source_url: "https://storage.dosm.gov.my/cpi/cpi_5d.csv"
source_name: "OpenDOSM"
licence: "Creative Commons Attribution 4.0"
refresh_frequency: "monthly"
last_checked: 2026-08-10T10:07:26Z
last_observed: 2026-06-01
last_modified: 2026-07-17T06:26:52Z
record_count: 35838
column_count: 3
status: aging
notes: "Tier-1 wave D newly verified direct-storage source; HTTP 200 and CSV header verified."
dataset_id: cpi_5d
freshness_delta: 70 days
next_expected_update: "monthly"
schema_version: 1.0
schema_drift: none
known_quirks: []
breaking_changes: []
attribution: "Department of Statistics Malaysia via OpenDOSM"
---

# Monthly CPI by Subclass

## Status

**Status:** Aging

**Freshness:** 70 days

HTTP 200

## Last checked

2026-08-10 at 10:07:26 UTC.

## File size

The checked resource is 809,469 bytes.

## Provenance

Department of Statistics Malaysia publishes this dataset through OpenDOSM:

- `https://storage.dosm.gov.my/cpi/cpi_5d.csv`

## Coverage

Malaysia. Latest source observation: 2026-06-01.

## Schema

The verified CSV contains 3 columns: `date`, `subclass`, `index`.

## Known quirks

- No additional source-specific quirks were established during reachability verification.

## Reproducibility

```sh
curl -sS -I "https://storage.dosm.gov.my/cpi/cpi_5d.csv"
curl -sS "https://storage.dosm.gov.my/cpi/cpi_5d.csv" | head -1
```

## Licence

Licensed under Creative Commons Attribution 4.0. Attribution: Department of Statistics Malaysia via OpenDOSM.
