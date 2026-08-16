---
id: "sppi_3d"
title: "Quarterly Services Producer Price Index by Group"
source_url: "https://storage.dosm.gov.my/ppi/sppi_3d.csv"
source_name: "OpenDOSM"
licence: "Creative Commons Attribution 4.0"
refresh_frequency: "monthly"
last_checked: 2026-08-16T02:09:20Z
last_observed: 2026-01-01
last_modified: 2026-05-08T04:31:43Z
record_count: 3062
column_count: 4
status: stale
notes: "Tier-1 wave D newly verified direct-storage source; HTTP 200 and CSV header verified."
dataset_id: sppi_3d
freshness_delta: 227 days
next_expected_update: "monthly"
schema_version: 1.0
schema_drift: none
known_quirks: []
breaking_changes: []
attribution: "Department of Statistics Malaysia via OpenDOSM"
---

# Quarterly Services Producer Price Index by Group

## Status

**Status:** Stale

**Freshness:** 227 days

HTTP 200

## Last checked

2026-08-16 at 02:09:20 UTC.

## File size

The checked resource is 88,094 bytes.

## Provenance

Department of Statistics Malaysia publishes this dataset through OpenDOSM:

- `https://storage.dosm.gov.my/ppi/sppi_3d.csv`

## Coverage

Malaysia. Latest source observation: 2026-01-01.

## Schema

The verified CSV contains 4 columns: `series`, `date`, `group`, `index`.

## Known quirks

- No additional source-specific quirks were established during reachability verification.

## Reproducibility

```sh
curl -sS -I "https://storage.dosm.gov.my/ppi/sppi_3d.csv"
curl -sS "https://storage.dosm.gov.my/ppi/sppi_3d.csv" | head -1
```

## Licence

Licensed under Creative Commons Attribution 4.0. Attribution: Department of Statistics Malaysia via OpenDOSM.
