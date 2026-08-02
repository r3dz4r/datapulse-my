---
dataset_id: dgm_state_finance_expenditure
last_checked: 2026-08-02T16:47:48Z
status: stale
freshness_delta: 688 days since file update
next_expected_update: overdue
record_count: 104
date_range: 2020-01-01 to 2022-01-01
schema_version: 1.0
schema_drift: none
known_quirks: ["Annual dates use 1 January.", "Values are in RM millions.", "Sarawak is represented by 2020 data while the other states use 2022.", "Federal territories are excluded because they do not have State Legislative Assemblies."]
breaking_changes: []
licence: Creative Commons Attribution 4.0
attribution: National Audit Department and Malaysian state governments via data.gov.my
---

# data.gov.my State Government Expenditure

## Provenance

National Audit Department and Malaysian state governments publishes this dataset through data.gov.my as direct CSV and
Parquet downloads:

- `https://storage.data.gov.my/publicadmin/state_finance_expenditure.csv`
- `https://storage.data.gov.my/publicadmin/state_finance_expenditure.parquet`

Catalogue description: [annual actual state-government expenditure by category](https://data.gov.my/data-catalogue/state_finance_expenditure).

## Status

**Status:** Stale

**Freshness:** File last updated 2024-09-13; observations end on 2022-01-01

**Refresh frequency:** Annual

The CSV endpoint returned HTTP 200 and its expected 3,946-byte file. It
contains 104 data rows.

## Last checked

2026-08-02 by direct HTTP HEAD request and CSV download.

## Coverage

The dataset covers Malaysia (13 states; federal territories excluded) from 2020-01-01 through 2022-01-01.

## Schema

| Field | Type | Description |
| --- | --- | --- |
| `state` | string | Malaysian state or federal territory. |
| `date` | date | Observation date in YYYY-MM-DD format. |
| `category` | string | Revenue or expenditure category code. |
| `expenditure` | number | Actual expenditure in RM millions. |

## Known quirks

- Annual dates use 1 January.
- Values are in RM millions.
- Sarawak is represented by 2020 data while the other states use 2022.
- Federal territories are excluded because they do not have State Legislative Assemblies.

## Breaking changes

None observed.

## Reproducibility

```sh
curl -sS --max-time 30 \
  "https://storage.data.gov.my/publicadmin/state_finance_expenditure.csv" \
  -o /tmp/state_finance_expenditure.csv
```

## Licence

Licensed under the Creative Commons Attribution 4.0 licence, as stated on the
official catalogue page.

Attribution: National Audit Department and Malaysian state governments via data.gov.my.

## Sample

- [samples/dgm_state_finance_expenditure.csv](../samples/dgm_state_finance_expenditure.csv)
- [samples/dgm_state_finance_expenditure.json](../samples/dgm_state_finance_expenditure.json)
