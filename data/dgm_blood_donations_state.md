---
dataset_id: dgm_blood_donations_state
last_checked: 2026-08-13T02:46:04Z
status: fresh
freshness_delta: 0 days
next_expected_update: daily
record_count: 489385
date_range: 2006-01-01 to 2026-08-01
schema_version: 1.0
schema_drift: none
known_quirks: ["Dates are daily calendar dates.", "The `all` blood-group rows coexist with the four detailed blood groups and must not be summed together.", "The 22 BBISv2 sites cover about 80% of donations; Perlis and W.P. Labuan are unavailable.", "W.P. Kuala Lumpur includes W.P. Putrajaya and mobile campaigns around Selangor."]
breaking_changes: []
licence: Creative Commons Attribution 4.0
attribution: National Blood Centre and Ministry of Health Malaysia via data.gov.my
---

# data.gov.my Daily Blood Donations by Blood Group & State

## Status

**Status:** Fresh

**Freshness:** 0 days

HTTP 200

## Last checked

2026-08-13 at 02:46:04 UTC.

## File size

The checked resource is 12,563,835 bytes.

## Provenance

National Blood Centre and Ministry of Health Malaysia publishes this dataset through data.gov.my as direct CSV and
Parquet downloads:

- `https://storage.data.gov.my/healthcare/blood_donations_state.csv`
- `https://storage.data.gov.my/healthcare/blood_donations_state.parquet`

Catalogue description: [Daily blood donations at state level for each of the 4 major blood groups. The table provides a preview of the dataset using the most recent year of data.](https://data.gov.my/data-catalogue/blood_donations_state).

## Coverage

The dataset covers Malaysia (13 reported state-level areas) from 2006-01-01 through 2026-08-01.

## Schema

| Field | Type | Description |
| --- | --- | --- |
| `date` | date | Date in YYYY-MM-DD format |
| `state` | string | One of 13 states - data for Perlis and W.P. Labuan is not available for now, while data for W.P. Putrajaya is recorded under W.P. Kuala Lumpur. |
| `blood_type` | string | One of 4 major blood groups (A, B, AB, O) or all groups ('all') |
| `donations` | integer | Number of blood donation transactions on that date. |

## Known quirks

- Dates are daily calendar dates.
- The `all` blood-group rows coexist with the four detailed blood groups and must not be summed together.
- The 22 BBISv2 sites cover about 80% of donations; Perlis and W.P. Labuan are unavailable.
- W.P. Kuala Lumpur includes W.P. Putrajaya and mobile campaigns around Selangor.

## Breaking changes

None observed.

## Reproducibility

```sh
curl -sS --max-time 30 \
  "https://storage.data.gov.my/healthcare/blood_donations_state.csv" \
  -o /tmp/blood_donations_state.csv
```

## Licence

Licensed under the Creative Commons Attribution 4.0 licence, as stated on the
official catalogue page.

Attribution: National Blood Centre and Ministry of Health Malaysia via data.gov.my.

## Sample

- [samples/dgm_blood_donations_state.csv](../samples/dgm_blood_donations_state.csv)
- [samples/dgm_blood_donations_state.json](../samples/dgm_blood_donations_state.json)
