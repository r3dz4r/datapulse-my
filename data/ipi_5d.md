---
id: "ipi_5d"
title: "Monthly Industrial Production Index by Item"
source_url: "https://storage.dosm.gov.my/ipi/ipi_5d.csv"
source_name: "OpenDOSM"
licence: "Creative Commons Attribution 4.0"
refresh_frequency: "monthly"
last_checked: 2026-08-10T04:08:14Z
last_observed: 2026-05-01
last_modified: 2026-07-20T14:59:42Z
record_count: 52536
column_count: 4
status: stale
notes: "Tier-1 wave D newly verified direct-storage source; HTTP 200 and CSV header verified."
dataset_id: ipi_5d
freshness_delta: 101 days
next_expected_update: "monthly"
schema_version: 1.0
schema_drift: none
known_quirks: []
breaking_changes: []
attribution: "Department of Statistics Malaysia via OpenDOSM"
---

# Monthly Industrial Production Index by Item

## Status

**Status:** Stale

**Freshness:** 101 days

HTTP 200

## Last checked

2026-08-10 at 04:08:14 UTC.

## File size

The checked resource is 1,712,614 bytes.

## Provenance

Department of Statistics Malaysia publishes this dataset through OpenDOSM:

- `https://storage.dosm.gov.my/ipi/ipi_5d.csv`

## Coverage

Malaysia. Latest source observation: 2026-05-01.

## Schema

The verified CSV contains 4 columns: `series`, `date`, `item`, `index`.

## Known quirks

- No additional source-specific quirks were established during reachability verification.

## Reproducibility

```sh
curl -sS -I "https://storage.dosm.gov.my/ipi/ipi_5d.csv"
curl -sS "https://storage.dosm.gov.my/ipi/ipi_5d.csv" | head -1
```

## Licence

Licensed under Creative Commons Attribution 4.0. Attribution: Department of Statistics Malaysia via OpenDOSM.
