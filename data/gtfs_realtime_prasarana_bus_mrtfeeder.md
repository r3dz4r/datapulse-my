---
dataset_id: gtfs_realtime_prasarana_bus_mrtfeeder
last_checked: 2026-08-04
status: fresh
record_count: 1
content_freshness_date: 2029-10-06
schema_version: GTFS
schema_drift: none
known_quirks: ["Zero vehicles is a valid off-peak response and does not indicate an unavailable feed.", "Vehicle positions are transient; the committed protobuf is a single reference snapshot.", "The sampled vehicle timestamp is ahead of the feed header timestamp; freshness follows the required maximum-timestamp rule."]
breaking_changes: []
licence: Creative Commons Attribution 4.0
attribution: Prasarana Malaysia Berhad via data.gov.my GTFS API
---

# GTFS Realtime — MRT Feeder Bus Vehicle Positions

GTFS Realtime — MRT Feeder Bus Vehicle Positions is monitored as a GTFS Realtime vehicle-position protobuf feed.

## Provenance

Source URL: `https://api.data.gov.my/gtfs-realtime/vehicle-position/prasarana?category=rapid-bus-mrtfeeder`

Licence: Creative Commons Attribution 4.0

Attribution: Prasarana Malaysia Berhad via data.gov.my GTFS API.

## Status

**Status:** Fresh

**Refresh cadence:** 30 seconds

**Header timestamp:** 1785781240

**Newest vehicle timestamp:** 1886017556

**Content freshness date:** 2029-10-06

## Coverage

The reference snapshot contains 1 vehicle positions; the source advertises updates every 30 seconds.

Geographic coverage: Klang Valley.

## Known quirks

- Zero vehicles is a valid off-peak response and does not indicate an unavailable feed.
- Vehicle positions are transient; the committed protobuf is a single reference snapshot.
- The sampled vehicle timestamp is ahead of the feed header timestamp; freshness follows the required maximum-timestamp rule.

## Last checked

2026-08-04 by the DataPulse MY automated GTFS probe using curl, zipfile/csv, and google.transit.gtfs_realtime_pb2 as applicable.

## Licence

Licensed under the Creative Commons Attribution 4.0 licence.

Attribution: Prasarana Malaysia Berhad via data.gov.my GTFS API.

## Sample

- [samples/gtfs-realtime/gtfs_realtime_prasarana_bus_mrtfeeder.pb](../samples/gtfs-realtime/gtfs_realtime_prasarana_bus_mrtfeeder.pb)
