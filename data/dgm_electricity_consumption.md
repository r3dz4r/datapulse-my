---
dataset_id: dgm_electricity_consumption
last_checked: 2026-08-03T02:00:00Z
status: stale
freshness_delta: 690 days since file update
next_expected_update: overdue
record_count: 468
date_range: 2018-01-01 to 2024-06-01
schema_version: 1.0
schema_drift: none
known_quirks: ["Monthly dates use the first day of the month.", "The `total` and `local` aggregates coexist with detailed sectors and must not be summed together.", "Consumption is measured in millions of kilowatt-hours (MKWh).", "The most recent six months may be revised."]
breaking_changes: []
licence: Creative Commons Attribution 4.0
attribution: Energy Commission, DOSM, and Malaysian electricity utilities via data.gov.my
---

# data.gov.my Monthly Electricity Consumption

## Provenance

Energy Commission and electricity utilities publishes this dataset through data.gov.my as direct CSV and
Parquet downloads:

- `https://storage.data.gov.my/energy/electricity_consumption.csv`
- `https://storage.data.gov.my/energy/electricity_consumption.parquet`

Catalogue description: [Monthly electricity consumption by sector.](https://data.gov.my/data-catalogue/electricity_consumption).

## Status

**Status:** Stale

**Freshness:** File last updated 2024-09-12; observations end on 2024-06-01

**Refresh frequency:** Monthly

The CSV endpoint returned HTTP 200 and its expected 17,338-byte file. It
contains 468 data rows.

## Last checked

2026-08-03 by direct HTTP HEAD request and CSV download.

## Coverage

The dataset covers Malaysia (national) from 2018-01-01 through 2024-06-01.

## Schema

| Field | Type | Description |
| --- | --- | --- |
| `date` | date | The date in YYYY-MM-DD format, with DD set to 01 as the data is at monthly frequency |
| `sector` | string | All sectors ('total'), local ('local') with breakdowns into commercial ('local_commercial') and domestic ('local_domestic') use, exports ('exports'), or losses ('losses'). Commercial usage includes the industrial and mining sectors, while domestic usage includes public lighting. |
| `consumption` | number | Amount of electricity consumed in millions of kilowatt-hours (MKWh) |

## Known quirks

- Monthly dates use the first day of the month.
- The `total` and `local` aggregates coexist with detailed sectors and must not be summed together.
- Consumption is measured in millions of kilowatt-hours (MKWh).
- The most recent six months may be revised.

## Breaking changes

None observed.

## Reproducibility

```sh
curl -sS --max-time 30 \
  "https://storage.data.gov.my/energy/electricity_consumption.csv" \
  -o /tmp/electricity_consumption.csv
```

## Licence

Licensed under the Creative Commons Attribution 4.0 licence, as stated on the
official catalogue page.

Attribution: Energy Commission, DOSM, and Malaysian electricity utilities via data.gov.my.

## Sample

- [samples/dgm_electricity_consumption.csv](../samples/dgm_electricity_consumption.csv)
- [samples/dgm_electricity_consumption.json](../samples/dgm_electricity_consumption.json)
