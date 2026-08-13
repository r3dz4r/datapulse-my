---
dataset_id: dosm_cpi_core_inflation
last_checked: 2026-08-11T14:21:08Z
status: aging
freshness_delta: 71 days
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

## Status

**Status:** Aging

**Freshness:** 71 days

HTTP 200

## Last checked

2026-08-11 at 14:21:08 UTC.

## File size

The checked resource is 30,978 bytes.

## Provenance

Department of Statistics Malaysia publishes this dataset through OpenDOSM as direct CSV and
Parquet downloads:

- `https://storage.dosm.gov.my/cpi/cpi_2d_core_inflation.csv`
- `https://storage.dosm.gov.my/cpi/cpi_2d_core_inflation.parquet`

Catalogue description: [national core CPI inflation for the main groups of goods and services](https://open.dosm.gov.my/data-catalogue/cpi_core_inflation).

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
