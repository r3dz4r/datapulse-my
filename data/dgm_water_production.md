---
dataset_id: dgm_water_production
last_checked: 2026-08-03T02:00:00Z
status: stale
freshness_delta: 680 days since file update
next_expected_update: overdue
record_count: 345
date_range: 2000-01-01 to 2022-01-01
schema_version: 1.0
schema_drift: none
known_quirks: ["Observed dates are annual and use 1 January.", "Malaysia-level and state-level rows coexist and must not be summed together.", "Values are millions of litres per day (MLD).", "W.P. Kuala Lumpur and W.P. Putrajaya are included under Selangor; the most recent year is provisional."]
breaking_changes: []
licence: Creative Commons Attribution 4.0
attribution: SPAN, NRES, and DOSM via data.gov.my
---

# data.gov.my Water Production by State

## Provenance

National Water Services Commission publishes this dataset through data.gov.my as direct CSV and
Parquet downloads:

- `https://storage.data.gov.my/water/water_production.csv`
- `https://storage.data.gov.my/water/water_production.parquet`

Catalogue description: [Annual water production by state.](https://data.gov.my/data-catalogue/water_production).

## Status

**Status:** Stale

**Freshness:** File last updated 2024-09-22; observations end on 2022-01-01

**Refresh frequency:** Annual

The CSV endpoint returned HTTP 200 and its expected 8,366-byte file. It
contains 345 data rows.

## Last checked

2026-08-03 by direct HTTP HEAD request and CSV download.

## Coverage

The dataset covers Malaysia (national and 14 reported state-level areas) from 2000-01-01 through 2022-01-01.

## Schema

| Field | Type | Description |
| --- | --- | --- |
| `state` | string | One of 16 states, or Malaysia, which has been included for ease of analysis |
| `date` | date | The date in YYYY-MM-DD format, with MM-DD set to 01-01 as the data is at monthly frequency |
| `value` | integer | Amount of water produced in millions of litres per day (MLD) |

## Known quirks

- Observed dates are annual and use 1 January.
- Malaysia-level and state-level rows coexist and must not be summed together.
- Values are millions of litres per day (MLD).
- W.P. Kuala Lumpur and W.P. Putrajaya are included under Selangor; the most recent year is provisional.

## Breaking changes

None observed.

## Reproducibility

```sh
curl -sS --max-time 30 \
  "https://storage.data.gov.my/water/water_production.csv" \
  -o /tmp/water_production.csv
```

## Licence

Licensed under the Creative Commons Attribution 4.0 licence, as stated on the
official catalogue page.

Attribution: SPAN, NRES, and DOSM via data.gov.my.

## Sample

- [samples/dgm_water_production.csv](../samples/dgm_water_production.csv)
- [samples/dgm_water_production.json](../samples/dgm_water_production.json)
