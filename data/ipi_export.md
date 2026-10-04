---
id: "ipi_export"
title: "Monthly IPI for Export-Oriented Divisions"
source_url: "https://storage.dosm.gov.my/ipi/ipi_export.csv"
source_name: "OpenDOSM"
licence: "Creative Commons Attribution 4.0"
refresh_frequency: "monthly"
last_checked: 2026-10-03T10:36:37Z
last_observed: 2026-07-01
last_modified: 2026-09-11T05:59:53Z
record_count: 5252
column_count: 4
status: fresh
notes: "Tier-1 wave D newly verified direct-storage source; HTTP 200 and CSV header verified."
dataset_id: ipi_export
freshness_delta: 23 days
next_expected_update: "monthly"
schema_version: 1.0
schema_drift: none
known_quirks: []
breaking_changes: []
attribution: "Department of Statistics Malaysia via OpenDOSM"
---

# Monthly IPI for Export-Oriented Divisions

## Status

**Status:** Fresh

**Freshness:** 23 days

HTTP 200

## Last checked

2026-10-03 at 10:36:37 UTC.

## File size

The checked resource is 158,167 bytes.

## Provenance

Department of Statistics Malaysia publishes this dataset through OpenDOSM:

- `https://storage.dosm.gov.my/ipi/ipi_export.csv`

## Coverage

Malaysia. Latest source observation: 2026-05-01.

## Schema

The verified CSV contains 4 columns: `series`, `date`, `division`, `index`.

## Known quirks

- No additional source-specific quirks were established during reachability verification.

## Reproducibility

```sh
curl -sS -I "https://storage.dosm.gov.my/ipi/ipi_export.csv"
curl -sS "https://storage.dosm.gov.my/ipi/ipi_export.csv" | head -1
```

## Licence

Licensed under Creative Commons Attribution 4.0. Attribution: Department of Statistics Malaysia via OpenDOSM.
