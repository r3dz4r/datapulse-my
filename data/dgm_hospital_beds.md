---
dataset_id: dgm_hospital_beds
last_checked: 2026-08-03T02:00:00Z
status: stale
freshness_delta: 675 days since file update
next_expected_update: overdue
record_count: 5468
date_range: 2015-01-01 to 2022-01-01
schema_version: 1.0
schema_drift: none
known_quirks: ["Annual dates use 1 January, while bed counts reflect active beds at 31 December.", "National, state, district, and hospital-type aggregates coexist and must not be summed together.", "The `all` hospital type coexists with three detailed hospital-type categories."]
breaking_changes: []
licence: Creative Commons Attribution 4.0
attribution: Ministry of Health Malaysia via data.gov.my
---

# data.gov.my Hospital Beds by State and Hospital Type

## Provenance

Ministry of Health Malaysia publishes this dataset through data.gov.my as direct CSV and
Parquet downloads:

- `https://storage.data.gov.my/healthcare/hospital_beds.csv`
- `https://storage.data.gov.my/healthcare/hospital_beds.parquet`

Catalogue description: [Number of public sector hospital beds at national, state, and district level, with a breakdown by hospital type.](https://data.gov.my/data-catalogue/hospital_beds).

## Status

**Status:** Stale

**Freshness:** File last updated 2024-09-27; observations end on 2022-01-01

**Refresh frequency:** Annual

The CSV endpoint returned HTTP 200 and its expected 260,704-byte file. It
contains 5,468 data rows.

## Last checked

2026-08-03 by direct HTTP HEAD request and CSV download.

## Coverage

The dataset covers Malaysia (national, state, and district level) from 2015-01-01 through 2022-01-01.

## Schema

| Field | Type | Description |
| --- | --- | --- |
| `date` | date | Date in YYYY-MM-DD format, with MM-DD set to 01-01 as the data is at annual frequency |
| `state` | string | One of 16 states, or Malaysia for national-level data |
| `district` | string | One of 160 administrative districts, or 'All Districts' for state-level data |
| `type` | string | Either an MoH-administered hospital ('hospital_moh'), MoH-administered special medical institution ('special_medical_institution'), or non-MoH hospital ('hospital_non_moh'). Special medical institutions refer to institutions with a specific focus, such as on cancer, heart disease, etc. Non-MoH hospitals refer to government hospitals under the purview of other agencies, such as army hospitals. |
| `beds` | integer | Number of hospital beds |

## Known quirks

- Annual dates use 1 January, while bed counts reflect active beds at 31 December.
- National, state, district, and hospital-type aggregates coexist and must not be summed together.
- The `all` hospital type coexists with three detailed hospital-type categories.

## Breaking changes

None observed.

## Reproducibility

```sh
curl -sS --max-time 30 \
  "https://storage.data.gov.my/healthcare/hospital_beds.csv" \
  -o /tmp/hospital_beds.csv
```

## Licence

Licensed under the Creative Commons Attribution 4.0 licence, as stated on the
official catalogue page.

Attribution: Ministry of Health Malaysia via data.gov.my.

## Sample

- [samples/dgm_hospital_beds.csv](../samples/dgm_hospital_beds.csv)
- [samples/dgm_hospital_beds.json](../samples/dgm_hospital_beds.json)
