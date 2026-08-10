---
dataset_id: dgm_schools_district
last_checked: 2026-08-10T10:07:26Z
status: fresh
freshness_delta: 7 days
next_expected_update: overdue
record_count: 3977
date_range: 2017-01-01 to 2022-01-01
schema_version: 1.0
schema_drift: none
known_quirks: ["Annual dates use 1 January.", "National, state, and district aggregates coexist and must not be summed together.", "The dataset covers public primary, secondary, and tertiary institutions recorded in EMIS."]
breaking_changes: []
licence: Creative Commons Attribution 4.0
attribution: Ministry of Education Malaysia via data.gov.my
---

# data.gov.my Public Education Institutions by District

## Status

**Status:** Fresh

**Freshness:** 7 days

HTTP 200

## Last checked

2026-08-10 at 10:07:26 UTC.

## File size

The checked resource is 241,044 bytes.

## Provenance

Ministry of Education Malaysia publishes this dataset through data.gov.my as direct CSV and
Parquet downloads:

- `https://storage.data.gov.my/education/schools_district.csv`
- `https://storage.data.gov.my/education/schools_district.parquet`

Catalogue description: [Number of primary, secondary, and tertiary public education institutions at national, state, and district level.](https://data.gov.my/data-catalogue/schools_district).

## Coverage

The dataset covers Malaysia (national, state, and district level) from 2017-01-01 through 2022-01-01.

## Schema

| Field | Type | Description |
| --- | --- | --- |
| `state` | string | One of 16 states, or Malaysia for national-level data |
| `district` | string | One of 160 administrative districts, or 'All Districts' for state-level data |
| `stage` | string | Either primary, secondary, or tertiary education |
| `type` | string | Type of public school or institution |
| `date` | date | Date in YYYY-MM-DD format, with MM-DD set to 01-01 as the data is at annual frequency |
| `schools` | integer | Number of schools or institutions |

## Known quirks

- Annual dates use 1 January.
- National, state, and district aggregates coexist and must not be summed together.
- The dataset covers public primary, secondary, and tertiary institutions recorded in EMIS.

## Breaking changes

None observed.

## Reproducibility

```sh
curl -sS --max-time 30 \
  "https://storage.data.gov.my/education/schools_district.csv" \
  -o /tmp/schools_district.csv
```

## Licence

Licensed under the Creative Commons Attribution 4.0 licence, as stated on the
official catalogue page.

Attribution: Ministry of Education Malaysia via data.gov.my.

## Sample

- [samples/dgm_schools_district.csv](../samples/dgm_schools_district.csv)
- [samples/dgm_schools_district.json](../samples/dgm_schools_district.json)
