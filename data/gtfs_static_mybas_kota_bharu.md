---
dataset_id: gtfs_static_mybas_kota_bharu
last_checked: 2026-08-04
status: fresh
record_count: 47556
content_freshness_date: 2026-12-31
schema_version: GTFS
schema_drift: none
known_quirks: ["Calendar end dates describe the published service horizon, not the last day on which the ZIP changed.", "The probe requires agency.txt, stops.txt, routes.txt, trips.txt, stop_times.txt, and calendar.txt."]
breaking_changes: []
licence: Creative Commons Attribution 4.0
attribution: BAS.MY via data.gov.my GTFS API
---

# GTFS Static — BAS.MY Kota Bharu Bus Schedule

GTFS Static — BAS.MY Kota Bharu Bus Schedule is monitored as a validated GTFS schedule ZIP.

## Provenance

Source URL: `https://api.data.gov.my/gtfs-static/mybas-kota-bharu`

Licence: Creative Commons Attribution 4.0

Attribution: BAS.MY via data.gov.my GTFS API.

## Status

**Status:** Fresh

**Refresh cadence:** as-required

**Calendar service range:** 2025-06-01 to 2026-12-31

**Content freshness date:** 2026-12-31

## Coverage

The sampled ZIP contains 16 routes, 755 stops, 752 trips, and 47,556 stop-time rows.

Geographic coverage: Kota Bharu, Kelantan.

## Known quirks

- Calendar end dates describe the published service horizon, not the last day on which the ZIP changed.
- The probe requires agency.txt, stops.txt, routes.txt, trips.txt, stop_times.txt, and calendar.txt.

## Last checked

2026-08-04 by the DataPulse MY automated GTFS probe using curl, zipfile/csv, and google.transit.gtfs_realtime_pb2 as applicable.

## Licence

Licensed under the Creative Commons Attribution 4.0 licence.

Attribution: BAS.MY via data.gov.my GTFS API.

## Sample

- [samples/gtfs-static/gtfs_static_mybas_kota_bharu.zip](../samples/gtfs-static/gtfs_static_mybas_kota_bharu.zip)
