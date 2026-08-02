---
dataset_id: dosm_lfs_year
last_checked: 2026-08-02T16:47:48Z
status: stale
freshness_delta: 663 days since file update
next_expected_update: overdue
record_count: 40
date_range: 1982-01-01 to 2023-01-01
schema_version: 1.0
schema_drift: none
known_quirks: ["Annual dates use 1 January.", "Observations for 1991 and 1994 are unavailable.", "Counts are reported in thousands of persons.", "Rounded components may not sum exactly to published totals."]
breaking_changes: []
licence: Creative Commons Attribution 4.0
attribution: DOSM via OpenDOSM
---

# OpenDOSM Annual Labour Force Statistics

## Provenance

Department of Statistics Malaysia publishes this dataset through OpenDOSM as direct CSV and
Parquet downloads:

- `https://storage.dosm.gov.my/labour/lfs_year.csv`
- `https://storage.dosm.gov.my/labour/lfs_year.parquet`

Catalogue description: [annual principal labour-force counts and rates](https://open.dosm.gov.my/data-catalogue/lfs_year).

## Status

**Status:** Stale

**Freshness:** File last updated 2024-10-08; observations end on 2023-01-01

**Refresh frequency:** Annual

The CSV endpoint returned HTTP 200 and its expected 2,188-byte file. It
contains 40 data rows.

## Last checked

2026-08-02 by direct HTTP HEAD request and CSV download.

## Coverage

The dataset covers Malaysia (national) from 1982-01-01 through 2023-01-01.

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

- Annual dates use 1 January.
- Observations for 1991 and 1994 are unavailable.
- Counts are reported in thousands of persons.
- Rounded components may not sum exactly to published totals.

## Breaking changes

None observed.

## Reproducibility

```sh
curl -sS --max-time 30 \
  "https://storage.dosm.gov.my/labour/lfs_year.csv" \
  -o /tmp/lfs_year.csv
```

## Licence

Licensed under the Creative Commons Attribution 4.0 licence, as stated on the
official catalogue page.

Attribution: DOSM via OpenDOSM.

## Sample

- [samples/dosm_lfs_year.csv](../samples/dosm_lfs_year.csv)
- [samples/dosm_lfs_year.json](../samples/dosm_lfs_year.json)
