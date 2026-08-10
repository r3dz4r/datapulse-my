---
dataset_id: dosm_lfs_month
last_checked: 2026-08-09T08:37:11Z
status: stale
freshness_delta: 100 days
next_expected_update: monthly
record_count: 197
date_range: 2010-01-01 to 2026-05-01
schema_version: 1.0
schema_drift: none
known_quirks: ["Monthly dates use the first day of the month.", "Counts are reported in thousands of persons.", "A population-benchmark break occurs in 2025 when the reference changes from the 2010 to the 2020 Census.", "Rounded components may not sum exactly to published totals."]
breaking_changes: []
licence: Creative Commons Attribution 4.0
attribution: DOSM via OpenDOSM
---

# OpenDOSM Monthly Labour Force Statistics

## Status

**Status:** Stale

**Freshness:** 100 days

HTTP 200

## Last checked

2026-08-09 at 08:37:11 UTC.

## File size

The checked resource is 10,706 bytes.

## Provenance

Department of Statistics Malaysia publishes this dataset through OpenDOSM as direct CSV and
Parquet downloads:

- `https://storage.dosm.gov.my/labour/lfs_month.csv`
- `https://storage.dosm.gov.my/labour/lfs_month.parquet`

Catalogue description: [monthly principal labour-force counts and rates](https://open.dosm.gov.my/data-catalogue/lfs_month).

## Coverage

The dataset covers Malaysia (national) from 2010-01-01 through 2026-05-01.

## Schema

| Field | Type | Description |
| --- | --- | --- |
| `date` | date | Observation date in YYYY-MM-DD format. |
| `lf` | number | Labour force, in thousands of persons. |
| `lf_employed` | number | Employed persons, in thousands. |
| `lf_unemployed` | number | Unemployed persons, in thousands. |
| `lf_outside` | number | Persons outside the labour force, in thousands. |
| `p_rate` | number | Labour-force participation rate in percent. |
| `ep_ratio` | number | Employment-to-population ratio in percent. |
| `u_rate` | number | Unemployment rate in percent. |

## Known quirks

- Monthly dates use the first day of the month.
- Counts are reported in thousands of persons.
- A population-benchmark break occurs in 2025 when the reference changes from the 2010 to the 2020 Census.
- Rounded components may not sum exactly to published totals.

## Breaking changes

None observed.

## Reproducibility

```sh
curl -sS --max-time 30 \
  "https://storage.dosm.gov.my/labour/lfs_month.csv" \
  -o /tmp/lfs_month.csv
```

## Licence

Licensed under the Creative Commons Attribution 4.0 licence, as stated on the
official catalogue page.

Attribution: DOSM via OpenDOSM.

## Sample

- [samples/dosm_lfs_month.csv](../samples/dosm_lfs_month.csv)
- [samples/dosm_lfs_month.json](../samples/dosm_lfs_month.json)
