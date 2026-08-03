---
dataset_id: gtfs_static_prasarana_bus_mrtfeeder
last_checked: 2026-08-04
status: fresh
record_count: 174759
content_freshness_date: 2026-08-31
schema_version: GTFS
schema_drift: none
known_quirks: ["Calendar end dates describe the published service horizon, not the last day on which the ZIP changed.", "The probe requires agency.txt, stops.txt, routes.txt, trips.txt, stop_times.txt, and calendar.txt."]
breaking_changes: []
licence: Creative Commons Attribution 4.0
attribution: Prasarana Malaysia Berhad via data.gov.my GTFS API
---

# GTFS Static — MRT Feeder Bus Schedule

GTFS Static — MRT Feeder Bus Schedule is monitored as a validated GTFS schedule ZIP.

## Provenance

Source URL: `https://api.data.gov.my/gtfs-static/prasarana?category=rapid-bus-mrtfeeder`

Licence: Creative Commons Attribution 4.0

Attribution: Prasarana Malaysia Berhad via data.gov.my GTFS API.

## Status

**Status:** Fresh

**Refresh cadence:** as-required

**Calendar service range:** 2026-08-08 to 2026-08-31

**Content freshness date:** 2026-08-31

## Coverage

The sampled ZIP contains 91 routes, 2,112 stops, 6,277 trips, and 174,759 stop-time rows.

Geographic coverage: Klang Valley.

## Known quirks

- Calendar end dates describe the published service horizon, not the last day on which the ZIP changed.
- The probe requires agency.txt, stops.txt, routes.txt, trips.txt, stop_times.txt, and calendar.txt.

## Last checked

2026-08-04 by the DataPulse MY automated GTFS probe using curl, zipfile/csv, and google.transit.gtfs_realtime_pb2 as applicable.

## Licence

Licensed under the Creative Commons Attribution 4.0 licence.

Attribution: Prasarana Malaysia Berhad via data.gov.my GTFS API.

## Sample

- [samples/gtfs-static/gtfs_static_prasarana_bus_mrtfeeder.zip](../samples/gtfs-static/gtfs_static_prasarana_bus_mrtfeeder.zip)
