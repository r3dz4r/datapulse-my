---
id: "ipi_export"
title: "Monthly IPI for Export-Oriented Divisions"
source_url: "https://storage.dosm.gov.my/ipi/ipi_export.csv"
source_name: "OpenDOSM"
licence: "Creative Commons Attribution 4.0"
refresh_frequency: "monthly"
last_checked: 2026-08-16T02:09:20Z
last_observed: 2026-06-01
last_modified: 2026-08-12T22:38:48Z
record_count: 5213
column_count: 4
status: aging
notes: "Tier-1 wave D newly verified direct-storage source; HTTP 200 and CSV header verified."
dataset_id: ipi_export
freshness_delta: 76 days
next_expected_update: "monthly"
schema_version: 1.0
schema_drift: none
known_quirks: []
breaking_changes: []
attribution: "Department of Statistics Malaysia via OpenDOSM"
---

# Monthly IPI for Export-Oriented Divisions

## Status

**Status:** Aging

**Freshness:** 76 days

HTTP 200

## Last checked

2026-08-16 at 02:09:20 UTC.

## File size

The checked resource is 156,995 bytes.

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
