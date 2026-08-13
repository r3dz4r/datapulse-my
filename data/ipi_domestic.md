---
id: "ipi_domestic"
title: "Monthly IPI for Domestic-Oriented Divisions"
source_url: "https://storage.dosm.gov.my/ipi/ipi_domestic.csv"
source_name: "OpenDOSM"
licence: "Creative Commons Attribution 4.0"
refresh_frequency: "monthly"
last_checked: 2026-08-11T14:21:08Z
last_observed: 2026-05-01
last_modified: 2026-07-20T14:59:43Z
record_count: 5970
column_count: 4
status: stale
notes: "Tier-1 wave D newly verified direct-storage source; HTTP 200 and CSV header verified."
dataset_id: ipi_domestic
freshness_delta: 102 days
next_expected_update: "monthly"
schema_version: 1.0
schema_drift: none
known_quirks: []
breaking_changes: []
attribution: "Department of Statistics Malaysia via OpenDOSM"
---

# Monthly IPI for Domestic-Oriented Divisions

## Status

**Status:** Stale

**Freshness:** 102 days

HTTP 200

## Last checked

2026-08-11 at 14:21:08 UTC.

## File size

The checked resource is 177,950 bytes.

## Provenance

Department of Statistics Malaysia publishes this dataset through OpenDOSM:

- `https://storage.dosm.gov.my/ipi/ipi_domestic.csv`

## Coverage

Malaysia. Latest source observation: 2026-05-01.

## Schema

The verified CSV contains 4 columns: `series`, `date`, `division`, `index`.

## Known quirks

- No additional source-specific quirks were established during reachability verification.

## Reproducibility

```sh
curl -sS -I "https://storage.dosm.gov.my/ipi/ipi_domestic.csv"
curl -sS "https://storage.dosm.gov.my/ipi/ipi_domestic.csv" | head -1
```

## Licence

Licensed under Creative Commons Attribution 4.0. Attribution: Department of Statistics Malaysia via OpenDOSM.
