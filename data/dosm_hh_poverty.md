---
dataset_id: dosm_hh_poverty
last_checked: 2026-08-09T08:37:11Z
status: fresh
freshness_delta: 951 days
next_expected_update: biennial to triennial (survey years)
record_count: 21
date_range: 1970-01-01 to 2024-01-01
schema_version: 1.0
schema_drift: none
known_quirks: ["Dates mark survey years and are not a continuous annual series.", "Hardcore-poverty values are unavailable before 1984.", "Relative-poverty values are unavailable before 1995.", "Rates are percentages, not proportions."]
breaking_changes: []
licence: Creative Commons Attribution 4.0
attribution: DOSM via OpenDOSM
---

# OpenDOSM Poverty, Malaysia

## Status

**Status:** Fresh

**Freshness:** 951 days

HTTP 200

## Last checked

2026-08-09 at 08:37:11 UTC.

## File size

The checked resource is 531 bytes.

## Provenance

The Department of Statistics Malaysia publishes this dataset through OpenDOSM as direct CSV and Parquet downloads:

- `https://storage.dosm.gov.my/hies/hh_poverty.csv`
- `https://storage.dosm.gov.my/hies/hh_poverty.parquet`

## Coverage

The dataset covers Malaysia at national level from 1970-01-01 through 2024-01-01.

## Schema

| Field | Type | Description |
| --- | --- | --- |
| `date` | date | Observation date in YYYY-MM-DD format. |
| `poverty_absolute` | number | Incidence of absolute poverty, in percent. |
| `poverty_hardcore` | number | Incidence of hardcore poverty, in percent. |
| `poverty_relative` | number | Incidence of relative poverty, in percent. |

## Known quirks

- Dates mark survey years and are not a continuous annual series.
- Hardcore-poverty values are unavailable before 1984.
- Relative-poverty values are unavailable before 1995.
- Rates are percentages, not proportions.

## Breaking changes

None observed.

## Reproducibility

```sh
curl -sS --max-time 30 \
  "https://storage.dosm.gov.my/hies/hh_poverty.csv" \
  -o /tmp/hh_poverty.csv
```

## Licence

Licensed under the Creative Commons Attribution 4.0 licence.

Attribution: DOSM via OpenDOSM.

## Sample

- [samples/dosm_hh_poverty.csv](../samples/dosm_hh_poverty.csv)
- [samples/dosm_hh_poverty.json](../samples/dosm_hh_poverty.json)
