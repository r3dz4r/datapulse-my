---
dataset_id: doe_apims
last_checked: 2026-08-02T14:00:00Z
status: healthy
freshness_delta: 0 hours
next_expected_update: 2026-08-02T15:00:00Z
record_count: 68
date_range: latest 16 hourly readings
schema_version: 1.0
schema_drift: none
known_quirks: ["JavaScript-rendered and requires Camofox", "double asterisk means two or more parameters share the same dominant API index", "legacy apims.doe.gov.my is blocked by anti-bot protection"]
breaking_changes: []
licence: Open Government Licence (Malaysia)
attribution: DOE Malaysia via MyEQMS
---

# DOE APIMS Air Quality (Hourly API)

## Status

**Status:** Healthy  
**Freshness:** 0 hours  
**Refresh frequency:** Hourly

The Camofox-rendered MyEQMS view is reachable and reports 68 stations: 23
Good, 45 Moderate, and none in the Unhealthy or higher categories.

## Last checked

2026-08-02 at 14:00:00 UTC using Camofox.

## Coverage

The view covers 68 Malaysian air-quality monitoring stations. It reports the
Air Pollutant Index (API) derived from pollutant readings for PM2.5, PM10, SO2,
NO2, O3, and CO.

## Schema

| Field | Type | Description |
| --- | --- | --- |
| `NO` | integer | Row number. |
| `STATE` | string | Malaysian state. |
| `LOCATION` | string | Monitoring-station location. |
| `hr_22` through `hr_13` | integer or null | Sixteen hourly API readings, ordered 22:00, 23:00, then 00:00 through 13:00. |

## Known quirks

- The table is JavaScript-rendered and collection requires Camofox.
- A `**` suffix means two or more pollutant parameters share the same dominant
  API index; normalized samples omit this display suffix.
- The legacy `apims.doe.gov.my` host returns 403 anti-bot responses. Use the
  current `eqms.doe.gov.my/APIMS/main` view.

## Breaking changes

None observed.

## Sample

- [samples/doe_apims.csv](samples/doe_apims.csv)
- [samples/doe_apims.json](samples/doe_apims.json)

## Reproducibility

Open `https://eqms.doe.gov.my/APIMS/main` in Camofox, wait 10 seconds for the
table to render, capture the accessibility snapshot, and close the tab.

## Licence

Licensed under the Open Government Licence (Malaysia).

Attribution: DOE Malaysia via MyEQMS.
