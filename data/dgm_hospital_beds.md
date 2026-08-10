---
dataset_id: dgm_hospital_beds
last_checked: 2026-08-10T04:08:14Z
status: stale
freshness_delta: 1682 days
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

## Status

**Status:** Stale

**Freshness:** 1682 days

HTTP 200

## Last checked

2026-08-10 at 04:08:14 UTC.

## File size

The checked resource is 260,704 bytes.

## Provenance

Ministry of Health Malaysia publishes this dataset through data.gov.my as direct CSV and
Parquet downloads:

- `https://storage.data.gov.my/healthcare/hospital_beds.csv`
- `https://storage.data.gov.my/healthcare/hospital_beds.parquet`

Catalogue description: [Number of public sector hospital beds at national, state, and district level, with a breakdown by hospital type.](https://data.gov.my/data-catalogue/hospital_beds).

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
