---
dataset_id: ridership_headline
last_checked: 2026-08-14T04:59:27Z
status: stale
freshness_delta: 14 days
next_expected_update: daily
record_count: 2769
date_range: 2019-01-01 to 2026-06-30
schema_version: 1.0
schema_drift: none
known_quirks: ["Dates are daily calendar dates, but audited headline totals are published monthly.", "Values count trips, not unique passengers.", "Service columns begin on different dates and therefore contain blanks.", "Prasarana line totals should not be reconstructed by summing origin-destination data."]
breaking_changes: []
licence: Creative Commons Attribution 4.0
attribution: Prasarana, KTMB, and Ministry of Transport Malaysia via data.gov.my
---

# data.gov.my Daily Public Transport Ridership

## Status

**Status:** Stale

**Freshness:** 14 days

HTTP 200

## Last checked

2026-08-14 at 04:59:27 UTC.

## File size

The checked resource is 202,418 bytes.

## Provenance

Ministry of Transport Malaysia and public transport operators publishes this dataset through data.gov.my as direct CSV and
Parquet downloads:

- `https://storage.data.gov.my/transportation/ridership_headline.csv`
- `https://storage.data.gov.my/transportation/ridership_headline.parquet`

Catalogue description: [Daily-frequency ridership data for various public transport services across the country.](https://data.gov.my/data-catalogue/ridership_headline).

## Coverage

The dataset covers Malaysia (selected major public transport services) from 2019-01-01 through 2026-06-30.

## Schema

| Field | Type | Description |
| --- | --- | --- |
| `date` | date | Date in YYYY-MM-DD format |
| `bus_rkl` | integer | Number of trips, NOT number of unique individuals |
| `bus_rkn` | integer | Number of trips, NOT number of unique individuals |
| `bus_rpn` | integer | Number of trips, NOT number of unique individuals |
| `rail_lrt_ampang` | integer | Number of trips, NOT number of unique individuals |
| `rail_mrt_kajang` | integer | Number of trips, NOT number of unique individuals |
| `rail_lrt_kj` | integer | Number of trips, NOT number of unique individuals |
| `rail_monorail` | integer | Number of trips, NOT number of unique individuals |
| `rail_mrt_pjy` | integer | Number of trips, NOT number of unique individuals |
| `rail_ets` | integer | Number of trips, NOT number of unique individuals |
| `rail_intercity` | integer | Number of trips, NOT number of unique individuals |
| `rail_komuter_utara` | integer | Number of trips, NOT number of unique individuals |
| `rail_tebrau` | integer | Number of trips, NOT number of unique individuals |
| `rail_komuter` | integer | Number of trips, NOT number of unique individuals |

## Known quirks

- Dates are daily calendar dates, but audited headline totals are published monthly.
- Values count trips, not unique passengers.
- Service columns begin on different dates and therefore contain blanks.
- Prasarana line totals should not be reconstructed by summing origin-destination data.

## Breaking changes

None observed.

## Reproducibility

```sh
curl -sS --max-time 30 \
  "https://storage.data.gov.my/transportation/ridership_headline.csv" \
  -o /tmp/ridership_headline.csv
```

## Licence

Licensed under the Creative Commons Attribution 4.0 licence, as stated on the
official catalogue page.

Attribution: Prasarana, KTMB, and Ministry of Transport Malaysia via data.gov.my.

## Sample

- [samples/dgm_ridership_headline.csv](../samples/dgm_ridership_headline.csv)
- [samples/dgm_ridership_headline.json](../samples/dgm_ridership_headline.json)
