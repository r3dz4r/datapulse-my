---
dataset_id: doe_rqims
last_checked: 2026-08-02T14:00:00Z
status: healthy
freshness_delta: 0 hours
next_expected_update: 2026-08-02T15:00:00Z
record_count: 30
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

**Status:** Healthy  
**Freshness:** 0 hours  
**Refresh frequency:** Hourly

The Camofox-rendered Continuous River view is reachable and reports 30
stations: 20 Clean (WQI 81-100), 10 Slightly Polluted (WQI 60-80), and none
Polluted.

## Last checked

2026-08-02 at 14:00:00 UTC using Camofox.

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
