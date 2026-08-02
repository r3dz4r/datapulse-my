---
dataset_id: dgm_cellular_subscribers
last_checked: 2026-08-03T02:00:00Z
status: stale
freshness_delta: 614 days since file update
next_expected_update: overdue
record_count: 66
date_range: 2000-01-01 to 2021-01-01
schema_version: 1.0
schema_drift: none
known_quirks: ["Annual dates use 1 January.", "Total-plan rows coexist with prepaid and postpaid rows and must not be summed together.", "Counts represent subscriptions rather than unique people, so a person with multiple plans is counted multiple times.", "Eight subscription values are blank."]
breaking_changes: []
licence: Creative Commons Attribution 4.0
attribution: MCMC via data.gov.my
---

# data.gov.my Cellular Subscribers by Plan Type

## Provenance

Malaysian Communications and Multimedia Commission publishes this dataset through data.gov.my as direct CSV and
Parquet downloads:

- `https://storage.data.gov.my/communications/cellular_subscribers.csv`
- `https://storage.data.gov.my/communications/cellular_subscribers.parquet`

Catalogue description: [Annual data on the number of postpaid and prepaid cellular subscribers in Malaysia.](https://data.gov.my/data-catalogue/cellular_subscribers).

## Status

**Status:** Stale

**Freshness:** File last updated 2024-11-27; observations end on 2021-01-01

**Refresh frequency:** Annual

The CSV endpoint returned HTTP 200 and its expected 1,770-byte file. It
contains 66 data rows.

## Last checked

2026-08-03 by direct HTTP HEAD request and CSV download.

## Coverage

The dataset covers Malaysia (national) from 2000-01-01 through 2021-01-01.

## Schema

| Field | Type | Description |
| --- | --- | --- |
| `date` | date | The year of the data in YYYY-MM-DD format, with MM-DD set to 01-01 because the data is annual. |
| `plan` | string | The type of cellular plan: total, postpaid, or prepaid. |
| `subscriptions` | integer | The number of cellular subscriptions. |

## Known quirks

- Annual dates use 1 January.
- Total-plan rows coexist with prepaid and postpaid rows and must not be summed together.
- Counts represent subscriptions rather than unique people, so a person with multiple plans is counted multiple times.
- Eight subscription values are blank.

## Breaking changes

None observed.

## Reproducibility

```sh
curl -sS --max-time 30 \
  "https://storage.data.gov.my/communications/cellular_subscribers.csv" \
  -o /tmp/cellular_subscribers.csv
```

## Licence

Licensed under the Creative Commons Attribution 4.0 licence, as stated on the
official catalogue page.

Attribution: MCMC via data.gov.my.

## Sample

- [samples/dgm_cellular_subscribers.csv](../samples/dgm_cellular_subscribers.csv)
- [samples/dgm_cellular_subscribers.json](../samples/dgm_cellular_subscribers.json)
