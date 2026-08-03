---
dataset_id: gtfs_static_mybas_ipoh
last_checked: 2026-08-04
status: fresh
record_count: 18788
content_freshness_date: 2026-08-03
schema_version: GTFS
schema_drift: none
known_quirks: ["Calendar end dates describe the published service horizon, not the last day on which the ZIP changed.", "The probe requires agency.txt, stops.txt, routes.txt, trips.txt, stop_times.txt, and calendar.txt."]
breaking_changes: []
licence: Creative Commons Attribution 4.0
attribution: BAS.MY via data.gov.my GTFS API
---

# GTFS Static — BAS.MY Ipoh Bus Schedule

GTFS Static — BAS.MY Ipoh Bus Schedule is monitored as a validated GTFS schedule ZIP.

## Provenance

Source URL: `https://api.data.gov.my/gtfs-static/mybas-ipoh`

Licence: Creative Commons Attribution 4.0

Attribution: BAS.MY via data.gov.my GTFS API.

## Status

**Status:** Fresh

**Refresh cadence:** as-required

**Calendar service range:** 2026-08-03 to 2026-08-03

**Content freshness date:** 2026-08-03

## Coverage

The sampled ZIP contains 17 routes, 2,079 stops, 354 trips, and 18,788 stop-time rows.

Geographic coverage: Ipoh, Perak.

## Known quirks

- Calendar end dates describe the published service horizon, not the last day on which the ZIP changed.
- The probe requires agency.txt, stops.txt, routes.txt, trips.txt, stop_times.txt, and calendar.txt.

## Last checked

2026-08-04 by the DataPulse MY automated GTFS probe using curl, zipfile/csv, and google.transit.gtfs_realtime_pb2 as applicable.

## Licence

Licensed under the Creative Commons Attribution 4.0 licence.

Attribution: BAS.MY via data.gov.my GTFS API.

## Sample

- [samples/gtfs-static/gtfs_static_mybas_ipoh.zip](../samples/gtfs-static/gtfs_static_mybas_ipoh.zip)
