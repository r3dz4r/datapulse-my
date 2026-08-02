---
dataset_id: dgm_federal_finance_qtr_oe
last_checked: 2026-08-02T16:47:48Z
status: stale
freshness_delta: 788 days since file update
next_expected_update: overdue
record_count: 1111
date_range: 1999-01-01 to 2024-01-01
schema_version: 1.0
schema_drift: none
known_quirks: ["Quarterly dates use the first day of each quarter.", "Values are in RM millions.", "Operating expenditure includes specified grants and transfers.", "Components may not sum exactly because of rounding; 2023 data is preliminary."]
breaking_changes: []
licence: Creative Commons Attribution 4.0
attribution: Accountant General's Department of Malaysia via data.gov.my
---

# data.gov.my Quarterly Federal Operating Expenditure

## Provenance

Accountant General's Department of Malaysia publishes this dataset through data.gov.my as direct CSV and
Parquet downloads:

- `https://storage.data.gov.my/publicadmin/federal_finance_qtr_oe.csv`
- `https://storage.data.gov.my/publicadmin/federal_finance_qtr_oe.parquet`

Catalogue description: [quarterly federal operating expenditure by object](https://data.gov.my/data-catalogue/federal_finance_qtr_oe).

## Status

**Status:** Stale

**Freshness:** File last updated 2024-06-05; observations end on 2024-01-01

**Refresh frequency:** Quarterly

The CSV endpoint returned HTTP 200 and its expected 33,278-byte file. It
contains 1,111 data rows.

## Last checked

2026-08-02 by direct HTTP HEAD request and CSV download.

## Coverage

The dataset covers Malaysia (federal government) from 1999-01-01 through 2024-01-01.

## Schema

| Field | Type | Description |
| --- | --- | --- |
| `date` | date | Observation date in YYYY-MM-DD format. |
| `object` | string | Operating-expenditure object code. |
| `value` | number | Observed value; units depend on the dataset and series. |

## Known quirks

- Quarterly dates use the first day of each quarter.
- Values are in RM millions.
- Operating expenditure includes specified grants and transfers.
- Components may not sum exactly because of rounding; 2023 data is preliminary.

## Breaking changes

None observed.

## Reproducibility

```sh
curl -sS --max-time 30 \
  "https://storage.data.gov.my/publicadmin/federal_finance_qtr_oe.csv" \
  -o /tmp/federal_finance_qtr_oe.csv
```

## Licence

Licensed under the Creative Commons Attribution 4.0 licence, as stated on the
official catalogue page.

Attribution: Accountant General's Department of Malaysia via data.gov.my.

## Sample

- [samples/dgm_federal_finance_qtr_oe.csv](../samples/dgm_federal_finance_qtr_oe.csv)
- [samples/dgm_federal_finance_qtr_oe.json](../samples/dgm_federal_finance_qtr_oe.json)
