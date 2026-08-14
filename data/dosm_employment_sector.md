---
dataset_id: dosm_employment_sector
last_checked: 2026-08-14T04:59:27Z
status: stale
freshness_delta: 1686 days
next_expected_update: overdue
record_count: 198
date_range: 2001-01-01 to 2022-01-01
schema_version: 1.0
schema_drift: none
known_quirks: ["annual dates use January 1", "both-sex aggregates coexist with male and female rows", "sector proportions sum to 100 within a date and sex"]
breaking_changes: []
licence: Creative Commons Attribution 4.0
attribution: DOSM via OpenDOSM
---

# OpenDOSM Annual Employment by Sector and Sex

## Status

**Status:** Stale

**Freshness:** 1686 days

HTTP 200

## Last checked

2026-08-14 at 04:59:27 UTC.

## File size

The checked resource is 6,458 bytes.

## Provenance

DOSM publishes this national dataset through OpenDOSM as direct CSV and
Parquet downloads:

- `https://storage.dosm.gov.my/labour/employment_sector.csv`
- `https://storage.dosm.gov.my/labour/employment_sector.parquet`

## Coverage

The dataset contains national annual employment proportions for Malaysia from
2001 through 2022. It has no subnational geographic field. Rows cover
agriculture, industry, and services for both sexes, females, and males.

## Schema

| Field | Type | Description |
| --- | --- | --- |
| `date` | date | Annual observation date in `YYYY-MM-DD` format. |
| `sector` | string | `agriculture`, `industry`, or `services`. |
| `sex` | string | `both`, `female`, or `male`. |
| `proportion` | number | Share of employment in the sector. |

## Known quirks

- Annual dates use January 1 as the reporting date.
- `both` is an aggregate and coexists with sex-disaggregated rows.
- The three sector proportions sum to 100 for each date and sex, subject to
  displayed precision.

## Breaking changes

None observed.

## Reproducibility

```sh
curl -sS --max-time 30 \
  "https://storage.dosm.gov.my/labour/employment_sector.csv" \
  -o /tmp/employment_sector.csv
```

## Licence

Licensed under the Creative Commons Attribution 4.0 licence.

Attribution: DOSM via OpenDOSM.

## Sample

- [samples/dosm_employment_sector.csv](../samples/dosm_employment_sector.csv)
- [samples/dosm_employment_sector.json](../samples/dosm_employment_sector.json)
