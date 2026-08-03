---
dataset_id: gtfs_static_prasarana_bus_kuantan
last_checked: 2026-08-04
status: unreachable
record_count: null
content_freshness_date: null
schema_version: GTFS
schema_drift: none
known_quirks: ["Calendar end dates describe the published service horizon, not the last day on which the ZIP changed.", "The probe requires agency.txt, stops.txt, routes.txt, trips.txt, stop_times.txt, and calendar.txt.", "The configured API category currently returns HTTP 404; the reference ZIP was retained from the official backing S3 object."]
breaking_changes: []
licence: Creative Commons Attribution 4.0
attribution: Prasarana Malaysia Berhad via data.gov.my GTFS API
---

# GTFS Static — Rapid Kuantan Bus Schedule

GTFS Static — Rapid Kuantan Bus Schedule is monitored as a validated GTFS schedule ZIP.

## Provenance

Source URL: `https://api.data.gov.my/gtfs-static/prasarana?category=rapid-bus-kuantan`

Licence: Creative Commons Attribution 4.0

Attribution: Prasarana Malaysia Berhad via data.gov.my GTFS API.

## Status

**Status:** Unreachable at configured API endpoint

**Refresh cadence:** as-required

**Calendar service range:** 2020-04-01 to 2027-03-31

**Content freshness date:** 2027-03-31

## Coverage

The sampled ZIP contains 17 routes, 635 stops, 270 trips, and 10,733 stop-time rows.

Geographic coverage: Kuantan, Pahang.

## Known quirks

- Calendar end dates describe the published service horizon, not the last day on which the ZIP changed.
- The probe requires agency.txt, stops.txt, routes.txt, trips.txt, stop_times.txt, and calendar.txt.
- The configured API category currently returns HTTP 404; the reference ZIP was retained from the official backing S3 object.

## Known issues

- **Deprecated endpoint:** The configured data.gov.my URL first returned HTTP 404 on 2026-08-04: `https://api.data.gov.my/gtfs-static/prasarana?category=rapid-bus-kuantan`.
- This manifest entry is retained as a permanent `unreachable` record so a future steward fix remains visible; no live schedule data is currently available from the configured endpoint.

## Last checked

2026-08-04 by the DataPulse MY automated GTFS probe using curl, zipfile/csv, and google.transit.gtfs_realtime_pb2 as applicable.

## Licence

Licensed under the Creative Commons Attribution 4.0 licence.

Attribution: Prasarana Malaysia Berhad via data.gov.my GTFS API.

## Sample

- [samples/gtfs-static/gtfs_static_prasarana_bus_kuantan.zip](../samples/gtfs-static/gtfs_static_prasarana_bus_kuantan.zip)
