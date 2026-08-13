---
id: "cpi_4d"
title: "Monthly CPI by Class"
source_url: "https://storage.dosm.gov.my/cpi/cpi_4d.csv"
source_name: "OpenDOSM"
licence: "Creative Commons Attribution 4.0"
refresh_frequency: "monthly"
last_checked: 2026-08-13T02:46:04Z
last_observed: 2026-06-01
last_modified: 2026-07-17T06:26:51Z
record_count: 19998
column_count: 3
status: aging
notes: "Tier-1 wave D newly verified direct-storage source; HTTP 200 and CSV header verified."
dataset_id: cpi_4d
freshness_delta: 73 days
next_expected_update: "monthly"
schema_version: 1.0
schema_drift: none
known_quirks: []
breaking_changes: []
attribution: "Department of Statistics Malaysia via OpenDOSM"
---

# Monthly CPI by Class

## Status

**Status:** Aging

**Freshness:** 73 days

HTTP 200

## Last checked

2026-08-13 at 02:46:04 UTC.

## File size

The checked resource is 434,628 bytes.

## Provenance

Department of Statistics Malaysia publishes this dataset through OpenDOSM:

- `https://storage.dosm.gov.my/cpi/cpi_4d.csv`

## Coverage

Malaysia. Latest source observation: 2026-06-01.

## Schema

The verified CSV contains 3 columns: `date`, `class`, `index`.

## Known quirks

- No additional source-specific quirks were established during reachability verification.

## Reproducibility

```sh
curl -sS -I "https://storage.dosm.gov.my/cpi/cpi_4d.csv"
curl -sS "https://storage.dosm.gov.my/cpi/cpi_4d.csv" | head -1
```

## Licence

Licensed under Creative Commons Attribution 4.0. Attribution: Department of Statistics Malaysia via OpenDOSM.
