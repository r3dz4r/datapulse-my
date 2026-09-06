---
id: "ppi_3d"
title: "Monthly Producer Price Index by Group"
source_url: "https://storage.dosm.gov.my/ppi/ppi_3d.csv"
source_name: "OpenDOSM"
licence: "Creative Commons Attribution 4.0"
refresh_frequency: "monthly"
last_checked: 2026-09-05T02:34:56Z
last_observed: 2026-07-01
last_modified: 2026-09-01T04:17:06Z
record_count: 37260
column_count: 4
status: aging
notes: "Tier-1 wave D newly verified direct-storage source; HTTP 200 and CSV header verified."
dataset_id: ppi_3d
freshness_delta: 66 days
next_expected_update: "monthly"
schema_version: 1.0
schema_drift: none
known_quirks: []
breaking_changes: []
attribution: "Department of Statistics Malaysia via OpenDOSM"
---

# Monthly Producer Price Index by Group

## Status

**Status:** Aging

**Freshness:** 66 days

HTTP 200

## Last checked

2026-09-05 at 02:34:56 UTC.

## File size

The checked resource is 1,104,652 bytes.

## Provenance

Department of Statistics Malaysia publishes this dataset through OpenDOSM:

- `https://storage.dosm.gov.my/ppi/ppi_3d.csv`

## Coverage

Malaysia. Latest source observation: 2026-06-01.

## Schema

The verified CSV contains 4 columns: `series`, `date`, `group`, `index`.

## Known quirks

- No additional source-specific quirks were established during reachability verification.

## Reproducibility

```sh
curl -sS -I "https://storage.dosm.gov.my/ppi/ppi_3d.csv"
curl -sS "https://storage.dosm.gov.my/ppi/ppi_3d.csv" | head -1
```

## Licence

Licensed under Creative Commons Attribution 4.0. Attribution: Department of Statistics Malaysia via OpenDOSM.
