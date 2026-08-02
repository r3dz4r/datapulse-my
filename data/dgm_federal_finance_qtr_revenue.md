---
dataset_id: dgm_federal_finance_qtr_revenue
last_checked: 2026-08-02T16:47:48Z
status: stale
freshness_delta: 788 days since file update
next_expected_update: overdue
record_count: 2373
date_range: 1996-01-01 to 2024-01-01
schema_version: 1.0
schema_drift: none
known_quirks: ["Quarterly dates use the first day of each quarter.", "Values are in RM millions.", "Components may not sum exactly because of rounding.", "Data for 2023 is preliminary and may be revised."]
breaking_changes: []
licence: Creative Commons Attribution 4.0
attribution: Accountant General's Department of Malaysia via data.gov.my
---

# data.gov.my Quarterly Federal Government Revenue

## Provenance

Accountant General's Department of Malaysia publishes this dataset through data.gov.my as direct CSV and
Parquet downloads:

- `https://storage.data.gov.my/publicadmin/federal_finance_qtr_revenue.csv`
- `https://storage.data.gov.my/publicadmin/federal_finance_qtr_revenue.parquet`

Catalogue description: [quarterly federal revenue by category and variable](https://data.gov.my/data-catalogue/federal_finance_qtr_revenue).

## Status

**Status:** Stale

**Freshness:** File last updated 2024-06-05; observations end on 2024-01-01

**Refresh frequency:** Quarterly

The CSV endpoint returned HTTP 200 and its expected 78,055-byte file. It
contains 2,373 data rows.

## Last checked

2026-08-02 by direct HTTP HEAD request and CSV download.

## Coverage

The dataset covers Malaysia (federal government) from 1996-01-01 through 2024-01-01.

## Schema

| Field | Type | Description |
| --- | --- | --- |
| `date` | date | Observation date in YYYY-MM-DD format. |
| `category` | string | Revenue or expenditure category code. |
| `variable` | string | Revenue component code. |
| `value` | number | Observed value; units depend on the dataset and series. |

## Known quirks

- Quarterly dates use the first day of each quarter.
- Values are in RM millions.
- Components may not sum exactly because of rounding.
- Data for 2023 is preliminary and may be revised.

## Breaking changes

None observed.

## Reproducibility

```sh
curl -sS --max-time 30 \
  "https://storage.data.gov.my/publicadmin/federal_finance_qtr_revenue.csv" \
  -o /tmp/federal_finance_qtr_revenue.csv
```

## Licence

Licensed under the Creative Commons Attribution 4.0 licence, as stated on the
official catalogue page.

Attribution: Accountant General's Department of Malaysia via data.gov.my.

## Sample

- [samples/dgm_federal_finance_qtr_revenue.csv](../samples/dgm_federal_finance_qtr_revenue.csv)
- [samples/dgm_federal_finance_qtr_revenue.json](../samples/dgm_federal_finance_qtr_revenue.json)
