---
dataset_id: dgm_pekab40_screenings_state
last_checked: 2026-08-16T02:09:20Z
status: aging
freshness_delta: 3 days
next_expected_update: daily
record_count: 42816
date_range: 2019-04-15 to 2026-07-31
schema_version: 1.0
schema_drift: none
known_quirks: ["Dates are daily calendar dates.", "Rows are state-level counts and contain no Malaysia aggregate.", "The series begins on 15 April 2019, reflecting PeKa B40 programme operations."]
breaking_changes: []
licence: Creative Commons Attribution 4.0
attribution: ProtectHealth Corporation and Ministry of Health Malaysia via data.gov.my
---

# data.gov.my Daily PeKaB40 Health Screenings by State

## Status

**Status:** Aging

**Freshness:** 3 days

HTTP 200

## Last checked

2026-08-16 at 02:09:20 UTC.

## File size

The checked resource is 1,009,721 bytes.

## Provenance

ProtectHealth Corporation and Ministry of Health Malaysia publishes this dataset through data.gov.my as direct CSV and
Parquet downloads:

- `https://storage.data.gov.my/healthcare/pekab40_screenings_state.csv`
- `https://storage.data.gov.my/healthcare/pekab40_screenings_state.parquet`

Catalogue description: [Daily healthcare screenings conducted under the PeKaB40 program, at state level. The table provides a preview of the dataset using the most recent year of data.](https://data.gov.my/data-catalogue/pekab40_screenings_state).

## Coverage

The dataset covers Malaysia (16 state-level areas) from 2019-04-15 through 2026-07-31.

## Schema

| Field | Type | Description |
| --- | --- | --- |
| `date` | date | Date in YYYY-MM-DD format |
| `state` | string | One of 16 states |
| `screenings` | integer | Number of health screenings conducted on that date |

## Known quirks

- Dates are daily calendar dates.
- Rows are state-level counts and contain no Malaysia aggregate.
- The series begins on 15 April 2019, reflecting PeKa B40 programme operations.

## Breaking changes

None observed.

## Reproducibility

```sh
curl -sS --max-time 30 \
  "https://storage.data.gov.my/healthcare/pekab40_screenings_state.csv" \
  -o /tmp/pekab40_screenings_state.csv
```

## Licence

Licensed under the Creative Commons Attribution 4.0 licence, as stated on the
official catalogue page.

Attribution: ProtectHealth Corporation and Ministry of Health Malaysia via data.gov.my.

## Sample

- [samples/dgm_pekab40_screenings_state.csv](../samples/dgm_pekab40_screenings_state.csv)
- [samples/dgm_pekab40_screenings_state.json](../samples/dgm_pekab40_screenings_state.json)
