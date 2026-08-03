---
dataset_id: gtfs_static_ktmb
last_checked: 2026-08-04
status: fresh
record_count: 2881
content_freshness_date: 2026-08-04
schema_version: GTFS
schema_drift: none
known_quirks: ["Calendar end dates describe the published service horizon, not the last day on which the ZIP changed.", "The probe requires agency.txt, stops.txt, routes.txt, trips.txt, stop_times.txt, and calendar.txt."]
breaking_changes: []
licence: Creative Commons Attribution 4.0
attribution: KTMB via data.gov.my GTFS API
---

# GTFS Static — KTMB Rail Schedule

GTFS Static — KTMB Rail Schedule is monitored as a validated GTFS schedule ZIP.

## Provenance

Source URL: `https://api.data.gov.my/gtfs-static/ktmb`

Licence: Creative Commons Attribution 4.0

Attribution: KTMB via data.gov.my GTFS API.

## Status

**Status:** Fresh

**Refresh cadence:** daily

**Calendar service range:** 2025-02-08 to 2026-08-04

**Content freshness date:** 2026-08-04

## Coverage

The sampled ZIP contains 9 routes, 191 stops, 304 trips, and 2,881 stop-time rows.

Geographic coverage: national.

## Known quirks

- Calendar end dates describe the published service horizon, not the last day on which the ZIP changed.
- The probe requires agency.txt, stops.txt, routes.txt, trips.txt, stop_times.txt, and calendar.txt.

## Last checked

2026-08-04 by the DataPulse MY automated GTFS probe using curl, zipfile/csv, and google.transit.gtfs_realtime_pb2 as applicable.

## Licence

Licensed under the Creative Commons Attribution 4.0 licence.

Attribution: KTMB via data.gov.my GTFS API.

## Sample

- [samples/gtfs-static/gtfs_static_ktmb.zip](../samples/gtfs-static/gtfs_static_ktmb.zip)
