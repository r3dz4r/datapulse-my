---
dataset_id: dosm_cpi_core_inflation
last_checked: 2026-08-02T16:47:48Z
status: current
freshness_delta: 16 days since file update
next_expected_update: monthly
record_count: 1414
date_range: 2018-02-01 to 2026-06-01
schema_version: 1.0
schema_drift: none
known_quirks: ["Monthly dates use the first day of the month.", "Division codes must remain strings.", "Year-on-year values contain nulls where a comparable core CPI value is unavailable.", "The source catalogue's field list is outdated; the download contains inflation_yoy and inflation_mom, not index."]
breaking_changes: []
licence: Creative Commons Attribution 4.0
attribution: DOSM via OpenDOSM
---

# OpenDOSM Monthly Core CPI Inflation by Division

## Provenance

Department of Statistics Malaysia publishes this dataset through OpenDOSM as direct CSV and
Parquet downloads:

- `https://storage.dosm.gov.my/cpi/cpi_2d_core_inflation.csv`
- `https://storage.dosm.gov.my/cpi/cpi_2d_core_inflation.parquet`

Catalogue description: [national core CPI inflation for the main groups of goods and services](https://open.dosm.gov.my/data-catalogue/cpi_core_inflation).

## Status

**Status:** Current

**Freshness:** File last updated 2026-07-17; observations end on 2026-06-01

**Refresh frequency:** Monthly

The CSV endpoint returned HTTP 200 and its expected 30,978-byte file. It
contains 1,414 data rows.

## Last checked

2026-08-02 by direct HTTP HEAD request and CSV download.

## Coverage

The dataset covers Malaysia (national) from 2018-02-01 through 2026-06-01.

## Schema

| Field | Type | Description |
| --- | --- | --- |
| `date` | date | Observation date in YYYY-MM-DD format. |
| `division` | string | CPI or MSIC division code, or overall aggregate. |
| `inflation_yoy` | number | Year-on-year inflation rate in percent. |
| `inflation_mom` | number | Month-on-month inflation rate in percent. |

## Known quirks

- Monthly dates use the first day of the month.
- Division codes must remain strings.
- Year-on-year values contain nulls where a comparable core CPI value is unavailable.
- The source catalogue's field list is outdated; the download contains inflation_yoy and inflation_mom, not index.

## Breaking changes

None observed.

## Reproducibility

```sh
curl -sS --max-time 30 \
  "https://storage.dosm.gov.my/cpi/cpi_2d_core_inflation.csv" \
  -o /tmp/cpi_2d_core_inflation.csv
```

## Licence

Licensed under the Creative Commons Attribution 4.0 licence, as stated on the
official catalogue page.

Attribution: DOSM via OpenDOSM.

## Sample

- [samples/dosm_cpi_core_inflation.csv](../samples/dosm_cpi_core_inflation.csv)
- [samples/dosm_cpi_core_inflation.json](../samples/dosm_cpi_core_inflation.json)
