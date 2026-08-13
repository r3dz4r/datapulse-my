---
dataset_id: dosm_hh_inequality
last_checked: 2026-08-13T02:46:04Z
status: fresh
freshness_delta: 955 days
next_expected_update: biennial to triennial (survey years)
record_count: 21
date_range: 1970-01-01 to 2024-01-01
schema_version: 1.0
schema_drift: none
known_quirks: ["Dates mark survey years and are not a continuous annual series.", "The 2020 survey year present in the income and poverty series is absent here.", "Gini values are coefficients on a zero-to-one scale."]
breaking_changes: []
licence: Creative Commons Attribution 4.0
attribution: DOSM via OpenDOSM
---

# OpenDOSM Income Inequality, Malaysia

## Status

**Status:** Fresh

**Freshness:** 955 days

HTTP 200

## Last checked

2026-08-13 at 02:46:04 UTC.

## File size

The checked resource is 365 bytes.

## Provenance

The Department of Statistics Malaysia publishes this dataset through OpenDOSM as direct CSV and Parquet downloads:

- `https://storage.dosm.gov.my/hies/hh_inequality.csv`
- `https://storage.dosm.gov.my/hies/hh_inequality.parquet`

## Coverage

The dataset covers Malaysia at national level from 1970-01-01 through 2024-01-01.

## Schema

| Field | Type | Description |
| --- | --- | --- |
| `date` | date | Observation date in YYYY-MM-DD format. |
| `gini` | number | Gini coefficient reported by the source. |

## Known quirks

- Dates mark survey years and are not a continuous annual series.
- The 2020 survey year present in the income and poverty series is absent here.
- Gini values are coefficients on a zero-to-one scale.

## Breaking changes

None observed.

## Reproducibility

```sh
curl -sS --max-time 30 \
  "https://storage.dosm.gov.my/hies/hh_inequality.csv" \
  -o /tmp/hh_inequality.csv
```

## Licence

Licensed under the Creative Commons Attribution 4.0 licence.

Attribution: DOSM via OpenDOSM.

## Sample

- [samples/dosm_hh_inequality.csv](../samples/dosm_hh_inequality.csv)
- [samples/dosm_hh_inequality.json](../samples/dosm_hh_inequality.json)
