---
dataset_id: dgm_ktmb_ridership_monthly
last_checked: 2026-08-03T02:00:00Z
status: current
freshness_delta: 2 days since file update
next_expected_update: monthly
record_count: 290
date_range: 2020-11-01 to 2026-07-01
schema_version: 1.0
schema_drift: none
known_quirks: ["Monthly dates use the first day of the month.", "Values count trips, not unique passengers.", "The five services have different starting dates because KITS was rolled out in phases."]
breaking_changes: []
licence: Creative Commons Attribution 4.0
attribution: KTMB and Ministry of Transport Malaysia via data.gov.my
---

# data.gov.my Monthly KTMB Ridership

## Provenance

Keretapi Tanah Melayu Berhad publishes this dataset through data.gov.my as direct CSV and
Parquet downloads:

- `https://storage.data.gov.my/transportation/ktmb/ridership_ktmb_monthly.csv`
- `https://storage.data.gov.my/transportation/ktmb/ridership_ktmb_monthly.parquet`

Catalogue description: [Monthly-frequency ridership data for the 5 main KTMB services, namely Komuter, Komuter Utara, Intercity, ETS and Shuttle Tebrau.](https://data.gov.my/data-catalogue/ridership_ktmb_monthly).

## Status

**Status:** Current

**Freshness:** File last updated 2026-08-01; observations extend through 2026-07-01

**Refresh frequency:** Monthly

The CSV endpoint returned HTTP 200 and its expected 8,136-byte file. It
contains 290 data rows.

## Last checked

2026-08-03 by direct HTTP HEAD request and CSV download.

## Coverage

The dataset covers Malaysia (five KTMB services) from 2020-11-01 through 2026-07-01.

## Schema

| Field | Type | Description |
| --- | --- | --- |
| `date` | date | Date in YYYY-MM-DD format, with DD set to 01 as the data is at monthly frequency |
| `service` | string | One of 5 services (Komuter, Komuter Utara, Intercity, ETS, Shuttle Tebrau) in lower snake case |
| `ridership` | integer | Number of trips taken using the service; it should be noted that this may not equal the number of passengers, as a single passenger may take multiple trips within the same month |

## Known quirks

- Monthly dates use the first day of the month.
- Values count trips, not unique passengers.
- The five services have different starting dates because KITS was rolled out in phases.

## Breaking changes

None observed.

## Reproducibility

```sh
curl -sS --max-time 30 \
  "https://storage.data.gov.my/transportation/ktmb/ridership_ktmb_monthly.csv" \
  -o /tmp/ridership_ktmb_monthly.csv
```

## Licence

Licensed under the Creative Commons Attribution 4.0 licence, as stated on the
official catalogue page.

Attribution: KTMB and Ministry of Transport Malaysia via data.gov.my.

## Sample

- [samples/dgm_ktmb_ridership_monthly.csv](../samples/dgm_ktmb_ridership_monthly.csv)
- [samples/dgm_ktmb_ridership_monthly.json](../samples/dgm_ktmb_ridership_monthly.json)
