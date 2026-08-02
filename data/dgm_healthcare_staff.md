---
dataset_id: dgm_healthcare_staff
last_checked: 2026-08-03T02:00:00Z
status: stale
freshness_delta: 675 days since file update
next_expected_update: overdue
record_count: 765
date_range: 2014-01-01 to 2022-01-01
schema_version: 1.0
schema_drift: none
known_quirks: ["Annual dates use 1 January, while staff counts reflect active staff at 31 December.", "Malaysia-level and state-level rows coexist and must not be summed together.", "The `all` staff type coexists with four detailed staff-type categories."]
breaking_changes: []
licence: Creative Commons Attribution 4.0
attribution: Ministry of Health Malaysia via data.gov.my
---

# data.gov.my Healthcare Staff by State and Staff Type

## Provenance

Ministry of Health Malaysia publishes this dataset through data.gov.my as direct CSV and
Parquet downloads:

- `https://storage.data.gov.my/healthcare/healthcare_staff.csv`
- `https://storage.data.gov.my/healthcare/healthcare_staff.parquet`

Catalogue description: [Number of public sector healthcare staff at national and state level, with a breakdown by staff type.](https://data.gov.my/data-catalogue/healthcare_staff).

## Status

**Status:** Stale

**Freshness:** File last updated 2024-09-27; observations end on 2022-01-01

**Refresh frequency:** Annual

The CSV endpoint returned HTTP 200 and its expected 25,802-byte file. It
contains 765 data rows.

## Last checked

2026-08-03 by direct HTTP HEAD request and CSV download.

## Coverage

The dataset covers Malaysia (national and state level) from 2014-01-01 through 2022-01-01.

## Schema

| Field | Type | Description |
| --- | --- | --- |
| `state` | string | One of 16 states, or Malaysia for national-level data |
| `type` | string | Either doctors ('doctor'), nurses ('nurse'), community nurses ('nurse_community'), dentists ('dentist'), or all staff ('all') |
| `date` | date | Date in YYYY-MM-DD format, with MM-DD set to 01-01 as the data is at annual frequency |
| `staff` | integer | Number of active staff |

## Known quirks

- Annual dates use 1 January, while staff counts reflect active staff at 31 December.
- Malaysia-level and state-level rows coexist and must not be summed together.
- The `all` staff type coexists with four detailed staff-type categories.

## Breaking changes

None observed.

## Reproducibility

```sh
curl -sS --max-time 30 \
  "https://storage.data.gov.my/healthcare/healthcare_staff.csv" \
  -o /tmp/healthcare_staff.csv
```

## Licence

Licensed under the Creative Commons Attribution 4.0 licence, as stated on the
official catalogue page.

Attribution: Ministry of Health Malaysia via data.gov.my.

## Sample

- [samples/dgm_healthcare_staff.csv](../samples/dgm_healthcare_staff.csv)
- [samples/dgm_healthcare_staff.json](../samples/dgm_healthcare_staff.json)
