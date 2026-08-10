---
dataset_id: dgm_state_finance_expenditure
last_checked: 2026-08-09T08:37:11Z
status: stale
freshness_delta: 1681 days
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

## Status

**Status:** Stale

**Freshness:** 1681 days

HTTP 200

## Last checked

2026-08-09 at 08:37:11 UTC.

## File size

The checked resource is 3,946 bytes.

## Provenance

National Audit Department and Malaysian state governments publishes this dataset through data.gov.my as direct CSV and
Parquet downloads:

- `https://storage.data.gov.my/publicadmin/state_finance_expenditure.csv`
- `https://storage.data.gov.my/publicadmin/state_finance_expenditure.parquet`

Catalogue description: [annual actual state-government expenditure by category](https://data.gov.my/data-catalogue/state_finance_expenditure).

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
