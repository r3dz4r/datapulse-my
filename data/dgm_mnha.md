---
dataset_id: dgm_mnha
last_checked: 2026-08-05T14:31:11Z
status: aging
freshness_delta: 631 days
next_expected_update: overdue
record_count: 60
date_range: 2013-01-01 to 2022-01-01
schema_version: 1.0
schema_drift: none
known_quirks: ["Annual dates use 1 January.", "Total-sector rows coexist with public- and private-sector rows and must not be summed together.", "Current expenditure on health excludes health-related expenditure included in total expenditure on health.", "Values are Malaysian ringgit and may be revised with methodology updates."]
breaking_changes: []
licence: Creative Commons Attribution 4.0
attribution: Ministry of Health Malaysia via data.gov.my
---

# data.gov.my MNHA: Total (TEH) and Current (CHE) Expenditure on Health

## Status

**Status:** Aging

**Freshness:** 631 days

HTTP 200

## Last checked

2026-08-05 at 14:31:11 UTC.

## File size

The checked resource is 2,450 bytes.

## Provenance

Ministry of Health Malaysia publishes this dataset through data.gov.my as direct CSV and
Parquet downloads:

- `https://storage.data.gov.my/healthcare/mnha.csv`
- `https://storage.data.gov.my/healthcare/mnha.parquet`

Catalogue description: [Total and current expenditure on health in Malaysia, with a breakdown into public and private sectors.](https://data.gov.my/data-catalogue/mnha).

## Coverage

The dataset covers Malaysia (national) from 2013-01-01 through 2022-01-01.

## Schema

| Field | Type | Description |
| --- | --- | --- |
| `date` | date | The year of the expenditure in YYYY-MM-DD format, with MM-DD set to 01-01 because the data is an annual frequency. |
| `variable` | string | Type of expenditure: Total Expenditure on Health (TEH) or Current Expenditure on Health (CEH). |
| `sector` | string | Sector of expenditure: total, private, or public. |
| `expenditure` | number | The amount of expenditure in Malaysian Ringgit. |

## Known quirks

- Annual dates use 1 January.
- Total-sector rows coexist with public- and private-sector rows and must not be summed together.
- Current expenditure on health excludes health-related expenditure included in total expenditure on health.
- Values are Malaysian ringgit and may be revised with methodology updates.

## Breaking changes

None observed.

## Reproducibility

```sh
curl -sS --max-time 30 \
  "https://storage.data.gov.my/healthcare/mnha.csv" \
  -o /tmp/mnha.csv
```

## Licence

Licensed under the Creative Commons Attribution 4.0 licence, as stated on the
official catalogue page.

Attribution: Ministry of Health Malaysia via data.gov.my.

## Sample

- [samples/dgm_mnha.csv](../samples/dgm_mnha.csv)
- [samples/dgm_mnha.json](../samples/dgm_mnha.json)
