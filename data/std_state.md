---
dataset_id: dgm_std_state
last_checked: 2026-08-16T02:09:20Z
status: stale
freshness_delta: 1688 days
next_expected_update: overdue
record_count: 480
date_range: 2017-01-01 to 2022-01-01
schema_version: 1.0
schema_drift: none
known_quirks: ["Annual dates use 1 January.", "Records use the date of report rather than the date of the event.", "Incidence is the number of new cases per 100,000 population, and reporting completeness varies by disease and state."]
breaking_changes: []
licence: Creative Commons Attribution 4.0
attribution: Ministry of Health Malaysia via data.gov.my
---

# data.gov.my Sexually Transmitted Diseases (STDs) by State

## Status

**Status:** Stale

**Freshness:** 1688 days

HTTP 200

## Last checked

2026-08-16 at 02:09:20 UTC.

## File size

The checked resource is 17,483 bytes.

## Provenance

Ministry of Health Malaysia publishes this dataset through data.gov.my as direct CSV and
Parquet downloads:

- `https://storage.data.gov.my/healthcare/std_state.csv`
- `https://storage.data.gov.my/healthcare/std_state.parquet`

Catalogue description: [Number and incidence of sexually transmitted diseases (STDs) by state, covering HIV, AIDS, chancroid, gonorrhea, and syphilis.](https://data.gov.my/data-catalogue/std_state).

## Coverage

The dataset covers Malaysia (national and state level) from 2017-01-01 through 2022-01-01.

## Schema

| Field | Type | Description |
| --- | --- | --- |
| `date` | date | The date in YYYY-MM-DD format, with MM-DD set to 01-01 as the data is at annual frequency |
| `state` | string | One of 16 states, or Malaysia; data for W.P. Putrajaya is subsumed under W.P. Kuala Lumpur. |
| `disease` | string | The type of sexually transmitted disease (STD) |
| `cases` | integer | Number of reported cases, classified based on the date of report |
| `incidence` | number | Incidence rate per 100,000 population in the state |

## Known quirks

- Annual dates use 1 January.
- Records use the date of report rather than the date of the event.
- Incidence is the number of new cases per 100,000 population, and reporting completeness varies by disease and state.

## Breaking changes

None observed.

## Reproducibility

```sh
curl -sS --max-time 30 \
  "https://storage.data.gov.my/healthcare/std_state.csv" \
  -o /tmp/std_state.csv
```

## Licence

Licensed under the Creative Commons Attribution 4.0 licence, as stated on the
official catalogue page.

Attribution: Ministry of Health Malaysia via data.gov.my.

## Sample

- [samples/dgm_std_state.csv](../samples/dgm_std_state.csv)
- [samples/dgm_std_state.json](../samples/dgm_std_state.json)
