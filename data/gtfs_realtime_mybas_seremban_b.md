---
dataset_id: gtfs_realtime_mybas_seremban_b
last_checked: 2026-08-04
status: fresh
record_count: 0
content_freshness_date: 2026-08-03
schema_version: GTFS
schema_drift: none
known_quirks: ["Zero vehicles is a valid off-peak response and does not indicate an unavailable feed.", "Vehicle positions are transient; the committed protobuf is a single reference snapshot."]
breaking_changes: []
licence: Creative Commons Attribution 4.0
attribution: BAS.MY via data.gov.my GTFS API
---

# GTFS Realtime — BAS.MY Seremban B Vehicle Positions

GTFS Realtime — BAS.MY Seremban B Vehicle Positions is monitored as a GTFS Realtime vehicle-position protobuf feed.

## Provenance

Source URL: `https://api.data.gov.my/gtfs-realtime/vehicle-position/mybas-seremban-b`

Licence: Creative Commons Attribution 4.0

Attribution: BAS.MY via data.gov.my GTFS API.

## Status

**Status:** Fresh

**Refresh cadence:** 30 seconds

**Header timestamp:** 1785781249

**Newest vehicle timestamp:** not supplied

**Content freshness date:** 2026-08-03

## Coverage

The reference snapshot contains 0 vehicle positions; the source advertises updates every 30 seconds.

Geographic coverage: Seremban, Negeri Sembilan.

## Known quirks

- Zero vehicles is a valid off-peak response and does not indicate an unavailable feed.
- Vehicle positions are transient; the committed protobuf is a single reference snapshot.

## Last checked

2026-08-04 by the DataPulse MY automated GTFS probe using curl, zipfile/csv, and google.transit.gtfs_realtime_pb2 as applicable.

## Licence

Licensed under the Creative Commons Attribution 4.0 licence.

Attribution: BAS.MY via data.gov.my GTFS API.

## Sample

- [samples/gtfs-realtime/gtfs_realtime_mybas_seremban_b.pb](../samples/gtfs-realtime/gtfs_realtime_mybas_seremban_b.pb)
