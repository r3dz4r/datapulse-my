---
dataset_id: met_weather
last_checked: 2026-08-08T07:30:47Z
status: fresh
freshness_delta: 0 days
next_expected_update: 2026-08-03
record_count: 2520
date_range: 2026-08-02 to 2026-08-08
schema_version: 1.0
schema_drift: none
known_quirks: ["forecast text is published in Bahasa Malaysia", "location is a nested object", "the endpoint has no canonical data.gov.my dataset id"]
breaking_changes: []
licence: Open Government Licence (Malaysia)
attribution: MET Malaysia via data.gov.my
---

# MET Malaysia Weather Forecast

## Status

**Status:** Fresh

**Freshness:** 0 days

HTTP 200

## Last checked

2026-08-08 at 07:30:47 UTC.

## File size

The checked resource is 723,072 bytes.

## Coverage

The endpoint covers 360 district-level locations across Malaysia for seven
forecast dates, from 2026-08-02 through 2026-08-08.

## Schema

| Field | Type | Description |
| --- | --- | --- |
| `location` | object | Nested location object containing `location_id` and `location_name`. |
| `date` | date | Forecast date in `YYYY-MM-DD` format. |
| `morning_forecast` | string | Morning forecast in Bahasa Malaysia. |
| `afternoon_forecast` | string | Afternoon forecast in Bahasa Malaysia. |
| `night_forecast` | string | Night forecast in Bahasa Malaysia. |
| `summary_forecast` | string | Daily summary forecast in Bahasa Malaysia. |
| `summary_when` | string | Period to which the summary applies, in Bahasa Malaysia. |
| `min_temp` | number | Minimum forecast temperature in degrees Celsius. |
| `max_temp` | number | Maximum forecast temperature in degrees Celsius. |

## Known quirks

- Forecast strings are published in Bahasa Malaysia and should be preserved.
- `location` is a nested object rather than a flat identifier and name.
- The direct API path has no canonical data.gov.my dataset `id`.

## Breaking changes

None observed.

## Sample

- [samples/met_weather.csv](samples/met_weather.csv)
- [samples/met_weather.json](samples/met_weather.json)

## Reproducibility

```sh
curl -sL "https://api.data.gov.my/weather/forecast" -o /tmp/met.json
```

## Licence

Licensed under the Open Government Licence (Malaysia).

Attribution: MET Malaysia via data.gov.my.
