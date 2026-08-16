---
dataset_id: doe_rqims
last_checked: 2026-08-16T01:55:59Z
status: browser-dependent
freshness_delta: 1 days
next_expected_update: 2026-08-02T15:00:00Z
record_count: null
date_range: latest 20 hourly readings
schema_version: 1.0
schema_drift: none
known_quirks: ["JavaScript-rendered and requires Camofox", "later hourly columns may be unpopulated and display N/A", "the Manual River path /RQIMS/manual_river returns 404"]
breaking_changes: []
licence: Open Government Licence (Malaysia)
attribution: DOE Malaysia via MyEQMS
---

# DOE RQIMS River Water Quality (Continuous)

## Status

**Status:** Browser dependent

**Freshness:** 1 days

Camofox unavailable; browser check required

## Last checked

2026-08-16 at 01:55:59 UTC.

## File size

The health snapshot did not report a file size.

## Coverage

The view covers 30 continuous river monitoring stations across Malaysia and
publishes hourly Water Quality Index (WQI) readings.

## Schema

| Field | Type | Description |
| --- | --- | --- |
| `NO` | integer | Row number. |
| `STATE` | string | Malaysian state. |
| `RIVER` | string | Monitored river name. |
| `WATER_INTAKE` | string | Associated water intake. |
| `STATION_ID` | string | DOE continuous-monitoring station identifier. |
| `hr_00` through `hr_19` | integer or null | Twenty hourly WQI columns from 00:00 through 19:00. |
| `REMARKS` | string or null | Portal remarks for the station. |

## Known quirks

- The table is JavaScript-rendered and collection requires Camofox.
- The first approximately 10 hourly columns may be populated while later
  hours display `N/A`; normalized JSON represents those values as `null`.
- Only the Continuous River view is available. The Manual River URL
  `https://eqms.doe.gov.my/RQIMS/manual_river` returns 404.

## Breaking changes

None observed.

## Sample

- [samples/doe_rqims.csv](samples/doe_rqims.csv)
- [samples/doe_rqims.json](samples/doe_rqims.json)

## Reproducibility

Open `https://eqms.doe.gov.my/RQIMS/conti_river` in Camofox, wait 12 seconds
for the table to render, capture the accessibility snapshot, and close the tab.

## Licence

Licensed under the Open Government Licence (Malaysia).

Attribution: DOE Malaysia via MyEQMS.
